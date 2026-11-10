#!/usr/bin/env bash
# Compile only for ARM32 against the prepared 6.6.162 kernel build tree.
# Never installs a module, never contacts TV or loads/flash any firmware.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: bash %s /absolute/path/to/configured/linux-6.6.162\n' "$0" >&2
  exit 2
fi
kernel_dir="$(realpath -- "$1")"
module_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/kernel" && pwd)"
if [[ ! -f "${kernel_dir}/Makefile" || ! -f "${kernel_dir}/include/generated/autoconf.h" ]]; then
  printf 'Kernel 6.6.162 must be configured and prepared first: %s\n' "$kernel_dir" >&2
  exit 2
fi
kernel_version="$(make -s -C "$kernel_dir" kernelversion)"
if [[ "$kernel_version" != "6.6.162" ]]; then
  printf 'Expected Linux 6.6.162, received %s; build refused.\n' "$kernel_version" >&2
  exit 2
fi
cross_prefix="${CROSS_COMPILE:-arm-linux-gnueabihf-}"
if ! command -v "${cross_prefix}gcc" >/dev/null 2>&1; then
  printf 'ARM32 cross-compiler missing: %sgcc\n' "$cross_prefix" >&2
  exit 2
fi

printf 'Compiling CPU/TMU experimental modules offline against Linux 6.6.162 (ARM32)\n'
make -C "$kernel_dir" M="$module_dir" ARCH=arm CROSS_COMPILE="$cross_prefix" modules
printf 'Compilation done. Do NOT insmod/modprobe these prototype modules.\n'
