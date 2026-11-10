#!/usr/bin/env bash
# Attempt first object from ORIGINAL media sources against original ARM32 kernel.
# Intended to stop on missing vendor headers; never load/flash generated objects.
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <extracted-linux-4.1.10-source> <build054-ARM32-kernel-obj> <build054-original-media-sdp_drm_nike-dir>" >&2
  exit 2
fi

KERNEL_SOURCE=$(realpath -e -- "$1")
ARM32_OBJECTS=$(realpath -e -- "$2")
VENDOR_SOURCE=$(realpath -e -- "$3")
ARM32_CROSS_COMPILE=${ARM32_CROSS_COMPILE:-arm-linux-gnueabi-}

if [[ "$VENDOR_SOURCE" != *build054-* || ! -f "$ARM32_OBJECTS/.config" ]]; then
  echo "Refusing: need Build-054 media copy and prepared ARM32 .config" >&2
  exit 2
fi
if [[ ! -f "$VENDOR_SOURCE/Kbuild" || ! -f "$VENDOR_SOURCE/sdp_drm_drv.c" ]]; then
  echo "Prepare original media copy with Build-054 ARM32 Kbuild first" >&2
  exit 2
fi
if ! grep -q '^CONFIG_ARM=y$' "$ARM32_OBJECTS/.config"; then
  echo "Refusing: ARCH=arm kernel configuration missing" >&2
  exit 2
fi

# Require the ORIGINAL driver, not our ARM64-patched Samsung Build 053/054.
ORIGINAL_SHA=2f35fcfe3fb284c460fb07a00d24f048277b839641b6738e91773ff11128981d
if [[ "$(sha256sum -- "$VENDOR_SOURCE/sdp_drm_drv.c" | cut -d ' ' -f1)" != "$ORIGINAL_SHA" ]]; then
  echo "Refusing: vendor source differs from pinned original Samsung driver" >&2
  exit 2
fi

make -C "$KERNEL_SOURCE" O="$ARM32_OBJECTS" \
  ARCH=arm CROSS_COMPILE="$ARM32_CROSS_COMPILE" \
  M="$VENDOR_SOURCE" sdp_drm_drv.o
