#!/usr/bin/env python3
"""Build 022: classify real QEMU serial evidence without inventing a boot pass.

Positive messages in a serial log are *observations*, not provenance proof that
they came from genuine LineageOS binaries or from the target Samsung hardware.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


MAX_LOG_BYTES = 16 * 1024 * 1024

STAGES: tuple[tuple[str, tuple[bytes, ...]], ...] = (
    ("linux_kernel", (rb"Linux version 4\.1\.10",)),
    ("android_init_first_stage", (rb"init: init first stage started!",)),
    ("android_init_second_stage", (rb"init: init second stage started!",)),
    ("property_service", (rb"init:.*(property service|property_service)",)),
    ("ueventd", (rb"(?:\bueventd\b).*?(?:starting|started|running)",)),
    ("logd", (rb"(?:\blogd\b).*?(?:starting|started|running)",)),
    ("servicemanager", (rb"(?:\bservicemanager\b).*?(?:starting|started|running)",)),
)


def inspect(log: bytes) -> dict:
    if len(log) > MAX_LOG_BYTES:
        raise ValueError("QEMU-Seriellog ist zu groß")
    # Preserve only a compact accounting of evidence, not a potentially secret log.
    matches = {}
    for label, expressions in STAGES:
        matches[label] = any(re.search(exp, log, re.IGNORECASE) is not None
                             for exp in expressions)
    panic = bool(re.search(rb"Kernel panic|Attempted to kill init|Fatal signal", log, re.I))
    # An incomplete log, a fabricated marker or a Linux /init is no proof of an
    # actual Android service process; never call this 'PASS'.
    return {
        "type": "q60t_qemu_android_init_log_observation",
        "build": "022",
        "status": "LOG_OBSERVATIONS_ONLY_NO_VERIFIED_LINEAGEOS_BOOT",
        "markers_seen": matches,
        "kernel_panic_or_fatal_signal_seen": panic,
        "init_first_stage_log_observed": matches["android_init_first_stage"] and not panic,
        "android_init_elf_provenance_verified": False,
        "real_lineageos_android_init_proven": False,
        "android_system_services_proven_running": False,
        "qemu_log_is_not_samsung_hardware_evidence": True,
        "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QEMU-Serial-Log nach Android-Init-Hinweisen auswerten")
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if not args.log.is_file() or args.log.is_symlink() or args.log.stat().st_size > MAX_LOG_BYTES:
            raise ValueError("Reguläres, begrenztes Log fehlt")
        report = inspect(args.log.read_bytes())
    except (ValueError, OSError) as exc:
        print(f"Build-022-Logprüfung abgebrochen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
