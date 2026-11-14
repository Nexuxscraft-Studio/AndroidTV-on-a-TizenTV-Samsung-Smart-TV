#!/usr/bin/env bash
set -euo pipefail

source porting/ci/selfhosted-llvm.sh
build=${1:?build directory}
ksrc="$build/linux-6.6.162"
kout="$build/arm"
evidence="$build/evidence"
mkdir -p "$evidence"
make_args=(-C "$ksrc" O="$kout" ARCH=arm LLVM=1)
config=("$ksrc/scripts/config" --file "$kout/.config")

make "${make_args[@]}" multi_v7_defconfig
"$ksrc/scripts/kconfig/merge_config.sh" -m -O "$kout" "$kout/.config" \
    porting/build059/kernel/configs/nikel-common.config \
    porting/build059/kernel/configs/nikel-arm.config \
    porting/build059/kernel/configs/nikel-drivers.config
"${config[@]}" -e MODULES -e RESET_CONTROLLER -d DEBUG_INFO_BTF
"${config[@]}" -m DRM_SDP -m DRM_PANFROST
make "${make_args[@]}" olddefconfig
cp "$kout/.config" "$evidence/kernel.config"

for symbol in ARCH_SDP SERIAL_SDP COMMON_CLK_SDP1804 GPIO_SDP SDP1804_GPU_POWER \
    PM_GENERIC_DOMAINS SDP_MSGBOX SDP_MICOM IR_SDP_MICOM CEC_SDP_CECIF CPUFREQ_DT THERMAL_OF SND_SOC \
    DRM_SIMPLEDRM MMC_DW_EXYNOS USB_EHCI_HCD_PLATFORM USB_OHCI_HCD_PLATFORM; do
    grep -qx "CONFIG_$symbol=y" "$kout/.config" || { echo "Missing $symbol=y"; exit 1; }
done
for symbol in DRM_SDP DRM_PANFROST SDP_MAC DRM_SDP_HDMI SDP_MICOM_IRB SDP_MICOM_IRS; do
    grep -qx "CONFIG_$symbol=m" "$kout/.config" || { echo "Missing $symbol=m"; exit 1; }
done

make "${make_args[@]}" -j "$(nproc)" W=1 KCFLAGS=-Werror drivers/gpu/drm/sdp/sdp_display.o
make "${make_args[@]}" -j "$(nproc)" zImage modules 2>&1 | tee "$evidence/kernel.log"
test -s "$kout/Module.symvers"
test -s "$kout/arch/arm/boot/zImage"
cp -R porting/build058/cpu/kernel "$build/cpu"
make "${make_args[@]}" M="$build/cpu" W=1 KCFLAGS=-Werror modules 2>&1 | tee "$evidence/cpu.log"

for elf in "$kout/vmlinux" \
    "$kout/drivers/gpu/drm/sdp/sdp_display.ko" \
    "$kout/drivers/gpu/drm/panfrost/panfrost.ko" \
    "$kout/drivers/gpu/drm/sdp-hdmi/sdp_hdmi.ko" \
    "$kout/drivers/net/ethernet/sdp/sdp_mac.ko" \
    "$kout/drivers/misc/sdp-micom/sdp_micom_"{irb,irs}.ko \
    "$build/cpu"/sdp_nikel_{cpu_clk,cpufreq,thermal}.ko; do
    llvm-readelf -h "$elf" | tee "$build/elf-header"
    grep -Eq 'Class:[[:space:]]+ELF32$' "$build/elf-header"
    grep -Eq 'Machine:[[:space:]]+ARM$' "$build/elf-header"
    { basename "$elf"; cat "$build/elf-header"; } >> "$evidence/elf.txt"
done
