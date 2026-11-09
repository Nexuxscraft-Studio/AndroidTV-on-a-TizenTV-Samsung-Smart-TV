#!/usr/bin/env python3
"""Build 018: bounded, isolated QEMU boot probe for the staged ARM32 kernel.

Never contacts Samsung hardware, opens network access, or claims Binder/Android
runtime compatibility. The compiler probe must succeed first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys


EXPECTED_ARTIFACT = "output/arch/arm/boot/zImage"
REQUIRED_CONFIG = {
    "ARCH_SDP": "n",
    "ARCH_MULTIPLATFORM": "y",
    "ARCH_MULTI_V7": "y",
    "ARCH_VIRT": "y",
    "SERIAL_AMBA_PL011_CONSOLE": "y",
    "BLK_DEV_INITRD": "y",
    "ANDROID_BINDER_IPC": "y",
    "ANDROID_BINDER_IPC_32BIT": "n",
}
KERNEL_BANNER = re.compile(rb"Linux version 4\.1\.10(?:\S*)?\s")
MAX_LOG_INSPECTION = 8 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"CONFIG_([A-Z0-9_]+)=(.*)", line)
        if match:
            values[match.group(1)] = match.group(2)
        else:
            match = re.fullmatch(r"# CONFIG_([A-Z0-9_]+) is not set", line)
            if match:
                values[match.group(1)] = "n"
    return values


def validate_workspace(workspace: Path) -> Path:
    """Accept only a successful QEMU-profile compile with a matching artifact."""
    if not workspace.is_dir() or workspace.is_symlink():
        raise ValueError("Workspace fehlt oder ist ein Symlink")
    report_path = workspace / "compile-report.json"
    if (not report_path.is_file() or report_path.is_symlink()
            or report_path.stat().st_size > 1024 * 1024):
        raise ValueError("Kein regulärer Compile-Bericht vorhanden")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (report.get("profile") != "qemu-binder-lab"
            or report.get("status") != "HOST_KERNEL_COMPILED_NOT_BOOTABLE_VALIDATED"
            or report.get("resolved_config", {}).get("verified") is not True):
        raise ValueError("Nur ein erfolgreiches QEMU-Binder-Lab-Profil darf starten")
    info = report.get("artifact", {})
    if info.get("path_within_workspace") != EXPECTED_ARTIFACT:
        raise ValueError("Unerwarteter Kernel-Artefaktpfad")
    image = workspace / EXPECTED_ARTIFACT
    if (not image.is_file() or image.is_symlink()
            or not image.resolve().is_relative_to(workspace.resolve())):
        raise ValueError("Kernelimage fehlt, ist verlinkt oder liegt außerhalb des Workspace")
    if image.stat().st_size != info.get("size_bytes") or sha256(image) != info.get("sha256"):
        raise ValueError("Kernelimage stimmt nicht mehr mit dem Compile-Bericht überein")
    config_path = workspace / "output/.config"
    if not config_path.is_file() or config_path.is_symlink():
        raise ValueError("Kconfig des QEMU-Builds fehlt")
    symbols = _read_config(config_path)
    mismatches = [name for name, value in REQUIRED_CONFIG.items()
                  if symbols.get(name, "n") != value]
    if mismatches:
        raise ValueError("QEMU-/Binder-Kconfig unvollständig: " + ", ".join(mismatches))
    return image


def qemu_command(binary: str, image: Path, initrd: Path | None) -> list[str]:
    """No disks, network, user-controlled kernel arguments or host passthrough."""
    args = [binary, "-machine", "virt,highmem=off", "-cpu", "cortex-a15",
            "-m", "1024", "-smp", "1", "-accel", "tcg", "-nodefaults",
            "-kernel", str(image), "-append",
            "console=ttyAMA0,115200 earlyprintk loglevel=8 ignore_loglevel",
            "-display", "none", "-serial", "stdio", "-monitor", "none",
            "-nic", "none", "-no-reboot"]
    if initrd is not None:
        args.extend(["-initrd", str(initrd)])
    return args


def inspect_console(log: Path) -> dict:
    """A kernel banner is evidence of boot progress, never a Binder ABI pass."""
    with log.open("rb") as stream:
        contents = stream.read(MAX_LOG_INSPECTION + 1)
    truncated = len(contents) > MAX_LOG_INSPECTION
    contents = contents[:MAX_LOG_INSPECTION]
    kernel_seen = bool(KERNEL_BANNER.search(contents))
    panic_seen = b"Kernel panic" in contents
    init_seen = b"Run /init as init process" in contents or b"Freeing unused kernel memory" in contents
    if panic_seen:
        state = "KERNEL_PANIC_OBSERVED"
    elif init_seen and kernel_seen:
        state = "KERNEL_INIT_PROGRESS_OBSERVED"
    elif kernel_seen:
        state = "KERNEL_BANNER_OBSERVED"
    else:
        state = "NO_KERNEL_BOOT_EVIDENCE"
    return {
        "status": state,
        "kernel_4_1_10_banner_seen": kernel_seen,
        "init_progress_seen": init_seen,
        "kernel_panic_seen": panic_seen,
        "console_log_truncated_for_analysis": truncated,
        "binder_devices_checked_by_guest": False,
        "binder_transactions_executed": False,
        "android_userspace_compatible": False,
        "safe_to_flash": False,
    }


def run_probe(workspace: Path, initrd: Path | None, timeout: int,
              binary: str = "qemu-system-arm", dry_run: bool = False) -> dict:
    image = validate_workspace(workspace)
    if not 5 <= timeout <= 600:
        raise ValueError("QEMU-Timeout muss zwischen 5 und 600 Sekunden liegen")
    if initrd is not None and (not initrd.is_file() or initrd.is_symlink()):
        raise ValueError("Initrd fehlt oder ist ein Symlink")
    qemu = shutil.which(binary)
    if not qemu:
        raise ValueError("qemu-system-arm fehlt (Debian: apt install qemu-system-arm)")
    command = qemu_command(qemu, image, initrd)
    if dry_run:
        return {"status": "QEMU_COMMAND_VALIDATED_NOT_EXECUTED", "command": command,
                "tv_accessed": False, "binder_runtime_verified": False}

    log_path = workspace / "qemu-serial.log"
    report_path = workspace / "qemu-runtime-report.json"
    if log_path.exists() or log_path.is_symlink() or report_path.exists() or report_path.is_symlink():
        raise ValueError("QEMU-Protokoll/Bericht existiert bereits: niemals überschreiben")
    with log_path.open("xb") as logfile:
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                stdout=logfile, stderr=subprocess.STDOUT,
                                start_new_session=True)
        timed_out = False
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            code = 124
    findings = inspect_console(log_path)
    result = {
        "type": "q60t_qemu_virt_armv7_host_probe", "build": "018",
        "command": command, "qemu_exit_code": code,
        "qemu_timeout_reached": timed_out,
        "console_log": log_path.name,
        "console_sha256": sha256(log_path),
        "observation": findings,
        "tv_accessed": False, "network_enabled": False,
        "binder_runtime_verified": False, "flash_authorized": False,
    }
    with report_path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 018: isolierter QEMU-ARMv7-Bootversuch")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--initrd", type=Path,
                        help="optionale ARM32-initramfs (niemals Samsung-Firmware)")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_probe(args.workspace, args.initrd, args.timeout, dry_run=args.dry_run)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Build-018-QEMU-Prüfung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.dry_run:
        return 0
    return 0 if result["observation"]["kernel_4_1_10_banner_seen"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
