#!/usr/bin/env python3
"""Build 022: read-only Q60T kernel/architecture migration evidence report.

Only analyzes existing *offline* reports and optionally a stock uImage.
Reference firmware Device Trees are not live device attestation. Nothing
produced by this program is a boot image, firmware patch or flash approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


REFERENCE_DTB_SHA256 = "9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2"
MAX_REPORT_BYTES = 16 * 1024 * 1024
MAX_STOCK_IMAGE_BYTES = 64 * 1024 * 1024
ARMV8_CPU_COMPATIBLES = frozenset({
    "arm,cortex-a35", "arm,cortex-a53", "arm,cortex-a55", "arm,cortex-a57",
    "arm,cortex-a72", "arm,cortex-a73", "arm,cortex-a75", "arm,cortex-a76",
    "arm,cortex-a77", "arm,cortex-a78", "arm,cortex-a710", "arm,armv8",
})

# Android *GKI* examples from the AOSP compatibility matrix; GKI is arm64.
# This is not a LineageOS-device support matrix or a Q60T kernel selection.
ANDROID_GKI_EXAMPLES = {
    "14": "android14-6.1",
    "15": "android15-6.6",
    "16": "android16-6.12",
}
CRITICAL_COMPATIBLES = {
    "board": ("samsung,sdp-nikel",),
    "gpu": ("arm,mali-midgard",),
    "display": ("samsung,sdp-drm", "samsung,sdp-hdmi", "samsung,sdp1202-panel"),
    "video": ("samsung,sdp-mfc",),
    "audio": ("samsung,sdp-mc-audio",),
    "input": ("samsung,sdp-mc-irb",),
}
SOURCE_CLASSES = frozenset({
    "KERNEL_CODE_REFERENCE", "MEDIA_CODE_REFERENCE",
    "DTS_DECLARATION_ONLY", "NO_LITERAL_SOURCE_REFERENCE",
})


def read_json_report(path: Path) -> tuple[dict, str]:
    """Reject links and oversized files; return data and input fingerprint."""
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError("JSON report missing, linked or oversized")
    raw = path.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("JSON report must be an object")
    return data, hashlib.sha256(raw).hexdigest()


def check_hash(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise ValueError("Expected reference DTB SHA-256 must be 64 hex digits")
    return value.lower()


def cpu_profiles(hardware: dict) -> list[dict]:
    trees = hardware.get("trees")
    if not isinstance(trees, list) or not 1 <= len(trees) <= 16:
        raise ValueError("Hardware report must contain 1-16 Device Trees")
    if hardware.get("device_trees_found") != len(trees):
        raise ValueError("Hardware report Device Tree count inconsistent")
    result = []
    for index, tree in enumerate(trees):
        summary = tree.get("summary", {})
        if not isinstance(summary, dict):
            raise ValueError("Invalid Device Tree summary")
        categories = summary.get("hardware_categories", {})
        if not isinstance(categories, dict):
            raise ValueError("Invalid hardware category mapping")
        cpus = categories.get("cpu", [])
        if not isinstance(cpus, list) or len(cpus) > 256:
            raise ValueError("Invalid CPU node list")
        compatible = []
        armv8 = []
        for cpu in cpus:
            values = cpu.get("compatible", []) if isinstance(cpu, dict) else []
            if not isinstance(values, list):
                raise ValueError("Invalid CPU compatible list")
            clean = [v for v in values if isinstance(v, str) and len(v) <= 100]
            compatible.append(clean)
            armv8.append(bool(set(clean) & ARMV8_CPU_COMPATIBLES))
        result.append({
            "profile_index": index,
            "dtb_sha256": check_hash(tree.get("dtb_sha256")),
            "cpu_nodes": len(cpus),
            "cpu_compatible_identifiers": sorted({c for group in compatible for c in group})[:30],
            "armv8_declared_in_every_cpu_node": bool(armv8) and all(armv8),
            "memory_profile_label_from_reference": summary.get("memory_profile_label"),
            "board_model_from_reference": summary.get("model"),
        })
    return result


def source_bindings(source: dict | None) -> dict:
    by_category = source.get("compatibility_references", {}) if source else {}
    if not isinstance(by_category, dict):
        raise ValueError("Invalid source compatibility matrix")
    result = {}
    for category, compatibles in CRITICAL_COMPATIBLES.items():
        raw = by_category.get(category, [])
        if not isinstance(raw, list):
            raise ValueError("Invalid source category")
        known = {e.get("compatible"): e for e in raw if isinstance(e, dict)}
        group = []
        for compatible in compatibles:
            entry = known.get(compatible)
            classification = entry.get("classification") if entry else "UNVERIFIED"
            if classification not in SOURCE_CLASSES:
                classification = "UNVERIFIED"
            group.append({"compatible": compatible,
                          "source_reference_classification": classification,
                          "driver_ported_to_modern_kernel": False,
                          "android_hal_verified": False})
        result[category] = group
    return result


def stock_uimage_metadata(path: Path | None) -> dict:
    if path is None:
        return {"supplied": False, "stock_kernel_architecture": "NOT_CHECKED"}
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_size > MAX_STOCK_IMAGE_BYTES):
        raise ValueError("Stock uImage missing, linked or oversized")
    # Reuse the existing CRC-checked reader; never execute the image.
    from q60t_lab import inspect_uimage

    image = inspect_uimage(path)
    if not image.get("valid"):
        raise ValueError("Stock uImage header or payload CRC invalid")
    arch = {2: "ARM32_LEGACY_UIMAGE_HEADER", 22: "ARM64_LEGACY_UIMAGE_HEADER"}.get(
        image.get("arch_id"), "UNKNOWN_LEGACY_UIMAGE_ARCH")
    return {
        "supplied": True,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "stock_uimage_crc_valid": True,
        "stock_uimage_arch_id": image.get("arch_id"),
        "stock_kernel_architecture": arch,
        "bootloader_accepts_modified_image": False,
    }


def verify_raw_reference_dtb(path: Path | None, expected_hash: str,
                             hardware: dict) -> bool:
    """If provided, independently hash and reparse raw DTB bytes read-only."""
    if path is None:
        return False
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_size > 32 * 1024 * 1024):
        raise ValueError("Raw DTB missing, linked or oversized")
    blob = path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != check_hash(expected_hash):
        raise ValueError("Raw reference DTB SHA-256 mismatch")
    import q60t_hardware

    reparsed = q60t_hardware.hardware_report(path)
    expected_trees = hardware["trees"]
    actual_trees = reparsed["trees"]
    if (len(expected_trees) != len(actual_trees) or any(
            a.get("dtb_sha256") != b.get("dtb_sha256")
            for a, b in zip(expected_trees, actual_trees))):
        raise ValueError("Raw DTB contents do not match supplied hardware report")
    return True


def analyze(hardware: dict, hardware_sha: str, source: dict | None = None,
            source_sha: str | None = None, expected_dtb_sha256: str = REFERENCE_DTB_SHA256,
            stock_image: dict | None = None, raw_dtb_reparsed: bool = False) -> dict:
    expected = check_hash(expected_dtb_sha256)
    if hardware.get("type") != "offline_hardware_device_tree_report":
        raise ValueError("Not an existing Q60T hardware report")
    observed = check_hash(hardware.get("dtb_bundle_sha256"))
    if observed != expected:
        raise ValueError("Reference firmware DTB fingerprint mismatch")
    profiles = cpu_profiles(hardware)
    if source is not None:
        if source.get("type") != "q60t_offline_compatible_source_matrix":
            raise ValueError("Invalid source compatibility report")
        if check_hash(source.get("dtb_bundle_sha256")) != observed:
            raise ValueError("Source and hardware reports describe different DTB bundles")
        if source.get("firmware_device_tree_count") != len(profiles):
            raise ValueError("Source and hardware reports disagree on DTB count")
    all_armv8 = all(profile["armv8_declared_in_every_cpu_node"] for profile in profiles)
    # This is ONLY a statement about the static reference DTs. The TV's live
    # hardware, EL1/EL2 execution state and secure-boot route are unknown.
    checks = {
        "reference_report_claimed_dtb_sha256_matches_expected": True,
        "raw_reference_dtb_reparsed_in_this_run": raw_dtb_reparsed,
        "all_reference_profiles_declare_armv8_cpu_nodes": all_armv8,
        "exact_50_inch_board_profile_verified_on_device": False,
        "arm64_kernel_execution_state_verified_on_device": False,
        "bootloader_accepts_arm64_test_kernel": False,
        "firmware_source_matches_stock_kernel_exactly": False,
        "modern_soc_display_and_gpu_drivers_ported": False,
        "lineageos_device_tree_vendor_hals_verified": False,
        "nonpersistent_boot_and_recovery_proven": False,
    }
    blockers = [name for name, value in checks.items()
                if not value and name not in {"all_reference_profiles_declare_armv8_cpu_nodes",
                                             "raw_reference_dtb_reparsed_in_this_run"}]
    if not all_armv8:
        blockers.append("armv8_not_confirmed_in_all_reference_cpu_nodes")
    return {
        "type": "q60t_build022_kernel_migration_audit",
        "build": "022",
        "status": "HOST_ONLY_HARDWARE_AUDIT_BLOCKED_FOR_DEVICE_BOOT",
        "target_device": "GQ50Q60TGUXZG (user stated; reference firmware only)",
        "target_userspace": "LineageOS Android TV (version not selected)",
        "firmware_reference": "T-NKLDEUC 2743.0 (reference package, not live device)",
        "evidence": {
            "hardware_report_sha256": hardware_sha,
            "source_report_sha256": source_sha,
            "reference_dtb_bundle_sha256": observed,
            "raw_reference_dtb_bytes_verified_in_this_run": raw_dtb_reparsed,
            "reference_device_tree_count": len(profiles),
            "stock_kernel_source_version_candidate": source.get("source_kernel_version") if source else None,
            "source_matches_firmware_2743_0": False,
            "stock_image": stock_image or stock_uimage_metadata(None),
        },
        "cpu_architecture": {
            "profiles": profiles,
            "reference_dts_indicate_armv8": all_armv8,
            "arm64_hardware_on_exact_tv_verified": False,
            "bootloader_64bit_entry_verified": False,
            "qemu_arm32_bionic_result_proves_arm64_capability": False,
        },
        "device_driver_evidence": source_bindings(source),
        "future_gki_reference_only": {
            "examples_by_android_version": ANDROID_GKI_EXAMPLES,
            "gki_requires_aarch64": True,
            "these_kernels_are_verified_on_q60t": False,
            "kernel_selected_for_lineageos": False,
            "matrix_source": "https://source.android.com/docs/core/architecture/kernel/android-common",
            "architecture_source": "https://source.android.com/docs/core/architecture/kernel",
        },
        "checks": checks,
        "blocking_gates": blockers,
        "android_booted": False,
        "lineageos_built": False,
        "hardware_test_performed": False,
        "tv_accessed": False,
        "original_samsung_files_modified": False,
        "safe_to_flash": False,
        "flash_authorized": False,
        "conclusion": "Cortex-A57/ARMv8 declarations in reference firmware do not prove "
                      "an ARM64 boot path on the exact Q60T. Kernel 6.x needs "
                      "SoC drivers, display/GPU, Android HALs, boot-chain and "
                      "reversible recovery evidence. No flash or TV boot authorized.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 022: offline Q60T kernel migration feasibility")
    parser.add_argument("--hardware-report", type=Path, required=True)
    parser.add_argument("--source-compat-report", type=Path)
    parser.add_argument("--stock-uimage", type=Path, help="optional immutable stock reference image")
    parser.add_argument("--raw-dtb", type=Path,
                        help="optionally hash/reparse reference firmware dtb.bin")
    parser.add_argument("--expected-dtb-sha256", default=REFERENCE_DTB_SHA256)
    parser.add_argument("--output", type=Path, help="write new JSON report; never overwrite")
    args = parser.parse_args(argv)
    try:
        hardware, hardware_sha = read_json_report(args.hardware_report)
        source, source_sha = (read_json_report(args.source_compat_report)
                              if args.source_compat_report else (None, None))
        image = stock_uimage_metadata(args.stock_uimage)
        raw_reparsed = verify_raw_reference_dtb(args.raw_dtb, args.expected_dtb_sha256,
                                                 hardware)
        result = analyze(hardware, hardware_sha, source, source_sha,
                         args.expected_dtb_sha256, image, raw_reparsed)
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(rendered)
        else:
            print(rendered, end="")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"Build-022-Analyse fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    return 0  # Host report generated, NOT permission to boot or flash.


if __name__ == "__main__":
    raise SystemExit(main())
