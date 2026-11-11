#!/usr/bin/env python3
"""Read-only inventory of ARM32 Nike-L porting inputs, not runtime readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


# Historical Build058 compile statuses are contextual only: no ELF test is
# rerun by this script and not all vendor sources are in the public repository.
PROBES = {
    "serial_uart": ("porting/build059/kernel/patches/0001-*.patch",),
    "clock_gpio": ("porting/build059/kernel/patches/0004-*.patch",
                   "porting/build059/kernel/patches/0008-*.patch"),
    "emmc_device_tree_disabled": ("porting/build059/kernel/patches/0006-*.patch",),
    "usb_device_tree_disabled": ("porting/build059/kernel/patches/0007-*.patch",),
    "gpu_clock_reset": ("porting/build058/kernel/sdp_nikel_gpu_clkrst.c",),
    "cpu_clock": ("porting/build058/cpu/kernel/sdp_nikel_cpu_clk.c",),
    "cpufreq": ("porting/build058/cpu/kernel/sdp_nikel_cpufreq.c",),
    "thermal": ("porting/build058/cpu/kernel/sdp_nikel_thermal.c",),
    "drm_utility": ("porting/build058/integration/drm/sdp_drm_util.c",),
    "drm_fence": ("porting/build058/integration/drm/sdp_drm_fence.c",),
    "samsung_drm_core_and_gem": ("porting/build058/integration/drm/sdp_drm_drv.c",
                                 "porting/build058/integration/drm/sdp_drm_gem.c"),
    "audio_hal": ("porting/device/samsung/nikel/audio/Android.bp",),
    "video_decoder_hal": ("porting/device/samsung/nikel/codec/Android.bp",),
}

HISTORICAL_COMPILER_REPORTS = {
    "gpu_clock_reset": "build058: ARM32 object reported compiled; modpost incomplete",
    "cpu_clock": "build058: ARM32 object reported compiled",
    "drm_utility": "build058: ARM32 object reported compiled",
    "drm_fence": "build058: ARM32 object reported compiled",
    "cpufreq": "build058: compilation failed, requires API port",
    "thermal": "build058: compilation failed, requires API port",
    "samsung_drm_core_and_gem": "build058: source exists in external Samsung media archive; port failed",
}


def inspect(repo: Path) -> dict:
    components = {}
    for name, patterns in PROBES.items():
        paths = sorted({p.relative_to(repo).as_posix()
                        for pattern in patterns for p in repo.glob(pattern)
                        if p.is_file()})
        components[name] = {
            "local_sources": paths,
            "source_present": bool(paths),
            "compile_status": "NOT_TESTED_IN_THIS_AUDIT",
            "historical_report": HISTORICAL_COMPILER_REPORTS.get(name, "none"),
            "boot_and_runtime": "UNVERIFIED",
        }
    return {
        "type": "nikel_arm32_driver_source_audit",
        "components": components,
        "disclaimer": "Absence only means not in this checkout. The Samsung media tarball is external; no vendor blob, driver execution or hardware check was performed.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2],
                   help="Local repository root")
    args = p.parse_args(argv)
    repo = args.repo.resolve()
    if not repo.is_dir():
        p.error("--repo must be a directory")
    print(json.dumps(inspect(repo), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
