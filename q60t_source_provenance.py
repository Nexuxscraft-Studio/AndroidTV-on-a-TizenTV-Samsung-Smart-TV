#!/usr/bin/env python3
"""Offline Samsung GPL-source *candidate* inventory.

Archives are inspected but never unpacked or executed. A matching SHA-256
does not establish that a Samsung package belongs to firmware 2743.0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
import tarfile
import zipfile

import q60t_kernel_build


MAX_ARCHIVE_ENTRIES = 200_000
MAX_ARCHIVE_BYTES = 8 * 1024 ** 3
MAX_UNPACKED_BYTES = 16 * 1024 ** 3
SOURCE_MARKERS = (
    "drivers/soc/sdp",
    "arch/arm/mach-sdp",
    "arch/arm/boot/dts",
    "drivers/gpu/arm",
)


def file_hash(path: Path) -> tuple[str, int]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Package must be a regular local file, not a symlink")
    size = path.stat().st_size
    if size > MAX_ARCHIVE_BYTES:
        raise ValueError("Source archive exceeds the inventory size limit")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest(), size


def safe_member(name: str) -> bool:
    # Archive paths must be safe on POSIX and Windows, even though this tool
    # intentionally never extracts them.
    if (not name or "\\" in name or "\x00" in name or name.startswith("/")
            or ":" in name):
        return False
    if re.match(r"^[A-Za-z]:", name):
        return False
    return all(part not in {"", ".", ".."} for part in name.rstrip("/").split("/"))


def archive_inventory(path: Path) -> dict:
    """Read archive *metadata* only; no extraction, linking or script execution."""
    digest, size = file_hash(path)
    issues: list[str] = []
    count = 0
    claimed_unpacked = 0
    candidate_names: list[str] = []
    seen: set[str] = set()

    def add(name: str, length: int, kind: str) -> None:
        nonlocal count, claimed_unpacked
        count += 1
        if count > MAX_ARCHIVE_ENTRIES:
            raise ValueError("Too many archive members")
        if length < 0:
            raise ValueError("Negative archive member size")
        claimed_unpacked += length
        if claimed_unpacked > MAX_UNPACKED_BYTES:
            raise ValueError("Archive declares excessive expanded size")
        normalized = name.rstrip("/")
        if not safe_member(name):
            issues.append("unsafe path: " + name[:180])
        elif normalized in seen:
            issues.append("duplicate path: " + name[:180])
        else:
            seen.add(normalized)
            if len(candidate_names) < 30 and any(m in normalized for m in SOURCE_MARKERS):
                candidate_names.append(normalized)
        if kind not in {"file", "dir"}:
            issues.append("unsupported member type: " + name[:180])

    if zipfile.is_zipfile(path):
        container = "zip"
        with zipfile.ZipFile(path, "r") as src:
            for member in src.infolist():
                ftype = (member.external_attr >> 16) & 0o170000
                if ftype not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    kind = "unsupported"
                else:
                    kind = "dir" if member.is_dir() else "file"
                add(member.filename, member.file_size, kind)
    elif tarfile.is_tarfile(path):
        container = "tar"
        with tarfile.open(path, "r:*") as src:
            for member in src:
                kind = "file" if member.isfile() else "dir" if member.isdir() else "link"
                add(member.name, member.size, kind)
    else:
        raise ValueError("Only ZIP and TAR source archives are supported")

    return {
        "sha256": digest,
        "bytes": size,
        "archive_format": container,
        "member_count": count,
        "claimed_expanded_bytes": claimed_unpacked,
        "archive_paths_safe_for_separate_review": not issues,
        "member_issues": issues[:50],
        "interesting_paths_sample": candidate_names,
        "archive_extracted": False,
    }


def source_fingerprint(source: Path) -> dict:
    """Hash a few bounded build inputs without treating them as provenance."""
    markers = ("Makefile", "arch/arm/Makefile", "arch/arm/boot/Makefile")
    found: dict[str, str] = {}
    for name in markers:
        p = source / name
        if p.is_file() and not p.is_symlink() and p.stat().st_size <= 2 * 1024 * 1024:
            found[name] = file_hash(p)[0]
    return {"kernel_version": q60t_kernel_build.source_version(source),
            "build_file_sha256": found,
            "samsung_marker_paths_present": [m for m in SOURCE_MARKERS if (source / m).exists()]}


def candidate_report(archive: Path | None, source: Path | None,
                     expected_sha256: str | None = None) -> dict:
    if expected_sha256 is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("Expected archive SHA-256 must have 64 hex characters")
    package = archive_inventory(archive) if archive else None
    source_data = source_fingerprint(source) if source else None
    hash_matches = package is not None and expected_sha256 is not None and (
        package["sha256"] == expected_sha256.lower())
    checks = {
        "local_archive_inspected": package is not None,
        "expected_archive_hash_supplied": expected_sha256 is not None,
        "archive_sha256_matches_supplied_hash": hash_matches,
        "archive_path_metadata_safe": bool(package and package["archive_paths_safe_for_separate_review"]),
        "local_source_tree_inspected": source_data is not None,
        "kernel_version_is_4_1_10": bool(source_data and source_data["kernel_version"] == "4.1.10"),
        "official_samsung_source_identity_independently_verified": False,
        "source_tree_matches_archive_contents": False,
        "source_matches_2743_0_binary": False,
    }
    ready_for_review = bool(
        package and package["archive_paths_safe_for_separate_review"]
        and hash_matches and source_data and source_data["kernel_version"] == "4.1.10")
    return {
        "type": "q60t_gpl_source_candidate_inventory",
        "status": "MANUAL_REVIEW_REQUIRED" if ready_for_review else "BLOCKED",
        "checks": checks, "archive": package, "source": source_data,
        "kernel_build_reproduced": False, "device_contacted": False,
        "flash_authorized": False,
        "note": "A local archive hash and a version match are NOT proof of the exact Samsung 2743.0 source. "
                "Samsung release identity, tree-to-archive correspondence and toolchain require independent review.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q60T GPL kernel-source candidate inventory; host-only")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--report", type=Path, help="new JSON file; never overwrite")
    args = parser.parse_args(argv)
    try:
        result = candidate_report(args.archive, args.source, args.expected_sha256)
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.report:
            with args.report.open("x", encoding="utf-8") as file:
                file.write(output)
        else:
            print(output, end="")
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        print(f"GPL-Quellenprüfung fehlgeschlagen: {error}", file=sys.stderr)
        return 2
    return 1  # Not a validated Samsung source package.


if __name__ == "__main__":
    raise SystemExit(main())
