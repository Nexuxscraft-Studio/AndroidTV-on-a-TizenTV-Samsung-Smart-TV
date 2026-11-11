#!/usr/bin/env bash
# Build 069 M3: read-only probe 3c - ashmem vs memfd selection in libcutils
# (system_server: "Failed to create ashmem", kernel 6.6 has no CONFIG_ASHMEM).
set -uo pipefail
L="${1:?los dir}"; cd "$L" || exit 1
sec() { printf '\n######## %s\n' "$*"; }
sec "libcutils ashmem-dev.cpp memfd decision"; grep -n -B2 -A40 '__has_memfd_support()' system/core/libcutils/ashmem-dev.cpp | head -120
sec "ApplicationSharedMemory jni"; f=$(grep -rl 'ApplicationSharedMemory_nativeCreate\|nativeCreate' frameworks/base/core/jni/*ApplicationSharedMemory* 2>/dev/null | head -1); echo "$f"; [ -n "$f" ] && grep -n -E 'ashmem|memfd' "$f" | head -20
sec "who sets sys.use_memfd"; grep -rn --include='*.mk' --include='*.rc' --include='*.prop' 'use_memfd' build device/google system/core 2>/dev/null | head
sec "sepolicy property context for sys.use_memfd"; grep -rn 'use_memfd' system/sepolicy 2>/dev/null | head
echo "(done)"
