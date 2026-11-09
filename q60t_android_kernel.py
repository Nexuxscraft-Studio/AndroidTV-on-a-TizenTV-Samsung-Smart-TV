#!/usr/bin/env python3
"""Research-only Tizen 4.1.10 -> Android kernel configuration assessment.

Never runs vendor build scripts, changes the Samsung source or contacts a TV.
An experimental Kconfig fragment is not a bootable or validated configuration.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

import q60t_kernel_build


MAX_CONFIG_BYTES = 8 * 1024 * 1024
MAX_KCONFIG_FILES = 5000
MAX_KCONFIG_BYTES = 32 * 1024 * 1024
CONFIG_VALUE = re.compile(r"^CONFIG_([A-Z0-9_]+)=(.+)$")
CONFIG_OFF = re.compile(r"^# CONFIG_([A-Z0-9_]+) is not set$")
KCONFIG_DECL = re.compile(r"^\s*(?:config|menuconfig)\s+([A-Z0-9_]+)\s*(?:#.*)?$")

# Research targets, not a device-specific Android 14 compatibility contract.
# The Linux 4.1 tree predates multiple Android interfaces, and its secure
# boot/SMACK/SFD policies must never be silently weakened by this tool.
FEATURES: dict[str, tuple[str, str, str]] = {
    "ANDROID_BINDER_IPC": ("android_ipc", "y", "candidate"),
    "ANDROID_BINDER_IPC_32BIT": ("android_ipc", "n", "manual_binder_abi_review"),
    "ANDROID_BINDERFS": ("android_ipc", "y", "newer_interface"),
    "ASHMEM": ("legacy_android_memory", "y", "candidate"),
    "MEMCG": ("memory_control", "y", "candidate"),
    "ION": ("legacy_gpu_buffers", "y", "candidate"),
    "DMA_SHARED_BUFFER": ("gpu_buffers", "y", "observe"),
    "SYNC": ("gpu_buffers", "y", "observe"),
    "DMA_HEAPS": ("gpu_buffers", "y", "newer_interface"),
    "SECURITY_SELINUX": ("security", "y", "manual_security_review"),
    "SECURITY_SMACK": ("security", "n", "vendor_security_observe"),
    "SECURITY_SFD": ("security", "n", "vendor_security_observe"),
    "CGROUPS": ("process_control", "y", "observe"),
    "CPUSETS": ("process_control", "y", "observe"),
    "PID_NS": ("process_control", "y", "observe"),
    "NET_NS": ("process_control", "y", "observe"),
    "SECCOMP": ("process_control", "y", "observe"),
    "EXT4_FS": ("filesystems", "y", "candidate"),
    "OVERLAY_FS": ("filesystems", "y", "candidate"),
    "TUN": ("network", "y", "candidate"),
    "VETH": ("network", "y", "observe"),
    "DRM_SDP": ("samsung_display", "y", "observe"),
    "DRM_PANEL_SDP": ("samsung_display", "y", "observe"),
    "VIDEO_V4L2": ("samsung_video", "y", "observe"),
    "SND_SOC": ("samsung_audio", "y", "observe"),
}

SELECTED_CANDIDATES = (
    "ANDROID_BINDER_IPC", "ASHMEM", "MEMCG", "ION",
    "EXT4_FS", "OVERLAY_FS", "TUN",
)
REFERENCE_PROFILE = "Nike.M-Tizen_release_defconfig"


def read_config(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Configuration missing or linked: {path.name}")
    data = path.read_bytes()
    if len(data) > MAX_CONFIG_BYTES or b"\x00" in data:
        raise ValueError("Configuration invalid or too large")
    selected: dict[str, str] = {}
    for line in data.decode("utf-8", errors="replace").splitlines():
        match = CONFIG_VALUE.fullmatch(line)
        if match:
            symbol, value = match.groups()
        else:
            match = CONFIG_OFF.fullmatch(line)
            if not match:
                continue
            symbol, value = match.group(1), "n"
        if symbol in selected and selected[symbol] != value:
            raise ValueError(f"Conflicting config values: CONFIG_{symbol}")
        selected[symbol] = value
    return {"name": path.name, "sha256": hashlib.sha256(data).hexdigest(),
            "symbols": selected, "symbol_count": len(selected)}


def read_nike_configs(source: Path) -> dict[str, dict]:
    config_dir = source / "arch/arm/configs"
    if not config_dir.is_dir() or config_dir.is_symlink():
        raise ValueError("ARM configuration directory missing")
    paths = sorted(config_dir.glob("Nike.*_defconfig"))
    if len(paths) > 64:
        raise ValueError("Too many Nike configuration candidates")
    profiles = {p.name: read_config(p) for p in paths}
    if REFERENCE_PROFILE not in profiles:
        raise ValueError("Reference Nike.M configuration missing")
    return profiles


def read_kconfig_definitions(source: Path) -> dict:
    """Find literal symbol definitions without following source symlinks.

    Non-ARM arch/ trees are excluded, so an x86-only declaration cannot
    incorrectly qualify a symbol for this ARM32 target.
    """
    if not source.is_dir() or source.is_symlink():
        raise ValueError("Source root must be a real directory")
    declarations: dict[str, list[str]] = {}
    count = bytes_scanned = skipped = 0
    for directory, dirs, files in os.walk(source, followlinks=False):
        base = Path(directory)
        relative_base = base.relative_to(source)
        if relative_base == Path("arch"):
            dirs[:] = sorted(d for d in dirs if d == "arm")
        else:
            dirs[:] = sorted(d for d in dirs if not (base / d).is_symlink())
        for name in sorted(files):
            if not (name == "Kconfig" or name.startswith("Kconfig.")):
                continue
            path = base / name
            if path.is_symlink():
                skipped += 1
                continue
            count += 1
            if count > MAX_KCONFIG_FILES:
                raise ValueError("Too many Kconfig files")
            size = path.stat().st_size
            if size > MAX_CONFIG_BYTES or bytes_scanned + size > MAX_KCONFIG_BYTES:
                raise ValueError("Kconfig scan exceeds byte limit")
            data = path.read_bytes()
            if b"\x00" in data:
                raise ValueError("Binary Kconfig file")
            bytes_scanned += len(data)
            relative = path.relative_to(source).as_posix()
            for line in data.decode("utf-8", errors="replace").splitlines():
                match = KCONFIG_DECL.fullmatch(line)
                if match and match.group(1) in FEATURES:
                    refs = declarations.setdefault(match.group(1), [])
                    if len(refs) < 8:
                        refs.append(relative)
    return {"declarations": declarations, "files_scanned": count,
            "bytes_scanned": bytes_scanned, "links_skipped": skipped}


def feature_state(value: str | None, desired: str, is_declared: bool) -> str:
    if not is_declared:
        return "NOT_DECLARED_FOR_ARM_TREE"
    if value is None:
        return "UNSPECIFIED"
    if value == desired:
        return "MATCHES_RESEARCH_GOAL"
    if value == "m" and desired == "y":
        return "MODULE_ONLY"
    if value == "n":
        return "DISABLED"
    return "DIFFERS_FROM_RESEARCH_GOAL"


def binder_abi_evidence(source: Path, baseline: dict[str, str]) -> dict:
    kconfig = source / "drivers/android/Kconfig"
    if not kconfig.is_file() or kconfig.is_symlink():
        return {"source_warning_detected": False,
                "requires_manual_binder_abi_review": True}
    if kconfig.stat().st_size > 256 * 1024:
        raise ValueError("Unexpectedly large Android Kconfig")
    contents = kconfig.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"(?ms)^config ANDROID_BINDER_IPC_32BIT\s*\n"
        r"(.*?)(?=^(?:config|menuconfig|endif|endmenu)\b|\Z)",
        contents,
    )
    block = match.group(1) if match else ""
    return {
        "source": "drivers/android/Kconfig",
        "legacy_32bit_symbol_defined": bool(match),
        "kconfig_default_y": bool(re.search(r"(?m)^\s*default\s+y\s*$", block)),
        "source_warning_detected": (
            "break newer Android user-space" in block
        ),
        "baseline_explicit_setting": baseline.get(
            "ANDROID_BINDER_IPC_32BIT", "unspecified"
        ),
        "requires_manual_binder_abi_review": True,
    }


def compute_report(source: Path) -> dict:
    version = q60t_kernel_build.source_version(source)
    if version != "4.1.10":
        raise ValueError("This research profile expects Samsung Linux 4.1.10")
    profiles = read_nike_configs(source)
    definitions = read_kconfig_definitions(source)
    baseline = profiles[REFERENCE_PROFILE]
    base_symbols = baseline["symbols"]
    features = []
    for symbol, (group, desired, intent) in FEATURES.items():
        references = definitions["declarations"].get(symbol, [])
        value = base_symbols.get(symbol)
        features.append({
            "symbol": "CONFIG_" + symbol, "group": group,
            "desired_research_value": desired, "intent": intent,
            "baseline_value": value if value is not None else "absent",
            "arm_source_declarations": references,
            "state": feature_state(value, desired, bool(references)),
            "profiles_with_goal": sorted(
                name for name, info in profiles.items()
                if info["symbols"].get(symbol) == desired
            ),
        })
    variation = {}
    for symbol in FEATURES:
        values = {name: config["symbols"].get(symbol, "absent")
                  for name, config in profiles.items()}
        if len(set(values.values())) > 1:
            variation["CONFIG_" + symbol] = values

    proposals = [
        "CONFIG_" + symbol + "=y"
        for symbol in SELECTED_CANDIDATES
        if definitions["declarations"].get(symbol)
        and base_symbols.get(symbol) != "y"
    ]
    binder_evidence = binder_abi_evidence(source, base_symbols)
    if (binder_evidence["legacy_32bit_symbol_defined"]
            and base_symbols.get("ANDROID_BINDER_IPC_32BIT") != "n"):
        # Explicitly cancel the old Kconfig default in the *unvalidated*
        # host-only fragment. Userspace ioctl compatibility remains unproved.
        proposals.append("# CONFIG_ANDROID_BINDER_IPC_32BIT is not set")
    security = {
        "smack_enabled": base_symbols.get("SECURITY_SMACK") == "y",
        "samsung_sfd_enabled": base_symbols.get("SECURITY_SFD") == "y",
        "selinux_enabled": base_symbols.get("SECURITY_SELINUX") == "y",
        "requires_manual_policy_and_lsm_review": True,
        "vendor_security_options_untouched": True,
    }
    available_compilers = {
        name: bool(shutil.which(name))
        for name in ("arm-linux-gnueabi-gcc", "arm-linux-gnueabihf-gcc",
                     "armv7l-tizen-linux-gnueabi-gcc", "clang")
    }
    return {
        "type": "q60t_nikel_android_kernel_bringup",
        "status": "OFFLINE_ANALYSIS_ONLY",
        "model": "GQ50Q60TGUXZG (reference; live board not verified)",
        "source_version": version,
        "source_matches_firmware_2743_0": False,
        "reference_config": {
            "name": baseline["name"], "sha256": baseline["sha256"],
            "symbol_count": baseline["symbol_count"],
        },
        "candidate_profile_names": sorted(profiles),
        "nike_l_named_profile_present": any("Nike.L" in name for name in profiles),
        "feature_definitions": features,
        "feature_state_counts": dict(Counter(f["state"] for f in features)),
        "cross_profile_variations": variation,
        "fragment_proposals": proposals,
        "binder_abi_risk": binder_evidence,
        "unvalidated_fragment_requires_olddefconfig": True,
        "vendor_security_review": security,
        "kconfig_scan": {key: value for key, value in definitions.items()
                         if key != "declarations"},
        "host_compiler_candidates": available_compilers,
        "cross_compiler_exact_provenance_verified": False,
        "kernel_built": False,
        "android_hal_verified": False,
        "tv_accessed": False,
        "boot_or_flash_performed": False,
        "flash_authorized": False,
        "caution": (
            "These are research goals, not a validated Android 14 compatibility "
            "profile. Fragment proposals require Kconfig dependency resolution "
            "and manual security/Binder ABI review. Linux 4.1.10, boot signing, driver "
            "ABI, Android HAL and recovery remain separate blockers."
        ),
    }


def fragment(report: dict) -> str:
    lines = [
        "# Q60T Build 012: research-only Kconfig fragment",
        "# Not a ready-to-flash configuration; do not modify TV firmware.",
        "# Review dependencies via isolated Kconfig olddefconfig.",
        "# Security: Smack and Samsung SFD are deliberately NOT disabled.",
        "# SELinux/LSM transition requires explicit manual analysis.",
    ]
    lines.extend(report["fragment_proposals"])
    lines += ["", "# No Android boot or kernel-build success is implied."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Host-only Samsung Nike-L Android-kernel Kconfig bridge"
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="new JSON report only")
    parser.add_argument("--fragment-out", type=Path, help="new Kconfig fragment only")
    args = parser.parse_args(argv)
    try:
        outputs = [p for p in (args.report, args.fragment_out) if p]
        if len(outputs) == 2 and outputs[0].resolve() == outputs[1].resolve():
            raise ValueError("Report and fragment must be separate paths")
        for path in outputs:
            if path.is_symlink() or path.exists():
                raise ValueError(f"Refusing to overwrite output: {path}")
        report = compute_report(args.source)
        if args.report:
            with args.report.open("x", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        if args.fragment_out:
            with args.fragment_out.open("x", encoding="utf-8") as stream:
                stream.write(fragment(report))
        if not outputs:
            print(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        print(f"Kernel-Bridge-Prüfung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
