#!/usr/bin/env python3
"""Read-only ELF and systemd unit audit for Samsung TV SWUVerifierTV.

Never executes SWU programs, never touches the TV, never modifies firmware.
Only evidence of static symbol names/units; not RSA verification proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

MAX_BIN_BYTES = 128 * 1024 * 1024
ROOT_REL_BINARY = "usr/bin/SWUVerifierTV"
UNITS_DIR = "usr/lib/systemd/system"
UNIT_FILES = (
    "swu-verifier-tv.service",
    "swu-verifier-tv.timer",
    "swu-core-tv.service",
    "swu-service.service",
    "org.tizen.tv.swu.verifier.TV.busname",
)
SYMBOL_TOKENS = (
    b"RSAValidation",
    b"AESEncryption",
    b"CRC32Validation",
    b"FlashSink",
    b"getExternalAppVerificationResult",
    b"OURSAValidationDesc",
    b"RSA_verify",
    b"EVP_PKEY_verify",
)
UNIT_KEYS = {
    "After", "Requires", "Requisite", "OnFailure", "ConditionPathExists",
    "Type", "BusName", "ExecStart", "User", "Group", "OnActiveSec", "Unit",
    "Name", "Service",
}


def inspect_blob(blob: bytes) -> dict:
    if len(blob) < 20 or blob[:4] != b"\x7fELF":
        raise ValueError("Not an ELF file")
    if len(blob) > MAX_BIN_BYTES:
        raise ValueError("ELF exceeds read-only size limit")
    machine = struct.unpack_from("<H", blob, 18)[0] if blob[5] == 1 else None
    markers = {}
    for token in SYMBOL_TOKENS:
        at = []
        start = 0
        while True:
            idx = blob.find(token, start)
            if idx == -1:
                break
            if len(at) < 4:
                at.append(f"0x{idx:x}")
            start = idx + 1
        markers[token.decode("ascii")] = {
            "present": bool(at),
            "first_file_offsets": at,
            "note": "literal bytes in ELF; not proven callable or reachable",
        }
    return {
        "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "elf_class": "ELF32" if blob[4] == 1 else ("ELF64" if blob[4] == 2 else "UNKNOWN"),
        "elf_endianness": "little" if blob[5] == 1 else ("big" if blob[5] == 2 else "UNKNOWN"),
        "elf_machine": machine,
        "machine_arm32": blob[4] == 1 and blob[5] == 1 and machine == 40,
        "string_markers": markers,
    }


def parse_unit(content: str) -> dict:
    section = None
    result = {}
    for line in content.splitlines():
        item = line.strip()
        if not item or item.startswith(("#", ";")):
            continue
        if item.startswith("[") and item.endswith("]"):
            section = item[1:-1]
            continue
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        if section in {"Unit", "Service", "Timer", "BusName"} and key in UNIT_KEYS:
            result.setdefault(section, {}).setdefault(key, []).append(value.strip())
    return result


def _symbol_priority(entry: dict) -> tuple[int, str]:
    """Put concrete SWU methods before generic Boost/RTTI boilerplate.

    Ranking is a research aid; it is NOT proof a verification method runs.
    """
    name = entry["name"]
    own_rsa = bool(re.search(r"N(?:K)?3SWU6Common12UpgradeGraph13RSAValidation", name))
    defined_func = entry["type"] == "FUNC" and entry["section"] != "UND"
    boost_or_rtti = ("boost" in name or name.startswith(("_ZT", "_ZGV")))
    ctor_or_dtor = bool(re.search(r"(?:C[123]|D[012])Ev(?:@|$)", name))
    if own_rsa and defined_func and not ctor_or_dtor and not boost_or_rtti:
        return (0, name)
    if own_rsa and defined_func and not boost_or_rtti:
        return (1, name)
    if "getExternalAppVerificationResult" in name and defined_func:
        return (2, name)
    if defined_func and not boost_or_rtti:
        return (3, name)
    if defined_func:
        return (4, name)
    return (5, name)


def classify_dynsym_lines(output: str) -> dict:
    """Examine all dynamic symbol rows, not only first 30 matching rows."""
    matches = []
    for line in output.splitlines():
        if not any(t.decode("ascii") in line for t in SYMBOL_TOKENS):
            continue
        fields = line.split()
        if len(fields) < 8 or not fields[0].endswith(":"):
            continue
        matches.append({
            "type": fields[3],
            "binding": fields[4],
            "section": fields[6],
            "name": fields[7][:500],
        })
    matches.sort(key=_symbol_priority)
    own_rsa = [
        x for x in matches if
        re.search(r"N(?:K)?3SWU6Common12UpgradeGraph13RSAValidation", x["name"])
        and x["type"] == "FUNC"
        and x["section"] != "UND"
        and "boost" not in x["name"]
    ]
    strongest = [x for x in own_rsa if _symbol_priority(x)[0] == 0]
    return {
        "interesting_dynsyms": matches[:30],
        "matching_dynamic_symbols_total": len(matches),
        "interesting_dynsyms_truncated": len(matches) > 30,
        "defined_rsa_class_functions": own_rsa[:30],
        "defined_rsa_class_function_count": len(own_rsa),
        "rsa_class_non_ctor_dtor_method_candidates": strongest[:30],
        "rsa_class_non_ctor_dtor_method_candidate_count": len(strongest),
        "warning": (
            "Defined method names alone do not identify a cryptographic check "
            "or prove execution; absence of exported symbols cannot exclude "
            "stripped/internal/static/dynamically loaded implementations."
        ),
    }


def readelf_metadata(binary: Path) -> dict:
    info = {
        "tool_available": False, "needed_libraries": [],
        "interesting_dynsyms": [], "matching_dynamic_symbols_total": 0,
        "rsa_class_non_ctor_dtor_method_candidates": [],
    }
    try:
        dyn = subprocess.run(
            ["readelf", "-W", "-d", str(binary)],
            capture_output=True, text=True, check=False, timeout=25
        )
        sym = subprocess.run(
            ["readelf", "-W", "--dyn-syms", str(binary)],
            capture_output=True, text=True, check=False, timeout=25
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        info["diagnostic"] = type(exc).__name__
        return info
    info["tool_available"] = True
    info["dynamic_section_success"] = dyn.returncode == 0
    info["dynamic_symbols_success"] = sym.returncode == 0
    if dyn.returncode == 0:
        info["needed_libraries"] = sorted(set(
            re.findall(r"Shared library: \[([^\]]+)\]", dyn.stdout)
        ))
    if sym.returncode == 0:
        info.update(classify_dynsym_lines(sym.stdout))
    return info


def analyze(root: Path) -> dict:
    if not root.is_dir():
        raise ValueError("RootFS path is not a directory")
    binary = root / ROOT_REL_BINARY
    if not binary.is_file():
        raise ValueError(f"Missing binary: {ROOT_REL_BINARY}")
    if binary.stat().st_size > MAX_BIN_BYTES:
        raise ValueError("ELF exceeds read-only size limit")
    binary_result = inspect_blob(binary.read_bytes())
    unit_results = {}
    for unit in UNIT_FILES:
        path = root / UNITS_DIR / unit
        unit_results[unit] = (
            {"exists": True, "selected_properties": parse_unit(path.read_text(encoding="utf-8", errors="replace"))}
            if path.is_file() else {"exists": False}
        )
    return {
        "schema": "build079_swu_verifier_static_audit_v1",
        "status": "STATIC_ELF_AND_SYSTEMD_METADATA_ONLY",
        "target_relative_path": ROOT_REL_BINARY,
        "binary": binary_result,
        "readelf": readelf_metadata(binary),
        "systemd_units": unit_results,
        "interpretation": [
            "RSAValidation names and C++ type information do not establish an executing RSA verification routine.",
            "Systemd After/Requisite describe start ordering/dependencies, not an internal function-call trace.",
            "MSD OURSAValidationDesc is an update-metadata descriptor, not proven equivalent to any extracted image 256-byte footer.",
            "Absence of direct libcrypto in NEEDED does not exclude static libraries or dlopen.",
        ],
        "rsa_validation_confirmed": False,
        "bootloader_authentication_confirmed": False,
        "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rootfs", required=True, type=Path, help="Existing extracted rootfs path")
    args = ap.parse_args(argv)
    try:
        report = analyze(args.rootfs)
    except (OSError, ValueError) as exc:
        print(f"Build079 error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
