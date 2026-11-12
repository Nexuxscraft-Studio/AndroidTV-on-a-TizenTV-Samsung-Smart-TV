#!/usr/bin/env bash
# Build 069 Boot 12: read-only probe - client target still "not usable by
# DRM/KMS" with ro.surface_flinger.default_composition_pixel_format=5.
set -uo pipefail
L="${1:?los dir}"; cd "$L" || exit 1
O=out/target/product/qemu_arm_tv
sec() { printf '\n######## %s\n' "$*"; }
S=frameworks/native/services/surfaceflinger
D=external/drm_hwcomposer
sec "prop in installed vendor build.prop"; grep -n 'surface_flinger' $O/vendor/build.prop $O/vendor/etc/build.prop 2>/dev/null
sec "SF.cpp 890-915 (defaultCompositionPixelFormat use)"; sed -n 890,915p $S/SurfaceFlinger.cpp
sec "SF.cpp 3795-3840 (RGBA_8888 for display surfaces)"; sed -n 3795,3840p $S/SurfaceFlinger.cpp
sec "drm_hwcomposer: client layer usability"; grep -rn -B12 -A4 'Client layer must be always usable' $D | head -60
sec "drm_hwcomposer: IsLayerUsableAsDevice / PopulateLayerData"; grep -rn -A25 'bool HwcLayer::IsLayerUsableAsDevice\|void HwcLayer::PopulateLayerData\|void HwcLayer::ImportFb' $D/hwc2_device/HwcLayer.cpp | head -90
sec "drm_hwcomposer: plane format check"; grep -rn -B3 -A12 'IsFormatSupported\|bool DrmPlane::IsValidForLayer' $D/drm/DrmPlane.cpp | head -60
echo "(done)"
