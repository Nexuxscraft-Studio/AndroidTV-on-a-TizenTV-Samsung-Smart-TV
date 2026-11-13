#!/usr/bin/env python3
"""Read-only evidence checker for an already extracted Samsung SERET reference.

Does NOT boot, extract, decrypt, sign, patch, upload, or access a television.
All reported addresses are offsets in a local copy of the original file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

EXPECTED_SHA256 = "c97ae1b4db73c2981b13fa9b7121930d77702e8705641225c3a1506064bec728"
EXPECTED_SIZE = 3_137_552
ZIMAGE_OFFSET = 0x8000
ZIMAGE_MAGIC = 0x016F2818
LITERAL_OFFSET = 0x7B0
PC_RELATIVE_ADD_OFFSET = 0x4F0
EXPECTED_APPENDED = 0x1A0CD8

# Literal data words: they are NOT ARM instructions.
EXPECTED_WORDS = {
    0x000000: 0xE1A0300F,  # mov r3, pc
    0x0006F8: 0xEB001E40,  # bl 0x8000, assuming file-offset 0 base
    0x008000: 0xE1A00000,  # ARM NOP (zImage entry)
    0x008024: ZIMAGE_MAGIC,
    0x008028: 0x00000000,
    0x00802C: 0x00198CD8,
    0x000958: 0xD00DFEED,  # FDT magic in the literal pool
    LITERAL_OFFSET: 0x001A07E0,
    EXPECTED_APPENDED: 0x00002020,
    EXPECTED_APPENDED + 4: 0x0017E010,
    EXPECTED_APPENDED + 8: 0x00006178,
}
EXPECTED_STRINGS = {
    0x24E0: b"/memory/reg\x00",
    0x24F6: b"/chosen/bootargs\x00",
}


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def audit_bytes(data: bytes, expected_sha256: str = EXPECTED_SHA256) -> dict:
    """Fail closed on changed input; never pretend unknown format data is proven."""
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise ValueError(f"SHA-256 mismatch: {digest}")
    if len(data) != EXPECTED_SIZE:
        raise ValueError(f"Unexpected reference size: {len(data)}")
    for offset, expected in EXPECTED_WORDS.items():
        value = read_u32(data, offset)
        if value != expected:
            raise ValueError(f"Header/literal mismatch at file offset 0x{offset:x}: 0x{value:08x}")
    for offset, expected in EXPECTED_STRINGS.items():
        if data[offset:offset + len(expected)] != expected:
            raise ValueError(f"String mismatch at file offset 0x{offset:x}")

    image_start = read_u32(data, ZIMAGE_OFFSET + 0x28)
    image_end = read_u32(data, ZIMAGE_OFFSET + 0x2C)
    if image_start != 0 or image_end <= image_start:
        raise ValueError("Unexpected embedded ARM zImage start/end fields")
    appended_offset = ZIMAGE_OFFSET + (image_end - image_start)

    # ARM A32 reads PC as current instruction address + 8.
    derived_pointer = PC_RELATIVE_ADD_OFFSET + 8 + read_u32(data, LITERAL_OFFSET)
    if derived_pointer != appended_offset or appended_offset != EXPECTED_APPENDED:
        raise ValueError("PC-relative pointer does not match zImage end offset")
    return {
        "schema": "q60t_build076_seret_static_evidence_v1",
        "status": "MATCHES_OWNER_SUPPLIED_STATIC_EVIDENCE",
        "seret_sha256": digest,
        "seret_size_bytes": len(data),
        "addresses_are": "file_offsets_not_physical_ram",
        "arm_wrapper_offset": "0x0",
        "embedded_arm_zimage_offset": f"0x{ZIMAGE_OFFSET:x}",
        "embedded_arm_zimage_magic_offset": f"0x{ZIMAGE_OFFSET + 0x24:x}",
        "embedded_zimage_start_word": f"0x{image_start:x}",
        "embedded_zimage_end_word": f"0x{image_end:x}",
        "appended_header_offset": f"0x{appended_offset:x}",
        "appended_header_word0": "0x2020",
        "appended_header_word1_uninterpreted": "0x17e010",
        "appended_header_word2_uninterpreted": "0x6178",
        "pc_relative_pointer_matches_appended_header": True,
        "trailing_data_size_bytes": len(data) - appended_offset,
        "fdt_magic_literal_found": True,
        "memory_reg_literal_found": True,
        "chosen_bootargs_literal_found": True,
        "touched_television": False,
        "performed_boot_test": False,
        "onboot_bootloader_recovered": False,
        "bootloader_signature_validation_known": False,
        "safe_to_flash": False,
        "notes": [
            "Word and string comparisons are static corroboration, not proof of live execution.",
            "Wrapper routine 0x354 conditionally edits /memory/reg; 0x3e0 edits boot arguments.",
            "An internal BL 0x8000 matches the embedded zImage entry, not a retail boot authorization.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seret", required=True, type=Path, help="Existing original seret.bin; read-only")
    args = parser.parse_args(argv)
    try:
        path: Path = args.seret
        if path.is_symlink() or not path.is_file():
            raise ValueError("Input must be a regular non-symlink file")
        if path.stat().st_size != EXPECTED_SIZE:
            raise ValueError("Input size differs from pinned reference")
        data = path.read_bytes()
        report = audit_bytes(data)
    except (OSError, ValueError, struct.error) as exc:
        print(f"Build076 evidence rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
