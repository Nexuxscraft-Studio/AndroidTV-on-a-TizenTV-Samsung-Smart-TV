#!/usr/bin/env bash
# Linux 6.6 ARM32 external-module build only; NEVER installs/loads the module.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s /absolute/path/to/prepared/linux-6.6-source\n' "$0" >&2
  exit 2
fi

kernel_root="$(realpath -- "$1")"
module_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/kernel" && pwd)"

if [[ ! -f "${kernel_root}/Makefile" || ! -f "${kernel_root}/include/generated/autoconf.h" ]]; then
  printf 'A configured Linux 6.6 kernel source/build tree is required: %s\n' "$kernel_root" >&2
  exit 2
fi

kernel_version="$(make -s -C "$kernel_root" kernelversion)"
if [[ ! "$kernel_version" =~ ^6\.6(\.|$) ]]; then
  printf 'Refusing non-6.6 kernel: %s\n' "$kernel_version" >&2
  exit 2
fi

cross_prefix="${CROSS_COMPILE:-arm-linux-gnueabihf-}"
if ! command -v "${cross_prefix}gcc" >/dev/null 2>&1; then
  printf 'ARM32 cross-compiler not found: %sgcc\n' "$cross_prefix" >&2
  exit 2
fi

printf 'ARM32 compile-only: Linux %s, prefix %s\n' "$kernel_version" "$cross_prefix"
make -C "$kernel_root" M="$module_root" ARCH=arm CROSS_COMPILE="$cross_prefix" modules
printf 'Build completed. Never insmod/modprobe this experimental module.\n'
