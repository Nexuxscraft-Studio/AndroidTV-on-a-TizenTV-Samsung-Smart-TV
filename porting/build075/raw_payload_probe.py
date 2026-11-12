#!/usr/bin/env python3
"""Build075: read-only ARM32 raw payload preflight (no device access).

Reports file identity and evidence for ARM zImage magic at byte offset 0x24.
The uImage LOAD/ENTRY (0x80008000) is a declared address, not proof that
the first byte of this file will be mapped/executed there on the Samsung TV.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

KNOWN_PAYLOAD_SHA256 = "88cfa2ecb7e8f6b6507e6651b7569d3fd77c9cc0c1ea60c17fb48fa517c182d0"
EXPECTED_PAYLOAD_BYTES = 7_040_960
RAW_BASE = 0x80008000
ZIMAGE_MAGIC = 0x016F2818
MAX_BYTES = 128 * 1024 * 1024


def inspect_payload(path: Path, expected_sha256: str = KNOWN_PAYLOAD_SHA256) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("Expected SHA-256 must be 64 lowercase hexadecimal digits")
    if path.is_symlink() or not path.is_file():
        raise ValueError("Input must be a local regular non-symlink file")
    size = path.stat().st_size
    if size < 64 or size > MAX_BYTES:
        raise ValueError("Input size outside bounded raw-kernel inspection range")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        head = stream.read(64)
        digest.update(head)
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    sha = digest.hexdigest()
    if sha != expected_sha256:
        raise ValueError("Payload SHA-256 differs from the original REA inventory")
    magic_le, start_le, end_le = struct.unpack_from("<III", head, 0x24)
    has_zimage_magic = (magic_le == ZIMAGE_MAGIC)
    return {
        "schema": "build075_raw_arm32_preflight_v1",
        "status": "LOCAL_FILE_VERIFIED",
        "sha256": sha,
        "bytes": size,
        "original_rea_payload_size_matches": size == EXPECTED_PAYLOAD_BYTES,
        "declared_uimage_load_entry": f"0x{RAW_BASE:08x}",
        "ghidra_raw_import_base_assumption": f"0x{RAW_BASE:08x}",
        "arm_zimage_magic_at_0x24": has_zimage_magic,
        "raw_kernel_format": (
            "ARM_ZIMAGE_HEADER_CANDIDATE" if has_zimage_magic
            else "UNCLASSIFIED_RAW_BINARY"
        ),
        "zimage_start_header_word": f"0x{start_le:08x}" if has_zimage_magic else None,
        "zimage_end_header_word": f"0x{end_le:08x}" if has_zimage_magic else None,
        "zimage_decompression_required_for_full_kernel_analysis": (
            "LIKELY" if has_zimage_magic else "UNKNOWN"
        ),
        "hardware_mmio_accessed": False,
        "real_tv_execution_proven": False,
        "note": (
            "Ghidra raw import does not prove runtime addresses. "
            "ARM zImage header implies a decompressor front-end; do not treat "
            "compressed data as ARM instructions. Check header assumptions "
            "and compare against original Nike-L kernel sources."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--expected-sha256", default=KNOWN_PAYLOAD_SHA256)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = inspect_payload(args.payload, args.expected_sha256)
        rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            if args.output.exists() or args.output.is_symlink():
                raise ValueError("Output exists already, refusing overwrite")
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(rendered)
        else:
            print(rendered, end="")
    except (OSError, ValueError) as exc:
        print(f"Build075: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
