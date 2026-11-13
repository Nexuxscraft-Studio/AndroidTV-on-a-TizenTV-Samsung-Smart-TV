#!/usr/bin/env python3
"""Build078: read-only footer/padding comparison for user-supplied Samsung files.

Describes observed bytes; DOES NOT perform RSA verification, decrypt,
modify firmware, contact a television, or authorize boot/flash.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

SUFFIX_LEN = 16
WINDOW_LEN = 256
TAIL_LEN = SUFFIX_LEN + WINDOW_LEN
SUFFIX = bytes([16]) * 16
MAX_FILE_BYTES = 16 * 1024 * 1024

# Owner-provided reference measurements, 2026-11-13. These are not signing keys.
EXPECTED = {
    "seret.bin": (3137552, "3c02a9c0f032590d76eafa3090beb3fb9293d5cf55d2401eaacb6e1f6f725255"),
    "uImage": (7041296, "29b4bdfe920a3af1854ab49f117279cf691c6a64256798a669f4c903415c86de"),
    "sign.bin": (1040, "5341e6b2646979a70e57653007a1f310169421ec9bdd9f1a5648f75ade005af1"),
    "secos.bin": (4186128, "add0b88cc5316ab7c5b0face5609c8eedeab52bbc2e94fbd0a7f5dee8c3e819b"),
    "ddr.init": (311312, "201171e79e6614c4b87f473dca4fe4f325c74b0f48ac5f92bdabdae5fd036a96"),
    "dtb.bin": (1564688, "b30b71478c50b502392eb6b7ad583129560997aaa547e4056973f22152008811"),
}


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    total = len(data)
    return -sum((n / total) * math.log2(n / total) for n in Counter(data).values())


def inspect_bytes(name: str, data: bytes, expected: tuple[int, str] | None = None) -> dict:
    if len(data) < TAIL_LEN:
        raise ValueError("Input too small for 272-byte end window")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Input exceeds 16 MiB bound")
    window = data[-TAIL_LEN:-SUFFIX_LEN]
    padding = data[-SUFFIX_LEN:]
    sha = hashlib.sha256(window).hexdigest()
    out = {
        "filename": name,
        "file_size_bytes": len(data),
        "window256_offset": f"0x{len(data) - TAIL_LEN:x}",
        "window256_sha256": sha,
        "window256_entropy_bits_per_byte": round(entropy(window), 4),
        "window256_zero_bytes": window.count(0),
        "window256_all_zero": not any(window),
        "terminal_16_bytes_equal_0x10": padding == SUFFIX,
        "matches_owner_reference_window_and_size": (
            len(data) == expected[0] and sha == expected[1] if expected else None
        ),
        "crypto_signature_verified": False,
    }
    if name == "uImage":
        valid_header = len(data) >= 64 and data[:4] == b"\x27\x05\x19\x56"
        declared_payload_end = (64 + struct.unpack_from(">I", data, 12)[0]) if valid_header else None
        out["legacy_uimage_header_detected"] = valid_header
        out["declared_payload_end"] = (
            f"0x{declared_payload_end:x}" if declared_payload_end is not None else None
        )
        out["272_byte_end_window_begins_at_declared_payload_end"] = (
            declared_payload_end == len(data) - TAIL_LEN
        )
    return out


def audit_directory(directory: Path) -> dict:
    if not directory.is_dir():
        raise ValueError("Components path is not a directory")
    components = []
    for name, expected in EXPECTED.items():
        path = directory / name
        if path.is_symlink() or not path.is_file():
            components.append({"filename": name, "status": "MISSING_OR_NOT_REGULAR_FILE"})
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            components.append({"filename": name, "status": "TOO_LARGE"})
            continue
        entry = inspect_bytes(name, path.read_bytes(), expected)
        entry["status"] = (
            "MATCHES_OWNER_MEASUREMENT" if
            entry["terminal_16_bytes_equal_0x10"]
            and entry["matches_owner_reference_window_and_size"]
            else "DIFFERS_FROM_OWNER_MEASUREMENT"
        )
        components.append(entry)
    all_match = all(x["status"] == "MATCHES_OWNER_MEASUREMENT" for x in components)
    return {
        "schema": "build078_reference_firmware_footer_audit_v1",
        "status": "SIX_COMPONENT_FOOTER_MATCH" if all_match else "INCOMPLETE_OR_DIFFERENT_REFERENCE",
        "components": components,
        "conclusions": {
            "identical_terminal_padding_is_consistent_with_unstripped_pkcs7": True,
            "synacktiv_decryptor_writes_cbc_plaintext_without_unpadding": True,
            "samygo_msddecrypt_truncates_the_padded_tail": True,
            "msd_metadata_has_oursa_validation_descriptor": True,
            "particular_window256_proven_to_be_an_rsa_signature": False,
            "tv_signature_verification_identified": False,
            "bootloader_accepts_modified_images": False,
            "safe_to_flash": False,
        },
        "note": "Findings concern offline files; decryption code does not validate signatures.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--components-dir", type=Path, required=True)
    p.add_argument("--strict", action="store_true", help="Exit 2 unless all six match")
    args = p.parse_args(argv)
    try:
        report = audit_directory(args.components_dir)
    except (OSError, ValueError, struct.error) as exc:
        print(f"Build078 error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 2 if args.strict and report["status"] != "SIX_COMPONENT_FOOTER_MATCH" else 0


if __name__ == "__main__":
    raise SystemExit(main())
