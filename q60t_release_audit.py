#!/usr/bin/env python3
"""Read-only source disclosure check before sharing the Q60T research tree.

Not a formal secret detector or guarantee of legal redistributability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


ALLOWED_SUFFIXES = {".py", ".md", ".json", ".mk", ".yml", ".yaml", ".patch"}
ALLOWED_SPECIAL = {".gitignore"}
# Deliberate, isolated C-only lab sources. Do not generally whitelist .c:
# a broad extension rule could accidentally ship proprietary vendor sources.
ALLOWED_C_PROBES = {"porting/probes/binder_uapi_arm32.c", "q60t_binder_init.c",
                    "q60t_android_probe_init.c"}
IGNORED_DIRECTORIES = {"__pycache__", ".git"}
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
SECRET_MARKERS = (
    b"-----BEGIN " + b"PRIVATE KEY-----",
    b"-----BEGIN RSA " + b"PRIVATE KEY-----",
    b"-----BEGIN OPENSSH " + b"PRIVATE KEY-----",
    b"gh" + b"p_",
    b"github_" + b"pat_",
)


def audit(root: Path) -> dict:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Project directory missing or symbolic link")
    items = []
    problems = []
    total_bytes = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        # These are generated local caches, never source artifacts.
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRECTORIES)
        for directory_name in dirs:
            if (base / directory_name).is_symlink():
                problems.append(f"Symlink directory: {(base / directory_name).relative_to(root)}")
        for filename in sorted(files):
            path = base / filename
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                problems.append(f"Symlink file: {relative}")
                continue
            if (path.suffix not in ALLOWED_SUFFIXES and
                    filename not in ALLOWED_SPECIAL and relative not in ALLOWED_C_PROBES):
                problems.append(f"Disallowed file type: {relative}")
                continue
            size = path.stat().st_size
            total_bytes += size
            if size > MAX_FILE_BYTES:
                problems.append(f"Oversized source file: {relative}")
                continue
            contents = path.read_bytes()
            if b"\x00" in contents:
                problems.append(f"Binary data inside source: {relative}")
                continue
            if any(marker in contents for marker in SECRET_MARKERS):
                problems.append(f"Potential secret marker: {relative}")
                continue
            items.append({"path": relative, "bytes": size,
                          "sha256": hashlib.sha256(contents).hexdigest()})
    if total_bytes > MAX_TOTAL_BYTES:
        problems.append("Overall source tree unexpectedly large")
    return {
        "type": "source_release_audit", "status": "PASS" if not problems else "FAIL",
        "files_checked": len(items), "total_source_bytes": total_bytes,
        "problems": problems, "file_hashes": items,
        "disclaimer": "Heuristic local check; no proof of licensing or absence of secrets.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit source before future public release")
    parser.add_argument("root", nargs="?", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        report = audit(args.root)
    except (OSError, ValueError) as exc:
        print(f"Release-Audit fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
