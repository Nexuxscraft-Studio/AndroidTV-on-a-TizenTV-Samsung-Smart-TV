#!/usr/bin/env python3
"""Build 023: bounded QEMU AArch64 virt smoke run, without devices/network.

The guest's PID1 intentionally remains alive. A timeout can therefore be an
expected process-control outcome, but not by itself a kernel boot success.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


MAX_LOG_BYTES = 16 * 1024 * 1024


def qemu_command(binary: str, image: Path, initrd: Path) -> list[str]:
    return [binary, "-machine", "virt", "-cpu", "cortex-a57", "-m", "2048",
            "-smp", "2", "-accel", "tcg", "-nodefaults", "-kernel", str(image),
            "-initrd", str(initrd),
            "-append", "console=ttyAMA0,115200 earlycon=pl011,0x09000000 loglevel=8 rdinit=/init",
            "-display", "none", "-serial", "stdio", "-monitor", "none",
            "-nic", "none", "-no-reboot"]


def run(image: Path, initrd: Path, directory: Path, *, run_id: str,
        timeout: int = 60, qemu_binary: str = "qemu-system-aarch64") -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,32}", run_id):
        raise ValueError("Unsichere Run-ID")
    if timeout < 10 or timeout > 180:
        raise ValueError("QEMU-Testzeit muss 10–180 Sekunden betragen")
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("QEMU-Protokollverzeichnis fehlt")
    for path in (image, initrd):
        if not path.is_file() or path.is_symlink() or path.stat().st_size < 100:
            raise ValueError("Kernel oder Initramfs fehlt/ist unsicher")
    with initrd.open("rb") as stream:
        signature = stream.read(2)
    if signature != b"\x1f\x8b":
        raise ValueError("ARM64-Initramfs muss gzip-komprimiertes newc-Archiv sein")
    binary = shutil.which(qemu_binary)
    if binary is None:
        raise ValueError("qemu-system-aarch64 nicht installiert")
    log = directory / f"qemu-serial-{run_id}.log"
    metadata = directory / f"qemu-meta-{run_id}.json"
    if log.exists() or log.is_symlink() or metadata.exists() or metadata.is_symlink():
        raise ValueError("Run-ID existiert bereits: Ausgaben werden nicht überschrieben")
    command = qemu_command(binary, image, initrd)
    code = None
    timed_out = False
    # Exclusive destination; the guest has no disk, NIC or attached target drive.
    with log.open("xb") as stream:
        try:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=timeout, check=False)
            code = result.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            code = 124  # Conventional timeout status; not a guest exit code.
    if log.stat().st_size > MAX_LOG_BYTES:
        raise ValueError("QEMU-Log über 16 MiB, keine automatische Erfolgsauswertung")
    blob = log.read_bytes()
    report = {
        "type": "q60t_arm64_virt_qemu_run", "build": "023",
        "status": "QEMU_EXECUTION_RECORDED_REQUIRES_GUEST_LOG_ANALYSIS",
        "command": command, "qemu_exit_code": code,
        "qemu_timeout_reached": timed_out, "log_file": str(log),
        "log_sha256": hashlib.sha256(blob).hexdigest(),
        "kernel_image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "initramfs_sha256": hashlib.sha256(initrd.read_bytes()).hexdigest(),
        "qemu_only": True, "android_userspace_booted": False,
        "samsung_tv_accessed": False, "safe_to_flash": False,
    }
    with metadata.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 023: Linux 6.6 ARM64 QEMU-virt-Test")
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--initrd", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args(argv)
    try:
        result = run(args.kernel, args.initrd, args.output_dir,
                     run_id=args.run_id, timeout=args.timeout)
    except (ValueError, OSError) as exc:
        print(f"Build-023-QEMU-Test fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
