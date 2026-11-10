#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read-only inventory of the Samsung SDP DRM sources for the drm_tztv.h blocker.

Reads the pinned ``tztv-media-nike.tgz`` directly with ``tarfile`` (nothing is
extracted, nothing is written except the JSON report) and answers:

* which files exist in ``tztv-media-nike/sdp_drm_nike/`` (e.g. a Samsung-local
  ``drm_gem_cma_helper.[ch]``),
* which headers each DRM source includes,
* which Samsung DRM identifiers (``DRM_SDP_*``, ``DRM_DPINST_*``,
  ``DRM_IOCTL_SDP_*``) are *defined somewhere in the archive* (``#define`` or
  an enum member) and which are only *used*.

Only identifiers that are used but defined nowhere in the archive can come
from the missing ``drm/drm_tztv.h``. This tool never guesses their values; it
lists names and the files using them. A lexical scan is not a C parser:
conditional compilation, macro-generated names and comments are not resolved,
so the result narrows the search but is not proof of the header's contents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path

PINNED_SHA256 = "40c2a25eba331b8b04d8d81baf76061493f15f228a74893c7f825f7a1da724b6"
DRM_DIR = "tztv-media-nike/sdp_drm_nike/"
IDENT = r"(?:DRM_SDP_|DRM_DPINST_|DRM_IOCTL_SDP_)[A-Z0-9_]+"
IDENT_RE = re.compile(rf"\b({IDENT})\b")
DEFINE_RE = re.compile(rf"^[ \t]*#[ \t]*define[ \t]+({IDENT})\b", re.MULTILINE)
# Enum members are only accepted inside an ``enum ... { ... }`` body, so that a
# continuation line of a function call is never mistaken for a definition.
ENUM_BODY_RE = re.compile(r"\benum\b[^{};]*\{([^{}]*)\}", re.DOTALL)
ENUM_MEMBER_RE = re.compile(rf"(?:^|,)\s*({IDENT})\s*(?==|,|$)")
INCLUDE_RE = re.compile(r'^[ \t]*#[ \t]*include[ \t]*([<"][^>"]+[>"])', re.MULTILINE)
SOURCE_SUFFIXES = (".c", ".h")
MAX_MEMBER_BYTES = 8 * 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", " ", text)


def inventory(archive_path: Path) -> dict:
    defined: dict[str, set[str]] = {}
    used: dict[str, set[str]] = {}
    includes: dict[str, list[str]] = {}
    drm_files: list[str] = []
    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive:
            if not member.isfile():
                continue
            name = member.name.lstrip("./")
            if name.startswith(DRM_DIR):
                drm_files.append(name[len(DRM_DIR):])
            if not name.endswith(SOURCE_SUFFIXES) or member.size > MAX_MEMBER_BYTES:
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            text = strip_comments(handle.read().decode("utf-8", errors="replace"))
            for match in DEFINE_RE.finditer(text):
                defined.setdefault(match.group(1), set()).add(name)
            for body in ENUM_BODY_RE.finditer(text):
                for match in ENUM_MEMBER_RE.finditer(body.group(1).strip()):
                    defined.setdefault(match.group(1), set()).add(name)
            for match in IDENT_RE.finditer(text):
                used.setdefault(match.group(1), set()).add(name)
            if name.startswith(DRM_DIR):
                includes[name[len(DRM_DIR):]] = INCLUDE_RE.findall(text)

    tztv_users = sorted(file for file, incs in includes.items() if "<drm/drm_tztv.h>" in incs)
    undefined = sorted(set(used) - set(defined))
    return {
        "archive": str(archive_path),
        "drm_directory": DRM_DIR,
        "drm_files": sorted(drm_files),
        "samsung_local_cma_helper": sorted(f for f in drm_files if "gem_cma_helper" in f),
        "files_including_drm_tztv_h": tztv_users,
        "includes": {k: includes[k] for k in sorted(includes)},
        "identifiers_used": len(used),
        "identifiers_defined_in_archive": {k: sorted(defined[k]) for k in sorted(defined)},
        "identifiers_used_but_undefined": {k: sorted(used[k]) for k in undefined},
        "interpretation": (
            "Undefined identifiers are CANDIDATES for drm/drm_tztv.h. Lexical scan only; "
            "no values, ioctl numbers or struct layouts are inferred."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("archive", type=Path, help="original tztv-media-nike.tgz")
    parser.add_argument("output", type=Path, help="new JSON report path")
    parser.add_argument("--allow-unpinned", action="store_true",
                        help="only for synthetic test archives")
    args = parser.parse_args(argv)
    if args.output.exists():
        print(f"Refusing to overwrite {args.output}", file=sys.stderr)
        return 2
    if not args.allow_unpinned and sha256_file(args.archive) != PINNED_SHA256:
        print("Refusing unpinned Samsung archive (SHA256 mismatch)", file=sys.stderr)
        return 2
    report = inventory(args.archive)
    report["archive_sha256_pinned"] = not args.allow_unpinned
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=False)
        handle.write("\n")
    print(f"drm files={len(report['drm_files'])} "
          f"defined={len(report['identifiers_defined_in_archive'])} "
          f"undefined_candidates={len(report['identifiers_used_but_undefined'])} "
          f"tztv_users={len(report['files_including_drm_tztv_h'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
