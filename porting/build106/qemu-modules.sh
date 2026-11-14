#!/usr/bin/env bash
# Build 106: load and unload the modular-variant modules on QEMU virt.
#
# Usage: qemu-modules.sh <work-dir used by build-modules.sh> <report-dir>
#
# Boots the Build 106 zImage (Nike-L patch stack, multi_v7 base) on the
# generic QEMU "virt" machine (Cortex-A15) with an initramfs that holds every
# Build 106 module plus its in-tree dependencies. QEMU cannot emulate Nike-L
# hardware: the Samsung drivers register but do not probe. A load result
# proves linking, relocation, symbol resolution, module_init and module_exit;
# it says nothing about the TV.
set -euo pipefail
export LC_ALL=C
work=${1:?work directory}
report=${2:?report directory}
src="$work/linux-nikel"
out="$work/nikel-arm"
cpu="$work/cpu"
drm="$work/samsung-ext"
q="$report/qemu"
ird="$work/qemu-initramfs"
mkdir -p "$q"
rm -rf "$ird"; mkdir -p "$ird/lib/modules"
source porting/ci/selfhosted-llvm.sh
command -v qemu-system-arm >/dev/null || { echo "::error::qemu-system-arm missing on runner" >&2; exit 1; }

# 1. /init against nolibc
make -C "$src" O="$out" ARCH=arm LLVM=1 headers >/dev/null
cp -r "$src/tools/include/nolibc" "$work/nolibc"
sed -i 's/%r0/r0/g' "$work/nolibc/arch-arm.h"
clang --target=armv7a-linux-gnueabi -march=armv7-a -mfloat-abi=soft -marm \
  -nostdinc -isystem "$(clang -print-resource-dir)/include" \
  -isystem "$out/usr/include" -include "$work/nolibc/nolibc.h" \
  -nostdlib -static -Os -fno-stack-protector -Wall -Werror \
  -Wno-unknown-attributes -fuse-ld=lld -Wl,--build-id=none \
  -o "$ird/init" porting/build106/init.c

# 2. module load order: Samsung modules plus transitive dependencies
declare -A path_of
while IFS= read -r ko; do
  path_of[$(modinfo -F name "$ko")]=$ko
done < <(find "$out" "$cpu" "$drm" -name '*.ko' | sort)
declare -A seen
order=()
visit() {
  local name=$1 dep
  [[ -n "${seen[$name]:-}" ]] && return
  seen[$name]=1
  [[ -n "${path_of[$name]:-}" ]] || { echo "::error::dependency $name has no .ko (built-in?)" >&2; return 1; }
  for dep in $(modinfo -F depends "${path_of[$name]}" | tr ',' ' '); do visit "$dep"; done
  order+=("$name")
}
for ko in "$report"/modules/*.ko; do visit "$(modinfo -F name "$ko")"; done
: > "$ird/modules.list"
for name in "${order[@]}"; do
  cp "${path_of[$name]}" "$ird/lib/modules/"
  echo "/lib/modules/${path_of[$name]##*/}" >> "$ird/modules.list"
done
cp "$ird/modules.list" "$q/modules.list"

# 3. initramfs
{
  echo 'dir /dev 0755 0 0'
  echo 'nod /dev/console 0600 0 0 c 5 1'
  echo 'dir /proc 0755 0 0'
  echo 'dir /sys 0755 0 0'
  echo 'dir /lib 0755 0 0'
  echo 'dir /lib/modules 0755 0 0'
  echo "file /init $ird/init 0755 0 0"
  echo "file /modules.list $ird/modules.list 0644 0 0"
  for f in "$ird"/lib/modules/*.ko; do echo "file /lib/modules/${f##*/} $f 0644 0 0"; done
} > "$ird/list"
[ -x "$out/usr/gen_init_cpio" ] || make -C "$src" O="$out" ARCH=arm LLVM=1 usr/gen_init_cpio >/dev/null
"$out/usr/gen_init_cpio" "$ird/list" | gzip -n -9 > "$q/initramfs.cpio.gz"

# 4. boot
qemu-system-arm --version | head -1 > "$q/qemu-version.txt"
set +e
timeout 300 qemu-system-arm -M virt -cpu cortex-a15 -smp 2 -m 1024 \
  -nographic -nodefaults -no-reboot -serial stdio \
  -kernel "$report/zImage-modular" -initrd "$q/initramfs.cpio.gz" \
  -append "console=ttyAMA0 earlycon panic=-1 rdinit=/init loglevel=7" \
  < /dev/null > "$q/serial.log" 2>&1
rc=$?
set -e
echo "qemu exit: $rc" >> "$q/qemu-version.txt"
grep -E 'BUILD106|Linux version|Machine model' "$q/serial.log" | tee "$q/result.txt" || true
summary=$(grep -m1 'BUILD106_QEMU_SUMMARY' "$q/serial.log" || true)
if [[ -z "$summary" ]]; then
  echo "::error::QEMU run produced no BUILD106 summary (exit $rc); see qemu/serial.log" >&2
  tail -40 "$q/serial.log" >&2
  exit 1
fi
# Per-module table
printf 'module\tload\tunload\n' > "$q/modules-qemu.tsv"
for name in "${order[@]}"; do
  l=$(grep -oE "BUILD106_LOAD_(OK|FAIL) $name rc=-?[0-9]+" "$q/serial.log" | head -1 | awk '{print $1":"$3}')
  u=$(grep -oE "BUILD106_UNLOAD_(OK|FAIL) $name rc=-?[0-9]+" "$q/serial.log" | head -1 | awk '{print $1":"$3}')
  printf '%s\t%s\t%s\n' "$name" "${l:-missing}" "${u:-missing}" >> "$q/modules-qemu.tsv"
done
column -t "$q/modules-qemu.tsv"
[[ "$summary" == *"failures=0"* ]] || { echo "::error::$summary" >&2; exit 1; }
echo "$summary"
