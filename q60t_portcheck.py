#!/usr/bin/env python3
"""Check offline hardware-profile correspondence and Android-TV port gates.

This tool never authorizes flashing, and deliberately does not build images.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REQUIRED_GATES = {
    "exact_model_code": "50-inch TV model code and Samsung support match not verified",
    "actual_tv_ram_profile": "Actual TV RAM/DTB variant not measured",
    "verified_kernel_source_and_config": "Matching Samsung GPL kernel source/config missing",
    "kernel_build_reproduced": "Kernel build not reproducible",
    "independent_reversible_boot_path": "Reversible boot path not demonstrated",
    "verified_recovery_method": "Recovery/rollback path not demonstrated",
    "android_graphics_hal_works": "Android hardware composer/gralloc not working",
    "android_audio_hal_works": "Android audio HAL not working",
    "android_video_codec_hal_works": "Android codec HAL not working",
    "input_remote_control_works": "Remote/input integration not working",
}
REFERENCE_DTB_BUNDLE = "9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2"
REFERENCE_TARGET_MODEL = "GQ50Q60TGUXZG"
TRACKED_INTERFACES = {
    "mali_gpu": "/soc/sdpgpu@00500000",
    "infrared_irb": "/soc/mcirb",
    "infrared_irs": "/soc/mcirs",
    "hdmi_cec": "/soc/cecif",
}


def check_port(project: Path, hw_report: Path | None = None) -> dict:
    manifest = json.loads((project / "port-state.json").read_text(encoding="utf-8"))
    supplied_model = manifest.get("exact_model_code")
    if supplied_model is not None and supplied_model != REFERENCE_TARGET_MODEL:
        raise ValueError("Model code does not match the documented 50-inch target")
    model_evidence_path = project / "model-evidence.json"
    model_evidence_valid = False
    if model_evidence_path.is_file():
        model_evidence = json.loads(model_evidence_path.read_text(encoding="utf-8"))
        model_evidence_valid = (
            model_evidence.get("model_code") == REFERENCE_TARGET_MODEL
            and model_evidence.get("official_model_support_page") ==
            "https://www.samsung.com/de/support/model/GQ50Q60TGUXZG/"
            and model_evidence.get("official_firmware_family") == "T-NKLDEUC"
            and model_evidence.get("official_firmware_version") == "2743.0"
            and model_evidence.get("official_firmware_entry_id") == 7701730)
    profiles = sorted(project.glob("profiles/*.json"))
    if len(profiles) != 2:
        raise ValueError("Expected exactly two research profiles")
    parsed_profiles = [json.loads(p.read_text(encoding="utf-8")) for p in profiles]
    ids = [p["id"] for p in parsed_profiles]
    if set(ids) != {"nikel-2g", "nikel-1.5g"}:
        raise ValueError("Unexpected hardware-profile IDs")
    if any(p["usable_for_flashing"] is not False for p in parsed_profiles):
        raise ValueError("Research profiles may not authorize flashing")
    report = None
    statuses = {}
    if hw_report is not None:
        report = json.loads(hw_report.read_text(encoding="utf-8"))
        if (report.get("dtb_bundle_sha256") != REFERENCE_DTB_BUNDLE
                or report.get("device_trees_found", 0) < 2):
            raise ValueError("Hardware report does not match verified reference DTB bundle")
        by_offset = {x["offset_bytes"]: x for x in report["trees"]}
        for profile in parsed_profiles:
            entry = by_offset.get(profile["dtb_offset_bytes"])
            if entry is None or entry["dtb_sha256"] != profile["dtb_sha256"]:
                raise ValueError("Hardware profile does not match reference DTB")
            reg = entry.get("summary", {}).get("memory_reg")
            if (not isinstance(reg, dict)
                    or reg.get("sum_advertised_mib") != profile["fdt_memory_reg_advertised_mib"]
                    or len(reg.get("ranges", [])) != profile["fdt_memory_reg_range_count"]):
                raise ValueError("Reference memory/reg ranges do not match hardware profile")
            observed = {
                node["path"]: node.get("dt_status", "not_reported")
                for category in entry.get("summary", {}).get("hardware_categories", {}).values()
                for node in category
                if isinstance(node, dict) and isinstance(node.get("path"), str)
            }
            statuses[profile["id"]] = {
                component: observed.get(path, "not_reported")
                for component, path in TRACKED_INTERFACES.items()
            }
    gates = [{"name": name, "reason": reason,
              "passed": (supplied_model == REFERENCE_TARGET_MODEL and model_evidence_valid)
              if name == "exact_model_code" else
              (isinstance(manifest.get(name), str)
               and bool(manifest.get(name).strip())) if name == "actual_tv_ram_profile"
              else manifest.get(name) is True}
             for name, reason in REQUIRED_GATES.items()]
    missing = [g for g in gates if not g["passed"]]
    actual_profile = manifest.get("actual_tv_ram_profile")
    if actual_profile is not None and actual_profile not in ids:
        raise ValueError("Actual TV RAM profile must match a known reference ID")
    # Human sign-off plus firmware signature/recovery evaluation is still
    # required even if a future manifest marks every gate as passed.
    return {
        "type": "offline_lineage_atv_port_preflight",
        "target": manifest.get("target"),
        "status": "BLOCKED" if missing else "MANUAL_REVIEW_REQUIRED",
        "gates": gates,
        "blocker_count": len(missing),
        "profiles": ids,
        "reference_hardware_verified": report is not None,
        "official_exact_model_and_firmware_verified": model_evidence_valid,
        "firmware_dt_status_by_profile": statuses,
        "flash_authorized": False,
        "image_build_enabled": False,
        "device_contacted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q60T Android TV: offline preflight")
    parser.add_argument("--project", type=Path, default=Path("porting"))
    parser.add_argument("--hardware-report", type=Path)
    parser.add_argument("--output", type=Path, help="new local JSON report (never overwrite)")
    args = parser.parse_args(argv)
    try:
        result = check_port(args.project, args.hardware_report)
        serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as output:
                output.write(serialized)
        else:
            print(serialized, end="")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Port-Prüfung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    # 1 means expected, safe blocked state; 0 needs human review, not flash.
    return 1 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
