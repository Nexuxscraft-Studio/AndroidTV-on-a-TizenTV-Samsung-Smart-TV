#!/usr/bin/env python3
"""Host-only Samsung Q60T kernel build preparation (never installs/boots images).

The reference contains an ARM32 4.1.10 uImage built with Tizen/Linaro GCC
6.2.1. Do not treat an arbitrary upstream 4.1.10 kernel as Samsung's tree.
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


EXPECTED_VERSION = "4.1.10"
EXPECTED_GCC = "6.2.1"
REFERENCE_IMAGE_HASH = "6603f3f5082d6ef74471f9233ce17063658daf10e1d9440a8a9c75749a5e72b2"
EXPECTED_CONFIG_FLAGS = ("CONFIG_ARM=y", "CONFIG_AEABI=y")


def source_version(source: Path) -> str | None:
    makefile = source / "Makefile"
    if not source.is_dir() or source.is_symlink() or not makefile.is_file():
        return None
    if not (source / "arch/arm/Makefile").is_file():
        return None
    if makefile.stat().st_size > 128 * 1024:
        return None
    content = makefile.read_text(encoding="utf-8", errors="replace")
    numbers = {}
    for key in ("VERSION", "PATCHLEVEL", "SUBLEVEL"):
        match = re.search(rf"^{key}\s*[:?+]?=\s*(\d+)\s*$", content, re.M)
        if not match:
            return None
        numbers[key] = match.group(1)
    return ".".join(numbers[key] for key in ("VERSION", "PATCHLEVEL", "SUBLEVEL"))


def config_details(config: Path) -> dict | None:
    if not config.is_file() or config.is_symlink() or config.stat().st_size > 8 * 1024 * 1024:
        return None
    content = config.read_bytes()
    if b"\x00" in content:
        return None
    lines = content.decode("utf-8", errors="replace").splitlines()
    return {
        "sha256": hashlib.sha256(content).hexdigest(),
        "config_entry_count": sum(line.startswith("CONFIG_") for line in lines),
        "required_flags_present": all(flag in lines for flag in EXPECTED_CONFIG_FLAGS),
    }


def toolchain_details(prefix: str | None) -> dict | None:
    if not prefix:
        return None
    gcc = shutil.which(prefix + "gcc")
    if not gcc:
        return None
    try:
        output = subprocess.run([gcc, "--version"], capture_output=True,
                                text=True, timeout=10, check=True)
    except (subprocess.TimeoutExpired, OSError, subprocess.CalledProcessError):
        return None
    version_line = output.stdout.splitlines()[0][:180] if output.stdout else ""
    return {"compiler": gcc, "version_line": version_line,
            "reference_version_match": EXPECTED_GCC in version_line}


def make_plan(source: Path | None, config: Path | None,
              cross_prefix: str | None, output: Path | None,
              *, toolchain_override: dict | None = None) -> dict:
    version = source_version(source) if source else None
    config_info = config_details(config) if config else None
    compiler = toolchain_override if toolchain_override is not None else toolchain_details(cross_prefix)
    checks = {
        "samsung_gpl_source_available": version is not None,
        "source_version_matches_reference": version == EXPECTED_VERSION,
        "source_provenance_for_exact_2743_firmware": False,
        "kernel_config_available": config_info is not None,
        "kernel_config_basic_arm_flags": bool(config_info and config_info["required_flags_present"]),
        "matching_tizen_linaro_toolchain": bool(compiler and compiler.get("reference_version_match")),
        "output_path_provided": bool(output),
    }
    # Provenance requires manual verification of an actual Samsung OSSRC
    # package; version equality or a filename never proves source identity.
    build_commands = []
    if source and output and cross_prefix:
        base = ["make", "-C", str(source.absolute()), f"O={output.absolute()}",
                "ARCH=arm", f"CROSS_COMPILE={cross_prefix}"]
        build_commands = [base + ["olddefconfig"], base + ["-j2", "zImage"]]
    return {
        "type": "offline_kernel_build_preflight",
        "status": "BLOCKED" if not all(checks.values()) else "MANUAL_REVIEW_REQUIRED",
        "checks": checks,
        "source_version": version, "config": config_info, "toolchain": compiler,
        "reference_kernel": EXPECTED_VERSION,
        "reference_toolchain_version": EXPECTED_GCC,
        "reference_uimage_sha256": REFERENCE_IMAGE_HASH,
        "build_commands_not_executed": build_commands,
        "image_built": False, "install_or_flash_possible": False,
        "note": "No exact Samsung source/config or cross-toolchain supplied. Commands require manual package-provenance validation.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q60T host-only kernel build preparation")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--cross-compile", help="arm GNU toolchain prefix")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--report", type=Path, help="create new report; never overwrite")
    args = parser.parse_args(argv)
    try:
        report = make_plan(args.source, args.config, args.cross_compile, args.output_dir)
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.report:
            with args.report.open("x", encoding="utf-8") as handle:
                handle.write(payload)
        else:
            print(payload, end="")
    except (OSError, ValueError) as exc:
        print(f"Kernel-Prüfung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    # We do not execute a kernel build without provenance. This code only
    # produces reproducible, inspectable build prerequisites and commands.
    return 1 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
