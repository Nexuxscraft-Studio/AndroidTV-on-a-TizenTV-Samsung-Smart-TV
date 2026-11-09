#!/usr/bin/env python3
"""Host-only Binder UAPI/driver surface comparison for the Samsung 4.1 tree.

The comparison is deliberately a *subset* of an official AOSP Binder header,
not an Android CDD/VTS result and never a device-boot authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import q60t_kernel_build as kernel


REFERENCE = (
    "https://android.googlesource.com/kernel/common/+/"
    "d04d0acdaf98506fca2e6501ed6adcdcc7d31a1f/"
    "include/uapi/linux/android/binder.h"
)

# Older core requests plus a focused set from the referenced newer UAPI.
CORE_IOCTL = (
    "BINDER_WRITE_READ", "BINDER_SET_IDLE_TIMEOUT",
    "BINDER_SET_MAX_THREADS", "BINDER_SET_IDLE_PRIORITY",
    "BINDER_SET_CONTEXT_MGR", "BINDER_THREAD_EXIT", "BINDER_VERSION",
)
MODERN_IOCTL = (
    "BINDER_GET_NODE_DEBUG_INFO", "BINDER_GET_NODE_INFO_FOR_REF",
    "BINDER_SET_CONTEXT_MGR_EXT", "BINDER_FREEZE",
    "BINDER_GET_FROZEN_INFO", "BINDER_ENABLE_ONEWAY_SPAM_DETECTION",
)
MODERN_OBJECT_TYPES = ("BINDER_TYPE_FDA", "BINDER_TYPE_PTR")
MODERN_TRANSACTION_FEATURES = (
    "TF_CLEAR_BUF", "FLAT_BINDER_FLAG_TXN_SECURITY_CTX",
    "BR_TRANSACTION_SEC_CTX", "BC_TRANSACTION_SG",
)
MODERN_STRUCTS = (
    "binder_object_header", "binder_buffer_object",
    "binder_fd_array_object", "binder_transaction_data_sg",
)


def limited_source(path: Path, limit: int = 1024 * 1024) -> str:
    if (not path.is_file() or path.is_symlink() or
            not 0 < path.stat().st_size <= limit):
        raise ValueError(f"Fehlende, verlinkte oder zu große Eingabedatei: {path.name}")
    return path.read_text(encoding="utf-8", errors="replace")


def strip_comments(source: str) -> str:
    """Remove comments while preserving newlines for anchored names."""
    return re.sub(r"/\*.*?\*/|//[^\n]*",
                  lambda m: "\n" * m.group().count("\n"), source, flags=re.S)


def symbols(source: str, values: tuple[str, ...], kind: str) -> dict[str, bool]:
    source = strip_comments(source)
    if kind == "ioctl":
        pattern = r"^\s*#define\s+{}\s+"
    elif kind == "handler":
        pattern = r"^\s*case\s+{}\s*:"
    elif kind == "struct":
        pattern = r"^\s*struct\s+{}\s*\{{"
    elif kind == "enum":
        pattern = r"^\s*{}\s*(?:=|,)"
    else:
        raise ValueError("Unbekannter Symboltyp")
    return {name: bool(re.search(pattern.format(re.escape(name)), source, re.M))
            for name in values}


def audit(source_root: Path) -> dict:
    if not source_root.is_dir() or source_root.is_symlink():
        raise ValueError("Ungültiger Kernel-Quellbaum")
    version = kernel.source_version(source_root)
    if version != "4.1.10":
        raise ValueError("Dieser Binder-Survey erwartet Linux 4.1.10")
    header_path = source_root / "include/uapi/linux/android/binder.h"
    driver_path = source_root / "drivers/android/binder.c"
    header = limited_source(header_path)
    driver = limited_source(driver_path)
    bare_driver = strip_comments(driver)
    core_declared = symbols(header, CORE_IOCTL, "ioctl")
    core_handled = symbols(driver, CORE_IOCTL, "handler")
    new_declared = symbols(header, MODERN_IOCTL, "ioctl")
    new_handled = symbols(driver, MODERN_IOCTL, "handler")
    modern_object = symbols(header, MODERN_OBJECT_TYPES, "enum")
    modern_features = symbols(header, MODERN_TRANSACTION_FEATURES, "enum")
    modern_structs = symbols(header, MODERN_STRUCTS, "struct")
    # The protocol macro occurs in both sides of #ifdef. Distinguish
    # its textual value from a tested runtime negotiation result.
    versions = sorted(set(int(v) for v in re.findall(
        r"^#define\s+BINDER_CURRENT_PROTOCOL_VERSION\s+(\d+)", header, re.M)))
    legacy_single_manager = bool(re.search(
        r"^static\s+struct\s+binder_node\s*\*binder_context_mgr_node\s*;",
        bare_driver, re.M))
    experimental_three_contexts = all(token in bare_driver for token in (
        "struct binder_context {", '"hwbinder"', '"vndbinder"',
        "target_proc->context != proc->context", "proc->context->mgr_node",
    ))
    return {
        "type": "q60t_binder_abi_surface_audit", "build": "017",
        "kernel_version": version,
        "source_kind": "Samsung GPL tree or experimental host-only shadow",
        "header_sha256": hashlib.sha256(header_path.read_bytes()).hexdigest(),
        "driver_sha256": hashlib.sha256(driver_path.read_bytes()).hexdigest(),
        "reference": REFERENCE,
        "reference_is_complete_android_requirement_list": False,
        "core_ioctl_in_header": core_declared,
        "core_ioctl_handlers_in_driver": core_handled,
        "newer_aosp_ioctl_in_header": new_declared,
        "newer_aosp_ioctl_handlers_in_driver": new_handled,
        "newer_aosp_object_types_in_header": modern_object,
        "newer_aosp_transaction_features_in_header": modern_features,
        "newer_aosp_structs_in_header": modern_structs,
        "protocol_versions_found_in_text": versions,
        "protocol_version_means_runtime_compatibility": False,
        "legacy_global_context_manager_present": legacy_single_manager,
        "experimental_three_context_source_detected": experimental_three_contexts,
        "ioctl_declared_but_no_handler": [name for name in CORE_IOCTL + MODERN_IOCTL
                                           if (core_declared | new_declared)[name]
                                           and not (core_handled | new_handled)[name]],
        "missing_newer_aosp_surface": list(dict.fromkeys(name for group in (
            new_declared, new_handled, modern_object, modern_features, modern_structs)
            for name, available in group.items() if not available)),
        "runtime_verified": False,
        "android_userspace_compatible": False,
        "hardware_tested": False,
        "flash_authorized": False,
        "status": "MODERN_BINDER_ABI_INCOMPLETE_AND_RUNTIME_UNVERIFIED",
        "warning": "Static ioctl/struct names do not prove kernel ABI compatibility or security. Do not flash.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline UAPI-versus-driver Android Binder survey")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit(args.source)
        serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
        print(serialized)
        return 0
    except (OSError, ValueError) as exc:
        print(f"Binder-ABI-Survey fehlgeschlagen: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
