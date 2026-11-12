#!/usr/bin/env python3
"""Build074: sanitize offline REA evidence without exposing original firmware bytes.

This script never modifies the input. The caller must pass one verified local
firmware file under its dedicated evidence root; it never contacts the TV.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_INPUT_BYTES = 128 * 1024 * 1024
MAX_REPORT_BYTES = 24 * 1024 * 1024
UIMAGE_MAGIC = b"\x27\x05\x19\x56"
DTB_MAGIC = b"\xd0\x0d\xfe\xed"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def validated_source(source: Path, allowed_root: Path, kind: str) -> tuple[Path, int, str]:
    """Reject escapes/symlinks and verify a local, bounded, regular source."""
    root = allowed_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Evidence root is not a directory")
    candidate = source.absolute()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Evidence file must be beneath the allowed root") from exc
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("Symlinks in evidence path are forbidden")
    resolved = source.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("Evidence path escapes the allowed root")
    if not resolved.is_file():
        raise ValueError("Evidence source must be a regular file")
    size = resolved.stat().st_size
    if size < 64 or size > MAX_INPUT_BYTES:
        raise ValueError("Evidence file size is not within the accepted range")
    with resolved.open("rb") as fh:
        magic = fh.read(4)
    if magic != (UIMAGE_MAGIC if kind == "uimage" else DTB_MAGIC):
        raise ValueError("Unexpected magic for selected evidence type")
    digest = hashlib.file_digest(resolved.open("rb"), "sha256").hexdigest()
    return resolved, size, digest


def find_uimage_metadata(rea: dict) -> dict:
    """Require verified uImage data in REA's observed nested inventory."""
    normalized = rea.get("normalized_result")
    if not isinstance(normalized, dict):
        raise ValueError("REA result lacks normalized evidence")
    for substep in normalized.get("substeps", []):
        if substep.get("status") != "completed":
            continue
        evidence = substep.get("evidence") or {}
        manifest = (evidence.get("normalized_result") or {})
        for entry in manifest.get("occurrences", []):
            metadata = entry.get("format_metadata") or {}
            if metadata.get("kind") == "uimage":
                if metadata.get("crc_verified") is not True:
                    raise ValueError("uImage CRC verification did not succeed")
                return metadata
    raise ValueError("No successful verified uImage header in REA evidence")


def sanitized_report(rea: dict, kind: str, actual_sha: str, size: int) -> dict:
    subject = rea.get("subject") or {}
    sha = ((subject.get("digest") or {}).get("sha256") or "").lower()
    if not SHA256.fullmatch(sha) or sha != actual_sha:
        raise ValueError("REA source identity differs from SHA-256 of selected file")
    if rea.get("operation") != ("inspect_artifact" if kind == "uimage" else "inspect_devicetree"):
        raise ValueError("REA operation did not match requested analysis")
    normalized = rea.get("normalized_result")
    if not isinstance(normalized, dict):
        raise ValueError("REA returned no normalized result")
    result = {
        "schema": "q60t_build074_sanitized_v1",
        "type": kind,
        "input_sha256": actual_sha,
        "input_bytes": size,
        "status": "OFFLINE_ANALYZED",
        "tv_boot_tested": False,
        "bootloader_verified": False,
        "ram_boot_demonstrated": False,
        "firmware_modification": False,
        "raw_firmware_in_report": False,
        "interpretation": "Static container metadata only; NOT proof of target boot acceptance.",
    }
    if kind == "uimage":
        meta = find_uimage_metadata(rea)
        required = (
            "payload_size", "load_address", "entry_point",
            "header_crc32", "data_crc32", "timestamp",
        )
        for field in required:
            if type(meta.get(field)) is not int or meta[field] < 0:
                raise ValueError(f"Unusable uImage field: {field}")
        if meta.get("arch_name") != "arm" or meta.get("type_name") != "kernel":
            raise ValueError("Header does not describe an ARM kernel")
        extra = size - 64 - meta["payload_size"]
        if extra < 0:
            raise ValueError("uImage declares a payload extending beyond the file")
        result["uimage"] = {
            "header_size_bytes": 64,
            "kernel_header_name": meta.get("name") if re.fullmatch(r"Linux-[0-9.]{1,20}", str(meta.get("name"))) else None,
            "payload_size_bytes": meta["payload_size"],
            "extra_bytes_after_payload": extra,
            "extra_bytes_meaning": "UNKNOWN; no signature, padding or trailer type inferred",
            "load_address": f"0x{meta['load_address']:08x}",
            "entry_point": f"0x{meta['entry_point']:08x}",
            "header_crc32": f"0x{meta['header_crc32']:08x}",
            "data_crc32": f"0x{meta['data_crc32']:08x}",
            "crc_verified": True,
            "arch": "arm",
            "type": "kernel",
            "compression_name": meta.get("compression_name") if meta.get("compression_name") in (
                "none", "gzip", "bzip2", "lzma", "lzo", "lz4", "zstd",
            ) else "other_or_unknown",
            "timestamp_unix": meta["timestamp"],
        }
    else:
        # DTBs can contain serials, MACs, tokens, URLs, and bootargs.
        # Do not copy any node, property or string into CI artifacts.
        result["devicetree"] = {
            "format_validated_by_REA": True,
            "node_properties_in_report": False,
            "note": "Inspect the full evidence locally; this report excludes DTB content.",
        }
    return result


def run_rea(executable: str, source: Path, kind: str) -> dict:
    command = (
        [executable, "inspect-artifact" if kind == "uimage" else "inspect-devicetree",
         str(source), "--json"]
    )
    try:
        result = subprocess.run(
            command, capture_output=True, timeout=180, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("REA failed to start or timed out (details kept local)") from exc
    if result.returncode != 0:
        # Intentionally suppress stdout/stderr: they may contain private firmware paths or content.
        raise ValueError(f"REA exited unsuccessfully ({result.returncode}); check local REA installation")
    if len(result.stdout) > MAX_REPORT_BYTES:
        raise ValueError("REA result exceeds the safe parsing budget")
    try:
        return json.loads(result.stdout)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("REA output is not a valid JSON report") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("uimage", "dtb"), required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--allowed-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rea", default="rea")
    args = parser.parse_args(argv)
    try:
        source, size, digest = validated_source(args.source, args.allowed_root, args.kind)
        evidence = run_rea(args.rea, source, args.kind)
        report = sanitized_report(evidence, args.kind, digest, size)
        if args.output.is_symlink() or args.output.exists():
            raise ValueError("Output already exists; refusing overwrite")
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(report, out, indent=2, ensure_ascii=True, sort_keys=True)
            out.write("\n")
        print("Build074: offline analysis complete; sanitized report created")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Build074: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
