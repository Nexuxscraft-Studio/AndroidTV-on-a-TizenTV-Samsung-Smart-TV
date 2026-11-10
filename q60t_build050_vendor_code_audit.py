#!/usr/bin/env python3
"""Hash-pinned, read-only audit of original Samsung OSS TGZ source members.

This script neither extracts filesystem trees nor executes vendor code. It
records file hashes, exact literal marker locations and unmodified defconfig
values. Marker presence is not evidence of Linux 6.6 compatibility.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tarfile


SOURCE_SHA = {
    "kernel": "31a92f0d20248abbe2976bd2da1ab95dde4fed3e010ddcdc1c07494c4fd867b0",
    "media": "40c2a25eba331b8b04d8d81baf76061493f15f228a74893c7f825f7a1da724b6",
    "bootmode": "7feb006983b35431df9408aef4ea176c7204578d7ba0e1b898dd10e364e58516",
}
MAX_MEMBER = 8 * 1024 * 1024

MEMBERS = {
    "kernel": {
        "board_legacy_arm32": "linux-4.1.10/arch/arm/mach-sdp/board-nike-dt.c",
        "nike_m_release_defconfig": "linux-4.1.10/arch/arm/configs/Nike.M-Tizen_release_defconfig",
        "different_arm64_sdp1600_dts": "linux-4.1.10/arch/arm64/boot/dts/sdp/sdp1600.dtsi",
        "panel_legacy": "linux-4.1.10/drivers/gpu/drm/panel/panel-sdp.c",
    },
    "media": {
        "drm_display": "tztv-media-nike/sdp_drm_nike/sdp_drm_drv.c",
        "mali_kernel": "tztv-media-nike/sdp_gpu_nike/drivers/gpu/arm/midgard/mali_kbase_core_linux.c",
        "mali_sdp_platform": "tztv-media-nike/sdp_gpu_nike/drivers/gpu/arm/midgard/platform/sdp/mali_kbase_platform_sdp.c",
        "mali_makefile": "tztv-media-nike/sdp_gpu_nike/drivers/gpu/arm/midgard/Makefile",
        "frc_nikel": "tztv-media-nike/sdp_frc_nike/nikel/sdp_frc_drv.c",
        "hdmi": "tztv-media-nike/sdp_hdmi_nike/sdp_hdmi_main.c",
        "mfc_video": "tztv-media-nike/sdp_codec_nike/sdp_mfc.c",
        "alsa_audio": "tztv-media-nike/sdp_alsa_nike/sdp_audio_machine.c",
    },
    "bootmode": {
        "tizen_bootmode_module": "tztv-bootmode/tztv-bootmode.c",
    },
}

MARKERS = {
    "board_legacy_arm32": ["samsung,sdp-nikel", "samsung,sdp-nikem", "DT_MACHINE_START",
                           "sdp_secondary_startup", "u32 entry", "sdp_nike_powerup_cpu"],
    "different_arm64_sdp1600_dts": ["samsung,sdp1600", 'compatible = "arm,cortex-a57"',
                                   "enable-method = \"psci\"", "arm,psci-0.2"],
    "panel_legacy": ["drm_panel", "panel-sdp", "sdp"],
    "drm_display": ["drm_platform_init", "drm_put_dev", ".load", ".unload",
                    ".gem_free_object", "drm_fbdev_cma_restore_mode", "samsung,sdp-drm"],
    "mali_kernel": ["KERNEL_SIDE_DDK_VERSION_STRING", "kbase_api_get_ddk_version",
                    "KERNEL_VERSION(4, 6, 0)", "dma_buf", "pm_runtime"],
    "mali_sdp_platform": ["MuseM_DVFS_table", "sdp_set_clkrst_mux", "gpufreq_tmu_notifier"],
    "mali_makefile": ["ARCH ?= arm", "CONFIG_MALI_MIDGARD=m", "PLATFORM_CONFIG ?= sdp"],
    "frc_nikel": ["sdp_frc_tcon.h", "sdp_frc_irq_init", "sdp_frc_dormant_suspend"],
    "hdmi": ["hdcp22", "V4L2_CID_DV_G_HDCP_STATUS", "video_register_device"],
    "mfc_video": ["mfc", "platform_driver"],
    "alsa_audio": ["snd_soc", "audio"],
    "tizen_bootmode_module": ["TIZEN_BOOTING", "bootmode_ew", "proc_create"],
}

CONFIG_SYMBOLS = ["CONFIG_ARM", "CONFIG_ARM64", "CONFIG_ARM_PSCI",
                  "CONFIG_ANDROID_BINDER_IPC", "CONFIG_SECURITY_SELINUX",
                  "CONFIG_SECURITY_SMACK", "CONFIG_ION", "CONFIG_BPF_SYSCALL",
                  "CONFIG_CGROUPS", "CONFIG_SECCOMP_FILTER"]


def sha256_file(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Source archives must be regular files, not symlinks")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def config_status(text):
    output = {}
    for symbol in CONFIG_SYMBOLS:
        enabled = re.search(r"^" + re.escape(symbol) + r"=(.+)$", text, flags=re.M)
        disabled = re.search(r"^# " + re.escape(symbol) + r" is not set$", text, flags=re.M)
        output[symbol] = enabled.group(1) if enabled else ("n" if disabled else "not_listed")
    return output


def markers_in(text, markers):
    lines = text.splitlines()
    return {marker: [i for i, line in enumerate(lines, 1) if marker in line][:15]
            for marker in markers}


def inspect_sources(archive_paths, verify_hashes=True):
    report = {"type": "q60t_build050_direct_original_source_audit", "build": "050",
              "status": "SOURCE_CODE_CONFIRMED_TV_UNVERIFIED", "source_files": {},
              "archives": {}, "original_nike_l_release_config_verified": False,
              "real_soc_gpu_ids_verified": False, "hardware_boot_tested": False,
              "linux_6_6_driver_compiled": False, "safe_to_flash": False}
    for family, member_map in MEMBERS.items():
        path = Path(archive_paths[family])
        digest = sha256_file(path)
        if verify_hashes and digest != SOURCE_SHA[family]:
            raise ValueError(f"Original {family} TGZ SHA-256 mismatch")
        report["archives"][family] = {"filename": path.name, "sha256": digest,
                                      "expected_source_hash_matches": digest == SOURCE_SHA[family]}
        # TarFile's member reader streams bytes into memory only. Never extractall.
        with tarfile.open(path, mode="r:gz") as archive:
            for key, member_path in member_map.items():
                member = archive.getmember(member_path)
                if not member.isfile() or member.size > MAX_MEMBER:
                    raise ValueError(f"Nonregular/oversized original source member: {key}")
                reader = archive.extractfile(member)
                if reader is None:
                    raise ValueError(f"Unreadable member: {key}")
                raw = reader.read(MAX_MEMBER + 1)
                if len(raw) != member.size:
                    raise ValueError(f"Unexpected member size for {key}")
                text = raw.decode("utf-8", errors="replace")
                report["source_files"][key] = {
                    "archive_family": family, "member": member_path, "size_bytes": member.size,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "literal_marker_line_numbers": markers_in(text, MARKERS.get(key, [])),
                }
                if key == "nike_m_release_defconfig":
                    report["nike_m_unmodified_release_defconfig"] = config_status(text)

    board = report["source_files"]["board_legacy_arm32"]["literal_marker_line_numbers"]
    drm = report["source_files"]["drm_display"]["literal_marker_line_numbers"]
    mali = report["source_files"]["mali_kernel"]["literal_marker_line_numbers"]
    report["findings"] = {
        "legacy_arm32_nikel_machine_registration_found": bool(board["samsung,sdp-nikel"] and board["DT_MACHINE_START"]),
        "legacy_32bit_secondary_entry_api_found": bool(board["u32 entry"] and board["sdp_secondary_startup"]),
        "legacy_drm_platform_init_call_found": bool(drm["drm_platform_init"]),
        "legacy_drm_load_unload_callbacks_found": bool(drm[".load"] and drm[".unload"]),
        "mali_kbase_ddk_userspace_version_handshake_found": bool(mali["kbase_api_get_ddk_version"]),
        "sdp1600_arm64_tree_is_not_nikel_tree": True,
        "bootmode_module_proves_safe_stock_recovery": False,
    }
    report["interpretation"] = (
        "These are literal observations in hash-pinned GPL sources, NOT a completed "
        "driver port. Exact Nike-L defconfig, live GPU ID, bootloader signatures, "
        "AArch64 entry and recovery remain unverified. The source package also "
        "contains a different sdp1600 ARM64 DTS; do not treat it as a Nike-L DTB."
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-tgz", required=True)
    parser.add_argument("--media-tgz", required=True)
    parser.add_argument("--bootmode-tgz", required=True)
    parser.add_argument("--output", required=True, help="Write a new JSON report only")
    args = parser.parse_args(argv)
    try:
        report = inspect_sources({"kernel": args.kernel_tgz, "media": args.media_tgz,
                                  "bootmode": args.bootmode_tgz})
        data = (json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
            output.write(data)
        print(json.dumps({"status": report["status"], "source_members": len(report["source_files"]),
                          "safe_to_flash": False, "output": args.output}))
        return 0
    except (OSError, ValueError, tarfile.TarError, KeyError) as exc:
        print(f"Build 050 direct source audit refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
