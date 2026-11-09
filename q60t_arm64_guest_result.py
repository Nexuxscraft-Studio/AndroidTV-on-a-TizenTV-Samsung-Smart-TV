#!/usr/bin/env python3
"""Build 023: strict reported QEMU AArch64 Binder/SELinux/DMA-BUF evidence.

Serial markers are *reported* evidence, never hardware or Android validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


MAX_BYTES = 16 * 1024 * 1024
BEGIN = b"Q60T_ARM64_GUEST_INIT_STARTED version=023 qemu_only=1 no_flash=1"
END = b"Q60T_ARM64_GUEST_PROBE_FINISHED version=023"


def inspect(log: bytes, metadata: dict | None = None) -> dict:
    if len(log) > MAX_BYTES:
        raise ValueError("QEMU-Log über 16 MiB")
    lines = [line.strip() for line in log.splitlines()]
    begin_count, end_count = lines.count(BEGIN), lines.count(END)
    started = begin_count == 1 and end_count == 1 and lines.index(BEGIN) < lines.index(END) if begin_count and end_count else False
    kernel = bool(re.search(rb"Linux version 6\.6\.162(?:[\s-]|$)", log))
    uname = bool(re.search(rb"Q60T_ARM64_UNAME machine=aarch64 release=6\.6\.162(?:[\s-]|$)", log))
    panic = bool(re.search(rb"Kernel panic|Attempted to kill init|Fatal signal", log, re.I))

    binder = {}
    for name in ("binder", "hwbinder", "vndbinder"):
        expression = (rb"^Q60T_ARM64_BINDER name=" + name.encode() +
                      rb" status=pass protocol=([1-9][0-9]?)$")
        matches = [int(m.group(1)) for line in lines if (m := re.fullmatch(expression, line))]
        binder[name] = {"passed_reported": len(matches) == 1,
                        "protocol": matches[0] if len(matches) == 1 else None}

    selinux = [line for line in lines if re.fullmatch(
        rb"Q60T_ARM64_SELINUX status=pass enforce=[01] policy_loaded=unverified", line)]
    memfd = lines.count(b"Q60T_ARM64_MEMFD status=pass bytes=4096") == 1
    dma_heap = lines.count(b"Q60T_ARM64_DMA_HEAP status=pass bytes=4096") == 1
    file_hash_match = bool(metadata and metadata.get("build") == "023" and
                           metadata.get("type") == "q60t_arm64_virt_qemu_run" and
                           metadata.get("log_sha256") == hashlib.sha256(log).hexdigest() and
                           metadata.get("qemu_only") is True and
                           metadata.get("samsung_tv_accessed") is False and
                           metadata.get("safe_to_flash") is False)

    reported_boot = bool(started and kernel and uname and not panic and file_hash_match)
    facilities = bool(reported_boot and all(entry["passed_reported"] for entry in binder.values())
                      and len(selinux) == 1 and memfd and dma_heap)
    return {
        "type": "q60t_arm64_qemu_guest_evidence", "build": "023",
        "status": "ARM64_QEMU_KERNEL_AND_FACILITIES_REPORTED" if facilities else
                  "ARM64_QEMU_TEST_PARTIAL_OR_UNVERIFIED",
        "kernel_6_6_162_banner_seen": kernel,
        "arm64_uname_seen": uname, "guest_probe_marker_order_valid": bool(started),
        "kernel_panic_seen": panic, "log_sha256_matches_qemu_metadata": file_hash_match,
        "binder": binder, "selinux_fs_enforce_read_reported": len(selinux) == 1,
        "selinux_android_policy_verified": False,
        "memfd_4k_reported": memfd, "dma_heap_4k_reported": dma_heap,
        "arm64_qemu_kernel_boot_reported": reported_boot,
        "arm64_android_kernel_facilities_reported": facilities,
        "android_init_executed": False, "lineageos_booted": False,
        "samsung_hardware_compatible": False, "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 023: QEMU-ARM64-Kernel-Testlog auswerten")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if (not args.log.is_file() or args.log.is_symlink() or
                args.log.stat().st_size > MAX_BYTES or not args.metadata.is_file() or
                args.metadata.is_symlink() or args.metadata.stat().st_size > 128 * 1024):
            raise ValueError("QEMU-Log oder Metadaten fehlen/zu groß")
        report = inspect(args.log.read_bytes(), json.loads(args.metadata.read_text(encoding="utf-8")))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Build-023-Logprüfung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
