#!/usr/bin/env python3
"""Manually invoked LineageOS 22.2 ARM32 Android TV build gate.

This builds the upstream *emulator* product, never a Samsung image.  It does not
download source, manipulate partitions, flash devices, or relax BoardConfig.mk.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


# Deliberately static shell text.  The source directory is passed as a positional
# argument, never interpolated into shell commands.
BUILD_SH = r"""
set -eo pipefail
cd -- "$1"
source build/envsetup.sh
breakfast sdk_tv_arm eng
target_arch="$(get_build_var TARGET_ARCH)"
target_product="$(get_build_var TARGET_PRODUCT)"
target_variant="$(get_build_var TARGET_BUILD_VARIANT)"
printf 'TARGET_ARCH=%s\nTARGET_PRODUCT=%s\nTARGET_BUILD_VARIANT=%s\n' \
  "$target_arch" "$target_product" "$target_variant"
if [[ "$target_arch" != arm || "$target_product" != *sdk_tv_arm* || "$target_variant" != eng ]]; then
  echo 'FAIL CLOSED: unexpected LineageOS product or ABI' >&2
  exit 12
fi
if [[ "$2" == build ]]; then
  mka
else
  echo 'TARGET CHECK PASSED: no complete build requested'
fi
"""


def validate_source(root: Path) -> list[str]:
    """Return missing landmarks of an already synced LineageOS source tree."""
    expected = (
        ".repo",
        "build/envsetup.sh",
        "vendor/lineage/config",
    )
    return [name for name in expected if not (root / name).exists()]


def command(source: Path, mode: str) -> list[str]:
    if mode not in ("check", "build"):
        raise ValueError("mode must be check or build")
    return ["bash", "-c", BUILD_SH, "lineage-arm32-atv", str(source), mode]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path,
                   help="Already synced lineage-22.2 source tree (no repo sync)")
    p.add_argument("--mode", choices=("check", "build"), default="check")
    p.add_argument("--confirm-large-build", action="store_true",
                   help="Mandatory explicit consent for CPU/disk-intensive mka")
    args = p.parse_args(argv)
    root = args.source.resolve()
    if not root.is_dir():
        p.error("--source must be an existing directory")
    missing = validate_source(root)
    if missing:
        p.error("Not a complete pre-synced LineageOS tree; missing: " +
                ", ".join(missing))
    if args.mode == "build" and not args.confirm_large_build:
        p.error("Large Android build requires --confirm-large-build")
    print(f"Target: lineage-22.2 sdk_tv_arm-eng; mode={args.mode}", flush=True)
    try:
        result = subprocess.run(command(root, args.mode), cwd=root, check=False)
    except OSError as exc:
        print(f"Failed to start shell: {exc}", file=sys.stderr)
        return 2
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
