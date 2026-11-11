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

# Deliberate, isolated source probes. Do not globally allow .c or .h:
# broad extension rules could accidentally ship non-redistributable firmware.
ALLOWED_C_PROBES = {
    "porting/probes/binder_uapi_arm32.c",
    "q60t_binder_init.c",
    "q60t_android_probe_init.c",
    "q60t_ion_probe_init.c",
    "q60t_bionic_hello.c",
    "q60t_bionic_init.c",
    "q60t_arm64_probe_init.c",
}

# Manually reviewed, source-only Linux porting artifacts. This is an exact
# path allowlist, not a directory or extension wildcard. New executable,
# binary, board firmware and unreviewed vendor files stay blocked.
ALLOWED_PORTING_SOURCES = {
    "porting/build052/contract/Makefile",
    "porting/build052/contract/nover_sdp_linux66_contract.c",
    "porting/build053/test-kbuild/Kbuild",
    "porting/build054/arm32-probe/Kbuild",
    "porting/build054/arm32-probe/nover_arm32_probe.c",
    "porting/build054/scripts/run-arm32-probe.sh",
    "porting/build054/scripts/run-arm32-vendor-diagnostic.sh",
    "porting/build054/test-kbuild-arm32/Kbuild",
    "porting/build055/inspect-sdp-gpu-ko.sh",
    "porting/build056/panfrost-sdp-nikel-disabled.dts",
    "porting/build058/build-arm32-offline.sh",
    "porting/build058/cpu/build-arm32-offline.sh",
    "porting/build058/cpu/kernel/Makefile",
    "porting/build058/cpu/kernel/sdp_nikel_cpu_clk.c",
    "porting/build058/cpu/kernel/sdp_nikel_cpufreq.c",
    "porting/build058/cpu/kernel/sdp_nikel_thermal.c",
    "porting/build058/cpu/model/nike_cpu_model.c",
    "porting/build058/cpu/model/nike_cpu_model.h",
    "porting/build058/cpu/model/test_nike_cpu_model.c",
    "porting/build058/cpu/nikel-cpu-thermal-disabled.dts",
    "porting/build058/cpu/run-host-tests.sh",
    "porting/build058/integration/drm/Makefile",
    "porting/build058/integration/drm/legacy-include/trace/early.h",
    "porting/build058/integration/drm/sdp_drm_fence.c",
    "porting/build058/integration/drm/sdp_drm_fence.h",
    "porting/build058/integration/drm/sdp_drm_util.c",
    "porting/build058/integration/drm/sdp_drm_util.h",
    "porting/build058/integration/run-arm32-compile-only.sh",
    "porting/build058/kernel/Makefile",
    "porting/build058/kernel/sdp_nikel_gpu_clkrst.c",
    "porting/build058/sdp-nikel-gpu-clkrst-disabled.dts",
    # Build 059: kernel build script and Kconfig fragments (text only)
    "porting/build059/initramfs/q60t-diag-init.c",
    "porting/build059/kernel/build.sh",
    "porting/build059/kernel/configs/nikel-arm.config",
    "porting/build059/kernel/configs/nikel-arm64.config",
    "porting/build059/kernel/configs/nikel-common.config",
    "porting/build059/kernel/configs/required-symbols.txt",
    # Build 063: driver bring-up scaffolds (text only, compile-gated in CI)
    "porting/build063/build.sh",
    "porting/build063/kernel/display/sdp_drm.c",
    "porting/build063/kernel/display/Kconfig",
    "porting/build063/kernel/display/Makefile",
    "porting/build063/configs/compile-test.config",
    "porting/build063/configs/nikel-display.config",
    "porting/build063/configs/nikel-gpu.config",
    "porting/build063/configs/nikel-cpu.config",
    "porting/build063/configs/nikel-soc-extra.config",
    "porting/build063/dts/sdp-nikel-display-disabled.dts",
    "porting/build063/dts/sdp-nikel-gpu-panfrost-disabled.dts",
    "porting/build063/dts/sdp-nikel-cpu-dvfs-disabled.dts",
    # Build 064: P1/P2 peripheral scaffolds (text only)
    "porting/build064/configs/nikel-peripherals.config",
    "porting/build064/dts/sdp-nikel-peripherals-disabled.dts",
    # Build 066: framebuffer-handoff scaffold (text only)
    "porting/build066/configs/nikel-simpledrm.config",
    "porting/build066/dts/sdp-nikel-simplefb-handoff.dts",
    # Build 067: QEMU boot harness (text only)
    "porting/build067/run-qemu-boot.sh",
    # Build 068: Android userspace build pipeline (text only, host-side)
    "porting/build068/userspace_pipeline.sh",
}

ALLOWED_EXPLICIT_SOURCES = ALLOWED_C_PROBES | ALLOWED_PORTING_SOURCES
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
                    filename not in ALLOWED_SPECIAL and
                    relative not in ALLOWED_EXPLICIT_SOURCES):
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
