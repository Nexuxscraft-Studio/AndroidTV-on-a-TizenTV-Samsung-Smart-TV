#!/usr/bin/env python3
"""Bounded, read-only Samsung Nike-L FDT and kernel metadata analysis.

Outputs intentionally omit raw property values except vetted hardware strings.
This is NOT a device port, image builder, firmware signer or flash utility.
"""

from __future__ import annotations

from collections import Counter
import gzip
import hashlib
from pathlib import Path
import re
import struct


FDT_MAGIC = b"\xd0\x0d\xfe\xed"
MAX_DTB_FILE = 32 * 1024 * 1024
MAX_NODES = 20_000
MAX_PROPERTIES = 100_000
MAX_KERNEL_FILE = 64 * 1024 * 1024
MAX_CONFIG_SIZE = 2 * 1024 * 1024
BOOTARGS_ALLOWLIST = {
    "root", "rootfstype", "rootwait", "rootdelay", "ro", "rw", "console",
    "earlyprintk", "init", "quiet", "loglevel", "panic", "mem",
}


def _hash(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _clean_strings(value: bytes) -> list[str]:
    """Decode *only* short printable NUL-terminated DT strings."""
    if not value or len(value) > 4096 or value[-1] != 0:
        return []
    results = []
    for part in value.split(b"\x00"):
        if not part:
            continue
        if len(part) > 256 or any(x < 32 or x > 126 for x in part):
            return []
        results.append(part.decode("ascii"))
    return results


def parse_fdt(blob: bytes) -> dict:
    """Parse the structural tree of exactly one bounded flattened device tree.

    The returned property values are *internal* binary objects. Do not put
    this result into reports; use summarize_tree/diff_trees instead.
    """
    if len(blob) < 40 or blob[:4] != FDT_MAGIC:
        raise ValueError("FDT magic or header missing")
    (magic, total, structure, strings, reserve, version, compatible_version,
     boot_cpu, strings_size, structure_size) = struct.unpack_from(">10I", blob)
    if (total > MAX_DTB_FILE or total < 40 or total > len(blob)
            or version not in (16, 17) or compatible_version > version
            or reserve < 40 or reserve >= total
            or structure < 40 or structure + structure_size > total
            or strings < 40 or strings + strings_size > total):
        raise ValueError("FDT size/version/section bounds invalid")
    strings_blob = blob[strings:strings + strings_size]
    position, end = structure, structure + structure_size
    stack: list[str] = []
    nodes: dict[str, dict[str, bytes]] = {}
    props_count = 0
    finished = False
    for _ in range(MAX_NODES + MAX_PROPERTIES + 10_000):
        if position + 4 > end:
            break
        (token,) = struct.unpack_from(">I", blob, position)
        position += 4
        if token == 1:  # BEGIN_NODE
            nul = blob.find(b"\x00", position, end)
            if nul < 0 or nul - position > 255:
                raise ValueError("FDT node name missing or oversized")
            name = blob[position:nul].decode("ascii", "replace")
            if "/" in name or (not stack and name != ""):
                raise ValueError("FDT invalid node path")
            stack.append(name)
            path = "/" + "/".join(stack[1:])
            if path in nodes:
                raise ValueError("FDT duplicate node path")
            nodes[path] = {}
            if len(nodes) > MAX_NODES:
                raise ValueError("FDT node limit exceeded")
            position = (nul + 4) & ~3
        elif token == 2:  # END_NODE
            if not stack:
                raise ValueError("FDT unbalanced end node")
            stack.pop()
        elif token == 3:  # PROPERTY
            if not stack or position + 8 > end:
                raise ValueError("FDT truncated/orphan property")
            length, name_offset = struct.unpack_from(">II", blob, position)
            position += 8
            if length > MAX_DTB_FILE or position + length > end or name_offset >= len(strings_blob):
                raise ValueError("FDT property out of bounds")
            name_nul = strings_blob.find(b"\x00", name_offset)
            if name_nul < 0:
                raise ValueError("FDT property name unterminated")
            name = strings_blob[name_offset:name_nul].decode("ascii", "replace")
            path = "/" + "/".join(stack[1:])
            if name in nodes[path]:
                raise ValueError("FDT duplicate property")
            nodes[path][name] = blob[position:position + length]
            props_count += 1
            if props_count > MAX_PROPERTIES:
                raise ValueError("FDT property limit exceeded")
            position = (position + length + 3) & ~3
        elif token == 4:  # NOP
            continue
        elif token == 9:  # END
            if stack:
                raise ValueError("FDT unclosed node")
            finished = True
            break
        else:
            raise ValueError(f"FDT unknown token {token}")
    if not finished or "/" not in nodes:
        raise ValueError("FDT missing END token or root")
    return {"nodes": nodes, "property_count": props_count,
            "bytes": total, "version": version, "boot_cpu": boot_cpu}


def _safe_compat(props: dict[str, bytes]) -> list[str]:
    return _clean_strings(props.get("compatible", b""))[:12]


def _safe_dt_status(props: dict[str, bytes]) -> str:
    """Distinguish disabled devices from mere presence in the device tree."""
    raw = props.get("status")
    if raw is None:
        return "unspecified"
    values = _clean_strings(raw)
    if values in (["okay"], ["ok"]):
        return "okay"
    if values == ["disabled"]:
        return "disabled"
    if values == ["reserved"]:
        return "reserved"
    return "unknown"


def _safe_bootargs(props: dict[str, bytes]) -> list[str]:
    raw = props.get("bootargs", b"")
    # Real Samsung DTBs carry blank padding after an ASCII command line;
    # strict DT string-list decoding would reject those extra NULs.
    raw = raw.split(b"\x00", 1)[0]
    if not raw or len(raw) > 4096 or any(x < 32 or x > 126 for x in raw):
        return []
    # Avoid exporting IP addresses, credentials or device-unique values.
    result = []
    for token in raw.decode("ascii").split():
        key = token.split("=", 1)[0]
        if key in BOOTARGS_ALLOWLIST and len(token) < 96:
            result.append(token)
    return result


def _memory_profile_hint(props: dict[str, bytes]) -> str | None:
    raw = props.get("bootargs", b"").split(b"\x00", 1)[0]
    if len(raw) > 4096:
        return None
    match = re.search(rb"\bdtsversion=\S*_nikel-(\d+(?:\.\d+)?)G\b", raw)
    return match.group(1).decode("ascii") + " GiB (firmware profile label)" if match else None


def _cell_count(props: dict[str, bytes], name: str, default: int) -> int | None:
    raw = props.get(name)
    if raw is None:
        return default
    if len(raw) != 4:
        return None
    count = struct.unpack(">I", raw)[0]
    return count if count in (1, 2) else None


def memory_reg_map(nodes: dict[str, dict[str, bytes]]) -> dict | None:
    """Read standard FDT /memory reg cells, not a physical RAM measurement.

    Only bounded address/size numbers are published. RAM reservations and
    bootloader-specific mappings can make the sum smaller than installed RAM.
    """
    root = nodes.get("/", {})
    address_cells = _cell_count(root, "#address-cells", 2)
    size_cells = _cell_count(root, "#size-cells", 1)
    if address_cells is None or size_cells is None:
        return None
    cell_width = address_cells + size_cells
    entries = []
    for path, props in nodes.items():
        if path != "/memory" and not path.startswith("/memory@"):
            continue
        reg = props.get("reg", b"")
        if not reg or len(reg) > 2048 or len(reg) % (cell_width * 4):
            continue
        words = struct.unpack(">" + "I" * (len(reg) // 4), reg)
        for pos in range(0, len(words), cell_width):
            addr = 0
            size = 0
            for word in words[pos:pos + address_cells]:
                addr = (addr << 32) | word
            for word in words[pos + address_cells:pos + cell_width]:
                size = (size << 32) | word
            if not size:
                continue
            if len(entries) >= 32:
                return None
            entries.append({"base_hex": f"0x{addr:x}", "size_bytes": size,
                            "size_mib": round(size / 1048576, 3)})
    if not entries:
        return None
    return {
        "address_cells": address_cells,
        "size_cells": size_cells,
        "ranges": entries,
        "sum_advertised_mib": round(sum(e["size_bytes"] for e in entries) / 1048576, 3),
        "warning": "FDT /memory/reg only. Not measured physical RAM or proof of TV compatibility.",
    }


def summarize_tree(tree: dict) -> dict:
    nodes = tree["nodes"]
    categories = {
        "cpu": [], "gpu": [], "display": [], "video": [],
        "audio": [], "network": [], "usb": [], "input": [], "storage": [],
    }
    patterns = {
        "gpu": r"mali|gpu",
        "display": r"drm|hdmi|panel|tcon|frc|display|lcd",
        "video": r"vdec|venc|codec|mfc|video",
        "audio": r"audio|sound|i2s|spdif|alsa",
        "network": r"ethernet|wifi|wlan|bluetooth|network|emac|gmac",
        "usb": r"usb|xhci|ehci|ohci",
        "input": r"gpio-key|infrared|remote|keypad|ir-receiver|"
                 r"sdp-mc-irb|sdp-mc-irs|micom|cecif",
        "storage": r"mmc|sdhci|emmc|spi-nand|flash|sata",
    }
    for path, props in nodes.items():
        compat = _safe_compat(props)
        # Include compatible labels rather than arbitrary path / property bytes.
        entry = {"path": path[:180], "compatible": compat[:8],
                 "dt_status": _safe_dt_status(props)}
        if path.startswith("/cpus/cpu@"):
            categories["cpu"].append(entry)
        for category, regex in patterns.items():
            if re.search(regex, (path + " " + " ".join(compat)).lower()):
                if len(categories[category]) < 80:
                    categories[category].append(entry)
    root_model = _clean_strings(nodes["/"].get("model", b""))
    boot = nodes.get("/chosen", {})
    return {
        "node_count": len(nodes), "property_count": tree["property_count"],
        "model": root_model[0] if root_model else None,
        "root_compatible": _safe_compat(nodes["/"]),
        "memory_profile_label": _memory_profile_hint(boot),
        "memory_reg": memory_reg_map(nodes),
        "bootargs_safe_subset": _safe_bootargs(boot),
        "hardware_categories": categories,
    }


def compare_trees(left: dict, right: dict, max_examples: int = 60) -> dict:
    a, b = left["nodes"], right["nodes"]
    left_paths, right_paths = set(a), set(b)
    common = left_paths & right_paths
    changes = []
    changed_properties = 0
    names_changed = Counter()
    for path in sorted(common):
        ap, bp = a[path], b[path]
        for name in sorted(set(ap) | set(bp)):
            if ap.get(name) == bp.get(name) and (name in ap) == (name in bp):
                continue
            changed_properties += 1
            names_changed[name] += 1
            if len(changes) < max_examples:
                changes.append({
                    "node": path[:180], "property_name": name[:80],
                    "kind": "added" if name not in ap else
                            "removed" if name not in bp else "value_changed",
                    # No values, serial numbers, MACs or keys are exported.
                })
    return {
        "only_first_node_count": len(left_paths - right_paths),
        "only_second_node_count": len(right_paths - left_paths),
        "only_first_node_examples": sorted(left_paths - right_paths)[:max_examples],
        "only_second_node_examples": sorted(right_paths - left_paths)[:max_examples],
        "changed_property_count": changed_properties,
        "changed_property_name_counts": dict(names_changed.most_common(35)),
        "changed_property_examples": changes,
        "note": "Property values deliberately omitted; paths/names are metadata only.",
    }


def hardware_report(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_DTB_FILE:
        raise ValueError("DTB file absent or exceeds 32 MiB")
    blob = path.read_bytes()
    trees = []
    start = 0
    while len(trees) < 64:
        offset = blob.find(FDT_MAGIC, start)
        if offset == -1:
            break
        start = offset + 4
        try:
            tree = parse_fdt(blob[offset:])
        except ValueError:
            continue
        length = tree["bytes"]
        trees.append({"offset_bytes": offset,
                      "dtb_sha256": _hash(blob[offset:offset + length]),
                      "summary": summarize_tree(tree), "_parsed": tree})
    report = {
        "type": "offline_hardware_device_tree_report",
        "dtb_bundle_sha256": _hash(blob), "device_trees_found": len(trees),
        "trees": [{k: v for k, v in t.items() if k != "_parsed"} for t in trees],
        "writes_to_tv": False,
        "disclaimer": "Firmware DT declarations, NOT verified on the user's 50-inch device.",
    }
    if len(trees) >= 2:
        report["comparison_first_two"] = compare_trees(
            trees[0]["_parsed"], trees[1]["_parsed"])
    return report


def inspect_kernel(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_KERNEL_FILE:
        raise ValueError("Kernel file absent or exceeds 64 MiB")
    blob = path.read_bytes()
    if len(blob) < 64 or blob[:4] != b"\x27\x05\x19\x56":
        raise ValueError("Expected U-Boot legacy uImage")
    size = struct.unpack_from(">I", blob, 12)[0]
    if size > len(blob) - 64:
        raise ValueError("Truncated uImage")
    payload = blob[64:64 + size]
    banner = re.search(rb"Linux version [\x20-\x7e]{5,220}", payload)
    # Keep only the version number, not full compiler builder names or paths.
    version = re.search(rb"Linux version (\d+\.\d+\.\d+[^\s]*)",
                        banner.group(0)) if banner else None
    compiler = re.search(rb"gcc version (\d+\.\d+\.\d+)",
                         banner.group(0)) if banner else None
    timestamp = re.search(rb"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) "
                          rb"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
                          rb"\d{1,2} \d\d:\d\d:\d\d UTC \d{4}",
                          banner.group(0)) if banner else None
    start = payload.find(b"IKCFG_ST")
    config = None
    config_error = None
    if start >= 0:
        compressed = payload[start + 8:]
        try:
            # gzip.GzipFile can inflate a malicious zip-bomb, so enforce cap.
            import io
            with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as handle:
                data = handle.read(MAX_CONFIG_SIZE + 1)
            if len(data) > MAX_CONFIG_SIZE:
                raise ValueError("embedded config exceeds 2 MiB")
            lines = data.decode("ascii", "replace").splitlines()
            configs = [line for line in lines if line.startswith("CONFIG_")]
            options = {
                "CONFIG_ARM64", "CONFIG_ARM", "CONFIG_SMP", "CONFIG_DEVTMPFS",
                "CONFIG_DRM", "CONFIG_FB", "CONFIG_MALI", "CONFIG_SND",
                "CONFIG_MODULES", "CONFIG_SECCOMP", "CONFIG_UEP",
                "CONFIG_ANDROID", "CONFIG_ASHMEM", "CONFIG_BINDER",
            }
            config = {"options_found": len(configs),
                      "selected_options": {key: value for key, value in
                                           (line.split("=", 1) for line in configs
                                            if "=" in line) if key in options}}
        except (OSError, EOFError, ValueError) as exc:
            config_error = str(exc)
    # Merely code/string presence; NOT a runtime test or successful verification.
    security_symbols = (
        "SfdUepVerifyExecutableBinary", "SfdUepVerifyFileSignature",
        "SfdUepVerifyDynamicLibrary", "SfdUepHandleVerificationResult",
        "security.SMACK64EXEC", "kernel/seccomp.c",
    )
    found_symbols = [symbol for symbol in security_symbols
                     if symbol.encode("ascii") in payload]
    return {
        "type": "offline_kernel_metadata_report",
        "uimage_sha256": _hash(blob), "payload_size": size,
        "version_from_banner": version.group(1).decode("ascii") if version else None,
        "gcc_version_from_banner": compiler.group(1).decode("ascii") if compiler else None,
        "tizen_linaro_toolchain_string_present": bool(
            banner and b"Tizen/Linaro GCC" in banner.group(0)),
        "build_timestamp_from_banner": timestamp.group(0).decode("ascii") if timestamp else None,
        "embedded_ikconfig_marker_present": start >= 0,
        "embedded_kconfig": config, "config_read_error": config_error,
        "security_symbols_found": found_symbols,
        "writes_to_tv": False,
        "note": "Strings imply compiled code or references, not runtime enforcement. "
                "No config marker is not proof of any particular kernel option.",
    }
