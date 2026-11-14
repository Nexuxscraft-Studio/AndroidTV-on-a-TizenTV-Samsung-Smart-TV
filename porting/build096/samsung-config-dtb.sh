#!/usr/bin/env bash
# Build 096: prepare the inputs of the Samsung Nike-L audit, separately from
# the QEMU test. Applies the Build 059 -> 093 patch stack to a fresh 6.6.162
# tree, regenerates the Nike-L ARM32 configuration exactly as Build 094's
# build-arm.sh does, and compiles the two Q60T DTBs plus the disabled display
# and CPU fixtures with the in-tree dtc.
#
# Usage: samsung-config-dtb.sh <work-dir> <verified linux-6.6.162.tar.xz>
#
# Nothing is compiled beyond kconfig and dtc: no zImage, no modules (Build 094
# owns those), no ARM64 build. Outputs land in <work-dir>/samsung-out.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
WORK="${1:?work directory}"
TARBALL="${2:?verified linux-6.6.162.tar.xz}"
TARBALL_SHA256=4aa89f3652fc131e5d39990f3bcd4b9e131028af3f315dbe83f3a8557dc06f06

cd "$REPO"
# shellcheck source=/dev/null
source porting/ci/selfhosted-llvm.sh
echo "$TARBALL_SHA256  $TARBALL" | sha256sum -c -

mkdir -p "$WORK"
WORK="$(cd "$WORK" && pwd)"
ksrc="$WORK/linux-nikel"
kout="$WORK/nikel-arm"
out="$WORK/samsung-out"
rm -rf "$ksrc" "$kout" "$out"
mkdir -p "$ksrc" "$out"
tar -xf "$TARBALL" -C "$ksrc" --strip-components=1

# Same patch order as .github/workflows/build094-integration.yml
patches=(porting/build059/kernel/patches/*.patch
         porting/build088/0001-prepare-display-clocks-and-test-pattern.patch
         porting/build089/0001-prepare-inert-test-pattern-plan.patch
         porting/build091/*.patch
         porting/build093/*.patch)
for p in "${patches[@]}"; do
  patch --fuzz=0 -d "$ksrc" -p1 --batch --forward --no-backup-if-mismatch -s < "$p"
  echo "$p" >> "$out/patches-applied.txt"
done

# Configuration: identical steps to porting/build094/build-arm.sh
make_args=(-C "$ksrc" O="$kout" ARCH=arm LLVM=1 -j"$(nproc)")
make "${make_args[@]}" multi_v7_defconfig
"$ksrc/scripts/kconfig/merge_config.sh" -m -O "$kout" "$kout/.config" \
    porting/build059/kernel/configs/nikel-common.config \
    porting/build059/kernel/configs/nikel-arm.config \
    porting/build059/kernel/configs/nikel-drivers.config
"$ksrc/scripts/config" --file "$kout/.config" -e MODULES -e RESET_CONTROLLER -d DEBUG_INFO_BTF
"$ksrc/scripts/config" --file "$kout/.config" -m DRM_SDP -m DRM_PANFROST
make "${make_args[@]}" olddefconfig
cp "$kout/.config" "$out/kernel.config"

# Device trees (dtc only)
make "${make_args[@]}" sdp/sdp-nikel-q60t-1g5.dtb sdp/sdp-nikel-q60t-2g.dtb
cp "$kout"/arch/arm/boot/dts/sdp/sdp-nikel-q60t-{1g5,2g}.dtb "$out/"
"$kout/scripts/dtc/dtc" -I dts -O dtb -o "$out/display-disabled.dtb" porting/build088/sdp-nikel-display-disabled.dts
"$kout/scripts/dtc/dtc" -I dts -O dtb -o "$out/cpu-disabled.dtb" porting/build058/cpu/nikel-cpu-thermal-disabled.dts
for dtb in "$out"/*.dtb; do
  "$kout/scripts/dtc/dtc" -I dtb -O dts -o "${dtb%.dtb}.dts.txt" "$dtb"
done
python3 porting/build094/check-dt.py "$out/display-disabled.dtb" "$out/cpu-disabled.dtb" \
  "$out"/sdp-nikel-q60t-{1g5,2g}.dtb | tee "$out/dt-status.txt"
python3 porting/build094/check-dt.py --probe "$ksrc/drivers/gpu/drm/sdp" | tee -a "$out/dt-status.txt"
(cd "$out" && sha256sum -- *.dtb kernel.config > SHA256SUMS)
cat "$out/SHA256SUMS"
