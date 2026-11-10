#!/usr/bin/env bash
# Build 054: compile ARM32 kernel probe ONLY, never load or install a module.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <extracted-linux-4.1.10-source> <NEW-build054-arm32-workdir>" >&2
  exit 2
fi

KERNEL_SOURCE=$(realpath -e -- "$1")
ARM32_WORK=$(realpath -m -- "$2")
PROBE_SOURCE=$(realpath -e -- "$(dirname -- "${BASH_SOURCE[0]}")/../arm32-probe")
ARM32_CROSS_COMPILE=${ARM32_CROSS_COMPILE:-arm-linux-gnueabi-}

if [[ "$(basename -- "$ARM32_WORK")" != build054-* || -e "$ARM32_WORK" ]]; then
  echo "Refusing: the output must be a new, nonexistent build054-* directory" >&2
  exit 2
fi
if [[ ! -f "$KERNEL_SOURCE/arch/arm/configs/Nike.M-Tizen_release_defconfig" ]]; then
  echo "Missing original Samsung Nike.M ARM32 defconfig" >&2
  exit 2
fi
if ! grep -q '^CONFIG_CPU_ARM_CORTEX_A15=y$' "$KERNEL_SOURCE/arch/arm/configs/Nike.M-Tizen_release_defconfig"; then
  echo "Refusing: ARM32 source is not the audited Cortex-A15 baseline" >&2
  exit 2
fi
if ! command -v "${ARM32_CROSS_COMPILE}gcc" >/dev/null; then
  echo "Cross compiler ${ARM32_CROSS_COMPILE}gcc is not installed" >&2
  exit 2
fi
if ! command -v "${ARM32_CROSS_COMPILE}readelf" >/dev/null; then
  echo "Cross binutils ${ARM32_CROSS_COMPILE}readelf is not installed" >&2
  exit 2
fi

mkdir -- "$ARM32_WORK"
mkdir -- "$ARM32_WORK/kernel-obj" "$ARM32_WORK/probe"
cp -- "$PROBE_SOURCE/Kbuild" "$PROBE_SOURCE/nover_arm32_probe.c" "$ARM32_WORK/probe/"

echo "ARM32 original-kernel defconfig (Cortex-A15), no module loading"
make -C "$KERNEL_SOURCE" O="$ARM32_WORK/kernel-obj" \
  ARCH=arm CROSS_COMPILE="$ARM32_CROSS_COMPILE" \
  Nike.M-Tizen_release_defconfig 2>&1 | tee "$ARM32_WORK/01-config.log"

make -C "$KERNEL_SOURCE" O="$ARM32_WORK/kernel-obj" \
  ARCH=arm CROSS_COMPILE="$ARM32_CROSS_COMPILE" \
  -j2 modules_prepare 2>&1 | tee "$ARM32_WORK/02-prepare.log"

# Single .o explicitly avoids modpost, .ko, insmod, flash or firmware writes.
make -C "$KERNEL_SOURCE" O="$ARM32_WORK/kernel-obj" \
  ARCH=arm CROSS_COMPILE="$ARM32_CROSS_COMPILE" \
  M="$ARM32_WORK/probe" nover_arm32_probe.o \
  2>&1 | tee "$ARM32_WORK/03-compile.log"

"${ARM32_CROSS_COMPILE}readelf" -h \
  "$ARM32_WORK/probe/nover_arm32_probe.o" \
  | tee "$ARM32_WORK/04-elf-header.log"

echo "Only ELF32/ARM compilation was tested, NOT Samsung Q60T compatibility."
