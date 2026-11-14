#!/usr/bin/env bash
# Build 106: turn the Samsung drivers that Build 094-097 link only as built-in
# objects (.o inside vmlinux) into real, loadable Linux 6.6.162 ARM32 modules.
#
# Usage: build-modules.sh <work-dir> <linux-6.6.162.tar.xz> <report-dir>
#
# Starts from the exact Build 096/097 Nike-L configuration (same patch stack,
# same defconfig + fragments), then switches the tristate Samsung drivers from
# =y to =m and lets Kbuild/modpost link them. The result is a separate
# "modular variant" kernel: its zImage and modules belong together (same
# vermagic, same Module.symvers). The boot kernel of Build 097 is unchanged.
#
# Not modularised on purpose (documented in README.md):
#   COMMON_CLK_SDP1804  bool, CLK_OF_DECLARE early clock provider
#   SDP1804_GPU_POWER   bool, genpd provider created from that early provider
set -euo pipefail
export LC_ALL=C
export KBUILD_BUILD_USER=build106 KBUILD_BUILD_HOST=ci KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP='2025-01-01 00:00:00 UTC'
export SOURCE_DATE_EPOCH=1735689600

work=${1:?absolute work directory}
tarball=${2:?absolute Linux tarball path}
report=${3:?absolute report directory}
mkdir -p "$report"
source porting/ci/selfhosted-llvm.sh
for tool in llvm-readelf llvm-nm modinfo; do
  command -v "$tool" >/dev/null || { echo "Missing runner prerequisite: $tool" >&2; exit 1; }
done
clang --version > "$report/clang.txt"

bash porting/build096/samsung-config-dtb.sh "$work" "$tarball" 2>&1 | tee "$report/config.log"
src="$work/linux-nikel"
out="$work/nikel-arm"
cpu="$work/cpu"
cp -R porting/build058/cpu/kernel "$cpu"
# Build 058 Samsung DRM utility/fence and GPU clock/reset: until now .o only.
drm="$work/samsung-ext"
mkdir -p "$drm"
cp porting/build106/external/Kbuild "$drm/Kbuild"
cp porting/build058/integration/drm/sdp_drm_{util,fence}.[ch] "$drm/"
cp porting/build058/kernel/sdp_nikel_gpu_clkrst.c "$drm/"
cp "$out/.config" "$report/kernel.config.build097"

# Inventory: which Samsung drivers are currently only built-in objects.
{
  printf 'symbol\tbuild097\tobject\n'
  while read -r sym obj; do
    printf '%s\t%s\t%s\n' "$sym" "$(grep -E "^CONFIG_$sym=" "$out/.config" | cut -d= -f2 || echo unset)" "$obj"
  done < porting/build106/samsung-objects.txt
} > "$report/objects-before.tsv"

# --- 1. modular Kconfig ---------------------------------------------------------
# New modules (were =y): message box, MICOM core, MICOM remote, CEC, GPIO, UART.
newmods=(SDP_MSGBOX SDP_MICOM IR_SDP_MICOM CEC_SDP_CECIF GPIO_SDP SERIAL_SDP)
cfg=("$src/scripts/config" --file "$out/.config")
for sym in "${newmods[@]}"; do "${cfg[@]}" -m "$sym"; done
# A modular UART cannot be the boot console; QEMU uses PL011 instead.
"${cfg[@]}" -d SERIAL_SDP_CONSOLE -e MODULE_UNLOAD -d MODULE_FORCE_UNLOAD \
  -d MODULE_SIG -d MODULE_COMPRESS_GZIP -d MODULE_COMPRESS_XZ -d MODULE_COMPRESS_ZSTD
make -C "$src" O="$out" ARCH=arm LLVM=1 olddefconfig
cp "$out/.config" "$report/kernel.config"

bad=0
for sym in "${newmods[@]}" DRM_SDP DRM_PANFROST DRM_SDP_HDMI SDP_MAC SDP_MICOM_IRB SDP_MICOM_IRS; do
  grep -qx "CONFIG_$sym=m" "$out/.config" || { echo "::error::CONFIG_$sym is not =m after olddefconfig" >&2; bad=1; }
done
for sym in COMMON_CLK_SDP1804 SDP1804_GPU_POWER; do
  grep -qx "CONFIG_$sym=y" "$out/.config" || { echo "::error::CONFIG_$sym must stay built-in" >&2; bad=1; }
done
test "$bad" -eq 0

# Every expected module: Kconfig symbol, path below the build tree.
mapfile -t expected < <(grep -v '^#' porting/build106/expected-modules.txt | sed '/^$/d')

# Kconfig/Makefile mapping must exist in the patched tree (no renamed .o).
for row in "${expected[@]}"; do
  read -r sym root path state <<<"$row"
  [[ "$root" == kernel ]] || continue
  dir=${path%/*}; obj=${path##*/}; obj=${obj%.ko}.o
  if ! grep -rqE "^[[:space:]]*(menu)?config[[:space:]]+$sym[[:space:]]*$" "$src/$dir/Kconfig" "$src/${dir%/*}/Kconfig" 2>/dev/null ||
     ! grep -qE "obj-\\\$\(CONFIG_$sym\)[[:space:]]*\+?=.*\b${obj%.o}\.o\b" "$src/$dir/Makefile"; then
    echo "::error::Kbuild mapping missing: CONFIG_$sym -> $path" >&2
    bad=1
  fi
done
test "$bad" -eq 0

# --- 2. build ---------------------------------------------------------------------
make_args=(-C "$src" O="$out" ARCH=arm LLVM=1 -j"$(nproc)")
export KCFLAGS="-ffile-prefix-map=$work=/build106"
make "${make_args[@]}" zImage modules 2>&1 | tee "$report/kernel-build.log"
test -s "$out/Module.symvers"
make "${make_args[@]}" M="$cpu" W=1 KCFLAGS="$KCFLAGS -Werror" modules 2>&1 | tee "$report/external-build.log"
# External Kbuild reads $out/Module.symvers itself (adding it again duplicates every export).
make "${make_args[@]}" M="$drm" W=1 modules 2>&1 \
  | tee "$report/samsung-ext-build.log"
release=$(cat "$out/include/config/kernel.release")
printf '%s\n' "$release" > "$report/kernel-release.txt"
[[ "$release" == 6.6.162 || "$release" == 6.6.162-* ]]
cp "$out/arch/arm/boot/zImage" "$report/zImage-modular"

# modpost: any unresolved symbol or Samsung section mismatch fails the build.
grep -h 'WARNING: modpost' "$report/kernel-build.log" "$report/external-build.log" "$report/samsung-ext-build.log" > "$report/modpost-warnings.txt" || true
if grep -E 'undefined!|sdp|micom|cecif|nikel' "$report/modpost-warnings.txt"; then
  echo "::error::modpost reported unresolved symbols or Samsung section mismatches" >&2
  exit 1
fi

# --- 3. verify every module ----------------------------------------------------
mkdir -p "$report/modules" "$report/metadata"
printf 'module\tkconfig\tstate\tdepends\tvermagic\tundefined_symbols\n' > "$report/modules.tsv"
for row in "${expected[@]}"; do
  read -r sym root path state <<<"$row"
  case "$root" in kernel) ko="$out/$path";; external) ko="$cpu/$path";; samsung-ext) ko="$drm/$path";; esac
  name=${ko##*/}
  if [[ ! -s "$ko" ]]; then echo "::error::Missing module: $path" >&2; bad=1; continue; fi
  header="$report/metadata/$name.elf.txt"
  llvm-readelf -h "$ko" > "$header"
  if ! grep -Eq 'Class:[[:space:]]+ELF32$' "$header" ||
     ! grep -Eq 'Machine:[[:space:]]+ARM$' "$header" ||
     ! grep -Eq 'Type:[[:space:]]+REL([[:space:]]|$)' "$header" ||
     ! llvm-readelf -S "$ko" | grep -q '\.modinfo' ||
     ! llvm-readelf -S "$ko" | grep -q '\.gnu\.linkonce\.this_module' ||
     ! modinfo "$ko" > "$report/metadata/$name.modinfo.txt"; then
    echo "::error::$name is not a linked ARM32 kernel module" >&2; bad=1; continue
  fi
  vermagic=$(modinfo -F vermagic "$ko")
  [[ "${vermagic%% *}" == "$release" ]] || { echo "::error::$name vermagic $vermagic" >&2; bad=1; continue; }
  deps=$(modinfo -F depends "$ko")
  llvm-nm -u "$ko" | awk '{print $2}' | sort > "$report/metadata/$name.undefined.txt"
  # Every undefined symbol must be exported by vmlinux or another module.
  unresolved=$(comm -23 "$report/metadata/$name.undefined.txt" \
    <(awk '{print $2}' "$out/Module.symvers" "$cpu/Module.symvers" "$drm/Module.symvers" 2>/dev/null | sort -u) \
    | grep -vE '^(__this_module|__aeabi_|__gnu_mcount_nc$|_GLOBAL_OFFSET_TABLE_)' || true)
  if [[ -n "$unresolved" ]]; then
    printf '%s\n' "$unresolved" > "$report/metadata/$name.unresolved.txt"
    echo "::error::$name has unresolved symbols: $(tr '\n' ' ' <<<"$unresolved")" >&2
    bad=1
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$name" "$sym" "$state" "${deps:--}" "$vermagic" \
    "$(wc -l < "$report/metadata/$name.undefined.txt")" >> "$report/modules.tsv"
  cp "$ko" "$report/modules/"
done

# Built-in objects that must remain .o (documented reasons).
printf 'object\tkconfig\treason\n' > "$report/objects-builtin.tsv"
printf '%s\n' \
  "drivers/clk/clk-sdp1804.o	COMMON_CLK_SDP1804	CLK_OF_DECLARE early clock provider (bool)" \
  "drivers/clk/clk-sdp1804-gpu.o	SDP1804_GPU_POWER	genpd created by clk-sdp1804 at of_clk_init (bool)" \
  >> "$report/objects-builtin.tsv"
for o in drivers/clk/clk-sdp1804.o drivers/clk/clk-sdp1804-gpu.o; do
  test -s "$out/$o" || { echo "::error::expected built-in object $o missing" >&2; bad=1; }
done
test "$bad" -eq 0

# The modules that used to be .o must no longer be in vmlinux.
for f in sdp_msgbox_send sdp_micom_send_cmd; do
  if llvm-nm "$out/vmlinux" | grep -qw "$f"; then
    echo "::error::$f still linked into vmlinux" >&2; exit 1
  fi
done

# All module files of the tree (for QEMU dependency resolution).
(cd "$out" && find . -name '*.ko' | sort) > "$report/all-tree-modules.txt"
(cd "$report" && sha256sum zImage-modular modules/*.ko > SHA256SUMS && sha256sum -c SHA256SUMS)
echo "Build 106: $(ls "$report"/modules/*.ko | wc -l) verified ARM32 modules"
column -t -s $'\t' "$report/modules.tsv"
