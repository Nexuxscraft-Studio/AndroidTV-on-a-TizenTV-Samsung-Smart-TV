#!/usr/bin/env python3
"""Build 023: isolated, reproducible Linux 6.6.162 ARM64 QEMU-virt kernel build.

Accepts an already downloaded/extracted *official* source tree. Source
signature verification is a manual precondition, not silently asserted here.
No edits to Samsung trees, source checkout or existing build output.
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


VERSION = (6, 6, 162)
MIN_IMAGE_BYTES = 256 * 1024
MAX_IMAGE_BYTES = 256 * 1024 * 1024

# CONFIG_ANDROID_BINDERFS may be optional because the classic binder devices
# are exposed through CONFIG_ANDROID_BINDER_DEVICES.
REQUESTED_BUILTINS = (
    "BLK_DEV_INITRD", "RD_GZIP", "DEVTMPFS", "DEVTMPFS_MOUNT", "PROC_FS",
    "SYSFS", "TMPFS", "BINFMT_ELF", "SERIAL_AMBA_PL011",
    "SERIAL_AMBA_PL011_CONSOLE", "ANDROID_BINDER_IPC",
    # Linux 6.6 security/selinux/Kconfig: SECURITY_NETWORK && AUDIT && NET && INET.
    "SECURITY", "SECURITY_NETWORK", "AUDIT", "NET", "INET", "SECURITY_SELINUX",
    "SECURITYFS", "CGROUPS", "NAMESPACES", "SECCOMP", "SECCOMP_FILTER",
    "MEMFD_CREATE", "DMABUF_HEAPS", "DMABUF_HEAPS_SYSTEM",
)
OPTIONAL_BUILTINS = ("ANDROID_BINDERFS", "DMABUF_HEAPS_CMA")
BINDER_DEVICES = "binder,hwbinder,vndbinder"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def source_version(source: Path) -> tuple[int, int, int]:
    makefile = source / "Makefile"
    if not source.is_dir() or source.is_symlink() or not makefile.is_file() or makefile.is_symlink():
        raise ValueError("Kernel-Quellbaum oder Makefile fehlt")
    values = {}
    for line in makefile.read_text(encoding="utf-8", errors="replace").splitlines()[:60]:
        found = re.fullmatch(r"(VERSION|PATCHLEVEL|SUBLEVEL)\s*=\s*(\d+)\s*", line)
        if found:
            values[found.group(1)] = int(found.group(2))
    if len(values) != 3:
        raise ValueError("Kernel-Makefile hat keine gültige Versionskennung")
    return values["VERSION"], values["PATCHLEVEL"], values["SUBLEVEL"]


def add_selinux_lsm(config_content: str) -> str:
    """Enable the already compiled SELinux LSM in Linux 6.6's ordered LSM list."""
    match = re.search(r'^CONFIG_LSM="([^"]*)"    options = {}
    for line in content.splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            options[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            options[line[2:-11]] = "n"
    required = {f"CONFIG_{name}": options.get(f"CONFIG_{name}") for name in REQUESTED_BUILTINS}
    optional = {f"CONFIG_{name}": options.get(f"CONFIG_{name}") for name in OPTIONAL_BUILTINS}
    return {
        "required": required,
        "optional": optional,
        "selinux_lsm_selected": "selinux" in (options.get("CONFIG_LSM", "").strip('"').split(",")),
        "binder_device_names": options.get("CONFIG_ANDROID_BINDER_DEVICES"),
        "missing_required": [key for key, value in required.items() if value != "y"],
        "binder_device_names_match": options.get("CONFIG_ANDROID_BINDER_DEVICES") ==
                                      '"' + BINDER_DEVICES + '"',
    }


def build(source: Path, output: Path, *, cross_prefix: str = "aarch64-linux-gnu-",
          jobs: int = 2, timeout: int = 7200) -> dict:
    if source_version(source) != VERSION:
        raise ValueError(f"Exakt Linux {'.'.join(map(str, VERSION))} erforderlich")
    if jobs < 1 or jobs > 32 or timeout < 60 or timeout > 14400:
        raise ValueError("Ungültige Build-Limits")
    if (output.exists() or output.is_symlink() or not output.parent.is_dir() or
            output.parent.is_symlink() or output.resolve().is_relative_to(source.resolve()) or
            source.resolve().is_relative_to(output.resolve())):
        raise ValueError("Neues getrenntes Ausgabeverzeichnis erforderlich")
    make = shutil.which("make")
    compiler = shutil.which(cross_prefix + "gcc")
    config_tool = source / "scripts/config"
    if (not make or not compiler or not config_tool.is_file() or
            config_tool.is_symlink() or not (source / "arch/arm64/Makefile").is_file()):
        raise ValueError("Linux-6.6-Quellbaum oder AArch64-Cross-Build-Werkzeuge unvollständig")

    output.mkdir(mode=0o755)
    log = output / "build.log"
    base = [make, "ARCH=arm64", f"CROSS_COMPILE={cross_prefix}", f"O={output.resolve()}"]

    def logged(command: list[str], logfile) -> None:
        result = subprocess.run(command, cwd=source, stdout=logfile, stderr=subprocess.STDOUT,
                                timeout=timeout, check=False)
        if result.returncode:
            raise ValueError(f"Kernel-Build-Schritt fehlgeschlagen (Code {result.returncode}): {command[-1]}; siehe {log}")

    with log.open("x", encoding="utf-8") as logstream:
        logged(base + ["defconfig"], logstream)
        config = output / ".config"
        if not config.is_file():
            raise ValueError("ARM64-defconfig fehlt")
        for option in REQUESTED_BUILTINS + OPTIONAL_BUILTINS:
            logged([str(config_tool), "--file", str(config), "--enable", option], logstream)
        logged([str(config_tool), "--file", str(config), "--set-str",
                "ANDROID_BINDER_DEVICES", BINDER_DEVICES], logstream)
        lsm_order = add_selinux_lsm(config.read_text(encoding="utf-8"))
        logged([str(config_tool), "--file", str(config), "--set-str",
                "LSM", lsm_order], logstream)
        logged(base + ["olddefconfig"], logstream)
        validated = inspect_config(config.read_text(encoding="utf-8"))
        if (validated["missing_required"] or not validated["binder_device_names_match"]
                or not validated["selinux_lsm_selected"]):
            raise ValueError("Linux-Kconfig-Abhängigkeiten fehlen: " +
                             str(validated["missing_required"]) + "; Binder-Devices=" +
                             str(validated["binder_device_names"]) + "; SELinux LSM=" +
                             str(validated["selinux_lsm_selected"]))
        logged(base + [f"-j{jobs}", "Image"], logstream)

    image = output / "arch/arm64/boot/Image"
    if (not image.is_file() or image.is_symlink() or
            not MIN_IMAGE_BYTES < image.stat().st_size < MAX_IMAGE_BYTES):
        raise ValueError("AArch64-Image fehlt oder Größenprüfung fehlgeschlagen")
    return {
        "type": "q60t_linux66_arm64_virt_kernel_build", "build": "023",
        "status": "HOST_KERNEL_IMAGE_BUILT_NOT_BOOTED", "kernel_version": ".".join(map(str, VERSION)),
        "kernel_image": str(image), "kernel_image_sha256": sha256_file(image),
        "kernel_config_sha256": sha256_file(output / ".config"),
        "source_origin_signature_verified_by_script": False,
        "config": validated, "qemu_only": True,
        "samsung_hardware_compatible": False, "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 023: Linux 6.6.162 ARM64 für QEMU virt bauen")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cross-prefix", default="aarch64-linux-gnu-")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=7200)
    args = parser.parse_args(argv)
    try:
        report = build(args.source, args.output, cross_prefix=args.cross_prefix,
                       jobs=args.jobs, timeout=args.timeout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"Build-023-Kernel-Build abgebrochen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
, config_content, re.MULTILINE)
    if not match:
        raise ValueError("CONFIG_LSM fehlt in ARM64-defconfig")
    names = [part.strip() for part in match.group(1).split(",") if part.strip()]
    if "selinux" not in names:
        pos = names.index("bpf") if "bpf" in names else len(names)
        names.insert(pos, "selinux")
    return ",".join(names)


def inspect_config(content: str) -> dict:
    options = {}
    for line in content.splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            options[key] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            options[line[2:-11]] = "n"
    required = {f"CONFIG_{name}": options.get(f"CONFIG_{name}") for name in REQUESTED_BUILTINS}
    optional = {f"CONFIG_{name}": options.get(f"CONFIG_{name}") for name in OPTIONAL_BUILTINS}
    return {
        "required": required,
        "optional": optional,
        "binder_device_names": options.get("CONFIG_ANDROID_BINDER_DEVICES"),
        "missing_required": [key for key, value in required.items() if value != "y"],
        "binder_device_names_match": options.get("CONFIG_ANDROID_BINDER_DEVICES") ==
                                      '"' + BINDER_DEVICES + '"',
    }


def build(source: Path, output: Path, *, cross_prefix: str = "aarch64-linux-gnu-",
          jobs: int = 2, timeout: int = 7200) -> dict:
    if source_version(source) != VERSION:
        raise ValueError(f"Exakt Linux {'.'.join(map(str, VERSION))} erforderlich")
    if jobs < 1 or jobs > 32 or timeout < 60 or timeout > 14400:
        raise ValueError("Ungültige Build-Limits")
    if (output.exists() or output.is_symlink() or not output.parent.is_dir() or
            output.parent.is_symlink() or output.resolve().is_relative_to(source.resolve()) or
            source.resolve().is_relative_to(output.resolve())):
        raise ValueError("Neues getrenntes Ausgabeverzeichnis erforderlich")
    make = shutil.which("make")
    compiler = shutil.which(cross_prefix + "gcc")
    config_tool = source / "scripts/config"
    if (not make or not compiler or not config_tool.is_file() or
            config_tool.is_symlink() or not (source / "arch/arm64/Makefile").is_file()):
        raise ValueError("Linux-6.6-Quellbaum oder AArch64-Cross-Build-Werkzeuge unvollständig")

    output.mkdir(mode=0o755)
    log = output / "build.log"
    base = [make, "ARCH=arm64", f"CROSS_COMPILE={cross_prefix}", f"O={output.resolve()}"]

    def logged(command: list[str], logfile) -> None:
        result = subprocess.run(command, cwd=source, stdout=logfile, stderr=subprocess.STDOUT,
                                timeout=timeout, check=False)
        if result.returncode:
            raise ValueError(f"Kernel-Build-Schritt fehlgeschlagen (Code {result.returncode}): {command[-1]}; siehe {log}")

    with log.open("x", encoding="utf-8") as logstream:
        logged(base + ["defconfig"], logstream)
        config = output / ".config"
        if not config.is_file():
            raise ValueError("ARM64-defconfig fehlt")
        for option in REQUESTED_BUILTINS + OPTIONAL_BUILTINS:
            logged([str(config_tool), "--file", str(config), "--enable", option], logstream)
        logged([str(config_tool), "--file", str(config), "--set-str",
                "ANDROID_BINDER_DEVICES", BINDER_DEVICES], logstream)
        logged(base + ["olddefconfig"], logstream)
        validated = inspect_config(config.read_text(encoding="utf-8"))
        if validated["missing_required"] or not validated["binder_device_names_match"]:
            raise ValueError("Linux-Kconfig-Abhängigkeiten fehlen: " +
                             str(validated["missing_required"]) + "; Binder-Devices=" +
                             str(validated["binder_device_names"]))
        logged(base + [f"-j{jobs}", "Image"], logstream)

    image = output / "arch/arm64/boot/Image"
    if (not image.is_file() or image.is_symlink() or
            not MIN_IMAGE_BYTES < image.stat().st_size < MAX_IMAGE_BYTES):
        raise ValueError("AArch64-Image fehlt oder Größenprüfung fehlgeschlagen")
    return {
        "type": "q60t_linux66_arm64_virt_kernel_build", "build": "023",
        "status": "HOST_KERNEL_IMAGE_BUILT_NOT_BOOTED", "kernel_version": ".".join(map(str, VERSION)),
        "kernel_image": str(image), "kernel_image_sha256": sha256_file(image),
        "kernel_config_sha256": sha256_file(output / ".config"),
        "source_origin_signature_verified_by_script": False,
        "config": validated, "qemu_only": True,
        "samsung_hardware_compatible": False, "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 023: Linux 6.6.162 ARM64 für QEMU virt bauen")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cross-prefix", default="aarch64-linux-gnu-")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=7200)
    args = parser.parse_args(argv)
    try:
        report = build(args.source, args.output, cross_prefix=args.cross_prefix,
                       jobs=args.jobs, timeout=args.timeout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"Build-023-Kernel-Build abgebrochen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
