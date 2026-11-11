#!/usr/bin/env bash
# Build 069 M3: read-only probe of the LineageOS tree for the graphics/audio
# building blocks (module names, arch restrictions). Prints to stdout only.
# Usage: probe_graphics.sh <los-dir>
set -uo pipefail
L="${1:?los dir}"
cd "$L" || exit 1
sec() { printf '\n######## %s\n' "$*"; }
modnames() {  # modnames <Android.bp...>: module type + name
  for f in "$@"; do
    [ -f "$f" ] || continue
    echo "--- $f"
    awk '/^[a-z_]+ *\{/ {t=$1} /^[[:space:]]+name: *"/ && t!="" {gsub(/[",]/,"",$2); print "   " t " " $2; t=""}' "$f"
  done
}
archblocks() {  # show enabled/arch hints
  grep -n -E 'enabled: *(true|false)|^\s+(arm|arm64|x86|x86_64|riscv64): *\{|host_supported|compile_multilib|android_arm' "$@" 2>/dev/null | head -60
}

sec "minigbm"
ls external/minigbm 2>/dev/null | head -50
modnames external/minigbm/Android.bp external/minigbm/cros_gralloc/*/Android.bp external/minigbm/cros_gralloc/*/*/Android.bp
grep -rn -E 'virtgpu|virtio_gpu|DRV_' external/minigbm/Android.bp 2>/dev/null | head -20

sec "drm_hwcomposer"
modnames external/drm_hwcomposer/Android.bp external/drm_hwcomposer/hwc3/Android.bp
ls external/drm_hwcomposer/hwc3 2>/dev/null | head

sec "swiftshader (arch)"
modnames external/swiftshader/Android.bp external/swiftshader/src/Android.bp 2>/dev/null | grep -i -E 'vulkan|pastel|egl|gles|^---' | head -20
archblocks external/swiftshader/src/Android.bp external/swiftshader/Android.bp

sec "angle (modules, arch)"
grep -n -E 'name: "(libEGL_angle|libGLESv1_CM_angle|libGLESv2_angle|com.android.angle|ANGLE.*)"' external/angle/Android.bp 2>/dev/null | head
grep -n -E '^\s+(arm|arm64|x86|x86_64): *\{|enabled: false' external/angle/Android.bp 2>/dev/null | head -20

sec "mesa3d"
ls external/mesa3d 2>/dev/null | head -40
ls external/mesa3d/android 2>/dev/null | head
grep -rn -E 'BOARD_MESA3D_[A-Z_]+' external/mesa3d/android/*.mk 2>/dev/null | head -20

sec "cuttlefish graphics/audio packages"
grep -rn -h -E 'minigbm|hwc3|drm_hwcomposer|swiftshader|pastel|angle|composer|allocator|mapper|audio\.(service|primary)|audio-impl|android\.hardware\.audio' device/google/cuttlefish/shared/*.mk device/google/cuttlefish/shared/*/*.mk 2>/dev/null | sort -u | head -60

sec "goldfish graphics/audio packages (reference)"
grep -rn -h -E 'mapper|allocator|composer|hwcomposer|EGL|audio' device/generic/goldfish/product/*.mk 2>/dev/null | sort -u | head -40

sec "audio default HAL modules"
for f in hardware/interfaces/audio/aidl/default/Android.bp; do modnames "$f" | grep -E 'service|^---' | head; done

sec "health/power/... example services available"
for d in health power thermal light memtrack; do
  f="hardware/interfaces/$d/aidl/default/Android.bp"; [ -f "$f" ] && modnames "$f" | grep -i -E 'service|^---' | head -4
done

sec "kernel virtio-gpu"
grep -E 'CONFIG_(DRM|DRM_VIRTIO_GPU|DRM_KMS_HELPER|FB|VIRTIO_INPUT|INPUT_EVDEV|DRM_SIMPLEDRM)=' \
  "${KCONFIG:-/dev/null}" 2>/dev/null || true
echo "(done)"
