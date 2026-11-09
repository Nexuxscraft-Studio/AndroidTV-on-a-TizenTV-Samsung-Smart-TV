#!/usr/bin/env python3
"""Build 024: stage a user-supplied real ARM64 Android /init for QEMU only.

Does not create a fake Android init, mount images, access devices or execute
the supplied binary on the host. Missing Android system partitions remain a
known blocker to a complete Android/LineageOS boot.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import stat
import sys

from q60t_initramfs_lab import newc_entry
from q60t_lineageos_preflight import inspect_static_arm64_init, sha256


MAX_REPORT_BYTES = 128 * 1024


def archive_init(elf: bytes) -> bytes:
    inspect_static_arm64_init(elf)
    entries = [
        ("dev", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("proc", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("sys", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("sys/fs", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("sys/fs/selinux", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("system", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("vendor", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("metadata", stat.S_IFDIR | 0o700, b"", 0, 0),
        ("mnt", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("first_stage_ramdisk", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("apex", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("tmp", stat.S_IFDIR | 0o1777, b"", 0, 0),
        ("dev/console", stat.S_IFCHR | 0o600, b"", 5, 1),
        ("init", stat.S_IFREG | 0o755, elf, 0, 0),
    ]
    output = bytearray()
    for ino, (name, mode, data, major, minor) in enumerate(entries, 1):
        output.extend(newc_entry(name, mode, data, ino, major, minor))
    output.extend(newc_entry("TRAILER!!!", 0, ino=len(entries) + 1))
    return gzip.compress(bytes(output), compresslevel=9, mtime=0)


def read_preflight(path: Path) -> tuple[dict, str]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError("Build-024-Preflight fehlt oder ist ungültig")
    raw = path.read_bytes()
    report = json.loads(raw.decode("utf-8"))
    if not isinstance(report, dict) or not isinstance(report.get("arm64_init_elf"), dict):
        raise ValueError("Preflight muss geprüfte ELF-Metadaten enthalten")
    if (report.get("build") != "024" or
            report.get("type") != "q60t_build024_lineageos_first_stage_init_preflight" or
            report.get("staging_ready") is not True or
            report.get("binary_provenance_cryptographically_verified") is not False or
            report.get("safe_to_flash") is not False):
        raise ValueError("Preflight nicht für isoliertes ARM64-QEMU-Staging freigegeben")
    return report, sha256(raw)


def stage(init_elf: Path, preflight_path: Path, output: Path, report_path: Path) -> dict:
    for target in (output, report_path):
        if (target.exists() or target.is_symlink() or not target.parent.is_dir() or
                target.parent.is_symlink()):
            raise ValueError("Neuer Ausgabepfad erforderlich; niemals überschreiben")
    if output == report_path:
        raise ValueError("Archiv- und Reportpfad dürfen nicht identisch sein")
    if init_elf.is_symlink() or not init_elf.is_file():
        raise ValueError("Android-init-Binärdatei fehlt oder ist ein Symlink")
    preflight, preflight_sha = read_preflight(preflight_path)
    blob = init_elf.read_bytes()
    elf_info = inspect_static_arm64_init(blob)
    if elf_info["sha256"] != preflight["arm64_init_elf"]["sha256"]:
        raise ValueError("Init-Binärdatei hat sich seit Preflight verändert")
    packed = archive_init(blob)
    record = {
        "type": "q60t_build024_lineageos_arm64_initramfs_stage", "build": "024",
        "status": "ANDROID_ARM64_INIT_STAGED_QEMU_ONLY_NOT_EXECUTED",
        "init_elf_sha256": elf_info["sha256"],
        "preflight_report_sha256": preflight_sha,
        "archive_sha256": sha256(packed), "archive_bytes": len(packed),
        "archive": str(output), "source_commit": preflight["source"]["commit"],
        "android_first_stage_init_executed": False,
        "lineageos_origin_cryptographically_verified": False,
        "android_booted": False, "lineageos_booted": False,
        "samsung_hardware_compatible": False, "tv_accessed": False, "safe_to_flash": False,
    }
    # All analysis completes before either file is created.
    with output.open("xb") as stream:
        stream.write(packed)
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 024: geprüfte ARM64-Android-init als QEMU-Ramdisk stage")
    parser.add_argument("--init-binary", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        record = stage(args.init_binary, args.preflight, args.output, args.report)
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError, KeyError) as exc:
        print("Build-024-Initramfs-Staging abgebrochen: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
