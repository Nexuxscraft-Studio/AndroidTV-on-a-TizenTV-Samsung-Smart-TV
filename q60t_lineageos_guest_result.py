#!/usr/bin/env python3
"""Build 024: correlate QEMU evidence for an attempted real Android /init.

The result intentionally distinguishes console text from a verified Android
process, SELinux policy, working property service or complete LineageOS boot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


MAX_LOG_BYTES = 16 * 1024 * 1024
MAX_JSON_BYTES = 128 * 1024
INIT_MARKER = b"init first stage started!"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect(log: bytes, qemu: dict, stage: dict, preflight_raw: bytes) -> dict:
    if len(log) > MAX_LOG_BYTES or len(preflight_raw) > MAX_JSON_BYTES:
        raise ValueError("Gastlog/Preflight zu groß")
    source = json.loads(preflight_raw)
    if not all(isinstance(value, dict) for value in (qemu, stage, source)):
        raise ValueError("QEMU-, Staging- und Preflight-Reports müssen JSON-Objekte sein")
    init_metadata = source.get("arm64_init_elf")
    if not isinstance(init_metadata, dict):
        init_metadata = {}
    integrity = bool(
        qemu.get("type") == "q60t_arm64_virt_qemu_run" and
        qemu.get("build") == "023" and
        qemu.get("qemu_only") is True and
        qemu.get("samsung_tv_accessed") is False and
        qemu.get("safe_to_flash") is False and
        qemu.get("log_sha256") == digest(log) and
        stage.get("type") == "q60t_build024_lineageos_arm64_initramfs_stage" and
        stage.get("build") == "024" and
        stage.get("safe_to_flash") is False and
        stage.get("archive_sha256") == qemu.get("initramfs_sha256") and
        stage.get("preflight_report_sha256") == digest(preflight_raw) and
        source.get("type") == "q60t_build024_lineageos_first_stage_init_preflight" and
        source.get("staging_ready") is True and
        init_metadata.get("sha256") == stage.get("init_elf_sha256")
    )
    kernel = bool(re.search(rb"Linux version 6\.6\.162(?:[\s-]|$)", log))
    marker_count = log.count(INIT_MARKER)
    panic = bool(re.search(rb"Kernel panic|Attempted to kill init|Fatal signal", log, re.I))
    first_stage_reported = integrity and kernel and marker_count == 1
    return {
        "type": "q60t_build024_lineageos_arm64_first_stage_guest_evidence",
        "build": "024",
        "status": ("ANDROID_FIRST_STAGE_LOG_MARKER_REPORTED_QEMU_ONLY" if first_stage_reported
                   else "QEMU_ANDROID_INIT_ATTEMPT_UNVERIFIED_OR_INCOMPLETE"),
        "kernel_6_6_162_banner_seen": kernel,
        "log_and_artifact_hash_chain_valid": integrity,
        "android_first_stage_log_marker_count": marker_count,
        "android_first_stage_init_log_reported": first_stage_reported,
        "kernel_panic_seen": panic,
        "android_init_executed_attested": False,
        "android_second_stage_init_verified": False,
        "android_property_service_verified": False,
        "android_selinux_policy_verified": False,
        "lineageos_origin_cryptographically_verified": False,
        "lineageos_booted": False,
        "samsung_hardware_compatible": False,
        "tv_accessed": False,
        "safe_to_flash": False,
    }


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("JSON-Metadaten fehlen, sind zu groß oder sind ein Symlink")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON-Metadaten sind kein Objekt")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 024: echte Android-init-Gastbelege vorsichtig auswerten")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--qemu-metadata", type=Path, required=True)
    parser.add_argument("--stage-report", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if (args.log.is_symlink() or not args.log.is_file() or
                args.log.stat().st_size > MAX_LOG_BYTES):
            raise ValueError("QEMU-Gastlog fehlt, ist zu groß oder ist ein Symlink")
        if (args.preflight.is_symlink() or not args.preflight.is_file() or
                args.preflight.stat().st_size > MAX_JSON_BYTES):
            raise ValueError("Preflight fehlt/ist zu groß")
        result = inspect(args.log.read_bytes(), read_json(args.qemu_metadata),
                         read_json(args.stage_report), args.preflight.read_bytes())
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
        print("Build-024-Gastbericht fehlgeschlagen: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
