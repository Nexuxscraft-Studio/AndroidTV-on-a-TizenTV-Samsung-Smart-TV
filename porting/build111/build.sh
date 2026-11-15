#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
work=${1:?absolute scratch path}
tarball=${2:?absolute kernel tarball path}
results=${3:?absolute output path}
cd "$repo"
source porting/ci/selfhosted-llvm.sh
export LC_ALL=C TZ=UTC SOURCE_DATE_EPOCH=1735689600
export KBUILD_BUILD_TIMESTAMP='2025-01-01 00:00:00 UTC'
export KBUILD_BUILD_USER=build111 KBUILD_BUILD_HOST=ci KBUILD_BUILD_VERSION=1
mkdir -p "$work" "$results"

for pass in a b; do
    tree="$work/$pass"
    mkdir "$tree"
    bash porting/build096/samsung-config-dtb.sh "$tree" "$tarball" > "$results/config-$pass.log" 2>&1
    src="$tree/linux-nikel"
    out="$tree/nikel-arm"
    python3 porting/build111/package.py prepare "$src"
    cc=(make -C "$src" O="$out" ARCH=arm LLVM=1 -j"${BUILD111_JOBS:-$(nproc)}")
    "$src/scripts/config" --file "$out/.config" \
        -e SERIAL_SDP -e SERIAL_SDP_CONSOLE -e IKCONFIG -e IKCONFIG_PROC \
        -e KERNEL_GZIP -e BLK_DEV_INITRD -e SERIAL_AMBA_PL011 -e SERIAL_AMBA_PL011_CONSOLE \
        -d LOCALVERSION_AUTO -d CMDLINE_FORCE --set-str LOCALVERSION "" --set-str INITRAMFS_SOURCE "" \
        -m SDP_MSGBOX -m SDP_MICOM -m IR_SDP_MICOM -m CEC_SDP_CECIF -m GPIO_SDP \
        -m DRM_SDP -m DRM_SDP_HDMI -m DRM_PANFROST
    export KCFLAGS="-ffile-prefix-map=$tree=/build111"
    "${cc[@]}" olddefconfig >> "$results/config-$pass.log" 2>&1
    grep -x 'CONFIG_SERIAL_SDP=y' "$out/.config"
    grep -x 'CONFIG_SERIAL_SDP_CONSOLE=y' "$out/.config"

    driver="$src/drivers/tty/serial/sdp_uart.c"
    grep -nE 'CONFIG_SERIAL_SDP_CONSOLE|struct console|OF_EARLYCON_DECLARE|samsung,sdp-uart2' "$driver" \
        > "$results/uart-$pass.txt"
    grep -q 'samsung,sdp-uart2' "$driver"
    python3 porting/build094/check-dt.py --probe "$src/drivers/gpu/drm/sdp" \
        | tee "$results/interlock-$pass.txt"
    "${cc[@]}" zImage sdp/sdp-nikel-q60t-1g5.dtb sdp/sdp-nikel-q60t-2g.dtb \
        > "$results/kernel-$pass.log" 2>&1
    llvm-nm "$out/vmlinux" > "$tree/vmlinux.nm"
    grep -E ' [bBdDrRtT] sdp_.*(console|uart)' "$tree/vmlinux.nm" >> "$results/uart-$pass.txt"
    grep -Eq ' [bBdDrRtT] sdp_.*console' "$tree/vmlinux.nm"
    python3 porting/build111/package.py build "$out" "$tree/BUILD111-Q60T-OFFLINE-ONLY.zip"
done

name=BUILD111-Q60T-OFFLINE-ONLY.zip
cmp "$work/a/$name" "$work/b/$name"
printf '%s\n' 'Byte-identical offline ZIP from two independent kernel build trees' | tee "$results/reproducibility.txt"
python3 porting/build111/package.py qemu "$work/a/$name" | tee "$results/qemu.txt"
cp "$work/a/$name" "$work/a/$name.sha256" "$results/"
(cd "$results" && sha256sum -c "$name.sha256")
