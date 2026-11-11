#!/usr/bin/env python3
"""Build 069: read a QEMU serial log of an Android boot and report how far it got.

Milestones are matched on literal kernel/init log lines (Android 15 init
messages). The highest milestone reached and the first failure lines (with
context) are reported. Nothing is inferred beyond the log text.
Exit code: 0 if second-stage init was reached, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

MILESTONES = [
    ("kernel_start", r"Booting Linux on physical CPU"),
    ("kernel_initrd_init", r"Run /init as init process"),
    ("first_stage_init", r"init: init first stage started!"),
    ("first_stage_mount_done", r"init: Switching root to|Switching root to '/system'"),
    ("selinux_setup", r"init: init (?:selinux|SELinux) setup|Loading SELinux policy|selinux.*policy"),
    ("second_stage_init", r"init: init second stage started!"),
    ("property_service", r"init: (?:Setting up|Starting) property service|property_service"),
    ("servicemanager", r"starting service 'servicemanager'"),
    ("logd", r"starting service 'logd'"),
    ("zygote", r"starting service 'zygote'"),
    ("boot_completed", r"sys\.boot_completed=1|Boot is finished"),
]

FAILURES = [
    r"Kernel panic",
    r"init: .*[Ff]ailed to mount",
    r"init: .*Failed to .*fstab",
    r"init: InitFatalReboot",
    r"init: .*(?:Unable to load SELinux|Failed to load SELinux|SELinux: Could not)",
    r"init: .*Failed to (?:open|read|execv)",
    r"VFS: Unable to mount",
    r"No working init found",
    r"reboot: (?:Restarting|Power down)",
    r"init: .*[Ss]ervice '[^']+' .*(?:crashed|exited with status [1-9])",
]


def analyse(text: str) -> dict:
    lines = text.splitlines()
    reached = {}
    for name, pat in MILESTONES:
        rx = re.compile(pat)
        for i, line in enumerate(lines):
            if rx.search(line):
                reached[name] = {"line": i + 1, "text": line.strip()[:240]}
                break
    highest = None
    for name, _ in MILESTONES:
        if name in reached:
            highest = name
    failures = []
    frx = [re.compile(p) for p in FAILURES]
    for i, line in enumerate(lines):
        if any(r.search(line) for r in frx):
            failures.append({"line": i + 1,
                             "context": [l.strip()[:240] for l in lines[max(0, i - 6): i + 3]]})
            if len(failures) >= 6:
                break
    return {
        "build": "069",
        "lines": len(lines),
        "highest_milestone": highest,
        "milestones": {n: reached.get(n) for n, _ in MILESTONES},
        "failures": failures,
        "second_stage_reached": "second_stage_init" in reached,
        "note": "QEMU virt emulation only; says nothing about the Q60T.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("log", type=Path)
    p.add_argument("--json", type=Path, help="also write JSON here")
    a = p.parse_args(argv)
    r = analyse(a.log.read_text(encoding="utf-8", errors="replace"))
    if a.json:
        a.json.write_text(json.dumps(r, indent=2, ensure_ascii=False))
    for name, _ in MILESTONES:
        m = r["milestones"][name]
        print(f"  {'OK ' if m else '-- '} {name:<24} {('L%d: %s' % (m['line'], m['text'])) if m else ''}")
    print(f"HOECHSTER MEILENSTEIN: {r['highest_milestone']}")
    for f in r["failures"]:
        print(f"--- Fehlerstelle Zeile {f['line']}:")
        for c in f["context"]:
            print("    " + c)
    return 0 if r["second_stage_reached"] else 1


if __name__ == "__main__":
    sys.exit(main())
