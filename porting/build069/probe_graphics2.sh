#!/usr/bin/env bash
# Build 069 M3: read-only probe 2 - GLES/Vulkan options for ARM32.
set -uo pipefail
L="${1:?los dir}"; cd "$L" || exit 1
sec() { printf '\n######## %s\n' "$*"; }
sec "swiftshader/Android.bp 55-110"; sed -n 55,110p external/swiftshader/Android.bp
sec "swiftshader/src/Android.bp vulkan.pastel block"; awk '/name: "vulkan.pastel"/{f=1} f{print; n++} n>60{exit}' external/swiftshader/src/Android.bp
sec "swiftshader reactor arm32 support"; ls external/swiftshader/src/Reactor 2>/dev/null | head -30; grep -rln -i 'arm32\|__arm__\|ARM_32' external/swiftshader/src/Reactor 2>/dev/null | head
sec "angle: default enabled? first module block"; sed -n 1140,1170p external/angle/Android.bp
grep -n -E '^\s+arm: *\{' external/angle/Android.bp | head -5; grep -c -E '^\s+arm64: *\{' external/angle/Android.bp
sec "angle cc_defaults enabled/arch"; grep -n -B2 -A8 'name: "angle_common_library_cflags"\|name: "angle_common_auto_cflags"' external/angle/Android.bp | head -40
sec "mesa3d Android.bp modules + soong config"; grep -n -E 'name: "|soong_config|module_type|config_namespace|variables|gallium|drivers' external/mesa3d/Android.bp | head -60
sec "mesa3d android docs"; ls external/mesa3d/docs | grep -i android; sed -n 1,80p external/mesa3d/docs/android.rst 2>/dev/null | grep -i -E 'BOARD_MESA|soong|gallium|panfrost|virgl|softpipe|llvmpipe|hermetic' | head -30
sec "mesa3d meson_to_hermetic"; ls external/mesa3d/meson_to_hermetic | head; ls external/mesa3d/meson_to_hermetic/* 2>/dev/null | head -20
sec "mesa3d in any device mk"; grep -rln --include='*.mk' -E 'mesa3d|libGLES_mesa|BOARD_MESA3D' device vendor/lineage 2>/dev/null | head
sec "prebuilt GLES libs in tree (arm)"; find prebuilts vendor -maxdepth 6 \( -name 'libGLESv2*.so' -o -name 'libEGL_*.so' \) 2>/dev/null | grep -E '/arm/|armeabi' | head
echo "(done)"
