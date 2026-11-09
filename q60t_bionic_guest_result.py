#!/usr/bin/env python3
"""Build 021: verify serial evidence of a real Bionic child process.

The static /init does NOT print Q60T_BIONIC_HELLO; only the dynamically
linked Bionic executable contains that string. This remains a guest report,
not proof of compatibility with the physical Samsung television.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


MAX_LOG_BYTES = 8 * 1024 * 1024
MARKERS = (
    "Q60T_GUEST_INIT_STARTED host_only=1 no_flash=1",
    "Q60T_BIONIC_EXEC_BEGIN version=021",
    "Q60T_BIONIC_HELLO version=020 host_only=1",
    "Q60T_BIONIC_EXEC_RESULT status=pass exit=0",
)


def inspect(raw: bytes) -> dict:
    if len(raw) > MAX_LOG_BYTES:
        raise ValueError("QEMU-Log zu lang/abgeschnitten")
    lines = raw.replace(b"\r", b"").decode("utf-8", errors="replace").splitlines()
    located = [lines.index(value) if lines.count(value) == 1 else -1 for value in MARKERS]
    kernel_seen = any("Linux version 4.1.10" in line for line in lines)
    panic_seen = any("Kernel panic" in line for line in lines)
    execve_failed = any("Q60T_BIONIC_EXECVE_FAILED" in line for line in lines)
    passed = (kernel_seen and not panic_seen and not execve_failed and
              -1 not in located and located == sorted(located) and
              not any("Q60T_BIONIC_EXEC_RESULT status=fail" in line for line in lines))
    return {
        "build": "021",
        "status": ("BIONIC_CHILD_EXIT_ZERO_GUEST_REPORTED" if passed else
                   "BIONIC_GUEST_EXECUTION_NOT_VERIFIED"),
        "kernel_4_1_10_banner_seen": kernel_seen,
        "kernel_panic_seen": panic_seen,
        "required_guest_marker_counts": {value: lines.count(value) for value in MARKERS},
        "guest_marker_order_valid": -1 not in located and located == sorted(located),
        "execve_error_reported": execve_failed,
        "arm32_bionic_process_exit_zero_reported": passed,
        "android_init_booted": False,
        "android_userspace_compatible": False,
        "hardware_compatibility_verified": False,
        "tv_accessed": False,
        "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 021: echter Bionic-Child / QEMU-Serial-Beleg")
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if (not args.log.is_file() or args.log.is_symlink() or
                args.log.stat().st_size > MAX_LOG_BYTES):
            raise ValueError("Reguläres QEMU-Log fehlt/ist zu groß")
        report = inspect(args.log.read_bytes())
    except (ValueError, OSError) as exc:
        print(f"Build-021-Auswertung abgebrochen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["arm32_bionic_process_exit_zero_reported"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
