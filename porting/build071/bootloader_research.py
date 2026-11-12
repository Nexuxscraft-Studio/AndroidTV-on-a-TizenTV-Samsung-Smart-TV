#!/usr/bin/env python3
"""Build071: offline bootloader research; no TV access or firmware writes."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from q60t_lab import inspect_uimage  # noqa: E402

GATES = (
    "exact_target_hardware_identified",
    "bootloader_authentication_policy_verified",
    "nonpersistent_test_boot_interface_demonstrated",
    "recovery_entrypoint_verified",
    "known_good_backup_verified",
    "rollback_drill_completed_on_spare_hardware",
    "watchdog_fallback_verified",
    "power_loss_recovery_verified",
)
PATTERNS = {
    "U-Boot": re.compile(r"\bU-Boot\s+20\d{2}\.\d{1,2}\b", re.I),
    "barebox": re.compile(r"\bbarebox\s+20\d{2}\.\d{1,2}\b", re.I),
    "EDK II": re.compile(r"\b(?:EDK II|TianoCore|DXE Core)\b", re.I),
}
KERNEL_START = re.compile(r"(?:Starting kernel|Linux version\s+\d)", re.I)
SECURE_BOOT = re.compile(r"(?:secure[\s-]?boot|image signature|verified boot)", re.I)


def read_regular(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Only local regular non-symlink files are allowed")
    if path.stat().st_size > limit:
        raise ValueError("Input exceeds size limit")
    return path.read_bytes()


def passive_uart(path: Path) -> dict:
    data = read_regular(path, 8 * 1024 * 1024)
    lines = data.decode("utf-8", "replace").splitlines()[:20_000]
    kernel_idx = next((i for i, line in enumerate(lines) if KERNEL_START.search(line)), None)
    early = lines[:kernel_idx] if kernel_idx is not None else lines[:400]
    counts = {name: sum(bool(rx.search(line)) for line in early)
              for name, rx in PATTERNS.items()}
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "kernel_boundary_seen": kernel_idx is not None,
        "banner_counts": {name: n for name, n in counts.items() if n},
        "bootloader_candidates": [name for name, n in counts.items() if n],
        "secure_boot_mentions": sum(bool(SECURE_BOOT.search(line)) for line in early),
        "provenance": "User-supplied saved capture; device authenticity not verified",
        "raw_log_in_report": False,
        "warning": ("No kernel boundary detected; scanned only first 400 lines"
                    if kernel_idx is None else None),
    }


def research(evidence: Path, uimage: Path | None = None,
             uart_log: Path | None = None) -> dict:
    gates_obj = json.loads(read_regular(evidence, 1024 * 1024).decode("utf-8"))
    if not isinstance(gates_obj, dict):
        raise ValueError("Evidence must be a JSON object")
    gates = {name: gates_obj.get(name) is True for name in GATES}
    result = {
        "type": "build071_bootloader_research",
        "target": "Samsung GQ50Q60TGUXZG",
        "baseline": [
            "porting/BOOTCHAIN.md",
            "reports/bootchain_forensics_build061.json",
            "porting/build066/docs/BOOT_ACCESS.md",
            "porting/boot-evidence.json",
        ],
        "bootloader_identity": "UNVERIFIED",
        "uefi_or_grub_on_tv": "NOT_DEMONSTRATED",
        "replacement_loader_acceptance": "NOT_DEMONSTRATED",
        "nonpersistent_test_boot": "NOT_DEMONSTRATED",
        "boot_safety": {
            "status": "BLOCKED" if not all(gates.values()) else "MANUAL_REVIEW_REQUIRED",
            "gates": gates,
            "unverified": [name for name, ok in gates.items() if not ok],
        },
        "uimage": None,
        "uart": None,
        "no_device_modified": True,
        "flash_authorized": False,
        "warning": ("A legacy U-Boot uImage format and its CRC do NOT identify "
                    "the bootloader on the TV or prove Secure Boot acceptance."),
    }
    if uimage is not None:
        read_regular(uimage, 128 * 1024 * 1024)
        result["uimage"] = inspect_uimage(uimage)
    if uart_log is not None:
        result["uart"] = passive_uart(uart_log)
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--uimage", type=Path, help="Optional extracted ORIGINAL uImage")
    p.add_argument("--uart-log", type=Path, help="Optional SAVED passive UART log")
    p.add_argument("--evidence", type=Path, default=REPO / "porting/boot-evidence.json")
    p.add_argument("--output", type=Path, help="Create NEW local JSON, no overwrite")
    args = p.parse_args(argv)
    try:
        report = research(args.evidence, args.uimage, args.uart_log)
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            if args.output.is_symlink():
                raise ValueError("Output symlink refused")
            with args.output.open("x", encoding="utf-8") as f:
                f.write(payload)
        else:
            print(payload, end="")
        return 0
    except (ValueError, OSError) as exc:
        print(f"Build071: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
