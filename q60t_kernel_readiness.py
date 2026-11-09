#!/usr/bin/env python3
"""Offline gap report: Samsung Nike kernel vs Android kernel feature needs.

This is a source/configuration *triage*, not Android CDD/VTS certification.
No firmware/device I/O, signing, patching or kernel compilation takes place.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import q60t_android_kernel as android
import q60t_kernel_build as kernel


ANDROID_4_4_EXAMPLE = (
    "https://android.googlesource.com/kernel/common/+/refs/tags/"
    "ASB-2020-04-05_4.4-o/android/configs/android-base.cfg"
)
ANDROID_14_KERNEL_MATRIX = "https://source.android.com/docs/core/architecture/kernel/android-common"
BINDER_DOC = "https://source.android.com/docs/core/architecture/hidl/binder-ipc"
SELINUX_DOC = "https://source.android.com/docs/security/features/selinux"

# A focused diagnostic subset from the published Android 4.4 base config,
# plus platform-enabling features. This is not a complete requirements list.
FEATURES = {
    "ANDROID_BINDER_IPC": "Android IPC",
    "ASHMEM": "Legacy Android shared memory",
    "AUDIT": "Security audit",
    "BLK_DEV_INITRD": "Initial ramdisk support",
    "CGROUPS": "Control groups",
    "CGROUP_CPUACCT": "CPU accounting",
    "CGROUP_FREEZER": "Freeze process groups",
    "HIGH_RES_TIMERS": "High-resolution timers",
    "IKCONFIG": "Embedded kernel config",
    "IKCONFIG_PROC": "Config accessible via proc",
    "SECURITY_SELINUX": "SELinux LSM",
    "DEFAULT_SECURITY_SELINUX": "SELinux selected by default",
}
SUPPORTING = {
    "ION": "Legacy Android memory allocator",
    "OVERLAY_FS": "Overlay filesystem",
    "SECCOMP_FILTER": "Seccomp-BPF filters",
    "NET_NS": "Network namespaces",
    "BPF_SYSCALL": "BPF system call (not the full modern eBPF stack)",
}
def read_limited(path: Path, limit: int = 2 * 1024 * 1024) -> str:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
        raise ValueError(f"Missing, linked or oversized source: {path.name}")
    return path.read_text(encoding="utf-8", errors="replace")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(source: Path, resolved_config: Path) -> dict:
    if not source.is_dir() or source.is_symlink():
        raise ValueError("Ungültiger oder verlinkter Kernel-Quellordner")
    version = kernel.source_version(source)
    if version != "4.1.10":
        raise ValueError("Dieser Bericht erwartet Samsungs Linux 4.1.10")
    config = android.read_config(resolved_config)
    if not config["symbols"]:
        raise ValueError("Leere oder ungültige Kconfig-Auflösung")
    values = config["symbols"]
    binder_kconfig = read_limited(source / "drivers/android/Kconfig")
    binder_c = read_limited(source / "drivers/android/binder.c")
    binder_header = read_limited(source / "include/uapi/linux/android/binder.h")
    original_defconfig = source / "arch/arm/configs" / android.REFERENCE_PROFILE
    read_limited(original_defconfig)

    required = [
        {"symbol": f"CONFIG_{name}", "name": description,
         "expected": "y", "actual": values.get(name, "n"),
         "enabled": values.get(name, "n") == "y"}
        for name, description in FEATURES.items()
    ]
    supporting = [
        {"symbol": f"CONFIG_{name}", "name": description,
         "actual": values.get(name, "n"), "enabled": values.get(name, "n") == "y"}
        for name, description in SUPPORTING.items()
    ]
    version_pattern = r"#define\s+BINDER_CURRENT_PROTOCOL_VERSION\s+(\d+)"
    binder_versions = [int(x) for x in re.findall(version_pattern, binder_header)]
    # A single misc device and lack of BINDER_DEVICES are negative evidence
    # for modern multi-context binder. Do not infer runtime ABI compatibility.
    single_binder = bool(re.search(r'\.name\s*=\s*"binder"', binder_c))
    binder_devices_declared = bool(re.search(
        r"^config\s+ANDROID_BINDER_DEVICES\s*$", binder_kconfig, re.M))
    multi_binder = binder_devices_declared and all(
        name in binder_c for name in ("hwbinder", "vndbinder"))
    # Recognize the opt-in Build-016 host patch but deliberately do not
    # equate a compiled source scaffold with Binder runtime correctness.
    lab_scaffold = all(marker in binder_c for marker in (
        "struct binder_context {", '"hwbinder"', '"vndbinder"',
        "proc->context->mgr_node", "target_proc->context != proc->context",
    ))
    selinux_enabled = values.get("SECURITY_SELINUX") == "y"
    selinux_default = values.get("DEFAULT_SECURITY") == '"selinux"'
    gaps = []
    if lab_scaffold:
        gaps.append("Experimental Binder three-context source is not runtime ABI-tested")
    elif multi_binder:
        gaps.append("Multi-device Binder names exist but runtime ABI is unverified")
    else:
        gaps.append("No proven /dev/hwbinder + /dev/vndbinder contexts")
    if not (selinux_enabled and selinux_default):
        gaps.append("SELinux not built and selected as default LSM")
    if values.get("SECURITY_SFD") == "y":
        gaps.append("Samsung SFD/UEP integration with Android is unverified")
    gaps.extend(item["symbol"] for item in required if not item["enabled"])
    gaps.append("Linux 4.1.10 is outside official Android 14 supported-kernel matrix")
    gaps.append("No verified Q60T Nike-L defconfig / TV boot / Android HAL / rollback")
    return {
        "type": "q60t_android_kernel_gap_audit",
        "build": "016" if lab_scaffold else "015", "kernel_version": version,
        "defconfig_reference": android.REFERENCE_PROFILE,
        "defconfig_sha256": sha256(original_defconfig),
        "resolved_config_sha256": sha256(resolved_config),
        "supported_android14_kernel": False,
        "benchmark_is_complete_android_cdd": False,
        "essential_sample": required,
        "supporting_features": supporting,
        "binder": {
            "single_misc_binder_declared": single_binder,
            "kconfig_multi_device_option_present": binder_devices_declared,
            "experimental_three_context_source_detected": lab_scaffold,
            "multi_device_kconfig_and_names_present": multi_binder,
            "hwbinder_and_vndbinder_proven": False,
            "protocol_versions_in_source": binder_versions,
            "runtime_abi_tested": False,
        },
        "security": {
            "selinux_compiled": selinux_enabled,
            "selinux_default": selinux_default,
            "smack_compiled": values.get("SECURITY_SMACK") == "y",
            "samsung_sfd_compiled": values.get("SECURITY_SFD") == "y",
            "android_policy_compatible": False,
        },
        "gaps": list(dict.fromkeys(gaps)),
        "status": "GAPS_FOUND_NOT_ANDROID_READY",
        "tv_accessed": False, "flash_authorized": False,
        "sources": [ANDROID_4_4_EXAMPLE, ANDROID_14_KERNEL_MATRIX,
                    BINDER_DOC, SELINUX_DOC],
        "warning": "A config check is not an Android boot or runtime test. Do not flash.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline Android compatibility gaps")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit(args.source, args.config)
        serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
        print(serialized)
        return 0
    except (ValueError, OSError) as exc:
        print(f"Kernel-Kompatibilitätsprüfung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
