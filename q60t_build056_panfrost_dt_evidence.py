#!/usr/bin/env python3
"""Build 056: read-only, hash-pinned firmware DTB and Mali-G51 module audit.

The output is an offline evidence report, not a bootable or flashable device tree.
No Linux kernel module, device tree, or firmware code is ever executed.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys


KNOWN_SHA256 = {
    "dtb": "9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2",
    "gpu": "115aadc5b2874cc4210f9b6c58bf2b4e09abadfe84fe7ad217f17770b21ecf29",
    "drm": "be8d3e249f813dad1258269dfe074d66668111390b84ed6c7915a310fe4b94ba",
}
FDT_MAGIC = b"\xd0\x0d\xfe\xed"


def get_pinned_file(path, family, limit=8 * 1024 * 1024):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Expected small regular original firmware file: " + family)
    blob = path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != KNOWN_SHA256[family]:
        raise ValueError("Hash mismatch for original firmware " + family)
    return blob


def words(blob):
    if len(blob) % 4:
        raise ValueError("Non-cell-aligned numeric device-tree property")
    return list(struct.unpack(">" + "I" * (len(blob) // 4), blob))


def strings(blob):
    return [item.decode("utf-8", "replace") for item in blob.split(b"\0") if item]


def parse_fdt_at(blob, rootbase):
    if blob[rootbase:rootbase + 4] != FDT_MAGIC or len(blob) < rootbase + 40:
        raise ValueError("Invalid device-tree magic/header")
    (magic, total, off_struct, off_strings, off_reserved, version, last_compat,
     boot_cpuid, strings_size, struct_size) = struct.unpack_from(">10I", blob, rootbase)
    if (version != 17 or total > 256 * 1024 or rootbase + total > len(blob)
            or off_struct + struct_size > total or off_strings + strings_size > total):
        raise ValueError("Unexpected device-tree bounds/version")

    name_table = blob[rootbase + off_strings:rootbase + off_strings + strings_size]
    position = rootbase + off_struct
    end = position + struct_size
    stack = []
    nodes = {}

    while position + 4 <= end:
        tag = struct.unpack_from(">I", blob, position)[0]
        position += 4
        if tag == 1:  # FDT_BEGIN_NODE
            terminator = blob.find(b"\0", position, end)
            if terminator < 0:
                raise ValueError("Unterminated device-tree node")
            stack.append(blob[position:terminator].decode("utf-8", "replace"))
            position = (terminator + 4) & ~3
            path = "/" + "/".join(part for part in stack if part)
            if path in nodes:
                raise ValueError("Duplicate device-tree path: " + path)
            nodes[path] = {}
        elif tag == 2:  # FDT_END_NODE
            if not stack:
                raise ValueError("Unbalanced device-tree end-node")
            stack.pop()
        elif tag == 3:  # FDT_PROP
            if position + 8 > end or not stack:
                raise ValueError("Truncated device-tree property")
            length, name_offset = struct.unpack_from(">II", blob, position)
            position += 8
            if name_offset >= len(name_table) or position + length > end:
                raise ValueError("Invalid device-tree property length/name")
            terminator = name_table.find(b"\0", name_offset)
            if terminator < 0:
                raise ValueError("Unterminated device-tree property name")
            key = name_table[name_offset:terminator].decode("ascii", "replace")
            path = "/" + "/".join(part for part in stack if part)
            nodes[path][key] = blob[position:position + length]
            position = (position + length + 3) & ~3
        elif tag == 4:  # FDT_NOP
            continue
        elif tag == 9:  # FDT_END
            if stack:
                raise ValueError("Unbalanced device-tree root")
            return nodes
        else:
            raise ValueError("Unknown device-tree token: " + str(tag))
    raise ValueError("Missing device-tree END token")


def inspect(dtb_path, gpu_path, drm_path):
    dtb = get_pinned_file(dtb_path, "dtb")
    gpu = get_pinned_file(gpu_path, "gpu")
    drm = get_pinned_file(drm_path, "drm")
    for label, module in (("GPU", gpu), ("DRM", drm)):
        if (module[:5] != b"\x7fELF\x01" or module[5] != 1
                or struct.unpack_from("<H", module, 18)[0] != 40):
            raise ValueError(label + " is not the expected ELF32 ARM module")
    if b"Mali-G51" not in gpu or b"r11p0-01rel0" not in gpu:
        raise ValueError("Mali-G51 or r11p0 marker missing from pinned module")

    # The Samsung firmware file is a multi-DTB container with two known FDTs.
    bases = [m.start() for m in re.finditer(re.escape(FDT_MAGIC), dtb)]
    if bases != [0, 86016]:
        raise ValueError("Unexpected Samsung firmware DTB layout")

    variants = []
    for base in bases:
        nodes = parse_fdt_at(dtb, base)
        gpu_node = nodes.get("/soc/sdpgpu@00500000")
        clock_node = nodes.get("/soc/clock-controller@00F50000")
        chosen = nodes.get("/chosen", {})
        if not gpu_node or not clock_node:
            raise ValueError("Required original Samsung GPU/clock nodes are missing")
        if strings(gpu_node.get("compatible", b"")) != ["arm,mali-midgard"]:
            raise ValueError("Unexpected original Samsung GPU compatible")
        if strings(gpu_node.get("interrupt-names", b"")) != ["JOB", "MMU", "GPU"]:
            raise ValueError("Unexpected Samsung GPU interrupt order")

        reg = words(gpu_node.get("reg", b""))
        irqs = words(gpu_node.get("interrupts", b""))
        clock_regs = words(clock_node.get("reg", b""))
        if (reg != [0x00500000, 0x4000]
                or irqs != [0, 0x72, 0, 0, 0x71, 0, 0, 0x70, 0]
                or clock_regs != [0x00F50000, 0x3000]):
            raise ValueError("Unexpected GPU, IRQ, or clock-controller register values")

        cpu_nodes = [name for name in nodes if re.search(r"/cpu@[0-3]$", name)]
        if len(cpu_nodes) != 4 or any("arm,cortex-a57" not in strings(nodes[n].get("compatible", b""))
                                      for n in cpu_nodes):
            raise ValueError("Expected original ARMv8 Cortex-A57 device tree CPU nodes absent")

        bootargs = strings(chosen.get("bootargs", b""))
        marker = re.search(r"nikel-(?:2G|1\.5G)", " ".join(bootargs))
        if not marker:
            raise ValueError("Unknown Nike-L memory variant")
        variants.append({
            "offset": base,
            "label": marker.group(0),
            "cpu_compatible": "arm,cortex-a57",
            "cpu_count": len(cpu_nodes),
            "gpu": {
                "original_compatible": strings(gpu_node["compatible"])[0],
                "register_base": "0x%08x" % reg[0],
                "register_bytes": reg[1],
                "interrupt_names_original": ["JOB", "MMU", "GPU"],
                "interrupt_specifiers_raw": [irqs[i:i + 3] for i in range(0, len(irqs), 3)],
                "has_clocks_property": "clocks" in gpu_node,
                "has_power_domains_property": "power-domains" in gpu_node,
            },
            "clock_controller": {
                "compatible": strings(clock_node["compatible"]),
                "register_base": "0x%08x" % clock_regs[0],
                "register_bytes": clock_regs[1],
            },
        })

    if {v["label"] for v in variants} != {"nikel-2G", "nikel-1.5G"}:
        raise ValueError("Expected both Samsung Nike-L memory variants")

    return {
        "build": "056",
        "status": "ORIGINAL_FIRMWARE_GPU_DTB_EVIDENCE_VERIFIED_OFFLINE",
        "origin": "Samsung-Q60T-Tizen-2743-FullOS.zip (user-provided URL)",
        "original_archive_sha256_verified": False,
        "extracted_entry_crc32_checked": True,
        "verified_entry_sha256": KNOWN_SHA256,
        "verified_elf32_arm_modules": ["sdp_gpu.ko", "sdp_drm.ko"],
        "gpu_model_string_in_original_module": "Mali-G51",
        "original_gpu_module_version": "r11p0-01rel0 (UK version 11.6)",
        "upstream_linux_6_6_candidate": "arm,mali-bifrost / Panfrost GPU_MODEL(g51, 0x7000)",
        "variants": variants,
        "caveats": [
            "Firmware image may cover more than one TV hardware configuration.",
            "Cortex-A57 is specified in this DTB; Cortex-A72 is NOT verified by this evidence.",
            "Raw interrupt specifier flags are zero; verify IRQ polarity/type before enabling.",
            "Samsung GPIO/clock/reset and power-domain integration is NOT ported.",
            "The disabled compile-only DTS is not a complete Samsung board DT.",
        ],
        "device_tree_candidate_status": "DISABLED_REFERENCE_ONLY_NOT_BINDING_VALIDATED",
        "real_tv_access_performed": False,
        "driver_compiled_against_linux_6_6": False,
        "safe_to_flash": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dtb", required=True)
    parser.add_argument("--gpu-ko", required=True)
    parser.add_argument("--drm-ko", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect(args.dtb, args.gpu_ko, args.drm_ko)
        with os.fdopen(os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600),
                       "w", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        print(result["status"] + "; safe_to_flash=false")
        return 0
    except (OSError, ValueError, KeyError, struct.error) as exc:
        print("Build 056 firmware audit refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
