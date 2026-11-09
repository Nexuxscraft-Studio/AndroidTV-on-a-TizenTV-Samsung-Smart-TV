#!/usr/bin/env python3
"""Stage an experimental ARM32 .config outside the vendor kernel tree.

This performs a deterministic text-level merge only. It deliberately never
invokes Kbuild, runs vendor scripts, signs images, or touches a television.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import q60t_android_kernel as bridge
import q60t_kernel_build


FRAGMENT_SYMBOL = re.compile(r"^CONFIG_([A-Z0-9_]+)=([ymn])$")
FRAGMENT_OFF = re.compile(r"^# CONFIG_([A-Z0-9_]+) is not set$")
ALLOWED_SET = set(bridge.SELECTED_CANDIDATES) | {"ANDROID_BINDER_IPC_32BIT"}
MAX_FRAGMENT_BYTES = 32 * 1024


def parse_fragment(path: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_FRAGMENT_BYTES:
        raise ValueError("Fragment missing, linked or too large")
    data = path.read_bytes()
    if b"\x00" in data:
        raise ValueError("Fragment must be UTF-8 text")
    values: dict[str, str] = {}
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        match = FRAGMENT_OFF.fullmatch(line)
        if match:
            name, value = match.group(1), "n"
        else:
            match = FRAGMENT_SYMBOL.fullmatch(line)
            if match:
                name, value = match.groups()
            elif line.lstrip().startswith("# "):
                continue
            else:
                raise ValueError("Unexpected fragment expression")
        if name not in ALLOWED_SET:
            raise ValueError(f"Unsafe or unsupported overlay symbol: CONFIG_{name}")
        if name in values:
            raise ValueError(f"Duplicate overlay symbol: CONFIG_{name}")
        if name == "ANDROID_BINDER_IPC_32BIT" and value != "n":
            raise ValueError("The legacy binder ABI may not be auto-enabled")
        if name != "ANDROID_BINDER_IPC_32BIT" and value != "y":
            raise ValueError("Research fragment permits only y for candidate features")
        values[name] = value
    if not values:
        raise ValueError("Empty overlay fragment")
    return values


def shadow_config(source_text: str, changes: dict[str, str]) -> str:
    lines = source_text.splitlines()
    processed: set[str] = set()
    patched: list[str] = []
    for line in lines:
        active = bridge.CONFIG_VALUE.fullmatch(line)
        inactive = bridge.CONFIG_OFF.fullmatch(line)
        symbol = active.group(1) if active else inactive.group(1) if inactive else None
        if symbol not in changes:
            patched.append(line)
            continue
        if symbol in processed:
            continue
        processed.add(symbol)
        value = changes[symbol]
        patched.append(
            f"CONFIG_{symbol}={value}"
            if value != "n" else f"# CONFIG_{symbol} is not set"
        )
    for symbol in sorted(changes.keys() - processed):
        value = changes[symbol]
        patched.append(
            f"CONFIG_{symbol}={value}"
            if value != "n" else f"# CONFIG_{symbol} is not set"
        )
    return "\n".join([
        "# GENERATED OFFLINE: UNVALIDATED Q60T BUILD-012 RESEARCH CONFIG",
        "# Requires Kconfig olddefconfig, manual security review and ABI tests.",
        "# Never flash this file or any image made from it to a TV.",
        *patched, "",
    ])


def stage(source: Path, fragment_path: Path, stage_dir: Path) -> dict:
    if q60t_kernel_build.source_version(source) != "4.1.10":
        raise ValueError("Expected a Linux 4.1.10 ARM source tree")
    if source.resolve() == stage_dir.resolve() or stage_dir.resolve().is_relative_to(source.resolve()):
        raise ValueError("Staging directory must be outside vendor source")
    if stage_dir.exists() or stage_dir.is_symlink():
        raise ValueError("Staging directory already exists; refusing overwrite")
    candidates = bridge.read_nike_configs(source)
    baseline = candidates[bridge.REFERENCE_PROFILE]
    changes = parse_fragment(fragment_path)
    if ("ANDROID_BINDER_IPC" in changes
            and changes.get("ANDROID_BINDER_IPC_32BIT") != "n"):
        raise ValueError("Binder enablement requires explicit legacy ABI override")
    original_path = source / "arch/arm/configs" / bridge.REFERENCE_PROFILE
    original_bytes = original_path.read_bytes()
    expected = hashlib.sha256(original_bytes).hexdigest()
    if expected != baseline["sha256"]:
        raise ValueError("Source configuration changed during staging")
    original = original_bytes.decode("utf-8")
    result_text = shadow_config(original, changes)
    candidate_values = {
        **baseline["symbols"], **changes,
    }
    security_untouched = all(
        candidate_values.get(name) == baseline["symbols"].get(name)
        for name in ("SECURITY_SFD", "SECURITY_SMACK", "SECURITY_SELINUX")
    )
    if not security_untouched:
        raise ValueError("Vendor kernel security options changed")
    manifest = {
        "type": "q60t_kernel_shadow_staging",
        "status": "STAGED_NOT_KCONFIG_VALIDATED",
        "source_version": "4.1.10",
        "baseline_config_name": bridge.REFERENCE_PROFILE,
        "baseline_sha256": baseline["sha256"],
        "fragment_sha256": hashlib.sha256(fragment_path.read_bytes()).hexdigest(),
        "staged_config_sha256": hashlib.sha256(result_text.encode("utf-8")).hexdigest(),
        "changed_symbols": {f"CONFIG_{name}": value for name, value in sorted(changes.items())},
        "expected_symbol_values_before_kconfig": {
            f"CONFIG_{name}": candidate_values[name] for name in sorted(changes)
        },
        "vendor_security_untouched": security_untouched,
        "kconfig_olddefconfig_executed": False,
        "cross_compile_executed": False,
        "android_abi_verified": False,
        "boot_or_flash_performed": False,
        "flash_authorized": False,
        "note": "The staged .config is a text merge only. Kconfig may change its "
                "values after dependency resolution; no compiler or Android HAL "
                "has been validated. Use an isolated build output directory.",
    }
    stage_dir.mkdir(parents=False, exist_ok=False)
    with (stage_dir / ".config").open("x", encoding="utf-8") as handle:
        handle.write(result_text)
    with (stage_dir / "STAGE_MANIFEST.json").open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage a host-only experimental Nike-L candidate config"
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--fragment", type=Path, required=True)
    parser.add_argument("--stage-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = stage(args.source, args.fragment, args.stage_dir)
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"Kernel-Staging fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
