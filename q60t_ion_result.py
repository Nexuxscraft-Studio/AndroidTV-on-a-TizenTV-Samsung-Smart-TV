#!/usr/bin/env python3
"""Build 020: distinguish real legacy ION ioctls from merely opening /dev/ion.

Reads a QEMU serial log only. Does not execute binaries or contact hardware.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


MAX_BYTES = 8 * 1024 * 1024
STAGES = ("open", "alloc", "free")
MARKER = re.compile(r"^Q60T_ION_TEST stage=(open|alloc|free) result=(pass|fail)(?: bytes=(\d+)| errno=(\d+))?$")


def inspect(raw: bytes) -> dict:
    if len(raw) > MAX_BYTES:
        raise ValueError("QEMU-Log zu groß; Ergebnis nicht vertrauenswürdig")
    lines = raw.replace(b"\r", b"").decode("utf-8", errors="replace").splitlines()
    begin = lines.count("Q60T_ANDROID_PROBE_BEGIN version=020 host_only=1 no_flash=1")
    end = lines.count("Q60T_ANDROID_PROBE_END version=020")
    stages: dict[str, str] = {}
    stage_order: list[str] = []
    stage_bytes = None
    for line in lines:
        hit = MARKER.fullmatch(line)
        if not hit:
            continue
        name, result = hit.group(1), hit.group(2)
        if name in stages:
            raise ValueError("Doppelte ION-Stufe: Testprotokoll mehrdeutig")
        stages[name] = result
        stage_order.append(name)
        if name == "alloc":
            stage_bytes = int(hit.group(3)) if hit.group(3) else None
    feature_pass = lines.count("Q60T_ANDROID_PROBE_FEATURE name=ion result=pass") == 1
    start_at = lines.index("Q60T_ANDROID_PROBE_BEGIN version=020 host_only=1 no_flash=1") if begin == 1 else -1
    end_at = lines.index("Q60T_ANDROID_PROBE_END version=020") if end == 1 else -1
    stage_lines = [i for i, line in enumerate(lines) if MARKER.fullmatch(line)]
    all_pass = (begin == end == 1 and start_at < end_at
                and all(start_at < index < end_at for index in stage_lines)
                and stage_order == list(STAGES)
                and all(stages.get(stage) == "pass" for stage in STAGES)
                and stage_bytes == 4096 and feature_pass and
                not any("Kernel panic" in line for line in lines))
    return {
        "build": "020",
        "status": "ION_OPEN_ALLOC_FREE_GUEST_PASS_REPORTED" if all_pass else "ION_GUEST_TEST_NOT_VERIFIED",
        "guest_probe_complete": begin == end == 1,
        "stages": stages,
        "allocation_bytes": stage_bytes,
        "ion_4k_allocation_verified_in_guest_log": all_pass,
        "android_booted": False,
        "tv_accessed": False,
        "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 020 ION Guest-Serial-Auswertung")
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if not args.log.is_file() or args.log.is_symlink():
            raise ValueError("Kein reguläres QEMU-Log")
        if args.log.stat().st_size > MAX_BYTES:
            raise ValueError("Log zu groß")
        report = inspect(args.log.read_bytes())
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ion_4k_allocation_verified_in_guest_log"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
