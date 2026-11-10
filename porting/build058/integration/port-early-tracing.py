#!/usr/bin/env python3
"""Minimal, fail-closed source transformation of the STAGED Samsung DRM core.

Only the optional early tracing hook is changed. Never touches vendor sources.
"""
import difflib
import pathlib
import sys

def transform(source: str) -> str:
    header = "#include <trace/early.h>"
    call = "trace_early_message(msg);"
    if source.count(header) != 1 or source.count(call) != 1:
        raise ValueError("unexpected Samsung early-tracing source: require exactly one include and call")
    result = source.replace(header, "/* Linux 6.6: optional Samsung early-tracing header removed. */")
    result = result.replace(call, 'pr_debug("%s", msg);')
    return result

def main() -> int:
    if len(sys.argv) != 3:
        print("usage: port-early-tracing.py <staged-sdp_drm_drv.c> <diff-output>", file=sys.stderr)
        return 2
    path, diff_path = map(pathlib.Path, sys.argv[1:])
    original = path.read_text(encoding="utf-8")
    try:
        patched = transform(original)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True), patched.splitlines(keepends=True),
        fromfile="a/sdp_drm_drv.c", tofile="b/sdp_drm_drv.c"))
    if not diff:
        return 1
    diff_path.write_text(diff, encoding="utf-8")
    path.write_text(patched, encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
