#!/usr/bin/env bash
# Use the same prebuilt LLVM as Build 070; never install system packages.
# Source this file so PATH is available to the calling build step.
set -euo pipefail
if ! command -v clang >/dev/null || ! command -v ld.lld >/dev/null; then
  ci_los_dir="${LOS_DIR:-/mnt/github-runner/lineage-22.2}"
  ci_clang_dir=""
  while IFS= read -r ci_candidate; do
    if [[ -x "$ci_candidate/clang" && -x "$ci_candidate/ld.lld" ]]; then
      ci_clang_dir="$ci_candidate"
    fi
  done < <(compgen -G "$ci_los_dir/prebuilts/clang/host/linux-x86/clang-r*/bin" | sort -V)
  [[ -n "$ci_clang_dir" ]] || { echo 'Missing clang/ld.lld and LineageOS prebuilt LLVM' >&2; return 1; }
  export PATH="$ci_clang_dir:$PATH"
fi
for ci_tool in clang ld.lld llvm-ar llvm-nm llvm-objcopy make gcc flex bison m4 bc python3; do
  command -v "$ci_tool" >/dev/null || { echo "Missing runner prerequisite: $ci_tool" >&2; return 1; }
done
clang --version | head -1
if [[ -n "${GITHUB_PATH:-}" ]]; then
  dirname "$(command -v clang)" >> "$GITHUB_PATH"
fi
