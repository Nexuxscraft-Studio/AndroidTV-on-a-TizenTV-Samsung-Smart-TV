#!/usr/bin/env python3
"""Static Samsung Nike-L GPU port strategy; no driver execution or build.

Distinct paths (legacy kbase vs upstream Panfrost DRM) must not be conflated.
The vendor's /dev/mali0 userspace ABI is not the same as a DRM render node.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from q60t_graphics import graphics_preflight, inspect_elf


MALI_SOURCE_PATHS = (
    "drivers/gpu/arm/midgard",
    "drivers/gpu/arm/bifrost",
    "drivers/gpu/arm/mali",
    "drivers/gpu/drm/panfrost",
)


def driver_source_clues(source: Path | None) -> dict:
    if source is None:
        return {"source_supplied": False, "paths_present": [], "drivers_built": False}
    if not source.is_dir() or source.is_symlink():
        raise ValueError("Driver source must be an existing directory, not a symlink")
    found = [p for p in MALI_SOURCE_PATHS if (source / p).is_dir()
             and not (source / p).is_symlink()]
    return {"source_supplied": True, "paths_present": found, "drivers_built": False}


def strategy_report(hardware: dict, kernel: dict, source: Path | None = None,
                    libmali: Path | None = None, module: Path | None = None) -> dict:
    userspace_info = inspect_elf(libmali) if libmali else None
    module_info = inspect_elf(module) if module else None
    baseline = graphics_preflight(hardware, kernel, userspace_info, module_info)
    clues = driver_source_clues(source)
    profiles = baseline["reference_profiles_by_dtb_offset"]
    has_gpu = all(bool(p["gpu"]) for p in profiles.values())
    has_display = all(bool(p["samsung_display_drm"]) for p in profiles.values())

    vendor_conditions = {
        "original_firmware_gpu_node_identified_in_both_profiles": has_gpu,
        "original_display_node_identified_in_both_profiles": has_display,
        "candidate_kbase_source_tree_seen": bool(set(clues["paths_present"]) &
                                                set(MALI_SOURCE_PATHS[:3])),
        "arm32_module_elf_supplied": bool(module_info and module_info["machine"] == "ARM32"),
        "module_vermagic_matches_4_1_10": bool(module_info and
            (module_info.get("module_vermagic_string") or "").startswith("4.1.10")),
        "arm32_libmali_elf_supplied": bool(userspace_info and userspace_info["machine"] == "ARM32"),
        "binary_driver_and_userspace_abi_verified_together": False,
        "android_buffer_allocator_integrated": False,
        "android_composer_hal_integrated": False,
        "panel_scanout_and_sync_fences_tested": False,
    }
    panfrost_conditions = {
        "kernel_source_contains_panfrost_drm": "drivers/gpu/drm/panfrost" in clues["paths_present"],
        "target_kernel_drm_panfrost_backport_compiled": False,
        "compatible_drm_render_and_display_pipeline_verified": False,
        "android_mesa_egl_and_gralloc_integrated": False,
        "samsung_panel_scanout_verified": False,
    }
    return {
        "type": "q60t_android_gpu_port_strategy",
        "status": "BLOCKED",
        "reference_firmware": "T-NKLDEUC 2743.0",
        "reference_hardware_sha256": baseline["source_fdt_bundle_sha256"],
        "source_scan": clues,
        "gpu_identity": {
            "vendor_dt_compatible": "arm,mali-midgard",
            "external_research_candidate": "Mali-G51 / Bifrost r11p0",
            "exact_hardware_revision_verified": False,
        },
        "paths": {
            "legacy_vendor_kbase": {
                "interface": "/dev/mali0",
                "checks": vendor_conditions,
                "ready": False,
                "limitation": "Kernel kbase, matching userspace ABI and Android composer/gralloc must be reconciled.",
            },
            "upstream_panfrost_drm": {
                "interface": "/dev/dri/renderD* (new DRM driver required)",
                "checks": panfrost_conditions,
                "ready": False,
                "limitation": "Panfrost is not a drop-in EGL replacement for the Samsung 4.1.10 kbase stack.",
            },
        },
        "android_14_requirement": "Hardware Composer (AIDL composer3 / relevant compatibility path), allocator and display sync",
        "source_links": [
            "https://developer.arm.com/Downloads/-/Bifrost%20Mali%203rd%20Gen%20GPU%20Architecture",
            "https://source.android.com/docs/core/graphics/aidl-hwc",
            "https://docs.mesa3d.org/drivers/panfrost.html",
        ],
        "private_device_exam_performed": False,
        "android_bootable": False,
        "flash_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Q60T Mali graphics source-path strategy; host-only")
    p.add_argument("--hardware-report", type=Path, required=True)
    p.add_argument("--kernel-report", type=Path, required=True)
    p.add_argument("--kernel-source", type=Path)
    p.add_argument("--libmali", type=Path)
    p.add_argument("--module", type=Path)
    p.add_argument("--report", type=Path, help="create only; never overwrite")
    a = p.parse_args(argv)
    try:
        hardware = json.loads(a.hardware_report.read_text(encoding="utf-8"))
        kernel = json.loads(a.kernel_report.read_text(encoding="utf-8"))
        result = strategy_report(hardware, kernel, a.kernel_source, a.libmali, a.module)
        payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if a.report:
            with a.report.open("x", encoding="utf-8") as output:
                output.write(payload)
        else:
            print(payload, end="")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"GPU-Strategieprüfung fehlgeschlagen: {error}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
