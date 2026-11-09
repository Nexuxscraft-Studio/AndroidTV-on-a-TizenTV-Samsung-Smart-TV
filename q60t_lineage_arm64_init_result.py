#!/usr/bin/env python3
"""Build 024: correlate real LineageOS-first-stage initramfs and QEMU log.

Do not infer successful Android boot, SELinux setup, property service or HALs
from a first-stage init banner. Kernel panic remains a failure state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from q60t_lineage_arm64_source import source_lock


MAX_LOG = 16 * 1024 * 1024
MAX_REPORT = 128 * 1024


def inspect(log: bytes, qemu: dict, staged: dict) -> dict:
    if len(log) > MAX_LOG:
        raise ValueError("QEMU-Log ist zu groß")
    locked = source_lock()
    matching_archive = bool(
        staged.get("type") == "q60t_lineage21_arm64_first_stage_initramfs" and
        staged.get("lineage_branch") == locked["branch"] and
        staged.get("lineage_manifest_commit") == locked["manifest_commit"] and
        staged.get("lineage_manifest_blob_sha1") == locked["manifest_git_blob_sha1"] and
        staged.get("status") == "REAL_SOURCE_BUILT_ARM64_INIT_STAGED_NOT_BOOTED" and
        staged.get("safe_to_flash") is False and staged.get("qemu_only") is True and
        staged.get("initramfs_sha256") == qemu.get("initramfs_sha256")
    )
    matching_qemu = bool(qemu.get("type") == "q60t_arm64_virt_qemu_run" and
                         qemu.get("build") == "023" and qemu.get("qemu_only") is True and
                         qemu.get("safe_to_flash") is False and
                         qemu.get("log_sha256") == hashlib.sha256(log).hexdigest())
    kernel = bool(re.search(rb"Linux version 6\.6\.162(?:[\s-]|$)", log))
    # Android first-stage init messages are version- and build-dependent.
    # This pattern only recognizes the normal Android-14 first-stage banner.
    begin = len(re.findall(rb"\binit: init first stage started!", log)) == 1
    second = bool(re.search(rb"\binit: init second stage started!", log))
    policy = bool(re.search(rb"\binit:.*selinux_setup", log, re.I))
    property_hint = bool(re.search(rb"\binit:.*property service", log, re.I))
    services = {name: bool(re.search(
        rb"\binit:.*(?:starting service|start service).*['\"]?" + name.encode() + rb"\b", log, re.I))
                for name in ("ueventd", "logd", "servicemanager", "hwservicemanager")}
    panic = bool(re.search(rb"Kernel panic|Attempted to kill init|Fatal signal", log, re.I))
    linked = matching_qemu and matching_archive
    first_stage_reported = bool(linked and kernel and begin)
    return {
        "type": "q60t_lineage21_arm64_qemu_init_observation", "build": "024",
        "status": ("FIRST_STAGE_ANDROID_INIT_BANNER_REPORTED" if first_stage_reported else
                   "FIRST_STAGE_ANDROID_INIT_NOT_PROVEN"),
        "qemu_run_and_stage_hashes_match": linked,
        "linux6_6_162_banner_seen": kernel,
        "real_lineage21_first_stage_init_banner_reported": first_stage_reported,
        "kernel_panic_seen": panic,
        "first_stage_init_completed": False,
        "selinux_setup_log_hint_seen": policy,
        "selinux_android_policy_validated": False,
        "second_stage_init_log_hint_seen": second,
        "second_stage_init_proven": False,
        "property_service_log_hint_seen": property_hint,
        "property_service_proven": False,
        "service_start_log_hints_seen": services,
        "system_services_proven_running": False,
        "lineage_android_tv_booted": False,
        "samsung_tv_accessed": False,
        "safe_to_flash": False,
    }


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT:
        raise ValueError(f"JSON-Report fehlt/ist zu groß: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON-Report muss Objekt sein")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 024: echte Android-ARM64-Init-Logs aus QEMU prüfen")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--qemu-metadata", type=Path, required=True)
    parser.add_argument("--stage-report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.log.is_symlink() or not args.log.is_file() or args.log.stat().st_size > MAX_LOG:
            raise ValueError("QEMU-Log fehlt/ist zu groß")
        result = inspect(args.log.read_bytes(), read_json(args.qemu_metadata),
                         read_json(args.stage_report))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Build-024-Init-Auswertung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
