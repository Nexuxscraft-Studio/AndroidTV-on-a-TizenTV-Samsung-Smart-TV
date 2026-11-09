#!/usr/bin/env python3
"""Build 025: bounded, read-only Samsung Nike-L to Linux 6.6 compatibility audit.

Consumes the existing firmware-vs-Samsung-source report (Build 011), and
optionally scans a *separate* Linux 6.6 source tree for literal DT compatible
references. A string match is NOT driver support; source-only analysis cannot
prove the 50-inch TV's board identity or permit flashing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


EXPECTED_REFERENCE_DTB = "9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2"
MAX_JSON = 4 * 1024 * 1024
MAX_XML = 2 * 1024 * 1024
MAX_FILES = 150_000
MAX_SOURCE_BYTES = 1024 * 1024 * 1024
MAX_ONE_SOURCE = 4 * 1024 * 1024
CODE_SUFFIXES = {".c", ".h", ".dts", ".dtsi"}

# Explicit device classes from the *reference* firmware's DTB. The Linux
# 6.6 scanner never assumes that an unrelated generic driver fits Nike-L.
TARGETS = (
    ("board", "samsung,sdp-nikel", "cpu_boot"),
    ("cpu", "arm,cortex-a57", "cpu_boot"),
    ("gpu", "arm,mali-midgard", "graphics"),
    ("display", "samsung,sdp-drm", "graphics"),
    ("display", "samsung,sdp1202-panel", "graphics"),
    ("display", "samsung,sdp-hdmi", "graphics"),
    ("display", "samsung,sdp-frc-l", "graphics"),
    ("video", "samsung,sdp-mfc", "media"),
    ("audio", "samsung,sdp-mc-audio", "audio"),
    ("input", "samsung,sdp-mc-irb", "input"),
    ("input", "samsung,sdp-mc-irs", "input"),
    ("input", "samsung,sdp-mc-cecif", "input"),
    ("storage", "samsung,sdp-mmc", "storage"),
)

HAL_NAMES = (
    "android.hardware.graphics.composer3",
    "android.hardware.graphics.allocator",
    "android.hardware.graphics.mapper",
    "android.hardware.audio.core",
    "android.hardware.media.c2",
    "android.hardware.tv.hdmi.cec",
    "android.hardware.tv.input",
    "android.hardware.light",
    "android.hardware.drm",
)

SAFETY_GATES = (
    "live_50inch_board_identity",
    "live_50inch_ram_and_dtb_variant",
    "actual_aarch64_boot_exception_level_and_psci",
    "bootloader_authentication_policy",
    "reversible_nonpersistent_test_boot",
    "known_good_stock_backup",
    "independent_recovery_entrypoint",
    "rollback_test_on_spare_board",
    "working_graphics_and_media_hals",
)


def load_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON:
        raise ValueError(f"Expected bounded JSON file: {path}")
    item = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(item, dict):
        raise ValueError("Report root must be an object")
    return item


def validate_legacy(report: dict) -> dict[tuple[str, str], dict]:
    if report.get("type") != "q60t_offline_compatible_source_matrix":
        raise ValueError("Require the Build-011 source compatibility report")
    if report.get("dtb_bundle_sha256") != EXPECTED_REFERENCE_DTB:
        raise ValueError("Reference firmware DTB hash mismatch")
    if report.get("source_kernel_version") != "4.1.10":
        raise ValueError("Expected Samsung 4.1.10 source inventory")
    if report.get("source_matches_firmware_2743_0") is not False:
        raise ValueError("Cannot treat generic Samsung source as exact firmware match")
    groups = report.get("compatibility_references")
    if not isinstance(groups, dict):
        raise ValueError("Missing compatible source matrix")
    found = {}
    for category, compatibles in groups.items():
        if not isinstance(category, str) or not isinstance(compatibles, list):
            raise ValueError("Malformed compatible source matrix")
        for item in compatibles:
            if not isinstance(item, dict) or not isinstance(item.get("compatible"), str):
                raise ValueError("Malformed compatible entry")
            if len(item.get("kernel_references", [])) > 100 or len(item.get("media_references", [])) > 100:
                raise ValueError("Unexpectedly large source reference list")
            found[(category, item["compatible"])] = item
    return found


def linux_version(root: Path) -> str:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Modern Linux source must be an existing directory, not a symlink")
    makefile = root / "Makefile"
    if makefile.is_symlink() or not makefile.is_file() or makefile.stat().st_size > 100_000:
        raise ValueError("Invalid kernel Makefile")
    content = makefile.read_text(encoding="utf-8", errors="replace")
    components = {}
    for name in ("VERSION", "PATCHLEVEL", "SUBLEVEL"):
        match = re.search(r"^" + name + r"\s*=\s*(\d+)\s*$", content, re.M)
        if not match:
            raise ValueError(f"Cannot identify Linux {name}")
        components[name] = int(match.group(1))
    if components["VERSION"] != 6 or components["PATCHLEVEL"] != 6:
        raise ValueError("Build 025 accepts Linux 6.6.x candidates only")
    return f"6.6.{components['SUBLEVEL']}"


def source_literals(root: Path, targets: set[str]) -> dict:
    """Search driver and ARM64-board source for bounded string references.

    This deliberately does not compile, run scripts, use external tools, or
    read .config/secrets. Matches may occur in disabled code or comments.
    """
    version = linux_version(root)
    matches = {name: {"code": [], "device_tree": []} for name in sorted(targets)}
    safe = [name for name in sorted(targets) if re.fullmatch(r"[A-Za-z0-9,._+-]+", name)]
    if len(safe) != len(targets):
        raise ValueError("Unsafe compatible identifier")
    matcher = re.compile(rb'(?<![A-Za-z0-9_,.+/-])(?:' + b'|'.join(re.escape(x.encode("ascii")) for x in safe) + rb')(?![A-Za-z0-9_,.+/-])')
    files_seen = bytes_seen = symlinks_skipped = oversized_skipped = 0
    # Do not scan all of arch/: a generic x86/ARM32 DTS hit would be
    # misleading evidence for a 64-bit Samsung board port.
    for relative in ("drivers", "arch/arm64", "sound", "include"):
        base = root / relative
        if not base.is_dir() or base.is_symlink():
            continue
        for directory, dirs, files in os.walk(base, followlinks=False):
            folder = Path(directory)
            dirs[:] = sorted(d for d in dirs if not (folder / d).is_symlink())
            for filename in sorted(files):
                path = folder / filename
                if path.is_symlink():
                    symlinks_skipped += 1
                    continue
                if path.suffix.lower() not in CODE_SUFFIXES:
                    continue
                files_seen += 1
                if files_seen > MAX_FILES:
                    raise ValueError("Too many Linux source files")
                size = path.stat().st_size
                if size > MAX_ONE_SOURCE:
                    oversized_skipped += 1
                    continue
                if bytes_seen + size > MAX_SOURCE_BYTES:
                    raise ValueError("Linux source scan byte limit exceeded")
                content = path.read_bytes()
                bytes_seen += len(content)
                if b"\x00" in content[:4096]:
                    continue
                category = "device_tree" if path.suffix.lower() in {".dts", ".dtsi"} else "code"
                rel = path.relative_to(root).as_posix()
                for found in set(matcher.findall(content)):
                    paths = matches[found.decode("ascii")][category]
                    if len(paths) < 6:
                        paths.append(rel)
    return {"kernel_version": version, "matches": matches,
            "files_scanned": files_seen, "bytes_scanned": bytes_seen,
            "symlinks_skipped": symlinks_skipped,
            "oversized_skipped": oversized_skipped}


def inspect_hal_manifest(path: Path | None) -> dict:
    if path is None:
        return {"status": "NO_DEVICE_MANIFEST_SUPPLIED", "declared": [],
                "missing_candidate_declarations": list(HAL_NAMES)}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_XML:
        raise ValueError("Invalid/big Android device manifest")
    # ElementTree does not fetch remote entities or run code. Block DTDs
    # explicitly to keep this a strictly static local XML inventory.
    raw = path.read_bytes()
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("DTD/entity declarations are not supported")
    root = ET.fromstring(raw)
    if root.tag != "manifest" or root.attrib.get("type") != "device":
        raise ValueError("Expected an Android VINTF device manifest")
    declared = set()
    for hal in root.findall("hal"):
        name = hal.findtext("name")
        if name in HAL_NAMES:
            declared.add(name)
    return {"status": "DEVICE_XML_DECLARATIONS_ONLY_NOT_IMPLEMENTATIONS",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "declared": sorted(declared),
            "missing_candidate_declarations": sorted(set(HAL_NAMES) - declared),
            "vintf_compatibility_verified": False, "services_running": False}


def build_report(legacy: dict, modern: dict | None, hal: dict) -> dict:
    found = validate_legacy(legacy)
    rows = []
    for category, compatible, subsystem in TARGETS:
        prior = found.get((category, compatible))
        prior_code = [] if prior is None else [p for p in prior.get("kernel_references", []) + prior.get("media_references", []) if p.endswith((".c", ".h"))]
        current = modern["matches"].get(compatible) if modern else None
        modern_code = current["code"] if current is not None else []
        modern_dts = current["device_tree"] if current is not None else []
        status = ("REFERENCE_NOT_IN_LEGACY_MATRIX" if prior is None else
                  "LINUX_6_6_NOT_SCANNED" if modern is None else
                  "MODERN_CODE_LITERAL_ONLY" if modern_code else
                  "MODERN_DTS_LITERAL_ONLY" if modern_dts else
                  "NO_MODERN_LITERAL_REFERENCE")
        rows.append({"subsystem": subsystem, "compatible": compatible,
                     "reference_legacy_category": category,
                     "reference_old_source_status": prior.get("classification") if prior else None,
                     "legacy_code_example_paths": prior_code[:4],
                     "modern_code_example_paths": modern_code,
                     "modern_dts_example_paths": modern_dts,
                     "source_reference_status": status,
                     "driver_binds_on_q60t_verified": False})
    return {
        "type": "q60t_build025_modern_kernel_gap_report", "build": "025",
        "status": "HARDWARE_BOOT_BLOCKED_HOST_ONLY",
        "target_model": "GQ50Q60TGUXZG",
        "reference_firmware_model": "GQ55Q60TGUXZG",
        "reference_firmware_family": "T-NKLDEUC 2743.0",
        "reference_dtb_bundle_sha256": EXPECTED_REFERENCE_DTB,
        "reference_cpu_hint": "4x arm,cortex-a57 (ARMv8-capable; 50-inch hardware not proven)",
        "reference_kernel": "ARM32 Linux 4.1.10 uImage",
        "modern_kernel": modern["kernel_version"] if modern else None,
        "modern_scan": {k: v for k, v in modern.items() if k != "matches"} if modern else None,
        "subsystem_rows": rows,
        "android_hal_manifest": hal,
        "unverified_safety_gates": list(SAFETY_GATES),
        "aarch64_hardware_boot_proven": False,
        "secure_boot_policy_proven": False,
        "nonpersistent_boot_proven": False,
        "recovery_proven": False,
        "flash_authorized": False,
        "device_accessed": False,
        "interpretation": "Code/DTS literals and a VINTF XML declaration do not prove kernel binding, "
                          "HAL implementation, ARM64 bootloader entry, display scanout, or recovery.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 025 Samsung Q60T read-only kernel/HAL gap analyzer")
    parser.add_argument("--legacy-report", required=True, type=Path,
                        help="Existing Build-011 source_compat report from Samsung firmware")
    parser.add_argument("--modern-source", type=Path, help="Optional Linux 6.6.x source tree")
    parser.add_argument("--device-manifest", type=Path, help="Optional, device-specific VINTF manifest.xml")
    parser.add_argument("--output", type=Path, help="Create new JSON output; refuses overwrite")
    args = parser.parse_args(argv)
    try:
        previous = load_json(args.legacy_report)
        validate_legacy(previous)
        modern = source_literals(args.modern_source, {compat for _, compat, _ in TARGETS}) if args.modern_source else None
        result = build_report(previous, modern, inspect_hal_manifest(args.device_manifest))
        data = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(data)
        else:
            print(data, end="")
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as exc:
        print(f"Build-025-Hardwareanalyse abgebrochen: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
