#!/usr/bin/env python3
"""Verify two offline Kconfig results differ only in the Binder ABI symbol.

This compares local evidence. It cannot authenticate who ran make, prove that
the firmware's exact source was used, or validate Android userspace behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import q60t_android_kernel as bridge


OLD_BLOCK = (
    "config ANDROID_BINDER_IPC_32BIT\n"
    "\tbool\n"
    "\tdepends on !64BIT && ANDROID_BINDER_IPC\n"
    "\tdefault y"
)
NEW_BLOCK = OLD_BLOCK[:-1] + "n"
REQUIRED = {
    "ANDROID_BINDER_IPC": "y",
    "ANDROID_BINDER_IPC_32BIT": "n",
    "ASHMEM": "y",
    "MEMCG": "y",
    "ION": "y",
    "EXT4_FS": "y",
    "OVERLAY_FS": "y",
    "TUN": "y",
}
VENDOR_SECURITY = ("SECURITY_SMACK", "SECURITY_SFD", "SECURITY_SELINUX")


def read_small_text(path: Path) -> tuple[str, str]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 256 * 1024:
        raise ValueError(f"Unsafe or missing Kconfig input: {path.name}")
    data = path.read_bytes()
    if b"\x00" in data:
        raise ValueError("Unexpected binary Kconfig content")
    return data.decode("utf-8"), hashlib.sha256(data).hexdigest()


def verify(old_kconfig: Path, new_kconfig: Path,
           old_config: Path, new_config: Path) -> dict:
    source_old, hash_old = read_small_text(old_kconfig)
    source_new, hash_new = read_small_text(new_kconfig)
    if source_old.count(OLD_BLOCK) != 1 or source_new != source_old.replace(
        OLD_BLOCK, NEW_BLOCK, 1
    ):
        raise ValueError("Unexpected Binder Kconfig patch or extra source changes")
    before = bridge.read_config(old_config)
    after = bridge.read_config(new_config)
    original_symbols = before["symbols"]
    modified_symbols = after["symbols"]
    for name, goal in REQUIRED.items():
        if modified_symbols.get(name) != goal:
            raise ValueError(f"Unresolved proposed symbol: CONFIG_{name}")
    for name in VENDOR_SECURITY:
        if original_symbols.get(name) != modified_symbols.get(name):
            raise ValueError(f"Vendor security configuration changed: CONFIG_{name}")
    delta = {
        name: {"before": original_symbols.get(name, "absent"),
               "after": modified_symbols.get(name, "absent")}
        for name in original_symbols.keys() | modified_symbols.keys()
        if original_symbols.get(name) != modified_symbols.get(name)
    }
    if delta != {
        "ANDROID_BINDER_IPC_32BIT": {"before": "y", "after": "n"}
    }:
        raise ValueError("Kconfig result changed more than expected Binder ABI")
    return {
        "type": "q60t_binder_abi_offline_kconfig_verification",
        "status": "KCONFIG_RESULT_VERIFIED_IN_ISOLATED_HOST_TREE",
        "kconfig_original_sha256": hash_old,
        "kconfig_binder_patch_sha256": hash_new,
        "candidate_before_sha256": before["sha256"],
        "candidate_patched_sha256": after["sha256"],
        "verified_research_values": {
            "CONFIG_" + name: goal for name, goal in REQUIRED.items()
        },
        "observed_config_changes": {
            "CONFIG_" + name: values for name, values in delta.items()
        },
        "vendor_security_unchanged_between_runs": True,
        "only_binder_kconfig_default_changed": True,
        "no_android_userspace_abi_tested": True,
        "source_patch_matches_firmware_2743_0": False,
        "kernel_compiled": False,
        "boot_or_flash_attempted": False,
        "flash_authorized": False,
        "caution": "Host-only Kconfig equivalence; compile, Android Binder "
                   "userspace ABI, secure boot and recovery remain unverified.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify isolated Binder Kconfig trial")
    parser.add_argument("--original-kconfig", type=Path, required=True)
    parser.add_argument("--patched-kconfig", type=Path, required=True)
    parser.add_argument("--original-config", type=Path, required=True)
    parser.add_argument("--patched-config", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="new JSON output only")
    args = parser.parse_args(argv)
    try:
        report = verify(args.original_kconfig, args.patched_kconfig,
                        args.original_config, args.patched_config)
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.report:
            with args.report.open("x", encoding="utf-8") as handle:
                handle.write(payload)
        else:
            print(payload, end="")
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"Kconfig-Verification fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
