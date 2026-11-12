#!/usr/bin/env bash
# Build 069 Boot 13: read-only probe - where is the client-target buffer format
# of a physical display really decided? (patched processDisplayAdded line had no
# effect: drm_hwcomposer still gets -ENOENT = format not XRGB/ARGB8888.)
set -uo pipefail
L="${1:?los dir}"; cd "$L" || exit 1
sec() { printf '\n######## %s\n' "$*"; }
S=frameworks/native/services/surfaceflinger
sec "patched? (git diff frameworks/native)"; git -C frameworks/native diff --stat; git -C frameworks/native diff | head -30
sec "processDisplayAdded: every use of pixelFormat"; awk '/^void SurfaceFlinger::processDisplayAdded/{p=1} p{print NR": "$0} /^}/{if(p){exit}}' $S/SurfaceFlinger.cpp | grep -n -E 'pixelFormat|FramebufferSurface|setPixelFormat|createRenderSurface|RenderSurfaceCreationArgs|DisplaySurface' 
sec "FramebufferSurface: buffer format"; grep -n -E 'setDefaultBufferFormat|PIXEL_FORMAT|getFormat|setDefaultBufferSize' $S/DisplayHardware/FramebufferSurface.cpp
sec "RenderSurface: window format"; grep -rn -E 'native_window_set_buffers_format|mFormat|getPixelFormat|setPixelFormat' $S/CompositionEngine/src/RenderSurface.cpp $S/CompositionEngine/include/compositionengine/RenderSurfaceCreationArgs.h | head -20
sec "setupNewDisplayDeviceInternal: format"; grep -n -B2 -A6 'setPixelFormat\|PixelFormat format' $S/SurfaceFlinger.cpp | sed -n 1,80p
sec "7b: RenderSurface.cpp 1-120"; sed -n 1,120p $S/CompositionEngine/src/RenderSurface.cpp
sec "7b: compositionengine shared_libs"; grep -n -A30 'name: "libcompositionengine_defaults"' $S/CompositionEngine/Android.bp | head -45
sec "7b: callers of setBufferPixelFormat"; grep -rn 'setBufferPixelFormat' $S --include='*.cpp' | grep -v test | head
sec "7c: Display.cpp around setBufferPixelFormat"; sed -n 340,372p $S/CompositionEngine/src/Display.cpp
sec "7c: drm_hwcomposer client target property"; grep -rn -B3 -A12 'ClientTargetProperty\|client_target_property\|clientTargetProperty' external/drm_hwcomposer --include='*.cpp' --include='*.h' | grep -v -i test | head -80
echo "(done)"
