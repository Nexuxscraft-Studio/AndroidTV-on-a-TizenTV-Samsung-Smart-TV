#!/usr/bin/env python3
"""Read-only host capacity check for the LineageOS 22.2 ARM32 ATV build.

No files are created or modified, and no network or TV access is performed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import shutil
import sys

GIB = 1024**3
MIN_RAM_GIB = 64
MIN_DISK_GIB = 400
TOOLS = ("git", "git-lfs", "repo")


def memory_gib(meminfo: str) -> float:
    """Return physical RAM from Linux MemTotal (reported in KiB)."""
    for line in meminfo.splitlines():
        key, sep, rest = line.partition(":")
        if sep and key == "MemTotal":
            tokens = rest.strip().split()
            if len(tokens) != 2 or tokens[1] != "kB":
                raise ValueError("Unexpected MemTotal unit")
            return int(tokens[0]) * 1024 / GIB
    raise ValueError("MemTotal is missing in /proc/meminfo")


def check_host(root: Path, ram_gib: float, free_gib: float,
               machine: str, tools: dict[str, bool],
               min_ram: int = MIN_RAM_GIB,
               min_disk: int = MIN_DISK_GIB) -> dict:
    checks = {
        "x86_64_build_host": machine.lower() in ("x86_64", "amd64"),
        "ram": ram_gib >= min_ram,
        "free_disk": free_gib >= min_disk,
        "tools_installed": all(tools.values()),
    }
    return {
        "target": "LineageOS 22.2 Android 15 / sdk_tv_arm (ARM32)",
        "build_directory": str(root),
        "machine": machine,
        "ram_gib": round(ram_gib, 2),
        "free_disk_gib": round(free_gib, 2),
        "minimum_ram_gib": min_ram,
        "minimum_free_disk_gib": min_disk,
        "tools": tools,
        "checks": checks,
        "ready": all(checks.values()),
        "note": "Host sizing only; no Android compile, Q60T boot or signature test.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build-dir", default=".", type=Path,
                   help="Existing target filesystem directory; read-only")
    p.add_argument("--json", action="store_true", help="Machine-readable output")
    args = p.parse_args(argv)
    root = args.build_dir.resolve(strict=False)
    if not root.is_dir():
        p.error("--build-dir must be an existing directory")
    try:
        ram = memory_gib(Path("/proc/meminfo").read_text(encoding="ascii"))
        free = shutil.disk_usage(root).free / GIB
    except (OSError, ValueError) as exc:
        p.error(f"Unable to inspect host: {exc}")
    installed = {name: shutil.which(name) is not None for name in TOOLS}
    report = check_host(root, ram, free, platform.machine(), installed)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Target: {report['target']}")
        print(f"Build filesystem: {root}")
        print(f"CPU architecture: {report['machine']}")
        print(f"RAM: {ram:.1f} GiB (recommended >= {MIN_RAM_GIB} GiB)")
        print(f"Free disk: {free:.1f} GiB (recommended >= {MIN_DISK_GIB} GiB)")
        for name, ok in report["checks"].items():
            print(f"  {'PASS' if ok else 'BLOCKED'}: {name}")
        for name, ok in installed.items():
            if not ok:
                print(f"  Missing tool: {name}")
        print("READY to attempt source sync" if report["ready"] else
              "NOT READY: address blocked checks before source sync")
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
