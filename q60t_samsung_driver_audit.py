#!/usr/bin/env python3
"""Build 023: read-only Samsung 4.1.10 source-tree *porting inventory*.

Only indexes filenames from selected subsystems. It never modifies or
redistributes vendor source, guesses the TV SoC, or certifies ARM64 support.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from q60t_arm64_kernel import source_version


SUBSYSTEMS = {
    "arm32_device_trees": ("arch/arm/boot/dts", (".dts", ".dtsi")),
    "arm64_device_trees": ("arch/arm64/boot/dts", (".dts", ".dtsi")),
    "mali_gpu": ("drivers/gpu/arm", (".c", ".h", ".mk", ".dts", ".dtsi")),
    "drm_gpu_display": ("drivers/gpu/drm", (".c", ".h", ".dts", ".dtsi")),
    "video_display": ("drivers/video", (".c", ".h", ".dts", ".dtsi")),
    "media_codecs": ("drivers/media", (".c", ".h")),
    "samsung_audio": ("sound/soc/samsung", (".c", ".h")),
    "infrared_remote": ("drivers/media/rc", (".c", ".h")),
}
MAX_FILES_PER_SUBSYSTEM = 50000
EXAMPLES_MAX = 12


def audit(source: Path) -> dict:
    version = source_version(source)
    if version != (4, 1, 10):
        raise ValueError("Samsung-Originalquellen Linux 4.1.10 erforderlich")
    observations = {}
    for name, (directory, suffixes) in SUBSYSTEMS.items():
        base = source / directory
        matches = []
        if base.is_dir() and not base.is_symlink():
            for item in base.rglob("*"):
                if item.is_file() and not item.is_symlink() and item.suffix in suffixes:
                    matches.append(item.relative_to(source).as_posix())
                    if len(matches) >= MAX_FILES_PER_SUBSYSTEM:
                        raise ValueError(f"Treiberverzeichnis zu groß: {directory}")
        observations[name] = {"file_count": len(matches),
                              "example_paths": sorted(matches)[:EXAMPLES_MAX],
                              "source_scanned": base.is_dir() and not base.is_symlink()}

    # A newer GPU or Android HAL requires hardware-specific register maps,
    # interrupt/DMA/IOMMU handling and potentially proprietary userspace.
    return {
        "type": "q60t_samsung_arm64_driver_portability_inventory", "build": "023",
        "status": "SOURCE_FILENAME_INVENTORY_ONLY_PORTABILITY_UNVERIFIED",
        "source_kernel_version": "4.1.10", "target_qemu_kernel_version": "6.6.162",
        "observations": observations,
        "porting_gates": {
            "soc_cpu_arm64_capability": "UNKNOWN_REQUIRES_HARDWARE_IDENTIFICATION",
            "firmware_device_tree_cpu_isa_verified": False,
            "mali_gpu_kernel_drm_and_userspace_abi": "REQUIRES_DRIVER_LICENSE_AND_INTERFACE_REVIEW",
            "video_codec_and_media_hal": "REQUIRES_V4L2_AND_ANDROID_HAL_ADAPTATION",
            "display_hdmi_and_audio": "REQUIRES_DEVICE_TREE_AND_DRIVER_PORTING",
            "remote_input_and_hdmi_cec": "REQUIRES_HARDWARE_IDENTIFICATION",
            "bootloader_recovery_path": "NOT_VERIFIED",
        },
        "kernel_driver_sources_copied": False,
        "samsung_tv_accessed": False, "samsung_hardware_arm64_verified": False,
        "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 023: Samsung-4.1.10-Treiberinventur (read-only)")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="Optionaler neuer JSON-Dateipfad")
    args = parser.parse_args(argv)
    try:
        result = audit(args.source)
        raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(raw)
        print(raw, end="")
    except (OSError, ValueError) as exc:
        print(f"Build-023-Treiberinventur abgebrochen: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
