#!/usr/bin/env python3
"""Build 054: generate a guarded follow-up diff on top of Samsung Build 053.

This is a compile-diagnostics stage, not a running Samsung driver. In
particular, legacy reservation_object and vendor CMA layouts are untouched.
"""

import argparse
import difflib
import os
from pathlib import Path
import sys

from q60t_build050_linux66_port_gaps import read_original_text
from q60t_build050_stage1_source_fixes import fix_drm_safety, replace_once
from q60t_build050_vendor_code_audit import SOURCE_SHA, sha256_file
from q60t_build053_samsung_drm_stage1 import (
    DRM, GEM, SHA256 as PREVIOUS_SHA, migrate_drm, migrate_gem,
)


DRM_H = "tztv-media-nike/sdp_drm_nike/sdp_drm_drv.h"
GEM_H = "tztv-media-nike/sdp_drm_nike/sdp_drm_gem.h"
HEADER_SHA = {
    DRM_H: "d61ea1f7d3bbbf0f6fa43bf1a8515e6c3dc0116035f085a6bbaa96aba9754ea8",
    GEM_H: "2c9571b9d3c757865b60d6f0611eda5361c7ec296b99d9cfb2bdcc96ed449099",
}


def advance_drm_source(build053_source):
    """Drop the obsolete no-op DRM_UNLOCKED flag without changing DRM_AUTH."""
    before = "static struct drm_ioctl_desc sdp_drm_ioctls[] = {"
    after = "static const struct file_operations sdp_drm_driver_fops = {"
    # This table alone is changed; no other DRM flag or ioctl gets dropped.
    if build053_source.count(before) != 1 or build053_source.count(after) != 1:
        raise ValueError("Unable to isolate original Samsung ioctl table")
    first = build053_source.index(before)
    last = build053_source.index(after)
    if last <= first:
        raise ValueError("Samsung ioctl table precedes its expected terminator")
    table = build053_source[first:last]
    if table.count("DRM_UNLOCKED") != 32:
        raise ValueError("Samsung ioctl flag count differs from audited source")
    # Retain DRM_AUTH where it was actually set, and retain the disabled
    # DRM_AUTH comments as comments (do not silently grant/revoke access).
    table = table.replace("DRM_UNLOCKED", "0")
    table = table.replace(before,
                          "/* Build 054: DRM_UNLOCKED is a legacy no-op; "
                          "keep original DRM_AUTH bits. */\n" + before, 1)
    if table.count("DRM_UNLOCKED") != 1:  # explanatory comment only
        raise ValueError("Unexpected DRM_UNLOCKED left in ioctl declarations")
    result = build053_source[:first] + table + build053_source[last:]
    if ('compatible = "nover,compile-only-sdp-drm"' not in result or
            "return -ENODEV;" not in result):
        raise ValueError("Build 053 hardware lockout was lost")
    return result


def advance_drm_header(source):
    return replace_once(
        source, "#include <drm/drmP.h>",
        "/* Build 054: explicit core declarations instead of removed drmP.h. */\n"
        "#include <drm/drm_device.h>\n"
        "#include <drm/drm_file.h>\n"
        "#include <drm/drm_crtc.h>\n"
        "#include <drm/drm_gem.h>\n"
        "#include <drm/drm_modes.h>\n"
        "#include <drm/drm_prime.h>\n"
        "#include <drm/drm_vblank.h>",
        "actual Samsung driver-header drmP.h import")


def advance_gem_header(source):
    return replace_once(
        source, "#include <drm/drmP.h>",
        "/* Build 054: explicit GEM and VM declarations for diagnostics. */\n"
        "#include <drm/drm_device.h>\n"
        "#include <drm/drm_file.h>\n"
        "#include <drm/drm_gem.h>\n"
        "#include <linux/mm.h>",
        "actual Samsung GEM-header drmP.h import")


def make_stage2_patch(drm, gem, drm_h, gem_h):
    original_build053_drm = migrate_drm(fix_drm_safety(drm))
    original_build053_gem = migrate_gem(gem)
    edits = (
        (DRM, original_build053_drm, advance_drm_source(original_build053_drm)),
        (DRM_H, drm_h, advance_drm_header(drm_h)),
        (GEM_H, gem_h, advance_gem_header(gem_h)),
    )
    if "#include <drm/drm_gem.h>" not in original_build053_gem:
        raise ValueError("Build 053 GEM source was not applied")
    lines = []
    for path, old, new in edits:
        lines.extend(difflib.unified_diff(
            old.splitlines(keepends=True), new.splitlines(keepends=True),
            fromfile="a/" + path, tofile="b/" + path, n=3))
    return "".join(lines)


def generate(media_tgz):
    media_tgz = Path(media_tgz)
    if sha256_file(media_tgz) != SOURCE_SHA["media"]:
        raise ValueError("Original media archive SHA-256 mismatch")
    contents = {}
    for path, expected in (PREVIOUS_SHA | HEADER_SHA).items():
        value, digest = read_original_text(media_tgz, path)
        if digest != expected:
            raise ValueError("Samsung original source SHA-256 mismatch: " + path)
        contents[path] = value
    return make_stage2_patch(contents[DRM], contents[GEM],
                             contents[DRM_H], contents[GEM_H])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-tgz", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        patch = generate(args.media_tgz)
        with os.fdopen(os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as dest:
            dest.write(patch)
        print(f"Build 054 DRM-headers/ioctls patch: {len(patch)} bytes; "
              "compile_test_run=false; safe_to_flash=false")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print("Build 054 refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
