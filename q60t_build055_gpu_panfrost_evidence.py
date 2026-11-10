#!/usr/bin/env python3
"""Build 055: pin Samsung GPU source evidence for a future Panfrost port.

Reads the original OSS archive only. Does not load modules or access hardware.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tarfile

from q60t_build050_linux66_port_gaps import read_original_text
from q60t_build050_vendor_code_audit import SOURCE_SHA, sha256_file


ROOT = "tztv-media-nike/sdp_gpu_nike/drivers/gpu/arm/midgard/"
MEMBERS = {
    "platform": ("platform/sdp/mali_kbase_platform_sdp.c",
                 "5b1f5a748854b4ce48dfd13ed7d2f2ef779001bb781765cf719c3b4bdeeb621d"),
    "registers": ("platform/sdp/mali_kbase_config_platform.h",
                  "021b5cf2ca2c87bda2c1a3c8938319deb487d0ba600d1585dfd93ea0ec7ed0b6"),
    "probe": ("mali_kbase_core_linux.c",
              "89b90beb0a2495388d634ad7f04a6eda260afdc7961c126a7e27eb699125d7f6"),
    "memory": ("mali_kbase_mem_linux.c",
               "4aca6876a9f7632ba68f75db313465e5339a1854a6d36019f50124d01f0ac04f"),
}

REGISTER_NAMES = (
    "SDP_REG_GPU_CLK_MASK",
    "SDP_REG_GPU_BUSIF_SW_RESET",
    "SDP_REG_GPU_CORE_SW_RESET",
    "SDP_REG_GPU_POWER_REQ_IDLE",
    "SDP_REG_GPU_POWER_IDLE",
)


def marker_lines(source, token):
    return [i for i, line in enumerate(source.splitlines(), 1) if token in line][:20]


def branch_defines(source, start, end):
    """Read one #ifdef-only branch without treating adjacent SoC values as equivalent."""
    begin = source.find(start)
    finish = source.find(end, begin + len(start))
    if begin < 0 or finish < 0 or finish <= begin:
        raise ValueError("Expected Samsung SoC branch not found")
    section = source[begin:finish]
    result = {}
    for symbol in REGISTER_NAMES:
        match = re.search(r"^\s*#define\s+" + symbol + r"\s+(0x[0-9a-fA-F]+)\s*$",
                          section, re.M)
        if not match:
            raise ValueError("Missing SoC-specific GPU symbol: " + symbol)
        result[symbol] = match.group(1).lower()
    return result


def inspect(media_tgz):
    media_tgz = Path(media_tgz)
    digest = sha256_file(media_tgz)
    if digest != SOURCE_SHA["media"]:
        raise ValueError("Samsung source archive SHA-256 mismatch")

    sources = {}
    members = {}
    for label, (name, expected_hash) in MEMBERS.items():
        member = ROOT + name
        body, current_hash = read_original_text(media_tgz, member)
        if current_hash != expected_hash:
            raise ValueError("Pinned Samsung GPU member SHA-256 mismatch: " + member)
        sources[label] = body
        members[label] = {"member": member, "sha256": current_hash}

    regs = sources["registers"]
    nikem = branch_defines(regs, "#ifdef\tCONFIG_SOC_CHIP_NIKEM", "#else")
    nikel = branch_defines(regs, "#ifdef\tCONFIG_SOC_CHIP_NIKEL", "#else")
    if nikem == nikel:
        raise ValueError("Nike.M and Nike.L register tables unexpectedly identical")

    checks = {
        "vendor_gpu_power_control": marker_lines(sources["platform"],
                                                  "kbase_platform_sdp_gpu_power_control"),
        "vendor_gpu_clock_reset_writes": marker_lines(sources["platform"],
                                                      "sdp_set_clkrst_mux("),
        "vendor_of_legacy_midgard_compatible": marker_lines(sources["probe"],
                                                            '"arm,mali-midgard"'),
        "vendor_of_legacy_malit6xx_compatible": marker_lines(sources["probe"],
                                                            '"arm,malit6xx"'),
        "vendor_dma_buf_use": marker_lines(sources["memory"], "dma_buf"),
        "vendor_gpu_memory_management": marker_lines(sources["memory"],
                                                     "kbase_mem"),
    }
    if any(not lines for lines in checks.values()):
        raise ValueError("One or more pinned Samsung GPU source markers are missing")

    return {
        "type": "q60t_build055_panfrost_vendor_gpu_reference",
        "build": "055",
        "status": "SOURCE_REFERENCE_VALIDATED_BOARD_UNVERIFIED",
        "safe_to_flash": False,
        "hardware_access_performed": False,
        "module_binary_supplied": False,
        "kernel_module_loaded": False,
        "kernel_66_gpu_driver_compiled": False,
        "tv_gpu_model_verified": False,
        "target": {
            "tv_model": "GQ50Q60TGUXZG",
            "user_reported_gpu": "Mali-G51 Bifrost r11p0",
            "gpu_id_from_upstream_linux_6_6_reference": "0x7000",
            "gpu_id_read_from_this_tv": None,
            "chip_working_hypothesis": "SDP19403 / Nike-L",
        },
        "upstream_references": {
            "kernel_tag": "torvalds/linux v6.6",
            "model_file": "drivers/gpu/drm/panfrost/panfrost_gpu.c",
            "model_marker": "GPU_MODEL(g51, 0x7000)",
            "driver_file": "drivers/gpu/drm/panfrost/panfrost_drv.c",
            "of_compatible": "arm,mali-bifrost",
            "dt_binding": "Documentation/devicetree/bindings/gpu/arm,mali-bifrost.yaml",
            "mesa_docs": "https://docs.mesa3d.org/drivers/panfrost.html",
        },
        "samsung_source": {
            "archive_sha256": digest,
            "source_members": members,
            "nike_m_registers": nikem,
            "nike_l_registers": nikel,
            "note": "These are Samsung CLK/RESET/IDLE control addresses from old source; "
                    "NOT a verified GPU MMIO base, IRQ map, or proven Q60T board configuration.",
            "markers": checks,
        },
        "requirements_for_board_port": [
            {"name": "GPU ID read from Q60T or trusted firmware", "status": "missing"},
            {"name": "GPU core MMIO reg base and size", "status": "missing"},
            {"name": "job, mmu and gpu interrupts", "status": "missing"},
            {"name": "clock, reset and power domain integration", "status": "vendor clues, unverified"},
            {"name": "regulator, devfreq and thermal integration", "status": "vendor clues, unverified"},
            {"name": "IOMMU, DMA addressing and memory coherence", "status": "vendor clues, unverified"},
            {"name": "device tree validated for actual Q60T variant", "status": "missing"},
            {"name": "firmware/secure world GPU dependencies", "status": "unknown"},
        ],
        "implementation_policy": (
            "Prefer upstream Panfrost DRM and Mesa; use Samsung kbase only as a "
            "read-only hardware/initialization reference. Do not transplant legacy "
            "kbase memory ABI or write register constants without board verification."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-tgz", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        report = inspect(args.media_tgz)
        with os.fdopen(os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600),
                       "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(report["status"] + "; safe_to_flash=false")
        return 0
    except (OSError, ValueError, KeyError, tarfile.TarError) as exc:
        print("Build 055 GPU audit refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
