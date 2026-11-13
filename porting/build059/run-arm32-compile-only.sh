#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
if [[ $# != 2 || -e $2 ]]; then
    echo "Usage: $0 <linux-6.6.162-source> <new-output-directory>" >&2
    exit 2
fi

src=$(realpath -e -- "$1")
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
cross=${CROSS_COMPILE:-arm-linux-gnueabi-}
[[ $(make -s -C "$src" kernelversion) == 6.6.162 ]]
for tool in "${cross}gcc" "${cross}readelf" dtc fdtget; do
    command -v "$tool" >/dev/null
done
mkdir -- "$2"
out=$(realpath -e -- "$2")
cp -R -- "$here/kernel" "$out/probe"

kmake() {
    make -C "$src" O="$out/obj" ARCH=arm CROSS_COMPILE="$cross" "$@"
}

dtb="$out/nikel-display-disabled.dtb"
dtc -I dts -O dtb -o "$dtb" "$here/nikel-display-disabled.dts"
[[ $(fdtget -tx "$dtb" /osdp@5d0000 reg) == '5d0000 4000' ]]
[[ $(fdtget -tx "$dtb" /osdp@5d0000 interrupts) == '0 2f 0' ]]
[[ $(fdtget -tx "$dtb" /mixer@5d8000 reg) == '5d8000 4000' ]]
if fdtget "$dtb" /mixer@5d8000 interrupts 2>/dev/null; then
    exit 1
fi
for node in /osdp@5d0000 /mixer@5d8000 /interrupt-controller; do
    [[ $(fdtget "$dtb" "$node" status) == disabled ]]
done
echo 'PASS: disabled DT fixture and resource cells'

kmake multi_v7_defconfig
kmake olddefconfig
for symbol in ARM MODULES OF OF_ADDRESS OF_IRQ HAS_IOMEM; do
    grep -qx "CONFIG_${symbol}=y" "$out/obj/.config"
done
echo 'PASS: ARM32 Kconfig prerequisites'
kmake -j"${JOBS:-2}" modules_prepare
kmake M="$out/probe" W=1 sdp_nikel_display_probe.o
LC_ALL=C "${cross}readelf" -h "$out/probe/sdp_nikel_display_probe.o" | tee "$out/elf-header.txt"
grep -Eq 'Class:[[:space:]]+ELF32' "$out/elf-header.txt"
grep -Eq 'Machine:[[:space:]]+ARM$' "$out/elf-header.txt"
echo 'PASS: Linux 6.6.162 ARM32 probe object'
