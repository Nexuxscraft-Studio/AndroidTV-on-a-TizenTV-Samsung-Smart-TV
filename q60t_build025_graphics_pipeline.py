#!/usr/bin/env python3
"""Build 025: Samsung Nike-L GPU/display -> Android HAL dependency audit.

Reads existing *reference* firmware reports; optionally inspects specific
legacy driver files for kernel API symbols. Does not copy proprietary code,
compile modules, contact the TV, or claim a usable Android display pipeline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


DTB_BUNDLE_SHA256 = "9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2"
MAX_REPORT_BYTES = 4 * 1024 * 1024
MAX_SOURCE_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_SOURCE_BYTES = 64 * 1024 * 1024
MAX_MATCH_FILES = 24

# Hardware candidates actually seen in firmware DTB reports. Labels are
# engineering categories, not kernel module or HAL implementation names.
DEVICES = (
    ("gpu", "arm,mali-midgard", "gpu_render"),
    ("display", "samsung,sdp-drm", "display_controller"),
    ("display", "samsung,sdp1202-panel", "panel"),
    ("display", "samsung,sdp-frc-l", "frame_processing"),
    ("display", "samsung,sdp-hdmi", "hdmi"),
    ("video", "samsung,sdp-mfc", "video_decode"),
    ("audio", "samsung,sdp-mc-audio", "audio"),
    ("input", "samsung,sdp-mc-irb", "remote_input"),
    ("input", "samsung,sdp-mc-cecif", "hdmi_cec"),
)

# Search for *references*, not proof of usage or support. Old Kbase/ION
# sources may use entirely different APIs from modern Linux 6.6 / Android 14.
INTERFACE_PATTERNS = {
    "legacy_ion": r"\b(?:ion_alloc|ion_import_dma_buf|ion_share_dma_buf_fd|ion_client_create|ion_handle)\b",
    "dma_buf": r"\b(?:dma_buf_attach|dma_buf_map_attachment|dma_buf_get|dma_buf_export|dma_buf_begin_cpu_access)\b",
    "sync_fence": r"\b(?:sync_file_create|sync_fence_create|dma_fence_init|sync_fence_wait|dma_fence_wait)\b",
    "drm_kms": r"\b(?:drm_mode_config_init|drm_connector_init|drm_crtc_init|drm_dev_register|drm_atomic_helper|drm_vblank_init)\b",
    "legacy_fb": r"\b(?:register_framebuffer|fb_register_client|fb_info)\b",
    "clocks_power": r"\b(?:clk_prepare_enable|pm_runtime_enable|pm_runtime_get_sync|regulator_enable|reset_control_deassert)\b",
    "iommu_memory": r"\b(?:iommu_attach_device|iommu_map|of_reserved_mem_device_init|dma_map_single|dma_alloc_coherent)\b",
    "irq": r"\b(?:devm_request_irq|request_threaded_irq|request_irq)\b",
    "of_platform": r"\b(?:of_device_id|of_match_device|of_property_read_u32|of_get_named_gpio|platform_driver_register)\b",
}
PATTERNS = {name: re.compile(expression.encode("ascii")) for name, expression in INTERFACE_PATTERNS.items()}


def read_report(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError("Require an existing, bounded JSON report")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("JSON report must be an object")
    return document


def validate_reports(hardware: dict, source: dict) -> None:
    if hardware.get("dtb_bundle_sha256") != DTB_BUNDLE_SHA256:
        raise ValueError("Hardware source is not the approved reference DTB bundle")
    if source.get("dtb_bundle_sha256") != DTB_BUNDLE_SHA256:
        raise ValueError("Samsung source comparison uses a different firmware DTB")
    if hardware.get("device_trees_found") != 2 or len(hardware.get("trees", [])) != 2:
        raise ValueError("Expected both reference RAM profiles")
    if source.get("source_kernel_version") != "4.1.10":
        raise ValueError("Source compatibility evidence must be Samsung Linux 4.1.10")
    if source.get("source_matches_firmware_2743_0") is not False:
        raise ValueError("Generic source is not proven byte-identical to firmware 2743.0")
    if source.get("type") != "q60t_offline_compatible_source_matrix":
        raise ValueError("Not a Samsung source-compatible evidence report")


def _path_refs(item: dict) -> list[str]:
    return [p for p in item.get("kernel_references", []) + item.get("media_references", [])
            if isinstance(p, str) and p.endswith((".c", ".h"))][:8]


def legacy_source_matches(source: dict, category: str, compatible: str) -> dict:
    category_rows = source.get("compatibility_references", {}).get(category, [])
    for item in category_rows:
        if isinstance(item, dict) and item.get("compatible") == compatible:
            return {"classification": item.get("classification"),
                    "source_paths": _path_refs(item)}
    return {"classification": "NOT_FOUND_IN_BUILD011_REPORT", "source_paths": []}


def reference_profiles(hardware: dict, category: str, compatible: str) -> list[dict]:
    reports = []
    for tree in hardware["trees"]:
        if not isinstance(tree, dict) or "offset_bytes" not in tree:
            raise ValueError("Malformed reference tree")
        found = []
        categories = tree.get("summary", {}).get("hardware_categories", {})
        for node in categories.get(category, []):
            if compatible in node.get("compatible", []):
                found.append({"path": node.get("path"),
                              "status": node.get("dt_status", "not_reported")})
        reports.append({"offset_bytes": tree["offset_bytes"],
                        "nodes": sorted(found, key=lambda x: (x["path"] or ""))})
    return reports


def safe_source(root: Path, relative: str) -> bytes | None:
    """Read only previously evidenced source paths, no symlinks or traversal."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Source must be a regular directory")
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(x in ("..", ".") for x in rel.parts):
        raise ValueError("Unsafe source path")
    if rel.suffix not in (".c", ".h"):
        return None
    position = root
    for segment in rel.parts:
        position = position / segment
        if position.is_symlink():
            raise ValueError("Refusing symlink inside vendor source")
    if not position.is_file():
        return None
    if position.stat().st_size > MAX_SOURCE_FILE_BYTES:
        raise ValueError("Vendor source too large")
    content = position.read_bytes()
    return content if b"\x00" not in content[:4096] else None


def inspect_source_interfaces(source_root: Path | None, refs: list[str]) -> dict:
    if source_root is None:
        return {"status": "SOURCE_FILES_NOT_SUPPLIED", "files_read": 0,
                "interfaces": {key: [] for key in PATTERNS}}
    if len(refs) > MAX_MATCH_FILES:
        raise ValueError("Too many source files requested")
    findings: dict[str, list[str]] = {key: [] for key in PATTERNS}
    files_read = total_bytes = 0
    for path in sorted(set(refs)):
        content = safe_source(source_root, path)
        if content is None:
            continue
        total_bytes += len(content)
        if total_bytes > MAX_TOTAL_SOURCE_BYTES:
            raise ValueError("Source read exceeded byte limit")
        files_read += 1
        for key, expression in PATTERNS.items():
            if expression.search(content) and len(findings[key]) < 6:
                findings[key].append(path)
    return {"status": "SYMBOL_REFERENCES_ONLY_NO_BUILD_OR_ABI_VERIFICATION",
            "files_read": files_read, "bytes_read": total_bytes,
            "interfaces": findings}


def pipeline_report(hardware: dict, source: dict, vendor_source: Path | None = None) -> dict:
    validate_reports(hardware, source)
    rows = []
    for category, compatible, role in DEVICES:
        paths = legacy_source_matches(source, category, compatible)
        profiles = reference_profiles(hardware, category, compatible)
        statuses = [n["status"] for p in profiles for n in p["nodes"]]
        refs = paths["source_paths"]
        observations = inspect_source_interfaces(vendor_source, refs)
        rows.append({"role": role, "compatible": compatible,
                     "firmware_reference_profiles": profiles,
                     "present_in_both_reference_profiles": all(p["nodes"] for p in profiles),
                     "disabled_in_reference": bool(statuses) and all(s == "disabled" for s in statuses),
                     "legacy_source": paths,
                     "legacy_api_symbol_observations": observations,
                     "modern_kernel_driver_built": False,
                     "real_target_hardware_match": False,
                     "runtime_verified": False})
    stages = [
        {"stage": "gpu_kbase_or_drm_render", "depends_on": ["gpu_render"], "verified": False},
        {"stage": "display_scanout", "depends_on": ["display_controller", "panel", "frame_processing"], "verified": False},
        {"stage": "allocator_mapper", "depends_on": ["gpu_kbase_or_drm_render"], "verified": False},
        {"stage": "dma_buf_and_sync_fence", "depends_on": ["display_scanout", "allocator_mapper"], "verified": False},
        {"stage": "egl_gles", "depends_on": ["gpu_kbase_or_drm_render", "allocator_mapper"], "verified": False},
        {"stage": "android_14_composer3", "depends_on": ["display_scanout", "dma_buf_and_sync_fence"], "verified": False},
        {"stage": "surfaceflinger_visible_frame", "depends_on": ["egl_gles", "android_14_composer3"], "verified": False},
    ]
    return {"type": "q60t_build025_graphics_hal_dependency_evidence",
            "status": "HOST_ONLY_GRAPHICS_AND_HAL_UNVERIFIED",
            "reference_dtb_sha256": DTB_BUNDLE_SHA256,
            "reference_firmware_model": "GQ55Q60TGUXZG",
            "target_model": "GQ50Q60TGUXZG",
            "hardware_rows": rows, "android_display_stages": stages,
            "reference_gpu_name": "arm,mali-midgard (generic DT identifier; GPU revision unknown)",
            "android_14_hal_interfaces": ["android.hardware.graphics.composer3", "android.hardware.graphics.allocator", "android.hardware.graphics.mapper"],
            "hal_sources_built": False,
            "android_display_rendered": False,
            "device_accessed": False,
            "flash_authorized": False,
            "note": "A string in legacy source is not a working Linux 6.6 driver or Android HAL. "
                    "The DTBs are from a 55-inch reference package, not live target hardware."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Samsung Nike-L GPU/display/HAL dependency audit")
    parser.add_argument("--hardware-report", type=Path, required=True)
    parser.add_argument("--legacy-source-report", type=Path, required=True)
    parser.add_argument("--vendor-source", type=Path, help="Optional local Samsung media source directory")
    parser.add_argument("--output", type=Path, help="New JSON report only; existing files are preserved")
    args = parser.parse_args(argv)
    try:
        hardware = read_report(args.hardware_report)
        legacy = read_report(args.legacy_source_report)
        result = pipeline_report(hardware, legacy, args.vendor_source)
        payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.output is None:
            print(payload, end="")
        else:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(payload)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"Build-025-Grafikprüfung abgebrochen: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
