#!/usr/bin/env bash
# Build 059: build the Nike-L base kernel (Linux 6.6.162 + patches/).
#
# Usage:
#   build.sh <linux-6.6.162-tree> <arm64|arm> <tiny|full|android> <output-dir>
#
# Environment:
#   TOOLCHAIN=llvm (default) | gcc   (gcc uses CROSS_COMPILE, see below)
#   CROSS_COMPILE                    (default aarch64-linux-gnu- / arm-linux-gnueabihf-)
#   JOBS                             (default: nproc)
#   DIAG_INITRAMFS=1 (default) | 0   embed initramfs/q60t-diag-init as /init
#   ANDROID_BASE_CONFIG              path to AOSP android-6.6/android-base.config
#                                    (required for the android profile)
#   EXTRA_FRAGMENTS                  colon-separated extra config fragments
#                                    (merged last, must survive like the others)
#
# The kernel tree must be a clean v6.6.162 checkout. The patches are applied
# in place (once); use a dedicated tree for this. Nothing is installed,
# flashed or booted: the result is a set of files in <output-dir>.
#
# Profiles:
#   tiny  allnoconfig + configs/nikel-*.config  (small, serial console only)
#   full     defconfig / multi_v7_defconfig + configs/nikel-*.config
#   android  like full, plus AOSP android-base.config; writes a coverage
#            report (android-coverage.txt) of the Android requirements
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KSRC="${1:?kernel tree}"
ARCH_NAME="${2:?arm64|arm}"
PROFILE="${3:?tiny|full}"
OUT="${4:?output dir}"
TOOLCHAIN="${TOOLCHAIN:-llvm}"
DIAG_INITRAMFS="${DIAG_INITRAMFS:-1}"
JOBS="${JOBS:-$(nproc)}"
EXPECTED_VERSION="6.6.162"

die() { echo "build059: ERROR: $*" >&2; exit 1; }
log() { echo "build059: $*"; }

case "$ARCH_NAME" in
  arm64) KARCH=arm64; BASE_DEFCONFIG=defconfig;          IMAGES="Image Image.gz"
         DEF_CROSS=aarch64-linux-gnu- ;;
  arm)   KARCH=arm;   BASE_DEFCONFIG=multi_v7_defconfig; IMAGES="zImage Image"
         DEF_CROSS=arm-linux-gnueabihf- ;;
  *) die "unknown arch '$ARCH_NAME'" ;;
esac
case "$PROFILE" in tiny|full|android) ;; *) die "unknown profile '$PROFILE'" ;; esac
if [ "$PROFILE" = android ]; then
  [ -f "${ANDROID_BASE_CONFIG:-}" ] || die "android profile needs ANDROID_BASE_CONFIG"
fi

[ -f "$KSRC/Makefile" ] || die "$KSRC is not a kernel tree"
version="$(make -s -C "$KSRC" kernelversion)"
[ "$version" = "$EXPECTED_VERSION" ] || die "kernel $version, expected $EXPECTED_VERSION"

mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
KOUT="$OUT/kbuild-$ARCH_NAME-$PROFILE"
ART="$OUT/artifacts-$ARCH_NAME-$PROFILE"
mkdir -p "$KOUT" "$ART"

MAKEARGS=(-C "$KSRC" O="$KOUT" ARCH="$KARCH" -j"$JOBS")
if [ "$TOOLCHAIN" = llvm ]; then
  MAKEARGS+=(LLVM=1)
else
  MAKEARGS+=(CROSS_COMPILE="${CROSS_COMPILE:-$DEF_CROSS}")
fi

# 1. patches -----------------------------------------------------------------
if [ -f "$KSRC/drivers/tty/serial/sdp_uart.c" ]; then
  log "patches already applied"
else
  for p in "$HERE"/patches/*.patch; do
    log "applying $(basename "$p")"
    patch -d "$KSRC" -p1 --forward --batch < "$p" > /dev/null
  done
fi

# 2. configuration -------------------------------------------------------------
FRAGS=("$HERE/configs/nikel-common.config" "$HERE/configs/nikel-$ARCH_NAME.config")
[ "$PROFILE" = android ] && FRAGS+=("$HERE/configs/nikel-android.config")
# Optional extra fragments (colon-separated paths), e.g. Build 069 QEMU virtio.
if [ -n "${EXTRA_FRAGMENTS:-}" ]; then
  IFS=: read -r -a _extra <<< "$EXTRA_FRAGMENTS"
  for f in "${_extra[@]}"; do [ -f "$f" ] || die "extra fragment not found: $f"; FRAGS+=("$f"); done
fi
MERGE_EXTRA=()
[ "$PROFILE" = android ] && MERGE_EXTRA=("$ANDROID_BASE_CONFIG")
if [ "$PROFILE" = tiny ]; then
  cat "${FRAGS[@]}" > "$KOUT/allno.config"
  make "${MAKEARGS[@]}" KCONFIG_ALLCONFIG="$KOUT/allno.config" allnoconfig
else
  make "${MAKEARGS[@]}" "$BASE_DEFCONFIG"
  (cd "$KOUT" && "$KSRC/scripts/kconfig/merge_config.sh" -m -O "$KOUT" \
      "$KOUT/.config" "${MERGE_EXTRA[@]}" "${FRAGS[@]}")
  make "${MAKEARGS[@]}" olddefconfig
fi

missing=0
while read -r sym; do
  case "$sym" in ''|'#'*) continue ;; esac
  if ! grep -qx "$sym=y" "$KOUT/.config"; then
    echo "build059: required symbol not set: $sym" >&2
    missing=1
  fi
done < "$HERE/configs/required-symbols.txt"
# every fragment line must have survived the configuration step
for f in "${FRAGS[@]}"; do
  while read -r line; do
    case "$line" in ''|'#'*) continue ;; esac
    grep -qx "$line" "$KOUT/.config" || { echo "build059: fragment value lost: $line ($f)" >&2; missing=1; }
  done < "$f"
done
[ "$missing" = 0 ] || die "configuration incomplete"

# Android requirement coverage (informational, never fails the build)
if [ "$PROFILE" = android ]; then
  python3 - "$ANDROID_BASE_CONFIG" "$KOUT/.config" > "$ART/android-coverage.txt" <<'PY'
import re, sys
want, have = {}, {}
for line in open(sys.argv[1]):
    m = re.match(r"(CONFIG_\w+)=(.*)", line.strip())
    n = re.match(r"# (CONFIG_\w+) is not set", line.strip())
    if m: want[m.group(1)] = m.group(2)
    elif n: want[n.group(1)] = "n"
for line in open(sys.argv[2]):
    m = re.match(r"(CONFIG_\w+)=(.*)", line.strip())
    n = re.match(r"# (CONFIG_\w+) is not set", line.strip())
    if m: have[m.group(1)] = m.group(2)
    elif n: have[n.group(1)] = "n"
bad = [(k, v, have.get(k, "n")) for k, v in sorted(want.items()) if have.get(k, "n") != v]
print("Android android-base.config coverage: %d/%d satisfied" % (len(want) - len(bad), len(want)))
for k, v, h in bad:
    print("  %-45s want %-10s have %s" % (k, v, h))
PY
  head -1 "$ART/android-coverage.txt"
fi

# 2b. embedded diagnostic initramfs ------------------------------------------
if [ "$DIAG_INITRAMFS" = 1 ]; then
  IRD="$KOUT/diag-initramfs"
  rm -rf "$IRD" && mkdir -p "$IRD"
  make "${MAKEARGS[@]}" headers
  cp -r "$KSRC/tools/include/nolibc" "$IRD/nolibc"
  NOLIBC_CFLAGS=(-nostdlib -static -Os -fno-stack-protector -Wall -Wextra
                 -isystem "$KOUT/usr/include" -include "$IRD/nolibc/nolibc.h")
  if [ "$TOOLCHAIN" = llvm ]; then
    # nolibc 6.6 uses GCC-only "%r0" operands in its ARM start code
    sed -i 's/%r0/r0/g' "$IRD/nolibc/arch-arm.h"
    if [ "$KARCH" = arm64 ]; then TGT=(--target=aarch64-linux-gnu)
    else TGT=(--target=armv7a-linux-gnueabihf -march=armv7ve); fi
    clang "${TGT[@]}" -nostdinc -isystem "$(clang -print-resource-dir)/include" \
      -Wno-unknown-attributes -fuse-ld=lld "${NOLIBC_CFLAGS[@]}" \
      -o "$IRD/init" "$HERE/../initramfs/q60t-diag-init.c"
  else
    "${CROSS_COMPILE:-$DEF_CROSS}gcc" "${NOLIBC_CFLAGS[@]}" \
      -o "$IRD/init" "$HERE/../initramfs/q60t-diag-init.c"
  fi
  cat > "$IRD/initramfs.list" <<EOL
dir /dev 0755 0 0
nod /dev/console 0600 0 0 c 5 1
dir /proc 0755 0 0
dir /sys 0755 0 0
file /init $IRD/init 0755 0 0
EOL
  "$KSRC/scripts/config" --file "$KOUT/.config" \
    --set-str INITRAMFS_SOURCE "$IRD/initramfs.list" \
    --enable DEBUG_FS
  make "${MAKEARGS[@]}" olddefconfig
  grep -q "^CONFIG_INITRAMFS_SOURCE=\"$IRD/initramfs.list\"" "$KOUT/.config" \
    || die "initramfs not configured"
  cp "$IRD/init" "$ART/q60t-diag-init"
fi
cp "$KOUT/.config" "$ART/config"

# 3. the new drivers with extra warnings, as an error gate ---------------------
make "${MAKEARGS[@]}" W=1 KCFLAGS=-Werror \
  drivers/tty/serial/sdp_uart.o drivers/clk/clk-sdp1804.o drivers/gpio/gpio-sdp.o

# 4. kernel image and device trees ---------------------------------------------
make "${MAKEARGS[@]}" $IMAGES dtbs

for img in $IMAGES; do
  cp "$KOUT/arch/$KARCH/boot/$img" "$ART/"
done
cp "$KOUT/System.map" "$ART/"
if [ "$KARCH" = arm64 ]; then DTBDIR="$KOUT/arch/arm64/boot/dts/samsung-sdp"
else DTBDIR="$KOUT/arch/arm/boot/dts/sdp"; fi
for d in sdp-nikel-q60t-1g5 sdp-nikel-q60t-2g; do
  cp "$DTBDIR/$d.dtb" "$ART/"
  python3 "$HERE/../tools/fdt2dts.py" "$ART/$d.dtb" "$ART/$d.decompiled.dts"
done

# 5. summary --------------------------------------------------------------------
(cd "$ART" && sha256sum -- * > SHA256SUMS)
{
  echo "kernel:    $version + Build 059 patches"
  echo "arch:      $ARCH_NAME ($KARCH)"
  echo "profile:   $PROFILE"
  echo "toolchain: $TOOLCHAIN"
  echo "initramfs: $( [ "$DIAG_INITRAMFS" = 1 ] && echo "q60t-diag-init embedded as /init" || echo none)"
  echo "compiler:  $(sed -n 's/^CONFIG_CC_VERSION_TEXT=//p' "$KOUT/.config")"
  echo
  ls -l "$ART"
} | tee "$ART/BUILD_INFO.txt"
log "done: $ART"
