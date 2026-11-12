#!/usr/bin/env bash
# Build 070: unpack Samsung's GPL sources (once) and print an inventory of the
# files the driver port needs, with their license markers, into the job log.
#
# Usage: gpl_inventory.sh <gpl-dir>
#   <gpl-dir> contains linux-4.1.10-tizen5.5.tgz and tztv-media-nike.tgz
#   (fetch_sources.py gpl). Sources are unpacked to <gpl-dir>/src/.
#
# Read-only analysis: nothing is built, installed or sent to a TV.
set -euo pipefail

GPL="${1:?gpl dir}"
SRC="$GPL/src"
mkdir -p "$SRC"

unpack() {  # <tgz> <dest>
  local tgz="$GPL/$1" dest="$SRC/$2"
  if [ ! -f "$tgz" ]; then echo "I> $1: not on the runner yet (skipped)"; mkdir -p "$dest"; return 0; fi
  if [ ! -f "$dest/.unpacked" ]; then
    rm -rf "$dest" && mkdir -p "$dest"
    tar -xzf "$tgz" -C "$dest" --no-same-owner --no-same-permissions
    touch "$dest/.unpacked"
  fi
  echo "I> $2: $(find "$dest" -type f | wc -l) files, top: $(ls "$dest" | head -5 | tr '\n' ' ')"
}
unpack linux-4.1.10-tizen5.5.tgz linux
unpack tztv-media-nike.tgz media
# the kernel tarball may carry a top-level directory
LIN="$(dirname "$(find "$SRC/linux" -maxdepth 3 -name MAINTAINERS -type f | head -1)")"
[ -d "$LIN/drivers" ] || { echo "no kernel tree under $SRC/linux" >&2; exit 1; }
echo "I> kernel root: ${LIN#"$SRC"/}"

# license marker of one source file: MODULE_LICENSE / SPDX / first copyright
lic() {
  local f="$1" m
  m="$(grep -h -o -E 'MODULE_LICENSE\("[^"]*"\)|SPDX-License-Identifier: *[^ */]+' "$f" 2>/dev/null | sort -u | tr '\n' ' ' || true)"
  [ -n "$m" ] || m="$(grep -h -m1 -i -E 'GNU General Public License|GPL|proprietary|confidential' "$f" 2>/dev/null | cut -c1-100 || true)"
  printf 'I> %7d lines  %-60s %s\n' "$(wc -l < "$f")" "${f#"$SRC"/}" "${m:-(no marker)}"
}

echo "===== media modules (tztv-media-nike): files + MODULE_LICENSE per module"
for d in $(find "$SRC/media" -mindepth 1 -maxdepth 3 -type d -name 'sdp_*' | sort); do
  n_c="$(find "$d" -name '*.c' | wc -l)"
  lics="$(grep -rh -o -E 'MODULE_LICENSE\("[^"]*"\)' "$d" 2>/dev/null | sort | uniq -c | tr -s ' ' | tr '\n' ';' || true)"
  echo "I> ${d#"$SRC"/}: ${n_c} .c files; ${lics:-no MODULE_LICENSE}"
done

echo "===== display (P0): sdp_drm_nike, panel, tcon/frc, logo"
for d in $(find "$SRC/media" -maxdepth 3 -type d \( -name 'sdp_drm_nike' -o -name 'sdp_logo_nike' \) | sort); do
  find "$d" -type f \( -name '*.c' -o -name '*.h' -o -name 'Makefile' -o -name 'Kbuild' -o -name 'Kconfig' \) \
    | sort | while read -r f; do lic "$f"; done
done
for f in drivers/gpu/drm/drm_tztv_helper.c drivers/gpu/drm/panel/panel-sdp.c; do
  if [ -f "$LIN/$f" ]; then lic "$LIN/$f"; else echo "I> linux/$f: not found"; fi
done

echo "===== where are the DT compatibles implemented (both trees)"
for c in samsung,sdp-drm samsung,sdp1202-panel samsung,tztv-tcon samsung,sdp-frc \
         samsung,sdp-mc-irb samsung,sdp-mc-irs samsung,sdp-mc-cecif samsung,sdp-mac \
         samsung,sdp-hdmi samsung,sdp-mfc arm,mali-midgard samsung,sdp-audio; do
  hits="$(grep -rl --include='*.c' -F "\"$c" "$LIN/drivers" "$LIN/sound" "$SRC/media" 2>/dev/null | head -6 || true)"
  if [ -z "$hits" ]; then echo "I> $c: no .c file"; continue; fi
  echo "I> $c:"
  while read -r f; do lic "$f"; done <<< "$hits"
done

echo "===== audio (sdp_alsa_nike), HDMI, IR/CEC (micom), Ethernet"
for pat in 'sdp_alsa_nike' 'sdp_hdmi_nike'; do
  for d in $(find "$SRC/media" -maxdepth 3 -type d -name "$pat"); do
    find "$d" -maxdepth 2 -type f -name '*.c' | sort | head -40 | while read -r f; do lic "$f"; done
  done
done
for f in $(find "$LIN/drivers" -type f -name '*.c' \( -path '*micom*' -o -name '*sdp*mac*' -o -name '*sdp_mac*' -o -name '*irb*' -o -name '*cec*sdp*' \) | sort | head -40); do
  lic "$f"
done

echo "===== GPL board/clock/DT sources referenced by the kickoff"
for f in arch/arm/mach-sdp/board-nike-dt.c drivers/clk/clk-sdp.c \
         arch/arm/configs/Nike.M-Tizen_release_defconfig; do
  if [ -f "$LIN/$f" ]; then lic "$LIN/$f"; else echo "I> linux/$f: not found"; fi
done
ls "$LIN/arch/arm/boot/dts" 2>/dev/null | grep -i -E 'sdp|nike' | sed 's/^/I> dts: /' | head -40 || true
echo "===== done"
