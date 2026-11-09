#!/usr/bin/env python3
"""Build 024: stage an *actual* LineageOS-built AArch64 first-stage /init.

Creates an independent QEMU-only test initramfs. This is not a full Android
boot image: first-stage mounts, partition layout, sepolicy and later init
stages require additional, real Android build artifacts and device porting.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import stat
import sys

from q60t_arm64_initramfs import validate_static_aarch64_elf
from q60t_arm64_kernel import inspect_config
from q60t_initramfs_lab import newc_entry
from q60t_lineage_arm64_source import inspect_checkout, limited_regular_bytes, source_lock


MAX_INIT = 64 * 1024 * 1024
REQUIRED_STAGE_ONE = (
    "CONFIG_BLK_DEV_INITRD", "CONFIG_DEVTMPFS", "CONFIG_PROC_FS",
    "CONFIG_SYSFS", "CONFIG_TMPFS", "CONFIG_SECURITY_SELINUX",
    "CONFIG_ANDROID_BINDER_IPC", "CONFIG_SECCOMP_FILTER",
)


def archive_from_init(elf: bytes) -> bytes:
    validate_static_aarch64_elf(elf)
    entries = [
        ("dev", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("proc", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("sys", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("tmp", stat.S_IFDIR | 0o1777, b"", 0, 0),
        ("first_stage_ramdisk", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("dev/console", stat.S_IFCHR | 0o600, b"", 5, 1),
        ("init", stat.S_IFREG | 0o755, elf, 0, 0),
    ]
    payload = bytearray()
    for ino, (name, mode, content, major, minor) in enumerate(entries, 1):
        payload.extend(newc_entry(name, mode, content, ino, major, minor))
    payload.extend(newc_entry("TRAILER!!!", 0, ino=len(entries) + 1))
    return gzip.compress(bytes(payload), compresslevel=9, mtime=0)


def stage(checkout: Path, first_stage_init: Path, kernel_config: Path,
          output: Path, report_output: Path) -> dict:
    lock = source_lock()
    verified = inspect_checkout(checkout, lock)
    if not verified["minimum_source_paths_present"]:
        raise ValueError("LineageOS-Quellcheckout ist unvollständig")
    if (not first_stage_init.resolve().is_relative_to((checkout / "out").resolve()) or
            first_stage_init.is_symlink()):
        raise ValueError("First-stage /init muss ein reguläres Build-Artefakt im LineageOS-out/ sein")
    elf = limited_regular_bytes(first_stage_init, MAX_INIT)
    validate_static_aarch64_elf(elf)
    config_blob = limited_regular_bytes(kernel_config, 4 * 1024 * 1024)
    config = inspect_config(config_blob.decode("ascii", errors="replace"))
    missing = [key for key in REQUIRED_STAGE_ONE if config["required"].get(key) != "y"]
    if missing:
        raise ValueError("ARM64-Kernel fehlt Android-First-Stage-Schalter: " + ", ".join(missing))
    for destination in (output, report_output):
        if (destination.exists() or destination.is_symlink() or
                not destination.parent.is_dir() or destination.parent.is_symlink()):
            raise ValueError("Initramfs- und Report-Ziel müssen neu sein")
    if output == report_output:
        raise ValueError("Initramfs und Report benötigen verschiedene Pfade")
    payload = archive_from_init(elf)
    report = {
        "type": "q60t_lineage21_arm64_first_stage_initramfs", "build": "024",
        "status": "REAL_SOURCE_BUILT_ARM64_INIT_STAGED_NOT_BOOTED",
        "lineage_branch": lock["branch"], "aosp_tag": lock["aosp_tag_observed"],
        "lineage_manifest_commit": lock["manifest_commit"],
        "lineage_manifest_blob_sha1": verified["manifest_blob_sha1"],
        "first_stage_elf_sha256": hashlib.sha256(elf).hexdigest(),
        "first_stage_elf_bytes": len(elf),
        "kernel_config_sha256": hashlib.sha256(config_blob).hexdigest(),
        "initramfs_sha256": hashlib.sha256(payload).hexdigest(),
        "initramfs_bytes": len(payload),
        "first_stage_android_init_executed": False,
        "second_stage_init_ready": False,
        "selinux_policy_loaded": False,
        "property_service_started": False,
        "qemu_only": True,
        "samsung_tv_accessed": False,
        "safe_to_flash": False,
    }
    with output.open("xb") as stream:
        stream.write(payload)
    with report_output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 024: echter LineageOS-ARM64-First-Stage-Init im QEMU-Initramfs")
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--first-stage-init", type=Path, required=True)
    parser.add_argument("--kernel-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = stage(args.checkout, args.first_stage_init, args.kernel_config,
                       args.output, args.report_output)
    except (ValueError, OSError) as exc:
        print(f"Build-024-Initramfs-Staging fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
