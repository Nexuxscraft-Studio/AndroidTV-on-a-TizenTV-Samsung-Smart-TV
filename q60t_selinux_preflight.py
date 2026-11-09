#!/usr/bin/env python3
"""Read-only Android SELinux policy prerequisite check for Build 020.

Finding a compiled SELinux LSM is NOT the same as loading Android policy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from q60t_qemu_runtime import _read_config


ANDROID_POLICY_PATHS = (
    "system/etc/selinux/plat_sepolicy.cil",
    "vendor/etc/selinux/vendor_sepolicy.cil",
    "system/etc/selinux/plat_file_contexts",
    "vendor/etc/selinux/vendor_file_contexts",
)


def inspect(workspace: Path, staged_rootfs: Path | None = None,
            guest_log: Path | None = None) -> dict:
    if not workspace.is_dir() or workspace.is_symlink():
        raise ValueError("Workspace fehlt oder ist verlinkt")
    config = workspace / "output/.config"
    if not config.is_file() or config.is_symlink():
        raise ValueError("Kernelkonfiguration fehlt")
    symbols = _read_config(config)
    kernel_capable = (symbols.get("SECURITY_SELINUX") == "y" and
                      symbols.get("DEFAULT_SECURITY_SELINUX") == "y")
    policy_files: dict[str, bool] = {}
    if staged_rootfs is not None:
        if not staged_rootfs.is_dir() or staged_rootfs.is_symlink():
            raise ValueError("Staging-Rootfs fehlt oder ist verlinkt")
        for name in ANDROID_POLICY_PATHS:
            path = staged_rootfs / name
            policy_files[name] = path.is_file() and not path.is_symlink() and path.stat().st_size > 0
    guest_mode = "not_observed"
    if guest_log is not None:
        if not guest_log.is_file() or guest_log.is_symlink() or guest_log.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("Ungültiges Gastsystemprotokoll")
        raw = guest_log.read_text(encoding="utf-8", errors="replace")
        if "Q60T_ANDROID_PROBE_FEATURE name=selinux_enforcing result=pass" in raw:
            guest_mode = "enforcing_reported_policy_not_verified"
        elif "Q60T_ANDROID_PROBE_FEATURE name=selinux_enforcing result=fail" in raw:
            guest_mode = "permissive_reported"
    all_files_staged = bool(policy_files) and all(policy_files.values())
    return {
        "build": "020",
        "kernel_selinux_compiled_and_selected": kernel_capable,
        "vendor_sfd_disabled": symbols.get("SECURITY_SFD", "n") == "n",
        "guest_selinux_mode": guest_mode,
        "required_policy_artifacts": policy_files,
        "policy_artifacts_staged": all_files_staged,
        "policy_loaded_into_guest_verified": False,
        "android_selinux_enforcement_ready": False,
        "status": ("KERNEL_READY_POLICY_NOT_LOADED_OR_VERIFIED" if kernel_capable else
                   "KERNEL_SELINUX_PREREQUISITES_MISSING"),
        "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 020 SELinux Android-Policy-Voraussetzungen")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--rootfs", type=Path)
    parser.add_argument("--guest-log", type=Path)
    args = parser.parse_args(argv)
    try:
        report = inspect(args.workspace, args.rootfs, args.guest_log)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["kernel_selinux_compiled_and_selected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
