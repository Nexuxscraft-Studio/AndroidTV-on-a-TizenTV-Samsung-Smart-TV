#!/usr/bin/env python3
"""Read-only Android-TV graphics bring-up evidence and Mali ELF ABI triage.

This is not a Mali driver, a compositor, or an Android HAL implementation.
Unknown vendor binaries must never be incorporated into a public release.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys


MAX_LIBRARY_SIZE = 128 * 1024 * 1024
MACHINES = {40: "ARM32", 183: "AArch64", 3: "x86", 62: "x86_64"}
REFERENCE_DTB_SHA256 = "9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2"
REFERENCE_KERNEL_SHA256 = "6603f3f5082d6ef74471f9233ce17063658daf10e1d9440a8a9c75749a5e72b2"


def _section_header(blob: bytes, offset: int, bits: int, order: str) -> dict:
    if bits == 32:
        values = struct.unpack_from(order + "10I", blob, offset)
        return {"type": values[1], "offset": values[4], "size": values[5],
                "link": values[6], "entsize": values[9]}
    values = struct.unpack_from(order + "IIQQQQIIQQ", blob, offset)
    return {"type": values[1], "offset": values[4], "size": values[5],
            "link": values[6], "entsize": values[9]}


def inspect_elf(path: Path) -> dict:
    """Extract ELF class/machine and DT_NEEDED without loading/executing it."""
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_LIBRARY_SIZE:
        raise ValueError("ELF absent, symlink or larger than 128 MiB")
    blob = path.read_bytes()
    if len(blob) < 64 or blob[:4] != b"\x7fELF":
        raise ValueError("ELF header missing")
    bits = {1: 32, 2: 64}.get(blob[4])
    order = {1: "<", 2: ">"}.get(blob[5])
    if bits is None or order is None:
        raise ValueError("Unsupported ELF class or endian")
    e_type, machine = struct.unpack_from(order + "HH", blob, 16)
    if bits == 32:
        shoff = struct.unpack_from(order + "I", blob, 32)[0]
        shentsize, shnum = struct.unpack_from(order + "HH", blob, 46)
        minimum_section_bytes = 40
    else:
        shoff = struct.unpack_from(order + "Q", blob, 40)[0]
        shentsize, shnum = struct.unpack_from(order + "HH", blob, 58)
        minimum_section_bytes = 64
    if shnum > 2048 or (shnum and (shentsize < minimum_section_bytes
                                    or shoff + shentsize * shnum > len(blob))):
        raise ValueError("ELF section table bounds invalid")
    sections = [_section_header(blob, shoff + i * shentsize, bits, order)
                for i in range(shnum)]
    needed = []
    for section in sections:
        if section["type"] != 6 or section["link"] >= len(sections):
            continue
        dynstr = sections[section["link"]]
        if (dynstr["offset"] + dynstr["size"] > len(blob)
                or section["offset"] + section["size"] > len(blob)):
            raise ValueError("ELF dynamic/string section out of bounds")
        strings = blob[dynstr["offset"]:dynstr["offset"] + dynstr["size"]]
        step = 8 if bits == 32 else 16
        if section["size"] % step:
            raise ValueError("ELF malformed dynamic entry array")
        for pos in range(section["offset"], section["offset"] + section["size"], step):
            tag, ptr = struct.unpack_from(order + ("II" if bits == 32 else "QQ"), blob, pos)
            if tag != 1 or ptr >= len(strings):
                continue
            end = strings.find(b"\x00", ptr)
            if end < 0:
                continue
            name = strings[ptr:end]
            if re.fullmatch(rb"[a-zA-Z0-9_.+\-]{1,90}", name):
                needed.append(name.decode("ascii"))
    # Linux modules normally carry an ASCII `vermagic` in .modinfo; finding
    # one does not establish the complete module ABI or signature validity.
    modversion = re.search(rb"(?:^|\x00)vermagic=([A-Za-z0-9_. +\-]{3,120})\x00", blob)
    return {"type": "elf_binary_abi_report", "sha256": hashlib.sha256(blob).hexdigest(),
            "bits": bits, "endianness": "little" if order == "<" else "big",
            "machine_id": machine, "machine": MACHINES.get(machine, "unknown"),
            "elf_type": e_type, "shared_dependencies": sorted(set(needed))[:80],
            "module_vermagic_string": modversion.group(1).decode("ascii") if modversion else None,
            "executable_loaded": False}


def graphics_preflight(hardware: dict, kernel: dict,
                       userspace: dict | None = None,
                       module: dict | None = None) -> dict:
    target_profiles = {}
    if (hardware.get("device_trees_found", 0) < 2
            or hardware.get("dtb_bundle_sha256") != REFERENCE_DTB_SHA256
            or kernel.get("uimage_sha256") != REFERENCE_KERNEL_SHA256):
        raise ValueError("Firmware report does not match the exact reference components")
    for tree in hardware["trees"][:2]:
        categories = tree["summary"]["hardware_categories"]
        gpu = [n for n in categories["gpu"]
               if n.get("path") == "/soc/sdpgpu@00500000"]
        drm = [n for n in categories["display"]
               if any("sdp-drm" in c for c in n.get("compatible", []))]
        target_profiles[str(tree["offset_bytes"])] = {
            "gpu": gpu[:1], "samsung_display_drm": drm[:4],
        }
    user_abi = userspace["machine"] if userspace else None
    if user_abi == "AArch64":
        # The *actual* legacy uImage (verified via its SHA-256 above) is ARM32.
        userspace_abi_compatible = False
    else:
        userspace_abi_compatible = user_abi == "ARM32" if userspace else None
    checks = {
        "matching_mali_kernel_driver_available": module is not None,
        "candidate_userspace_elf_available": userspace is not None,
        "candidate_userspace_arm32": userspace_abi_compatible is True,
        "kernel_module_arm32": module is not None and module.get("machine") == "ARM32",
        "kernel_module_version_string_matches": bool(
            module and (module.get("module_vermagic_string") or "").startswith("4.1.10")),
        "exact_gpu_hardware_revision_verified": False,
        "android_egl_gralloc_compatible": False,
        "android_composer3_hal_implemented": False,
        "samsung_panel_modesetting_verified": False,
        "android_sync_fences_validated": False,
    }
    return {
        "type": "samsung_nikel_android_graphics_preflight",
        "status": "BLOCKED",
        "source_fdt_bundle_sha256": hardware["dtb_bundle_sha256"],
        "source_kernel_uimage_sha256": kernel["uimage_sha256"],
        "reference_profiles_by_dtb_offset": target_profiles,
        "userspace_elf": userspace, "kernel_module_elf": module,
        "checks": checks,
        "caution": "DT-compatible arm,mali-midgard alone does NOT prove the GPU generation. "
                   "External researchers report Mali-G51/Bifrost r11p0; validate exact hardware/driver before porting.",
        "safe_for_android_build": False, "flash_authorized": False,
        "note": "Graphics adaptation requires kernel source, matching Mali driver, buffers, EGL, gralloc and an Android composer HAL.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q60T offline graphics/ELF preflight")
    parser.add_argument("--hardware-report", type=Path, required=True)
    parser.add_argument("--kernel-report", type=Path, required=True)
    parser.add_argument("--libmali", type=Path)
    parser.add_argument("--kernel-module", type=Path)
    parser.add_argument("--output", type=Path, help="new JSON only")
    args = parser.parse_args(argv)
    try:
        hardware = json.loads(args.hardware_report.read_text(encoding="utf-8"))
        kernel = json.loads(args.kernel_report.read_text(encoding="utf-8"))
        report = graphics_preflight(
            hardware, kernel,
            inspect_elf(args.libmali) if args.libmali else None,
            inspect_elf(args.kernel_module) if args.kernel_module else None)
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as output:
                output.write(payload)
        else:
            print(payload, end="")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Grafik-Prüfung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    return 1  # Evidence available, but Android graphics is not implemented.


if __name__ == "__main__":
    raise SystemExit(main())
