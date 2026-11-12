#!/usr/bin/env bash
# Build 069 Boot 11: read-only probe - can SurfaceFlinger compose the client
# target in BGRA_8888 (DRM ARGB8888)? virtio-gpu 6.6 accepts only
# XRGB8888/ARGB8888 framebuffers (virtgpu_display.c: -ENOENT otherwise).
set -uo pipefail
L="${1:?los dir}"; cd "$L" || exit 1
sec() { printf '\n######## %s\n' "$*"; }
S=frameworks/native/services/surfaceflinger
sec "sysprop definition"; grep -rn -B3 -A12 'default_composition_pixel_format' $S/sysprop/*.sysprop | head -40
sec "SurfaceFlinger use"; grep -rn -E 'default_composition_pixel_format|defaultCompositionPixelFormat|mDefaultCompositionPixelFormat' $S --include='*.cpp' --include='*.h' | head -30
sec "FramebufferSurface / client target format"; grep -rn -E 'setDefaultBufferFormat|HAL_PIXEL_FORMAT_RGBA_8888|PIXEL_FORMAT_RGBA_8888' $S/DisplayHardware/FramebufferSurface.cpp $S/SurfaceFlinger.cpp | head -20
sec "drm_hwcomposer HAL->DRM format mapping"; grep -rn -E 'HAL_PIXEL_FORMAT_BGRA_8888|HAL_PIXEL_FORMAT_RGBA_8888|DRM_FORMAT_ARGB8888|DRM_FORMAT_ABGR8888' external/drm_hwcomposer/bufferinfo/*.cpp external/minigbm/cros_gralloc/*.cc 2>/dev/null | head -20
sec "cuttlefish / goldfish: composition pixel format props"; grep -rn 'composition_pixel_format\|client_target' device/google/cuttlefish device/generic/goldfish 2>/dev/null | head -10
echo "(done)"
