#!/usr/bin/env python3
"""Build 024: inspect Android 14 split SELinux-policy inputs read-only.

File presence and hashes are prerequisites, not a policy compilation, an
enforcing boot, a replacement for vendor policy or an attestation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from q60t_arm64_kernel import inspect_config
from q60t_lineage_arm64_source import limited_regular_bytes


POLICY_FILES = {
    "platform_cil": "system/etc/selinux/plat_sepolicy.cil",
    "platform_file_contexts": "system/etc/selinux/plat_file_contexts",
    "platform_property_contexts": "system/etc/selinux/plat_property_contexts",
    "vendor_cil": "vendor/etc/selinux/vendor_sepolicy.cil",
    "vendor_file_contexts": "vendor/etc/selinux/vendor_file_contexts",
    "vendor_property_contexts": "vendor/etc/selinux/vendor_property_contexts",
}
MAX_POLICY_FILE = 32 * 1024 * 1024


def inspect(product_root: Path | None, kernel_config: Path | None = None) -> dict:
    if product_root is not None and (not product_root.is_dir() or product_root.is_symlink()):
        raise ValueError("Android-Produkt-Root-Verzeichnis fehlt/ist verlinkt")
    result = {}
    for label, relative in POLICY_FILES.items():
        path = product_root / relative if product_root else None
        if path is None or not path.exists():
            result[label] = {"status": "NOT_PROVIDED", "relative_path": relative}
        else:
            if not path.resolve().is_relative_to(product_root.resolve()):
                raise ValueError(f"SELinux-Quelldatei verlässt Produkt-Root: {relative}")
            blob = limited_regular_bytes(path, MAX_POLICY_FILE)
            result[label] = {"status": "FILE_EXISTS_NOT_POLICY_VALIDATED",
                             "relative_path": relative, "size_bytes": len(blob),
                             "sha256": hashlib.sha256(blob).hexdigest()}
    config = {"status": "NOT_PROVIDED"}
    if kernel_config is not None:
        raw = limited_regular_bytes(kernel_config, 4 * 1024 * 1024)
        options = inspect_config(raw.decode("ascii", errors="replace"))
        config = {"status": "INSPECTED", "config_sha256": hashlib.sha256(raw).hexdigest(),
                  "selinux_built_in": options["required"]["CONFIG_SECURITY_SELINUX"] == "y",
                  "securityfs_built_in": options["required"]["CONFIG_SECURITYFS"] == "y"}
    all_files = all(v["status"] == "FILE_EXISTS_NOT_POLICY_VALIDATED" for v in result.values())
    return {"type": "q60t_lineage21_arm64_sepolicy_inputs", "build": "024",
            "status": "SPLIT_POLICY_INPUT_INVENTORY_ONLY_NOT_VALIDATED",
            "platform_and_vendor_inputs_present": all_files,
            "policy_files": result, "kernel": config,
            "secilc_compiled_verified": False,
            "sepolicy_neverallow_checks_passed": False,
            "file_context_labels_verified": False,
            "property_service_contexts_verified": False,
            "selinux_enforcing_android_boot_verified": False,
            "samsung_vendor_policy_derived": False,
            "safe_to_flash": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 024: Android-14-SELinux-Policy-Gates")
    parser.add_argument("--product-root", type=Path)
    parser.add_argument("--kernel-config", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = inspect(args.product_root, args.kernel_config)
        raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(raw)
        print(raw, end="")
    except (OSError, ValueError) as exc:
        print(f"Build-024-SELinux-Vorprüfung abgebrochen: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
