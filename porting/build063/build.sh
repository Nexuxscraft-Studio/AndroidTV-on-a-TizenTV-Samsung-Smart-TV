#!/usr/bin/env bash
# Build 063: compile-gate the new driver scaffolds against Linux 6.6.162 (ARM32).
#
# Usage:
#   build.sh <linux-6.6.162-tree> <arm|arm64> <output-dir>
#
# Environment:
#   TOOLCHAIN=llvm (default) | gcc
#   CROSS_COMPILE  (gcc only; default arm-linux-gnueabihf- / aarch64-linux-gnu-)
#   JOBS           (default: nproc)
#
# What it does (compile-only, nothing is installed/flashed/booted):
#   1. verifies the tree is a clean v6.6.162 checkout
#   2. copies the sdp-drm display skeleton into drivers/gpu/drm/sdp/ and wires
#      it into the DRM Kconfig/Makefile (idempotent)
#   3. configures multi_v7_defconfig + COMPILE_TEST + the nikel-*.config fragments
#   4. compiles drivers/gpu/drm/sdp/sdp_drm.o with W=1 -Werror (the gate)
#   5. dtc-compiles every build063 reference DTS (syntax check)
#
# A green run proves the display skeleton and the device-tree fixtures are
# syntactically valid for ARM32. It does NOT prove any driver works or boots.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KSRC="${1:?kernel tree}"
ARCH_NAME="${2:?arm|arm64}"
OUT="${3:?output dir}"
TOOLCHAIN="${TOOLCHAIN:-llvm}"
JOBS="${JOBS:-$(nproc)}"
EXPECTED_VERSION="6.6.162"

die() { echo "build063: ERROR: $*" >&2; exit 1; }
log() { echo "build063: $*"; }

case "$ARCH_NAME" in
  arm)   KARCH=arm;   BASE_DEFCONFIG=multi_v7_defconfig; DEF_CROSS=arm-linux-gnueabihf- ;;
  arm64) KARCH=arm64; BASE_DEFCONFIG=defconfig;          DEF_CROSS=aarch64-linux-gnu- ;;
  *) die "unknown arch '$ARCH_NAME'" ;;
esac

[ -f "$KSRC/Makefile" ] || die "$KSRC is not a kernel tree"
version="$(make -s -C "$KSRC" kernelversion)"
[ "$version" = "$EXPECTED_VERSION" ] || die "kernel $version, expected $EXPECTED_VERSION"

mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
KOUT="$OUT/kbuild-$ARCH_NAME"; ART="$OUT/artifacts-$ARCH_NAME"
mkdir -p "$KOUT" "$ART"

MAKEARGS=(-C "$KSRC" O="$KOUT" ARCH="$KARCH" -j"$JOBS")
if [ "$TOOLCHAIN" = llvm ]; then MAKEARGS+=(LLVM=1)
else MAKEARGS+=(CROSS_COMPILE="${CROSS_COMPILE:-$DEF_CROSS}"); fi

# 1. place the display skeleton into the tree -------------------------------
DST="$KSRC/drivers/gpu/drm/sdp"
mkdir -p "$DST"
cp "$HERE/kernel/display/sdp_drm.c" "$HERE/kernel/display/Kconfig" \
   "$HERE/kernel/display/Makefile" "$DST/"

# wire into DRM Kconfig/Makefile (idempotent)
if ! grep -q 'drivers/gpu/drm/sdp/Kconfig' "$KSRC/drivers/gpu/drm/Kconfig"; then
  printf '\nsource "drivers/gpu/drm/sdp/Kconfig"\n' >> "$KSRC/drivers/gpu/drm/Kconfig"
fi
if ! grep -q 'obj-$(CONFIG_DRM_SDP)' "$KSRC/drivers/gpu/drm/Makefile"; then
  printf '\nobj-$(CONFIG_DRM_SDP) += sdp/\n' >> "$KSRC/drivers/gpu/drm/Makefile"
fi

# 2. configure --------------------------------------------------------------
make "${MAKEARGS[@]}" "$BASE_DEFCONFIG"
FRAGS=(
  "$HERE/configs/compile-test.config"
  "$HERE/configs/nikel-display.config"
  "$HERE/configs/nikel-gpu.config"
  "$HERE/configs/nikel-cpu.config"
  "$HERE/configs/nikel-soc-extra.config"
)
(cd "$KOUT" && "$KSRC/scripts/kconfig/merge_config.sh" -m -O "$KOUT" \
    "$KOUT/.config" "${FRAGS[@]}")
make "${MAKEARGS[@]}" olddefconfig

grep -qx 'CONFIG_DRM_SDP=m' "$KOUT/.config" \
  || grep -qx 'CONFIG_DRM_SDP=y' "$KOUT/.config" \
  || die "CONFIG_DRM_SDP not enabled after olddefconfig"
log "CONFIG_DRM_SDP enabled"

# 3. the compile gate: display skeleton, W=1 -Werror ------------------------
make "${MAKEARGS[@]}" W=1 KCFLAGS=-Werror drivers/gpu/drm/sdp/sdp_drm.o
cp "$KOUT/drivers/gpu/drm/sdp/sdp_drm.o" "$ART/" 2>/dev/null || true
log "sdp_drm.o compiled (W=1 -Werror)"

# 4. device-tree syntax check ------------------------------------------------
if command -v dtc >/dev/null 2>&1; then
  for d in "$HERE"/dts/*.dts; do
    out="$ART/$(basename "${d%.dts}").dtb"
    dtc -q -I dts -O dtb -o "$out" "$d" || die "dtc failed on $(basename "$d")"
    log "dtc ok: $(basename "$d")"
  done
else
  log "dtc not found; skipping DTS check"
fi

# 5. summary ----------------------------------------------------------------
(cd "$ART" && sha256sum -- * > SHA256SUMS 2>/dev/null || true)
{
  echo "kernel:    $version"
  echo "arch:      $ARCH_NAME ($KARCH)"
  echo "toolchain: $TOOLCHAIN"
  echo "gate:      drivers/gpu/drm/sdp/sdp_drm.o (W=1 -Werror) PASS"
  echo "dts:       $(ls "$HERE"/dts/*.dts | wc -l) fixtures checked"
} | tee "$ART/BUILD063_INFO.txt"
log "done: $ART"
