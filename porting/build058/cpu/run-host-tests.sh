#!/usr/bin/env bash
# Portable model verification on the development PC/server, no kernel load.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
test_dir="$(mktemp -d)"
trap 'rm -f -- "${test_dir}/test_nike_cpu_model"; rmdir -- "${test_dir}"' EXIT

cc -std=c11 -Wall -Wextra -Werror -pedantic \
  "${script_dir}/model/nike_cpu_model.c" \
  "${script_dir}/model/test_nike_cpu_model.c" \
  -o "${test_dir}/test_nike_cpu_model"
"${test_dir}/test_nike_cpu_model"
