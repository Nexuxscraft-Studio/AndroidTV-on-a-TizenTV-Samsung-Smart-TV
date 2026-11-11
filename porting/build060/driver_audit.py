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


VENDOR_PROBES = {
    "samsung_drm_core_and_gem": ("sdp_drm_drv.c", "sdp_drm_gem.c"),
    "drm_utility": ("sdp_drm_util.c",),
    "drm_fence": ("sdp_drm_fence.c",),
    "audio_hal": ("sdp_platform.c", "sdp_pcm.c"),
    "video_decoder_hal": ("sdp_mfc.c", "sdp_mfc*.c"),
}


def inspect(repo: Path, vendor_source: Path | None = None) -> dict:
    components = {}
    for name, patterns in PROBES.items():
        paths = sorted({p.relative_to(repo).as_posix()
                        for pattern in patterns for p in repo.glob(pattern)
                        if p.is_file()})
        vendor_paths = []
        if vendor_source is not None:
            vendor_patterns = VENDOR_PROBES.get(name, ())
            vendor_paths = sorted({p.relative_to(vendor_source).as_posix()
                                   for pattern in vendor_patterns
                                   for p in vendor_source.glob("**/" + pattern)
                                   if p.is_file()})[:20]
        components[name] = {
            "local_sources": paths,
            "source_present": bool(paths),
            "external_samsung_source_candidates": vendor_paths,
            "compile_status": "NOT_TESTED_IN_THIS_AUDIT",
            "historical_report": HISTORICAL_COMPILER_REPORTS.get(name, "none"),
            "boot_and_runtime": "UNVERIFIED",
        }
    return {
        "type": "nikel_arm32_driver_source_audit",
        "components": components,
        "disclaimer": "Absence means not found in the scanned trees, not that a driver does not exist. External source matching is filename-only. No vendor blob, driver execution or hardware check was performed.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2],
                   help="Local repository root")
    p.add_argument("--vendor-source", type=Path,
                   help="Optional locally extracted Samsung tztv-media-nike source (read only)")
    args = p.parse_args(argv)
    repo = args.repo.resolve()
    if not repo.is_dir():
        p.error("--repo must be a directory")
    vendor = args.vendor_source.resolve() if args.vendor_source else None
    if vendor is not None and not vendor.is_dir():
        p.error("--vendor-source must be an existing directory")
    print(json.dumps(inspect(repo, vendor), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
