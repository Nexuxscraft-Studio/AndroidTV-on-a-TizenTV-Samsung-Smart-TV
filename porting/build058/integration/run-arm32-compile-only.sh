#!/usr/bin/env bash
# Build 058 offline integration: kernel objects only, never load/flash/boot.
# All kernel objects, vendor copies, and logs go into a NEW output directory.
set -euo pipefail

usage() {
  printf 'Usage: %s <linux-6.6.162-source> <original-tztv-media-nike.tgz> <NEW-output-dir>\n' "$0" >&2
  exit 2
}
[[ $# == 3 ]] || usage

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
project_root="$(cd -- "$script_dir/../../.." && pwd -P)"
kernel_src="$(realpath -e -- "$1")"
vendor_tgz="$(realpath -e -- "$2")"
output_arg="$3"

[[ -f "$kernel_src/Makefile" && -f "$kernel_src/drivers/gpu/drm/panfrost/Kconfig" ]] || {
  printf 'Refusing: Linux 6.6 source tree with Panfrost not found.\n' >&2; exit 2;
}
[[ -f "$vendor_tgz" && "$vendor_tgz" == *.tgz ]] || usage

if [[ -e "$output_arg" ]]; then
  printf 'Refusing to overwrite existing output directory: %s\n' "$output_arg" >&2
  exit 2
fi
output_parent="$(realpath -e -- "$(dirname -- "$output_arg")")"
output_dir="$output_parent/$(basename -- "$output_arg")"
[[ "$output_dir" != "$kernel_src" && "$output_dir" != "$project_root" ]] || usage

expected_vendor_sha="40c2a25eba331b8b04d8d81baf76061493f15f228a74893c7f825f7a1da724b6"
actual_vendor_sha="$(sha256sum -- "$vendor_tgz" | cut -d ' ' -f1)"
if [[ "$actual_vendor_sha" != "$expected_vendor_sha" ]]; then
  printf 'Refusing unpinned Samsung vendor archive (SHA256 mismatch).\n' >&2
  exit 2
fi

kernel_ver="$(make -s -C "$kernel_src" kernelversion)"
if [[ "$kernel_ver" != 6.6.162 ]]; then
  printf 'Refusing kernel %s; require Linux 6.6.162 exactly.\n' "$kernel_ver" >&2
  exit 2
fi

cross_prefix="${CROSS_COMPILE:-arm-linux-gnueabi-}"
jobs="${JOBS:-2}"
full_kernel_build="${BUILD058_FULL_KERNEL:-0}"
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { printf 'JOBS must be a positive integer\n' >&2; exit 2; }
[[ "$full_kernel_build" == 0 || "$full_kernel_build" == 1 ]] || {
  printf 'BUILD058_FULL_KERNEL must be 0 or 1\n' >&2; exit 2;
}
for tool in "${cross_prefix}gcc" "${cross_prefix}readelf" patch tar sha256sum make; do
  command -v "$tool" >/dev/null 2>&1 || {
    printf 'Missing required tool: %s\n' "$tool" >&2; exit 2;
  }
done

mkdir -- "$output_dir"
mkdir -- "$output_dir/logs" "$output_dir/kernel-obj" "$output_dir/staging"
summary="$output_dir/RESULTS.tsv"
printf 'step\tresult\texit_code\tlog\n' > "$summary"
printf 'Linux=%s\nARCH=arm\nCROSS_COMPILE=%s\nSamsung-TGZ-SHA256=%s\nFULL_KERNEL_BUILD=%s\n' \
  "$kernel_ver" "$cross_prefix" "$actual_vendor_sha" "$full_kernel_build" > "$output_dir/inputs.txt"

record_step() {
  local step="$1"; shift
  local log="$output_dir/logs/$step.log"
  if "$@" > "$log" 2>&1; then
    printf '%s\tPASS\t0\t%s\n' "$step" "$log" >> "$summary"
    return 0
  else
    local rc=$?
    printf '%s\tFAIL\t%d\t%s\n' "$step" "$rc" "$log" >> "$summary"
    printf '[%s] failed (%s). See %s\n' "$step" "$rc" "$log" >&2
    return 1
  fi
}

kernel_make() {
  make -C "$kernel_src" O="$output_dir/kernel-obj" ARCH=arm \
    CROSS_COMPILE="$cross_prefix" "$@"
}

check_arm_object() {
  local object="$1"
  [[ -s "$object" ]] || return 1
  "${cross_prefix}readelf" -h -- "$object" | grep -Eq 'Machine:[[:space:]]*ARM([[:space:]]|$)'
}

note_step() {
  printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4" >> "$summary"
}

# A modules_prepare tree has headers but *not* the exported symbol table needed
# to complete external modules' modpost. Compile individual .o targets first;
# only attempt the full .ko link when explicitly requested after a full build.
build_external_objects() {
  local label="$1" staged="$2" source object name
  for source in "$staged"/*.c; do
    name="$(basename "${source%.c}")"
    object="${source%.c}.o"
    record_step "${label}_${name}_compile" kernel_make -j"$jobs" M="$staged" "${name}.o" || true
    if check_arm_object "$object"; then
      note_step "${name}_elf" PASS 0 "ARM 32-bit ELF: $object"
      # Preserve legacy result keys used by previous Build 058 reports.
      note_step "${name}.o" PASS 0 "ARM 32-bit ELF: $object"
    else
      note_step "${name}_elf" FAIL 1 "Object missing/invalid: $object"
      note_step "${name}.o" FAIL 1 "Object missing/invalid: $object"
    fi
  done

  if [[ "$full_kernel_build" == 1 ]]; then
    if [[ -s "$output_dir/kernel-obj/Module.symvers" ]]; then
      record_step "${label}_modpost" kernel_make -j"$jobs" M="$staged" modules || true
    else
      note_step "${label}_modpost" BLOCKED_NO_SYMVERS 2 "$output_dir/kernel-obj/Module.symvers"
    fi
  else
    note_step "${label}_modpost" SKIPPED_OBJECT_ONLY 0 "Set BUILD058_FULL_KERNEL=1 for .ko testing"
  fi
}

printf 'Build058 Linux 6.6.162 ARM32 offline compilation; TV access forbidden.\n'

if ! record_step arm32_defconfig kernel_make multi_v7_defconfig; then exit 1; fi
kernel_config="$output_dir/kernel-obj/.config"
"$kernel_src/scripts/config" --file "$kernel_config" -e MODULES -e DRM -m DRM_PANFROST
if ! record_step arm32_olddefconfig kernel_make olddefconfig; then exit 1; fi

if ! grep -qx 'CONFIG_MODULES=y' "$kernel_config"; then
  printf 'kernel_modules_kconfig\tBLOCKED\t2\t%s\n' "$kernel_config" >> "$summary"
  printf 'Kconfig rejected CONFIG_MODULES=y, cannot compile external objects.\n' >&2
  exit 2
fi
if ! grep -qx 'CONFIG_DRM_PANFROST=m' "$kernel_config"; then
  printf 'panfrost_kconfig\tBLOCKED\t2\t%s\n' "$kernel_config" >> "$summary"
  printf 'Panfrost Kconfig rejected module mode: check ARM32 dependencies and !GENERIC_ATOMIC64.\n' >&2
  exit 2
fi
if ! record_step arm32_modules_prepare kernel_make -j"$jobs" modules_prepare; then exit 1; fi

if [[ "$full_kernel_build" == 1 ]]; then
  if ! record_step arm32_full_kernel_for_symvers kernel_make -j"$jobs" vmlinux; then
    note_step kernel_module_symvers BLOCKED_KERNEL_BUILD 1 "Full kernel failed; see arm32_full_kernel_for_symvers.log"
  fi
fi
if [[ -s "$output_dir/kernel-obj/Module.symvers" ]]; then
  note_step kernel_module_symvers PRESENT 0 "$output_dir/kernel-obj/Module.symvers"
else
  note_step kernel_module_symvers MISSING 0 "modules_prepare does not generate Module.symvers"
fi

# In-tree Panfrost driver. The composite object includes all source objects
# defined in drivers/gpu/drm/panfrost/Makefile; no dummy replacement.
if record_step panfrost_arm32 kernel_make -j"$jobs" drivers/gpu/drm/panfrost/panfrost.o || \
   record_step panfrost_arm32_directory kernel_make -j"$jobs" drivers/gpu/drm/panfrost/; then
  if ! check_arm_object "$output_dir/kernel-obj/drivers/gpu/drm/panfrost/panfrost.o"; then
    printf 'panfrost_elf\tFAIL\t1\tinvalid ARM ELF\n' >> "$summary"
  else
    printf 'panfrost_elf\tPASS\t0\tARM 32-bit ELF\n' >> "$summary"
  fi
fi

# Build the REAL disabled Build058 prototypes in isolated staged copies.
for component in gpu cpu; do
  staged="$output_dir/staging/${component}-build058"
  mkdir -- "$staged"
  if [[ "$component" == gpu ]]; then
    cp -- "$project_root/porting/build058/kernel/Makefile" "$staged/Makefile"
    cp -- "$project_root/porting/build058/kernel/sdp_nikel_gpu_clkrst.c" "$staged/"
  else
    cp -- "$project_root/porting/build058/cpu/kernel/Makefile" "$staged/Makefile"
    cp -- "$project_root"/porting/build058/cpu/kernel/*.c "$staged/"
  fi
  build_external_objects "${component}_prototype_arm32" "$staged"
done

# Build the modernized functions derived from real Samsung sdp_drm_util.c.
modern="$output_dir/staging/drm-utility-linux66"
mkdir -- "$modern"
cp -- "$script_dir"/drm/Makefile "$script_dir"/drm/*.c \
  "$script_dir"/drm/*.h "$modern/"
build_external_objects sdp_drm_helpers_arm32 "$modern"

# Attempt Samsung's ORIGINAL drm_drv/gem with existing Build053+054 patches.
# Expected proprietary-header/API failures must be kept as evidence, NOT
# hidden by invented compatibility stubs or an empty replacement module.
drm_root="$output_dir/staging/drm-samsung-ports"
mkdir -- "$drm_root"
if record_step original_drm_extract tar -xzf "$vendor_tgz" -C "$drm_root"; then
  patch1="$project_root/porting/build053/patches/0001-original-sdp-drm-gem-linux66-partial.patch"
  patch2="$project_root/porting/build054/patches/0003-after-build053-drm-headers-ioctl-flags.patch"
  if record_step samsung_drm_stage1 patch -d "$drm_root" --batch -p1 -i "$patch1" && \
     record_step samsung_drm_stage2 patch -d "$drm_root" --batch -p1 -i "$patch2"; then
    vendor_drm="$drm_root/tztv-media-nike/sdp_drm_nike"
    cp -- "$project_root/porting/build054/test-kbuild-arm32/Kbuild" "$vendor_drm/Kbuild"
    # Real Samsung Linux 4.1.10 header recovered from its GPL source archive;
    # local staging only, never copied into the caller's source tree.
    mkdir -p -- "$vendor_drm/build058-legacy-include/trace"
    cp -- "$script_dir/drm/legacy-include/trace/early.h" \
      "$vendor_drm/build058-legacy-include/trace/early.h"
    printf '\nccflags-y += -I$(src)/build058-legacy-include\n' >> "$vendor_drm/Kbuild"
    note_step samsung_trace_early_header FOUND 0 "GPL Samsung Linux 4.1.10 source; staged"
    # drm_tztv.h is NOT in either pinned Samsung source bundle. Do not create
    # guessed ioctl numbers, data structures, or empty proprietary ABI stubs.
    note_step samsung_drm_tztv_header BLOCKED_MISSING_ABI 2 \
      "drm/drm_tztv.h absent from published Samsung Linux/media archives"
    build_external_objects samsung_drm_drv_gem_arm32 "$vendor_drm"
  fi
fi

printf 'Finished. Inspect %s and individual log files.\n' "$summary"
printf 'This does NOT validate functionality, booting, clocks, DRM display, or TV safety.\n'

# Do not emit a misleading success exit code for missing real ARM objects.
# Both large Samsung DRM files are required for a full integration PASS;
# current vendor interfaces may still block them, yielding PARTIAL/FAIL.
required_objects=(
  panfrost_elf
  sdp_drm_util_elf sdp_drm_fence_elf
  sdp_nikel_gpu_clkrst.o sdp_nikel_cpu_clk.o
  sdp_nikel_cpufreq.o sdp_nikel_thermal.o
  sdp_drm_drv_elf sdp_drm_gem_elf
)
missing=0
for object in "${required_objects[@]}"; do
  if ! awk -F '\t' -v key="$object" \
    '$1 == key && $2 == "PASS" { found = 1 } END { exit !found }' "$summary"; then
    printf 'Still blocked: %s\n' "$object" >&2
    missing=1
  fi
done
if [[ "$missing" != 0 ]]; then
  printf 'PARTIAL / FAILED: not all required ARM32 source objects compiled.\n' >&2
  exit 1
fi
printf 'OBJECTS_COMPILED: all required ARM32 objects exist (hardware still unverified).\n'
