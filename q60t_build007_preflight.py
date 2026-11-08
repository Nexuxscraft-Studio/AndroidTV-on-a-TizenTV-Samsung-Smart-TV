#!/usr/bin/env python3
"""Combine Samsung Q60T porting evidence into a fail-closed host report.

No Android compilation, TV communication, firmware changes or commands on
the target are performed by this program.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import q60t_gpu_strategy
import q60t_kernel_build
import q60t_portcheck
import q60t_source_provenance


def assess(project_root: Path, *, archive: Path | None = None,
           source: Path | None = None, config: Path | None = None,
           compiler_prefix: str | None = None, output: Path | None = None,
           expected_archive_sha256: str | None = None) -> dict:
    portdir = project_root / "porting"
    board = portdir / "device/samsung/nikel/BoardConfig.mk"
    product = portdir / "device/samsung/nikel/lineage_nikel.mk"
    if not board.is_file() or not product.is_file():
        raise ValueError("Missing device tree files")
    board_text = board.read_text(encoding="utf-8")
    product_text = product.read_text(encoding="utf-8")
    # A missing fail-closed guard is a tooling error, not a release signal.
    if "$(error" not in board_text:
        raise ValueError("BoardConfig build guard removed without verified boot review")
    if "PRODUCT_IS_ATV := true" not in product_text:
        raise ValueError("Android TV product flag missing")
    if "device/samsung/nikel/device.mk" not in product_text:
        raise ValueError("Device product inheritance missing")

    hardware = json.loads((project_root / "reports/hardware_2743.0_build004_final.json").read_text())
    kernel_data = json.loads((project_root / "reports/kernel_build005.json").read_text())
    port = q60t_portcheck.check_port(portdir,
                                   project_root / "reports/hardware_2743.0_build004_final.json")
    graphics = q60t_gpu_strategy.strategy_report(hardware, kernel_data, source)
    provenance = q60t_source_provenance.candidate_report(archive, source, expected_archive_sha256)
    kernel = q60t_kernel_build.make_plan(source, config, compiler_prefix, output)
    return {
        "type": "q60t_build007_integrated_host_preflight",
        "status": "BLOCKED",
        "target_model": "GQ50Q60TGUXZG",
        "firmware": "T-NKLDEUC 2743.0",
        "checks": {
            "device_board_explicitly_fails_closed": True,
            "android_tv_product_is_declared": True,
            "official_model_and_firmware_reference_verified": port["official_exact_model_and_firmware_verified"],
            "port_gates_satisfied": port["blocker_count"] == 0,
            "kernel_binary_reproduced": False,
            "samsung_gpl_source_verified_for_2743": False,
            "mali_vendor_graphics_integrated": graphics["paths"]["legacy_vendor_kbase"]["ready"],
            "panfrost_drm_graphics_integrated": graphics["paths"]["upstream_panfrost_drm"]["ready"],
            "reversible_boot_proven": False,
        },
        "port_blockers": [g["name"] for g in port["gates"] if not g["passed"]],
        "kernel": kernel,
        "source_candidate": provenance,
        "graphics": graphics,
        "boot_or_flash_attempted": False,
        "android_build_attempted": False,
        "flash_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build 007 host-only Android TV readiness gate")
    p.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent)
    p.add_argument("--source-archive", type=Path)
    p.add_argument("--source", type=Path)
    p.add_argument("--config", type=Path)
    p.add_argument("--cross-compile")
    p.add_argument("--output-dir", type=Path)
    p.add_argument("--expected-archive-sha256")
    p.add_argument("--report", type=Path, help="create new JSON; never overwrite")
    a = p.parse_args(argv)
    try:
        result = assess(a.project_root, archive=a.source_archive, source=a.source,
                        config=a.config, compiler_prefix=a.cross_compile,
                        output=a.output_dir, expected_archive_sha256=a.expected_archive_sha256)
        content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if a.report:
            with a.report.open("x", encoding="utf-8") as out:
                out.write(content)
        else:
            print(content, end="")
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Build-007-Prüfung fehlgeschlagen: {error}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
