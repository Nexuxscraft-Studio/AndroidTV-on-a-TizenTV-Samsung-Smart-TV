#!/usr/bin/env bash
# Compile only. No install, load, boot or flash. Kernel already configured/prepared.
set -euo pipefail
ksrc="$(realpath "${1:?Linux 6.6.162 source}")"
kout="$(realpath "${2:?configured ARM32 output}")"
here="$(cd "$(dirname "$0")" && pwd)"
[[ $(make -s -C "$ksrc" kernelversion) == 6.6.162 ]]
grep -qx CONFIG_ARM=y "$kout/.config"
# Use external Kbuild so historical Build 059 sources are never compiled by mistake.
makeargs=(-C "$ksrc" O="$kout" ARCH=arm)
if [[ ${TOOLCHAIN:-gcc} == llvm ]]; then
  makeargs+=(LLVM=1)
else
  makeargs+=(CROSS_COMPILE="${CROSS_COMPILE:-arm-linux-gnueabihf-}"
             CC="${CC:-${CROSS_COMPILE:-arm-linux-gnueabihf-}gcc}")
fi
make "${makeargs[@]}" M="$here/kernel" CONFIG_DRM_SDP=m W=1 KCFLAGS=-Werror sdp_display.o
file "$here/kernel/sdp_display.o"
"$kout/scripts/dtc/dtc" -I dts -O dtb -o "$kout/build087-display.dtb" \
  "$here/dts/sdp-nikel-display-disabled.dts"
