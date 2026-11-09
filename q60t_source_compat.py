#!/usr/bin/env python3
"""Cross-check firmware DT compatible strings against Samsung source references.

Host-only research: a literal source match is NOT a working driver, an Android
HAL, or evidence that a modified kernel can boot on a signed Samsung TV.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import q60t_hardware
import q60t_kernel_build


MAX_FILES = 100_000
MAX_SOURCE_FILE = 4 * 1024 * 1024
MAX_SCAN_TOTAL = 1024 * 1024 * 1024
MAX_COMPATIBLES = 300
MAX_REFERENCES_PER_COMPATIBLE = 8
CODE_SUFFIXES = frozenset({".c", ".h", ".s", ".dts", ".dtsi", ".inc"})
SAFE_COMPAT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9,._+@/-]{1,119}$")
DEFAULT_REFERENCE_DTB_SHA256 = (
    "9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2"
)


def selected_compatibles(hardware: dict) -> dict[str, list[str]]:
    """Return bounded, deduplicated, non-sensitive DT compatible identifiers."""
    groups: dict[str, set[str]] = {}
    for tree in hardware.get("trees", [])[:8]:
        summary = tree.get("summary", {})
        group_map = {"board": [{"compatible": summary.get("root_compatible", [])}]}
        group_map.update(summary.get("hardware_categories", {}))
        for category, devices in group_map.items():
            if not isinstance(category, str) or not isinstance(devices, list):
                continue
            for device in devices[:100]:
                if not isinstance(device, dict):
                    continue
                for entry in device.get("compatible", [])[:16]:
                    if isinstance(entry, str) and SAFE_COMPAT.fullmatch(entry):
                        groups.setdefault(category, set()).add(entry)
    if sum(map(len, groups.values())) > MAX_COMPATIBLES:
        raise ValueError("Excessive compatible entries")
    return {key: sorted(value) for key, value in sorted(groups.items())}


def scan_source(root: Path, compatibles: set[str]) -> dict:
    """Bounded read-only scan; skip symlinks and binary/oversized files."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Source directory unavailable or a symlink")
    identifiers = sorted(compatibles)
    refs: dict[str, list[str]] = {name: [] for name in identifiers}
    if not identifiers:
        return {"matches": refs, "files_scanned": 0, "bytes_scanned": 0,
                "symlinks_skipped": 0, "oversize_skipped": 0}

    # Restrict both ends so "samsung,foo" does not match "samsung,foobar".
    matcher = re.compile(
        rb"(?<![A-Za-z0-9_,.+/-])(?:"
        + b"|".join(re.escape(name.encode("ascii")) for name in identifiers)
        + rb")(?![A-Za-z0-9_,.+/-])"
    )
    files_scanned = bytes_scanned = symlinks = oversize = files_seen = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        dirs[:] = sorted(d for d in dirs if not (base / d).is_symlink())
        for filename in sorted(files):
            path = base / filename
            files_seen += 1
            if files_seen > MAX_FILES:
                raise ValueError("Source scan exceeds file limit")
            if path.is_symlink():
                symlinks += 1
                continue
            if path.suffix.lower() not in CODE_SUFFIXES:
                continue
            try:
                size = path.stat().st_size
                if size > MAX_SOURCE_FILE:
                    oversize += 1
                    continue
                if bytes_scanned + size > MAX_SCAN_TOTAL:
                    raise ValueError("Source scan exceeds byte limit")
                contents = path.read_bytes()
            except OSError as exc:
                raise ValueError("Could not read source file") from exc
            files_scanned += 1
            bytes_scanned += len(contents)
            if b"\x00" in contents[:4096]:
                continue
            relative = path.relative_to(root).as_posix()
            for hit in set(matcher.findall(contents)):
                name = hit.decode("ascii")
                if len(refs[name]) < MAX_REFERENCES_PER_COMPATIBLE:
                    refs[name].append(relative)
    return {"matches": refs, "files_scanned": files_scanned,
            "bytes_scanned": bytes_scanned, "symlinks_skipped": symlinks,
            "oversize_skipped": oversize}


def _classification(kernel_paths: list[str], media_paths: list[str]) -> str:
    if any(p.endswith((".c", ".h", ".s", ".inc")) for p in kernel_paths):
        return "KERNEL_CODE_REFERENCE"
    if any(p.endswith((".c", ".h", ".s", ".inc")) for p in media_paths):
        return "MEDIA_CODE_REFERENCE"
    if kernel_paths or media_paths:
        return "DTS_DECLARATION_ONLY"
    return "NO_LITERAL_SOURCE_REFERENCE"


def comparison(hardware: dict, kernel_source: Path, media_source: Path) -> dict:
    groups = selected_compatibles(hardware)
    wanted = {name for values in groups.values() for name in values}
    kernel = scan_source(kernel_source, wanted)
    media = scan_source(media_source, wanted)
    matrix = {}
    counts: dict[str, int] = {}
    for category, names in groups.items():
        entries = []
        for name in names:
            k = kernel["matches"][name]
            m = media["matches"][name]
            classification = _classification(k, m)
            counts[classification] = counts.get(classification, 0) + 1
            entries.append({"compatible": name, "classification": classification,
                            "kernel_references": k, "media_references": m})
        matrix[category] = entries

    configs = kernel_source / "arch/arm/configs"
    config_names = sorted(p.name for p in configs.glob("Nike.*_defconfig")
                          if p.is_file() and not p.is_symlink()) if configs.is_dir() else []
    return {
        "type": "q60t_offline_compatible_source_matrix",
        "status": "ANALYSIS_ONLY",
        "model": "GQ50Q60TGUXZG (reference family, actual board not read)",
        "dtb_bundle_sha256": hardware.get("dtb_bundle_sha256"),
        "firmware_device_tree_count": hardware.get("device_trees_found"),
        "source_kernel_version": q60t_kernel_build.source_version(kernel_source),
        "nike_candidate_configs": config_names,
        "nike_l_named_config_present": any("Nike.L" in name for name in config_names),
        "compatibility_references": matrix,
        "classification_counts": counts,
        "source_scan": {"kernel": {k: v for k, v in kernel.items() if k != "matches"},
                        "media": {k: v for k, v in media.items() if k != "matches"}},
        "source_matches_firmware_2743_0": False,
        "android_hal_verified": False,
        "kernel_built": False,
        "boot_or_flash_attempted": False,
        "flash_authorized": False,
        "interpretation": "A compatible string found in source proves only a literal reference. "
                          "It does not prove driver binding, usable Android HAL, GPU/video "
                          "acceleration, exact kernel provenance, or a safe boot path.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q60T Nike-L DT/source comparison (read-only)")
    parser.add_argument("--dtb", type=Path, required=True)
    parser.add_argument("--kernel-source", type=Path, required=True)
    parser.add_argument("--media-source", type=Path, required=True)
    parser.add_argument("--expected-dtb-sha256", default=DEFAULT_REFERENCE_DTB_SHA256)
    parser.add_argument("--report", type=Path, help="new JSON report, never overwrite")
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", args.expected_dtb_sha256):
            raise ValueError("Invalid expected DTB SHA-256")
        if not args.dtb.is_file() or args.dtb.is_symlink():
            raise ValueError("DTB must be a regular local file")
        actual = hashlib.sha256(args.dtb.read_bytes()).hexdigest()
        if actual != args.expected_dtb_sha256.lower():
            raise ValueError("Reference DTB SHA-256 mismatch")
        hardware = q60t_hardware.hardware_report(args.dtb)
        if not hardware["device_trees_found"]:
            raise ValueError("No valid device trees")
        result = comparison(hardware, args.kernel_source, args.media_source)
        output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.report:
            with args.report.open("x", encoding="utf-8") as stream:
                stream.write(output)
        else:
            print(output, end="")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Source-Kompatibilitätsprüfung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
