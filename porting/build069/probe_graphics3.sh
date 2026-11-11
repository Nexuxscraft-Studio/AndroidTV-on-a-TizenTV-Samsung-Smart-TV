#!/usr/bin/env bash
# Build 069 M3: read-only probe 3 - why the Vulkan loader cannot load
# vulkan.pastel.so ("Could not load ... from default namespace").
set -uo pipefail
L="${1:?los dir}"; P="${2:-qemu_arm_tv}"; cd "$L" || exit 1
O="out/target/product/$P"
sec() { printf '\n######## %s\n' "$*"; }
sec "libvndksupport linker.cpp"; sed -n 1,140p system/core/libvndksupport/linker.cpp
sec "linkerconfig environment.cpp"; sed -n 1,200p system/linkerconfig/modules/environment.cpp
sec "linkerconfig: legacy / sphal decisions"; grep -rn -E 'IsLegacyDevice|IsVndkLiteDevice|BuildSphalNamespace|IsTreblelizedDevice|ro.vndk.version|ro.board.api_level|ro.treble' system/linkerconfig --include='*.cpp' --include='*.h' | grep -v _test | head -60
sec "contents/configuration/baseconfig.cpp"; sed -n 1,140p system/linkerconfig/contents/configuration/baseconfig.cpp
sec "main.cpp config selection"; grep -n -B3 -A12 'IsLegacyDevice\|GetConfiguration' system/linkerconfig/main.cpp | head -80
sec "vulkan loader: driver load"; grep -n -B3 -A25 'android_load_sphal_library' frameworks/native/vulkan/libvulkan/driver.cpp | head -80
sec "built props: vndk/board/treble"; for f in "$O/vendor/build.prop" "$O/system/build.prop" "$O/vendor/default.prop" "$O/system/etc/prop.default"; do [ -f "$f" ] && { echo "--- $f"; grep -E 'vndk|board|treble|api_level|first_api|hardware' "$f"; }; done
sec "cuttlefish board api / vndk settings"; grep -rn -E 'BOARD_SHIPPING_API_LEVEL|BOARD_API_LEVEL|BOARD_VNDK_VERSION|PRODUCT_TREBLE|KEEP_VNDK|VENDOR_API' device/google/cuttlefish/shared/BoardConfig.mk device/google/cuttlefish/shared/device.mk device/google/cuttlefish/vsoc_arm/BoardConfig.mk 2>/dev/null | head -20
sec "vulkan.pastel deps"; readelf -d "$O/vendor/lib/hw/vulkan.pastel.so" 2>/dev/null | grep NEEDED
sec "linkerconfig built for target?"; ls "$O/system/bin/linkerconfig" "$O"/linkerconfig* 2>/dev/null; ls "$O/system/etc" | grep -i ld
echo "(done)"
