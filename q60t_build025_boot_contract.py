#!/usr/bin/env python3
"""Read-only boot-contract inventory of two *reference* Samsung Nike-L DTBs.

Analyzes the original DTB bundle, not the running TV. This is evidence about
CPU enable methods, PSCI, interrupts and timer declarations, NOT proof that an
AArch64 image can enter the TV boot chain. Never writes firmware or devices.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


REFERENCE_DTB_SHA256 = "9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2"
KNOWN_PROFILES = (
    (0, "0189cc94fe8dd7d016462f22e9f8e965fe328cbc901066c8955f26130f86ab61", "nikel-2g"),
    (86016, "36e8e77898ce2e253ffd959f96d0fb1d27e3fcf58887325d668b190ac8dcd79e", "nikel-1.5g"),
)
MAX_FILE_BYTES = 32 * 1024 * 1024


def safe_strings(raw: bytes) -> list[str]:
    if not raw or len(raw) > 4096 or not raw.endswith(b"\x00"):
        return []
    values = raw.split(b"\x00")[:-1]
    if any(len(v) > 120 or any(c < 32 or c > 126 for c in v) for v in values):
        return []
    return [v.decode("ascii") for v in values if v]


def inspect_nodes(nodes: dict[str, dict[str, bytes]]) -> dict:
    """Only publish explicit, generic device properties; no bootargs or IDs."""
    if not isinstance(nodes, dict) or "/" not in nodes:
        raise ValueError("Missing FDT root")
    board = safe_strings(nodes["/"].get("compatible", b""))
    cpus = []
    psci = []
    interrupt_controllers = []
    timers = []
    for path, props in nodes.items():
        if not isinstance(path, str) or not isinstance(props, dict):
            raise ValueError("Malformed FDT node")
        compatibles = safe_strings(props.get("compatible", b""))
        if path.startswith("/cpus/") and path.split("/")[-1].startswith("cpu@"):
            cpus.append({"path": path, "compatible": compatibles[:4],
                         "enable_method": safe_strings(props.get("enable-method", b""))[:1]})
        if any(x.startswith("arm,psci") for x in compatibles) or path == "/psci":
            psci.append({"path": path, "compatible": compatibles[:3],
                         "method": safe_strings(props.get("method", b""))[:1]})
        if any("gic" in x for x in compatibles):
            interrupt_controllers.append({"path": path, "compatible": compatibles[:4]})
        if any("timer" in x for x in compatibles):
            timers.append({"path": path, "compatible": compatibles[:4]})
    cpus.sort(key=lambda entry: entry["path"])
    if len(cpus) > 64 or len(psci) > 32 or len(interrupt_controllers) > 48 or len(timers) > 48:
        raise ValueError("Unexpected number of critical boot nodes")
    return {
        "board_compatible": board[:6],
        "cpu_nodes": cpus,
        "cpu_a57_claimed_in_fdt": bool(cpus) and all("arm,cortex-a57" in x["compatible"] for x in cpus),
        "psci_nodes": psci,
        "psci_declared_in_fdt": bool(psci),
        "interrupt_controller_nodes": interrupt_controllers,
        "timer_nodes": timers,
        "dtb_is_running_tv": False,
        "aarch64_exception_level_verified": False,
        "bootloader_aarch64_handoff_verified": False,
    }


def analyze_bundle(blob: bytes) -> dict:
    if not blob or len(blob) > MAX_FILE_BYTES or hashlib.sha256(blob).hexdigest() != REFERENCE_DTB_SHA256:
        raise ValueError("Bundle does not match the analyzed Samsung 2743.0 reference")
    # Import only after validating the reference bundle hash. The already
    # tracked helper parses FDT structure within explicit size limits.
    import q60t_hardware
    profiles = []
    for offset, expected_hash, label in KNOWN_PROFILES:
        if offset + 8 > len(blob) or blob[offset:offset + 4] != b"\xd0\x0d\xfe\xed":
            raise ValueError(f"Missing FDT header for {label}")
        size = struct.unpack_from(">I", blob, offset + 4)[0]
        if size < 40 or size > 2 * 1024 * 1024 or offset + size > len(blob):
            raise ValueError(f"Invalid FDT length for {label}")
        dtb = blob[offset:offset + size]
        if hashlib.sha256(dtb).hexdigest() != expected_hash:
            raise ValueError(f"FDT hash does not match {label}")
        tree = q60t_hardware.parse_fdt(dtb)
        boot_contract = inspect_nodes(tree["nodes"])
        memory = q60t_hardware.memory_reg_map(tree["nodes"])
        profiles.append({"profile": label, "offset_bytes": offset,
                         "dtb_sha256": expected_hash,
                         "node_count": len(tree["nodes"]),
                         "boot_contract": boot_contract,
                         "firmware_advertised_memory_mib": memory.get("sum_advertised_mib") if memory else None})
    return {
        "type": "q60t_build025_reference_fdt_arm64_boot_contract",
        "reference_model": "GQ55Q60TGUXZG",
        "target_model": "GQ50Q60TGUXZG",
        "bundle_sha256": REFERENCE_DTB_SHA256,
        "profiles": profiles,
        "status": "REFERENCE_FIRMWARE_ONLY_DEVICE_BOOT_UNVERIFIED",
        "actual_tv_profile_identified": False,
        "arm64_hardware_boot_verified": False,
        "safe_to_flash": False,
        "note": "No PSCI token, if absent, is not proof PSCI is unavailable. "
                "No DTB property proves secure boot acceptance or a safe recovery route.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Offline PSCI/CPU/GIC/timer boot-contract audit")
    p.add_argument("--dtb", type=Path, required=True, help="Reference 2743.0 dtb.bin, no device access")
    p.add_argument("--output", type=Path, help="Create-only report, never overwrite")
    a = p.parse_args(argv)
    try:
        if not a.dtb.is_file() or a.dtb.is_symlink() or a.dtb.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("DTB must be a bounded, regular file")
        report = analyze_bundle(a.dtb.read_bytes())
        content = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if a.output:
            with a.output.open("x", encoding="utf-8") as stream:
                stream.write(content)
        else:
            print(content, end="")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Build-025-Boot-Contract-Prüfung abgebrochen: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
