#!/usr/bin/env python3
"""Build077: read-only SERET ARM32 wrapper control-flow evidence.

All offsets are in an already-extracted original file. This does not model
physical RAM, authenticate Samsung boot images or execute code on a TV.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys

BASE_PATH = Path(__file__).resolve().parents[1] / "build076" / "seret_audit.py"
SPEC = importlib.util.spec_from_file_location("build076_seret_audit_for_077", BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Build076 audit module not found")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)

WRAPPER_START = 0x4B8
WRAPPER_STOP = 0x7AC  # 0x7ac and following are literal pool, not code
CALL_IMAGE_AT = 0x6F8
HEADER_REFERENCE_AT = 0x4E8
ADD_PC_AT = 0x4F0
LOAD_HEADER_AT = 0x534
MOVW_AT = 0x544
CMP_AT = 0x548

# Exact A32 instruction words recorded in owner-supplied objdump output.
# These are separate from the file-header evidence in Build076.
EXPECTED_INSTRUCTIONS = {
    HEADER_REFERENCE_AT: 0xE59F42C0,  # ldr r4, [pc, #704] => literal 0x7b0
    ADD_PC_AT: 0xE08F4004,           # add r4, pc, r4
    LOAD_HEADER_AT: 0xE5943000,      # ldr r3, [r4]
    MOVW_AT: 0xE3021020,             # movw r1, #0x2020
    CMP_AT: 0xE1530001,              # cmp r3, r1
    0x6EC: 0xE3A01000,               # mov r1, #0
    0x6F0: 0xE1A02004,               # mov r2, r4
    0x6F4: 0xE1A00001,               # mov r0, r1
    CALL_IMAGE_AT: 0xEB001E40,      # bl file-offset 0x8000
}

KNOWN_HELPERS = {
    0x00FC: "space-overwrite matching boot argument",
    0x0190: "append string helper",
    0x01CC: "append into padded boot-argument buffer",
    0x023C: "compact repeated spaces",
    0x02B8: "ASCII decimal parser",
    0x02EC: "substring search",
    0x0354: "conditional FDT /memory/reg property rewrite",
    0x03E0: "memory boot-argument rewriter",
    0x07D8: "endianness swap helper",
    0x0808: "FDT parser",
    0x095C: "byte-sequence comparison helper",
    0x09B0: "string length helper",
    0x09D8: "memory copy helper",
    0x0A04: "memory fill helper",
    0x8000: "embedded ARM zImage entry (internal call only)",
}


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def decode_arm_branch(word: int, file_offset: int) -> dict | None:
    """Decode A32 B/BL immediate, not BLX, BX, or arbitrary ARM opcodes."""
    condition = (word >> 28) & 0xF
    if condition == 0xF or ((word >> 25) & 0b111) != 0b101:
        return None
    imm24 = word & 0xFFFFFF
    if imm24 & 0x800000:
        imm24 -= 0x1000000
    target = file_offset + 8 + (imm24 << 2)
    is_link = bool(word & (1 << 24))
    return {
        "from": f"0x{file_offset:x}",
        "to": f"0x{target:x}" if target >= 0 else f"-0x{-target:x}",
        "kind": "BL" if is_link else "B",
        "condition": f"0x{condition:x}",
        "target_role": KNOWN_HELPERS.get(target, "not classified"),
    }


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    return round(-sum((n / len(data)) * math.log2(n / len(data)) for n in counts.values()), 4)


def analyze_bytes(data: bytes, expected_sha256: str = base.EXPECTED_SHA256) -> dict:
    # Build076 is mandatory: reject wrong bytes or reference identity.
    baseline = base.audit_bytes(data, expected_sha256=expected_sha256)
    for offset, expected in EXPECTED_INSTRUCTIONS.items():
        actual = u32(data, offset)
        if actual != expected:
            raise ValueError(
                f"A32 instruction mismatch at file offset 0x{offset:x}: "
                f"expected 0x{expected:08x}, observed 0x{actual:08x}"
            )

    # Verify the register/value path; do not confuse file offsets with TV RAM.
    literal_address = HEADER_REFERENCE_AT + 8 + (u32(data, HEADER_REFERENCE_AT) & 0xFFF)
    if literal_address != base.LITERAL_OFFSET:
        raise ValueError("LDR literal reference did not resolve to 0x7b0")
    pointer = ADD_PC_AT + 8 + u32(data, literal_address)
    if pointer != base.EXPECTED_APPENDED:
        raise ValueError("Header pointer is not aligned with appended block")
    word0 = u32(data, pointer)
    if word0 != 0x2020:
        raise ValueError("0x2020 dispatch header not present")

    branch_edges = [
        edge for offset in range(WRAPPER_START, WRAPPER_STOP, 4)
        if (edge := decode_arm_branch(u32(data, offset), offset)) is not None
    ]
    if not any(edge["from"] == "0x6f8" and edge["to"] == "0x8000"
               and edge["kind"] == "BL" for edge in branch_edges):
        raise ValueError("Embedded zImage entry call was not found")

    tail = data[pointer:]
    signatures = {
        "fdt_magic_be": bytes.fromhex("d00dfeed"),
        "zimage_magic_le": bytes.fromhex("18286f01"),
        "gzip": bytes.fromhex("1f8b08"),
        "xz": bytes.fromhex("fd377a585a00"),
    }
    markers = {name: {"count": tail.count(magic), "first_offset_in_tail":
                          (f"0x{tail.find(magic):x}" if magic in tail else None)}
               for name, magic in signatures.items()}
    sample = tail[12:12 + 65536]

    return {
        "schema": "build077_seret_deep_static_audit_v1",
        "status": "OFFLINE_STATIC_CONTROL_FLOW_CORROBORATED",
        "seret_sha256": baseline["seret_sha256"],
        "addresses": "file offsets ONLY, not mapped physical/virtual TV addresses",
        "main_wrapper_analysis_range": [f"0x{WRAPPER_START:x}", f"0x{WRAPPER_STOP:x}"],
        "known_a32_instruction_words_verified": len(EXPECTED_INSTRUCTIONS),
        "relative_literal_location": f"0x{literal_address:x}",
        "computed_header_pointer": f"0x{pointer:x}",
        "container_type_word": f"0x{word0:x}",
        "container_next_words_unknown": [
            f"0x{u32(data, pointer + 4):x}",
            f"0x{u32(data, pointer + 8):x}",
        ],
        "embedded_zimage_call_site": f"0x{CALL_IMAGE_AT:x}",
        "embedded_zimage_offset": "0x8000",
        "wrapper_lexical_branch_edges": branch_edges,
        "branch_edge_count": len(branch_edges),
        "trailing_data_length_bytes": len(tail),
        "first_64k_payload_entropy_bits_per_byte": shannon_entropy(sample),
        "trailer_standard_magic_search": markers,
        "limits": [
            "Linear ARM32 branch decoding is not a proof of dynamic reachability or execution order.",
            "No full instruction emulation, RAM map, signature validation or TV access was attempted.",
            "High entropy does not distinguish compression from encryption.",
            "The 0x2020 container semantics and its remaining header fields are unknown.",
            "No bootloader unlock or authorized alternate-kernel boot is demonstrated.",
        ],
        "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seret", required=True, type=Path,
                        help="Existing original reference seret.bin (read-only)")
    args = parser.parse_args(argv)
    try:
        path = args.seret
        if path.is_symlink() or not path.is_file():
            raise ValueError("Input must be a regular non-symlink file")
        if path.stat().st_size != base.EXPECTED_SIZE:
            raise ValueError("Unexpected input file size")
        report = analyze_bytes(path.read_bytes())
    except (OSError, ValueError, struct.error) as exc:
        print(f"Build077 rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
