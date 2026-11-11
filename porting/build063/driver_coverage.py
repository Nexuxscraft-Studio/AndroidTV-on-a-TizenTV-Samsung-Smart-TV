#!/usr/bin/env python3
"""Build 063 - static coverage matrix of the driver bring-up scaffolds.

Read-only. Checks that each subsystem has its expected artifacts (skeleton /
config fragment / DTS fixture / port doc) and extracts the key CONFIG symbols
from the fragments. Emits JSON. Makes NO claim that any driver works or boots.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# subsystem -> expected artifact paths (relative to the build063 dir)
SUBSYSTEMS = {
    "display": {
        "skeleton": ["kernel/display/sdp_drm.c", "kernel/display/Kconfig",
                     "kernel/display/Makefile"],
        "config": ["configs/nikel-display.config"],
        "dts": ["dts/sdp-nikel-display-disabled.dts"],
        "doc": ["docs/DISPLAY_PORT.md"],
        "kind": "custom-skeleton",
    },
    "gpu": {
        "skeleton": [],  # Panfrost is upstream; no custom kernel driver
        "config": ["configs/nikel-gpu.config"],
        "dts": ["dts/sdp-nikel-gpu-panfrost-disabled.dts"],
        "doc": ["docs/GPU_INTEGRATION.md"],
        "kind": "upstream-panfrost",
    },
    "cpu_dvfs": {
        "skeleton": [],  # cpufreq-dt is upstream; DT-driven
        "config": ["configs/nikel-cpu.config"],
        "dts": ["dts/sdp-nikel-cpu-dvfs-disabled.dts"],
        "doc": ["docs/CPU_THERMAL_SOC_PORT.md"],
        "kind": "upstream-cpufreq-dt",
    },
    "core_soc": {
        "skeleton": [],  # Build 059 provides uart/clk/gpio; this enables nodes
        "config": ["configs/nikel-soc-extra.config"],
        "dts": [],
        "doc": ["docs/CPU_THERMAL_SOC_PORT.md"],
        "kind": "enable-build059-nodes",
    },
}

CONFIG_RE = re.compile(r"^(CONFIG_\w+)=(.+)$")


def parse_config(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        m = CONFIG_RE.match(line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def coverage(root: Path) -> dict:
    matrix = {}
    for name, spec in SUBSYSTEMS.items():
        present, missing = [], []
        for group in ("skeleton", "config", "dts", "doc"):
            for rel in spec[group]:
                (present if (root / rel).is_file() else missing).append(rel)
        configs: dict[str, str] = {}
        for rel in spec["config"]:
            configs.update(parse_config(root / rel))
        matrix[name] = {
            "kind": spec["kind"],
            "artifacts_present": present,
            "artifacts_missing": missing,
            "complete": not missing,
            "config_symbols": configs,
            "status": "SCAFFOLD_PRESENT" if not missing else "INCOMPLETE",
        }
    return {
        "type": "driver_coverage_build063",
        "subsystems": matrix,
        "all_scaffolds_present": all(v["complete"] for v in matrix.values()),
        "disclaimer": "Static artifact check only. SCAFFOLD_PRESENT means the "
        "files exist and are compile-gated in CI; it does NOT mean a driver "
        "works, initialises hardware, or boots. No flash. BoardConfig.mk "
        "$(error) lock stays.",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                    help="build063 directory (default: this script's dir)")
    args = ap.parse_args(argv)
    print(json.dumps(coverage(args.root), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
