#!/usr/bin/env python3
"""Non-extracting VDFS4 image survey: unverified readable string references only."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re


WINDOW = 4 * 1024 * 1024
OVERLAP = 512
MAX_REFERENCES = 2_000
MODULE_PATH = re.compile(
    rb"/(?:lib|usr/lib|usr/driver|mtd_exe)/"
    rb"[A-Za-z0-9_+./-]{1,230}\.(?:ko|so(?:\.[0-9]{1,3}){0,4})"
)
DEVICE_PATH = re.compile(rb"/dev/(?:mali0|dri/card[0-9]|snd/[A-Za-z0-9_-]{1,30})")


def scan_rootfs_strings(path: Path) -> dict:
    """Search a local binary stream; never execute/extract its contents."""
    if not path.is_file():
        raise ValueError("Rootfs image not found")
    if path.stat().st_size > 8 * 1024 ** 3:
        raise ValueError("Rootfs image exceeds 8 GiB scan limit")
    digest = hashlib.sha256()
    references: set[str] = set()
    device_hints: set[str] = set()
    carry = b""
    count = 0
    with path.open("rb") as f:
        header = f.read(32)
        f.seek(0)
        for block in iter(lambda: f.read(WINDOW), b""):
            count += len(block)
            digest.update(block)
            sample = carry + block
            for match in MODULE_PATH.finditer(sample):
                entry = match.group().decode("ascii")
                if ".." not in entry.split("/"):
                    references.add(entry)
                if len(references) >= MAX_REFERENCES:
                    break
            for match in DEVICE_PATH.finditer(sample):
                device_hints.add(match.group().decode("ascii"))
            carry = sample[-OVERLAP:]
    sorted_refs = sorted(references)
    return {
        "type": "vdfs_raw_ascii_reference_survey",
        "format_marker": header[:8].decode("ascii", "replace"),
        "bytes_scanned": count,
        "sha256": digest.hexdigest(),
        "path_reference_count": len(sorted_refs),
        "path_references": sorted_refs,
        "device_node_references": sorted(device_hints),
        "writes_to_tv": False,
        "warning": "Strings are UNVERIFIED references in raw bytes, NOT verified files, "
                   "working drivers or proven compatibility; VDFS data was not decoded.",
    }
