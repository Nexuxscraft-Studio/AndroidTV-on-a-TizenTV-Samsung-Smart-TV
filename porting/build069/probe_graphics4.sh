#!/usr/bin/env bash
# Build 069 Boot 11: read-only probe - why drm_hwcomposer cannot create a KMS
# framebuffer for the client target ("could not create drm fb -2", then
# "Client layer must be always usable by DRM/KMS" / BAD_LAYER) on virtio-gpu
# (QEMU, no virgl) with minigbm.
set -uo pipefail
L="${1:?los dir}"; cd "$L" || exit 1
O=out/target/product/qemu_arm_tv
sec() { printf '\n######## %s\n' "$*"; }
M=external/minigbm
D=external/drm_hwcomposer
sec "minigbm: which allocator/mapper module + backend is built"; grep -n -B2 -A25 'name: "android.hardware.graphics.allocator-service.minigbm"\|name: "mapper.minigbm"\|name: "minigbm_cros_gralloc"\|cc_library.*"minigbm_gralloc' $M/Android.bp $M/cros_gralloc/aidl/Android.bp $M/cros_gralloc/mapper_stablec/Android.bp 2>/dev/null | head -150
sec "minigbm: backends and virtio_gpu selection"; ls $M/*.c | head -60; grep -n -E 'virtio_gpu|virtgpu|"virtio' $M/drv.c $M/virtgpu.c 2>/dev/null | head -30
sec "minigbm: virtgpu 2D (no virgl) path"; grep -n -E 'virgl|dumb|DRM_IOCTL_MODE_CREATE_DUMB|params\[|feature|cross_domain|has_3d|caps' $M/virtgpu.c $M/virtgpu_virgl.c 2>/dev/null | head -60
sec "minigbm: dumb helper"; grep -n -A30 'int drv_dumb_bo_create_ex' $M/helpers.c | head -45
sec "drm_hwcomposer: framebuffer import"; grep -rn -B15 -A10 'could not create drm fb' $D | head -80
sec "drm_hwcomposer: prime import"; grep -rn -B3 -A12 'drmPrimeFDToHandle' $D/drm/DrmFbImporter.cpp | head -60
sec "drm_hwcomposer: which fd (card / render)"; grep -rn -E 'renderD|/dev/dri/card|drmOpen|open\(' $D/drm/DrmDevice.cpp $D/drm/ResourceManager.cpp 2>/dev/null | head -20
sec "product: gralloc/minigbm related properties and packages"; grep -a -E 'gralloc|minigbm|hwcomposer|drm' $O/vendor/build.prop | head -20
sec "cuttlefish: minigbm + drm_hwcomposer setup"; grep -rn -E 'minigbm|drm_hwcomposer|hwc3-service.drm|ro.hardware.gralloc|ro.hardware.hwcomposer' device/google/cuttlefish/shared/graphics/*.mk device/google/cuttlefish/shared/device.mk 2>/dev/null | head -30
echo "(done)"
