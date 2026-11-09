#!/usr/bin/env python3
"""Build 019: fail-closed audit of guest-reported Android kernel primitives.

This intentionally does not execute Android, access a TV, use the network,
inspect host hardware, or authorize flashing. A QEMU boot only tests a virtual
ARM guest and cannot establish Samsung HAL or Android userspace compatibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


MAX_LOG_BYTES = 8 * 1024 * 1024
KERNEL_BANNER = re.compile(rb"Linux version 4\.1\.10(?:\S*)?\s")
BEGIN = b"Q60T_ANDROID_PROBE_BEGIN version=019 host_only=1 no_flash=1"
END = b"Q60T_ANDROID_PROBE_END version=019"
FEATURE_LINE = re.compile(
    rb"Q60T_ANDROID_PROBE_FEATURE name=([a-z0-9_]+) result=(pass|fail|unknown)"
)
FEATURES = (
    "devtmpfs", "procfs", "sysfs", "fork_wait", "futex", "epoll",
    "eventfd", "inotify", "binder", "hwbinder", "vndbinder",
    "ashmem", "ion", "cgroups", "selinux_enforcing",
)
# This is a *small* Linux ABI smoke test, never an Android CDD compliance gate.
STAGE1_REQUIRED = frozenset((
    "devtmpfs", "procfs", "sysfs", "fork_wait", "futex", "epoll",
    "eventfd", "inotify", "binder", "hwbinder", "vndbinder",
))
HARDWARE_GATES = (
    "actual_target_ram_device_tree", "reversible_device_boot",
    "gpu_egl_gralloc_hwc", "audio_hal", "video_codec_hal", "remote_input_hal",
    "hdmi_cec_hal", "android_drm_certification",
)
ANDROID_USERSPACE_GATES = (
    "android_init_and_property_service", "bionic_linker_and_runtime",
    "selinux_policy_enforcing", "servicemanager_hwservicemanager",
    "zygote_and_art", "vintf_device_manifest_and_hals",
    "surfaceflinger_and_hardware_composer",
    "android_platform_kernel_compatibility",
)


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def inspect_log(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Kein reguläres QEMU-Seriellprotokoll")
    with path.open("rb") as stream:
        raw = stream.read(MAX_LOG_BYTES + 1)
    truncated = len(raw) > MAX_LOG_BYTES
    # Normalization is for the parser only; the original log is never edited.
    data = raw[:MAX_LOG_BYTES].replace(b"\r", b"")
    lines = data.split(b"\n")
    banner = bool(KERNEL_BANNER.search(data))
    panic = b"Kernel panic" in data
    begin_count = 0
    end_count = 0
    in_probe = False
    marker_order_valid = True
    malformed = []
    features = {}
    duplicates = []
    for line in lines:
        if line == BEGIN:
            begin_count += 1
            if in_probe or end_count:
                marker_order_valid = False
            in_probe = True
        elif line == END:
            end_count += 1
            if not in_probe:
                marker_order_valid = False
            in_probe = False
        elif line.startswith(b"Q60T_ANDROID_PROBE_FEATURE"):
            if not in_probe:
                marker_order_valid = False
            match = FEATURE_LINE.fullmatch(line)
            if not match or match.group(1).decode("ascii") not in FEATURES:
                malformed.append(line[:160].decode("ascii", errors="replace"))
                continue
            name = match.group(1).decode("ascii")
            if name in features:
                duplicates.append(name)
            else:
                features[name] = match.group(2).decode("ascii")
    missing = sorted(set(FEATURES) - set(features))
    complete = (banner and not panic and not truncated and begin_count == 1
                and end_count == 1 and marker_order_valid and not malformed and not duplicates
                and not missing)
    stage1_ok = complete and all(features[name] == "pass" for name in STAGE1_REQUIRED)
    status = ("KERNEL_PANIC_OBSERVED" if panic else
              "TRUNCATED_LOG" if truncated else
              "INCOMPLETE_OR_INVALID_GUEST_PROBE" if not complete else
              "ARM32_KERNEL_ABI_SMOKE_PASS_REPORTED" if stage1_ok else
              "ARM32_KERNEL_ABI_SMOKE_INCOMPLETE")
    return {
        "status": status,
        "kernel_4_1_10_banner_seen": banner,
        "kernel_panic_seen": panic,
        "log_truncated_for_analysis": truncated,
        "begin_marker_count": begin_count,
        "end_marker_count": end_count,
        "marker_order_valid": marker_order_valid,
        "invalid_feature_lines": malformed[:10],
        "duplicate_feature_names": sorted(set(duplicates)),
        "missing_features": missing,
        "features_guest_reported": {key: features[key] for key in FEATURES if key in features},
        "stage1_kernel_abi_smoke_pass_reported": stage1_ok,
        "guest_code_attestation": False,
        "android_userspace_booted": False,
        "android_userspace_compatible": False,
        "hardware_compatibility_verified": False,
        "safe_to_flash": False,
    }


def create_report(log: Path) -> dict:
    result = inspect_log(log)
    return {
        "type": "q60t_android_userspace_preflight",
        "build": "019",
        "target_model": "GQ50Q60TGUXZG",
        "test_platform": "QEMU virt ARM32, not physical Samsung hardware",
        "source_log_name": log.name,
        "source_log_sha256": sha256(log),
        "kernel_abi_probe": result,
        "android_userspace_gates": {name: "unverified" for name in ANDROID_USERSPACE_GATES},
        "device_hardware_gates": {name: "unverified" for name in HARDWARE_GATES},
        "original_samsung_kernel_source_modified": False,
        "tv_accessed": False,
        "flash_authorized": False,
        "android_boot_ready": False,
        "conclusion": (
            "An independent ARM32 guest can report selected Linux kernel ABI "
            "features. This is not a Bionic/AOSP init boot, SELinux policy "
            "validation, hardware HAL validation or a safe device boot path."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 019: ARM32-QEMU-Android-ABI-Prüfung")
    parser.add_argument("--log", type=Path, required=True,
                        help="Serielles QEMU-Protokoll des Build-019-Gastprogramms")
    parser.add_argument("--output", type=Path, required=True,
                        help="Neuer JSON-Bericht (wird niemals überschrieben)")
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Bericht existiert bereits: niemals überschreiben")
        if not args.output.parent.is_dir() or args.output.parent.is_symlink():
            raise ValueError("Zielverzeichnis fehlt oder ist ein Symlink")
        if args.output.resolve() == args.log.resolve():
            raise ValueError("Bericht darf das Originalprotokoll nicht ersetzen")
        report = create_report(args.log)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except (OSError, ValueError) as error:
        print(f"Build-019-Prüfung fehlgeschlagen: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["kernel_abi_probe"]["stage1_kernel_abi_smoke_pass_reported"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
