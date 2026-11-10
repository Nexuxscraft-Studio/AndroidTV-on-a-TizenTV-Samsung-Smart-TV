#!/usr/bin/env python3
"""Build 050: reconcile earlier read-only Samsung Nike-L kernel/DTB reports.

Only existing provenance reports are parsed. No firmware, device, QEMU or
vendor build scripts are executed. An optional original OSS archive is hashed
for identity, but it is not extracted or interpreted as a live-device dump.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


DTB_SHA256 = "9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2"
UIMAGE_SHA256 = "6603f3f5082d6ef74471f9233ce17063658daf10e1d9440a8a9c75749a5e72b2"
OSS_ARCHIVE_SHA256 = "3e38ad1baf54be8ed91c1c18b2c3137692c28e01ca894db9690f632a1fbd3bad"
MAX_JSON_BYTES = 4 * 1024 * 1024


def load_report(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError(f"Missing, linked or oversized report: {path.name}")
    raw = path.read_bytes()
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError(f"Report must be a JSON object: {path.name}")
    return obj, hashlib.sha256(raw).hexdigest()


def archive_hash(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Original OSS archive must be a regular, non-symlinked file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != OSS_ARCHIVE_SHA256:
        raise ValueError("Original Samsung OSS archive SHA-256 mismatch")
    return {"filename": path.name, "sha256": actual, "identity_verified": True,
            "contents_reanalysed": False}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def matching_nodes(tree, category, compatible):
    nodes = tree.get("summary", {}).get("hardware_categories", {}).get(category, [])
    return [node for node in nodes if compatible in node.get("compatible", [])]


def source_reference(source, category, compatible):
    found = [entry for entry in source.get("compatibility_references", {}).get(category, [])
             if entry.get("compatible") == compatible]
    require(len(found) == 1, f"Missing/ambiguous original source reference: {compatible}")
    entry = found[0]
    return {"classification": entry.get("classification"),
            "kernel_paths": entry.get("kernel_references", [])[:12],
            "media_paths": entry.get("media_references", [])[:12],
            "source_code_examined_in_this_build": False}


def build_evidence(hardware, source, components, kernel, graphics, safety, android_gap):
    require(hardware.get("type") == "offline_hardware_device_tree_report", "Wrong hardware report")
    require(hardware.get("dtb_bundle_sha256") == DTB_SHA256, "Reference DTB hash mismatch")
    require(source.get("dtb_bundle_sha256") == DTB_SHA256, "Source DTB provenance mismatch")
    require(graphics.get("source_fdt_bundle_sha256") == DTB_SHA256, "Graphics DTB provenance mismatch")
    require(source.get("source_kernel_version") == "4.1.10", "Unexpected legacy kernel version")
    require(kernel.get("uimage_sha256") == UIMAGE_SHA256, "Kernel payload provenance mismatch")
    require(graphics.get("source_kernel_uimage_sha256") == UIMAGE_SHA256, "Graphics kernel provenance mismatch")
    require(safety.get("status") == "BLOCKED", "Expected blocked recovery baseline")

    files = components.get("files", [])
    uimages = [x for x in files if x.get("name") == "uImage"]
    require(len(uimages) == 1 and uimages[0].get("sha256") == UIMAGE_SHA256,
            "Missing/mismatched stock uImage")
    header = uimages[0].get("uimage", {})
    require(header.get("valid") is True and header.get("arch_id") == 2
            and header.get("name") == "Linux-4.1.10", "Legacy ARM image identity mismatch")
    require(header.get("header_crc_valid") is True and header.get("payload_crc_valid") is True,
            "uImage checksum not validated in baseline")
    require(kernel.get("version_from_banner") == "4.1.10", "Kernel banner mismatch")

    trees = hardware.get("trees", [])
    require(len(trees) == 2 and hardware.get("device_trees_found") == 2,
            "Expected exactly two Samsung reference FDTs")
    require({x.get("offset_bytes") for x in trees} == {0, 86016}, "Unexpected FDT offsets")
    dtb_profiles = []
    for tree in trees:
        root = tree.get("summary", {}).get("root_compatible", [])
        require("samsung,sdp-nikel" in root, "Unexpected reference SoC family")
        cpus = matching_nodes(tree, "cpu", "arm,cortex-a57")
        require(len(cpus) == 4, "Four Cortex-A57 reference CPU nodes not proven")
        require(len(matching_nodes(tree, "gpu", "arm,mali-midgard")) == 1,
                "Missing reference Mali node")
        require(len(matching_nodes(tree, "display", "samsung,sdp-drm")) == 1,
                "Missing Samsung DRM node")
        dtb_profiles.append({
            "offset_bytes": tree["offset_bytes"],
            "sha256": tree.get("dtb_sha256"),
            "firmware_ram_label": tree["summary"].get("memory_profile_label"),
            "memory_reg_advertised_mib": tree["summary"].get("memory_reg", {}).get("sum_advertised_mib"),
            "cortex_a57_nodes": len(cpus),
            "bootargs_safe_subset": tree["summary"].get("bootargs_safe_subset", []),
        })

    relevant = {
        "gpu": ("gpu", "arm,mali-midgard"),
        "display_drm": ("display", "samsung,sdp-drm"),
        "display_panel": ("display", "samsung,sdp1202-panel"),
        "display_frc": ("display", "samsung,sdp-frc-l"),
        "hdmi": ("display", "samsung,sdp-hdmi"),
        "video_decoder": ("video", "samsung,sdp-mfc"),
        "audio": ("audio", "samsung,sdp-mc-audio"),
        "input_ir": ("input", "samsung,sdp-mc-irb"),
        "storage": ("storage", "samsung,sdp-mmc"),
    }
    peripherals = {}
    for alias, (category, compatible) in relevant.items():
        peripherals[alias] = {
            "dt_compatible": compatible,
            "reference_profiles_containing_node": sum(bool(matching_nodes(t, category, compatible)) for t in trees),
            "source": source_reference(source, category, compatible),
            "confirmed_on_target_tv": False,
            "driver_ported_to_linux_6_6": False,
        }

    security_artifacts = {x.get("name"): x.get("sha256") for x in files
                          if x.get("name") in {"sign.bin", "secos.bin", "secos_drv.bin", "seret.bin"}}
    require({"sign.bin", "secos.bin", "seret.bin"}.issubset(security_artifacts),
            "Missing documented security artifacts")
    gates = safety.get("gates", [])
    require(len(gates) >= 8 and all(not g.get("verified", False) for g in gates),
            "Unresolved boot/recovery gates were unexpectedly changed")

    selected_android = {}
    if android_gap is not None:
        require(android_gap.get("kernel_version") == "4.1.10", "Android gap config kernel mismatch")
        require(android_gap.get("defconfig_reference") == "Nike.M-Tizen_release_defconfig",
                "Android gap check must remain explicitly Nike.M, not Nike.L")
        entries = android_gap.get("essential_sample", []) + android_gap.get("supporting_features", [])
        selected_android = {s["symbol"]: s.get("actual") for s in entries if s.get("symbol") in {
            "CONFIG_ANDROID_BINDER_IPC", "CONFIG_SECURITY_SELINUX", "CONFIG_ION",
            "CONFIG_SECCOMP_FILTER", "CONFIG_CGROUPS", "CONFIG_BPF_SYSCALL"}}

    return {
        "type": "q60t_build050_reference_hardware_evidence",
        "build": "050",
        "status": "REFERENCE_IDENTIFIED_LIVE_TV_UNVERIFIED",
        "target_model_reported_by_user": "GQ50Q60TGUXZG",
        "reference_scope": "T-NKLDEUC 2743.0, earlier 55-inch firmware extraction",
        "original_oss_archive_scanned_in_this_execution": False,
        "dtb_bundle_sha256": DTB_SHA256,
        "stock_kernel_sha256": UIMAGE_SHA256,
        "soc": {"dt_compatible": "samsung,sdp-nikel", "vendor_family": "Samsung SDP Nike-L",
                "exact_chip_id_verified": False, "actual_target_board_identified": False},
        "cpu": {"reference_dtb_cortex_a57_count": 4, "reference_isa": "ARMv8-A (AArch64-capable)",
                "running_stock_kernel_image_arch": "ARM32 (U-Boot IH_ARCH_ARM=2)",
                "live_cpu_midr_verified": False, "aarch64_boot_contract_verified": False},
        "reference_profiles": dtb_profiles,
        "boot": {"legacy_image": {"name": header["name"], "arch_id": header["arch_id"],
                                   "load_address": header.get("load_address"),
                                   "entry_address": header.get("entry_address"),
                                   "header_crc_valid": header["header_crc_valid"],
                                   "payload_crc_valid": header["payload_crc_valid"]},
                 "security_named_components": security_artifacts,
                 "kernel_security_symbol_strings": kernel.get("security_symbols_found", []),
                 "stock_signature_verification_demonstrated": False,
                 "bootloader_authentication_policy_verified": False,
                 "nonpersistent_boot_demonstrated": False,
                 "recovery_verified": False},
        "peripherals": peripherals,
        "android_kernel": {"sample_nike_m_defconfig_symbols": selected_android,
                           "actual_nike_l_config_verified": False,
                           "legacy_android_policy_and_abi_validated": False,
                           "linux_6_6_samsung_drivers_validated": False,
                           "android14_on_samsung_tested": False,
                           "qemu_arm64_test_is_not_samsung_hardware_proof": True},
        "safety_gates": [{"name": g.get("name"), "verified": False} for g in gates],
        "safe_to_flash": False,
        "next_steps": ["Verify exact 50-inch board, CPU MIDR, RAM and GPU ID with lawful read-only access",
                       "Inspect original vendor source and immutable 6.6 tree side by side",
                       "Map bootloader acceptance/signature behavior without modifying TV",
                       "Port clock/interrupt/storage prerequisites before graphics and Android HALs",
                       "Prove independent recovery and nonpersistent boot before any device boot attempt"],
    }


DEFAULT_PATHS = {
    "hardware": "reports/hardware_2743.0_build004_final.json",
    "source": "reports/source_compat_build011.json",
    "components": "reports/decrypted_components.json",
    "kernel": "reports/kernel_2743.0.json",
    "graphics": "reports/graphics_build005.json",
    "safety": "reports/boot_safety_build005.json",
    "android_gap": "reports/kernel_gap_build015_bootlab.json",
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in DEFAULT_PATHS.items():
        parser.add_argument("--" + name.replace("_", "-"), default=default)
    parser.add_argument("--original-oss-archive", help="Optional hash-only identity check, never extracted")
    parser.add_argument("--output", required=True, help="New JSON file; existing files are not replaced")
    args = parser.parse_args(argv)
    try:
        loaded = {}
        digests = {}
        for name in DEFAULT_PATHS:
            obj, digest = load_report(getattr(args, name))
            loaded[name] = obj
            digests[DEFAULT_PATHS[name]] = digest
        report = build_evidence(*(loaded[name] for name in DEFAULT_PATHS))
        report["source_report_sha256"] = digests
        if args.original_oss_archive:
            report["original_oss_archive"] = archive_hash(args.original_oss_archive)
        output = Path(args.output)
        data = (json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
        with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
            stream.write(data)
        print(json.dumps({"status": report["status"], "output": str(output),
                          "safe_to_flash": False, "reference_profiles": len(report["reference_profiles"])}))
        return 0
    except (ValueError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"Build 050 evidence refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
