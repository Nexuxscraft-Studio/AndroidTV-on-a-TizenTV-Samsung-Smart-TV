#!/usr/bin/env python3
"""Audit the ARM32 Nike.M vendor baseline; never claim that it is Q60T firmware."""

import argparse
import json
import os
from pathlib import Path
import sys
import tarfile

from q60t_build050_vendor_code_audit import SOURCE_SHA, sha256_file


KERNEL_CONFIG = "linux-4.1.10/arch/arm/configs/Nike.M-Tizen_release_defconfig"
ARM64_DEBUG_CONFIG = "linux-4.1.10/arch/arm64/configs/Nike.M-Tizen_debug_defconfig"
MEDIA_MAKEFILE = "tztv-media-nike/sdp_drm_nike/Makefile"


def get_member_text(archive, path):
    with tarfile.open(archive, "r:gz") as source:
        member = source.getmember(path)
        if not member.isfile() or member.size > 512 * 1024:
            raise ValueError("Unexpected source member type/size: " + path)
        stream = source.extractfile(member)
        if stream is None:
            raise ValueError("Source member is unavailable: " + path)
        return stream.read().decode("utf-8", "replace")


def arch_evidence(kernel_archive, media_archive):
    kernel_archive = Path(kernel_archive)
    media_archive = Path(media_archive)
    for file, family in ((kernel_archive, "kernel"), (media_archive, "media")):
        if sha256_file(file) != SOURCE_SHA[family]:
            raise ValueError(f"Original {family} archive SHA-256 mismatch")

    config = get_member_text(kernel_archive, KERNEL_CONFIG)
    other = get_member_text(kernel_archive, ARM64_DEBUG_CONFIG)
    makefile = get_member_text(media_archive, MEDIA_MAKEFILE)
    with tarfile.open(kernel_archive, "r:gz") as source:
        available = set(source.getnames())
    missing_vendor_headers = [
        name for name in (
            "linux-4.1.10/include/drm/drm_tztv.h",
            "linux-4.1.10/include/linux/videodev2_tztv.h",
        ) if name not in available
    ]
    required = {
        "CONFIG_ARM=y": config,
        "CONFIG_ARCH_SDP_NIKE=y": config,
        "CONFIG_CPU_V7=y": config,
        "CONFIG_CPU_ARM_CORTEX_A15=y": config,
        "ARCH = arm": makefile,
        "CROSS_COMPILER = armv7l-tizen-linux-gnueabi-": makefile,
    }
    for text, doc in required.items():
        if text not in doc:
            raise ValueError("Expected Samsung ARM32 evidence absent: " + text)

    return {
        "status": "ARM32_VENDOR_SOURCE_BASELINE_IDENTIFIED_NOT_TV_VERIFIED",
        "safe_to_flash": False,
        "build_executed": False,
        "samsung_original_baseline": {
            "kernel": "Linux 4.1.10-tizen5.5",
            "config": KERNEL_CONFIG,
            "config_arch": "arm (32-bit)",
            "config_cpu": "ARMv7 Cortex-A15",
            "media_makefile_default_arch": "arm",
            "media_makefile_has_optional_arm64": "ifeq ($(ARM64),YES)" in makefile,
            "arm64_debug_config_same_arm32_markers": (
                "CONFIG_ARM=y" in other and "CONFIG_CPU_V7=y" in other
            ),
            "unavailable_external_vendor_headers": missing_vendor_headers,
            "media_makefile_uses_external_kernel_interfaces": "vd_kernel-interfaces" in makefile,
        },
        "q60t_hypothesis_unverified": {
            "tv_model": "GQ50Q60TGUXZG",
            "chip": "SDP19403",
            "platform": "Nike-L",
            "cpu": "Cortex-A72",
            "gpu": "Mali-G31",
            "hardware_confirmed_on_this_tv": False,
        },
        "interpretation": (
            "Successful ARM32 compilation would show compatibility with the "
            "published Nike.M ARMv7/Cortex-A15 source baseline; it would NOT "
            "identify the Q60T SoC, boot architecture or firmware ABI."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-tgz", required=True)
    parser.add_argument("--media-tgz", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        report = arch_evidence(args.kernel_tgz, args.media_tgz)
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as dest:
            json.dump(report, dest, indent=2, ensure_ascii=False)
            dest.write("\n")
        print(report["status"] + "; safe_to_flash=false")
        return 0
    except (OSError, ValueError, KeyError, tarfile.TarError) as exc:
        print("Build 054 ARM32 evidence refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
