#!/usr/bin/env python3
"""BUILD112: offline, read-only ARM32 Samsung seret.bin handoff evidence.

File offsets are NOT physical/virtual runtime addresses. Candidate instructions
are not proof that the code is reachable or executed on the television.
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ZIMAGE_MAGIC = 0x016F2818
FDT_MAGIC = 0xD00DFEED
UIMAGE_MAGIC = 0x27051956


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def scan_magic(data, magic, endian, limit=64):
    needle = magic.to_bytes(4, endian)
    offsets = []
    pos = 0
    while len(offsets) < limit:
        hit = data.find(needle, pos)
        if hit < 0:
            break
        offsets.append(hex(hit))
        pos = hit + 1
    return offsets


def arm_branch_candidates(data, boundary, target):
    """Inspect aligned ARM B/BL immediate targets, with image base = 0 ONLY.

    The PC-relative displacement survives relocation, but an offset only maps
    to the file when the whole region is placed contiguously at runtime.
    """
    matches = []
    for off in range(0, min(boundary, len(data)) - 3, 4):
        instruction = struct.unpack_from("<I", data, off)[0]
        cond = instruction >> 28
        if cond == 0xF or (instruction & 0x0E000000) != 0x0A000000:
            continue
        displacement = (instruction & 0xFFFFFF) << 2
        if displacement & 0x2000000:
            displacement -= 0x4000000
        destination = off + 8 + displacement
        if destination == target:
            matches.append({
                "source_file_offset": hex(off),
                "target_file_offset_if_contiguous": hex(destination),
                "kind": "BL" if instruction & 0x01000000 else "B",
                "condition": hex(cond),
                "raw_instruction": f"{instruction:08x}"
            })
    return matches


def cmp_r2_zero_candidates(data, boundary):
    # ARM CMP r2,#0: cond | 0x03520000, potentially false positives in data.
    matches = []
    for off in range(0, min(boundary, len(data)) - 3, 4):
        inst = struct.unpack_from("<I", data, off)[0]
        if (inst & 0x0FFFFFFF) == 0x03520000 and (inst >> 28) != 0xF:
            matches.append({"file_offset": hex(off), "instruction": f"{inst:08x}"})
    return matches


def fdt_candidates(data, limit=64):
    results = []
    for offset_hex in scan_magic(data, FDT_MAGIC, "big", limit):
        offset = int(offset_hex, 16)
        if offset + 40 > len(data):
            continue
        total_size = struct.unpack_from(">I", data, offset + 4)[0]
        version = struct.unpack_from(">I", data, offset + 20)[0]
        results.append({
            "file_offset": offset_hex, "totalsize": total_size,
            "version": version,
            "bounds_valid": 40 <= total_size <= len(data) - offset
        })
    return results


def uimage_info(data):
    if len(data) < 64 or struct.unpack_from(">I", data, 0)[0] != UIMAGE_MAGIC:
        return {"format": "not_legacy_uimage"}
    size, load, entry, payload_crc = struct.unpack_from(">IIII", data, 12)
    return {
        "format": "legacy_uimage", "payload_size": size,
        "load_address": hex(load), "entry_address": hex(entry),
        "declared_payload_bounds_valid": size <= len(data) - 64,
        "payload_crc_header_value": hex(payload_crc)
    }


def analyze(seret, uimage=None, wrapper_bytes=0x8000):
    data = seret.read_bytes()
    boundary = min(wrapper_bytes, len(data))
    result = {
        "build": 112, "mode": "offline_read_only",
        "seret": {"name": seret.name, "size": len(data), "sha256": sha256(data)},
        "assumptions": [
            "Treat seret.bin as ARM32 little-endian for instruction candidates.",
            "ARM code may contain embedded data or execute from an unknown address.",
            "File offsets are not physical addresses; no runtime register values are inferred."
        ],
        "wrapper_scan_limit": hex(boundary),
        "embedded_zimage_magic_at_offset_plus_0x24":
            [hex(i) for i in range(max(0, len(data)-4-0x24))
             if i + 0x28 <= len(data) and
             struct.unpack_from("<I", data, i+0x24)[0] == ZIMAGE_MAGIC][:64],
        "fdt_candidates": fdt_candidates(data),
        "direct_arm_branch_to_wrapper_boundary_candidates":
            arm_branch_candidates(data, boundary, wrapper_bytes),
        "cmp_r2_immediate_zero_candidates": cmp_r2_zero_candidates(data, boundary),
        "string_evidence": {},
        "outstanding_questions": [
            "Which branch path is actually reachable at boot?",
            "Where is the runtime DTB pointer loaded into r2?",
            "What are the runtime load, decompression and reserved memory regions?",
            "Does the vendor verify a signature before kernel handoff?"
        ],
        "hardware_boot_authorized": False
    }
    for term in (b"bootargs", b"booti", b"/memory", b"mem=", b"chosen"):
        hits = []
        start = 0
        while len(hits) < 32:
            pos = data.find(term, start)
            if pos < 0:
                break
            hits.append(hex(pos))
            start = pos + 1
        result["string_evidence"][term.decode()] = hits
    if uimage:
        udata = uimage.read_bytes()
        result["stock_uimage"] = {
            "name": uimage.name, "sha256": sha256(udata),
            **uimage_info(udata)
        }
    return result


def self_test():
    data = bytearray(0x8100)
    # ARM B +0x7ff8 from offset 0 -> offset 0x8000
    struct.pack_into("<I", data, 0, 0xEA001FFE)
    struct.pack_into("<I", data, 4, 0xE3520000)
    struct.pack_into("<I", data, 0x8024, ZIMAGE_MAGIC)
    assert arm_branch_candidates(data, 0x8000, 0x8000)[0]["source_file_offset"] == "0x0"
    assert cmp_r2_zero_candidates(data, 0x8000)[0]["file_offset"] == "0x4"
    assert 0x8000 + 0x24 < len(data)
    assert uimage_info(b"x" * 64)["format"] == "not_legacy_uimage"
    print("BUILD112 self-test: PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seret", type=Path, help="Path to extracted stock seret.bin")
    parser.add_argument("--uimage", type=Path, help="Optional stock uImage")
    parser.add_argument("--output", type=Path, help="Write JSON report to path")
    parser.add_argument("--wrapper-bytes", type=lambda x: int(x, 0), default=0x8000)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.seret is None or not args.seret.is_file():
        parser.error("--seret must name an existing file")
    if args.uimage is not None and not args.uimage.is_file():
        parser.error("--uimage must name an existing file")
    if args.wrapper_bytes < 4:
        parser.error("--wrapper-bytes must be >= 4")
    result = analyze(args.seret, args.uimage, args.wrapper_bytes)
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
