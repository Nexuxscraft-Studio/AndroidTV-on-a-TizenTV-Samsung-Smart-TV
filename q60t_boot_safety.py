#!/usr/bin/env python3
"""Offline firmware/rollback safety checklist. NEVER writes to a TV.

Presence of Samsung signatures, TrustZone components or backups does not
prove that a modified image is authentic, bootable, or recoverable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from q60t_lab import inspect_uimage


REFERENCE_KERNEL_SHA256 = "6603f3f5082d6ef74471f9233ce17063658daf10e1d9440a8a9c75749a5e72b2"
REFERENCE_DTB_SHA256 = "9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2"
COMPONENTS = {"uImage": 64 * 1024 * 1024, "dtb.bin": 32 * 1024 * 1024,
              "sign.bin": 1024 * 1024, "secos.bin": 64 * 1024 * 1024,
              "secos_drv.bin": 64 * 1024 * 1024, "seret.bin": 64 * 1024 * 1024}
BOOT_GATES = {
    "exact_target_hardware_identified": "50-inch target board and RAM profile unverified",
    "bootloader_authentication_policy_verified": "signature/secure boot acceptance not verified",
    "nonpersistent_test_boot_interface_demonstrated": "no independent volatile boot route demonstrated",
    "recovery_entrypoint_verified": "recovery interface not confirmed",
    "known_good_backup_verified": "offline stock backup/restore not validated",
    "rollback_drill_completed_on_spare_hardware": "no tested rollback on equivalent spare board",
    "watchdog_fallback_verified": "no automatic fallback if Android testboot hangs",
    "power_loss_recovery_verified": "no proof of power-cut recovery",
}


def safe_component_inventory(directory: Path | None) -> dict:
    if directory is None:
        return {"status": "NOT_SUPPLIED", "components": {}}
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Firmware component directory absent or symlink")
    components = {}
    for name, cap in COMPONENTS.items():
        file = directory / name
        if not file.exists():
            components[name] = {"present": False}
            continue
        if not file.is_file() or file.is_symlink() or file.stat().st_size > cap:
            raise ValueError(f"Invalid/oversized firmware component: {name}")
        data = file.read_bytes()
        components[name] = {"present": True, "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest()}
    kernel = components.get("uImage", {})
    dtb = components.get("dtb.bin", {})
    integrity = None
    if kernel.get("present"):
        integrity = inspect_uimage(directory / "uImage")
    return {
        "status": "REFERENCE_PRESENT" if
        kernel.get("sha256") == REFERENCE_KERNEL_SHA256 and
        dtb.get("sha256") == REFERENCE_DTB_SHA256 else "REFERENCE_MISMATCH",
        "components": components,
        "uimage_header_crc_valid": integrity.get("header_crc_valid") if integrity else None,
        "uimage_payload_crc_valid": integrity.get("payload_crc_valid") if integrity else None,
        "signature_cryptographically_verified": False,
        "note": "Sign.bin presence and U-Boot CRC are not proof of secure-boot signature authenticity.",
    }


def boot_safety_report(evidence: dict, components: dict) -> dict:
    if not isinstance(evidence, dict):
        raise ValueError("Boot evidence must be a JSON object")
    gates = [{"name": key, "verified": evidence.get(key) is True,
              "reason": reason} for key, reason in BOOT_GATES.items()]
    blockers = [gate["name"] for gate in gates if not gate["verified"]]
    return {
        "type": "offline_nonpersistent_boot_and_rollback_review",
        "status": "BLOCKED" if blockers else "MANUAL_REVIEW_REQUIRED",
        "blocker_count": len(blockers), "unverified": blockers,
        "gates": gates,
        "stock_component_inventory": components,
        "hypothetical_test_boot_state": "REFUSED_BEFORE_BOOT",
        "no_device_modified": True,
        "boot_attempted": False,
        "rollback_proven": False,
        "flash_authorized": False,
        "note": "No bootloader commands, signatures, partition paths, exploits or writes are provided.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Samsung Q60T offline boot-chain/rollback safety")
    parser.add_argument("--components-dir", type=Path)
    parser.add_argument("--evidence", type=Path, default=Path("porting/boot-evidence.json"))
    parser.add_argument("--output", type=Path, help="new JSON report only")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.evidence.read_text(encoding="utf-8"))
        report = boot_safety_report(data, safe_component_inventory(args.components_dir))
        encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as destination:
                destination.write(encoded)
        else:
            print(encoded, end="")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Boot-Safety-Prüfung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    return 1 if report["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
