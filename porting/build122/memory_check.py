"""Check Nike-L static memory evidence and optionally verify BUILD121 files."""

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
import sys
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent / "build111"))
sys.path.insert(0, str(HERE.parent / "build121"))
import legacy_uimage
import package as build111
from q60t_hardware import parse_fdt

REPORTS = ROOT / "reports"
IMAGE = "BUILD121-Q60T-OFFLINE-ONLY.uImage"
LOAD = 0x80008000
BUILD121_IMAGE_BYTES = 34070520


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def intervals(ranges):
    return [[hex(start), hex(end)] for start, end in ranges]


def static_map(profile, tree):
    evidence = build111.STOCK[profile]
    build111.require(
        tree["dtb_sha256"] == evidence["fdt_sha256"]
        and tree["offset_bytes"] == int(evidence["offset"], 16),
        "Firmware DTB identity mismatch",
    )
    banks = []
    for row in tree["summary"]["memory_reg"]["ranges"]:
        start = int(row["base_hex"], 16)
        banks.append((start, start + row["size_bytes"]))
    banks = build111.disjoint(banks, "RAM banks")

    reservations = []
    for row in evidence["reservations"]:
        start = int(row["base"], 16)
        span = (start, start + int(row["size"], 16))
        overlaps = [part for bank in banks if (part := build111.intersect(bank, span))]
        reservations.append({
            **row, "interval": intervals([span])[0],
            "in_ram_intervals": intervals(overlaps),
            "offline_dtb_no_map": "no-map" in row["stock_flags"],
        })
    free = build111.free_intervals(banks, [
        tuple(int(value, 16) for value in row["interval"]) for row in reservations
    ])
    return {
        "ram_banks": intervals(banks), "reservations": reservations,
        "free_intervals_static_only": intervals(free),
        "largest_static_gap_bytes": max(end - start for start, end in free),
    }


def load_check(header, static):
    result = legacy_uimage.placement(header, static["free_intervals_static_only"])
    start, end = (int(value, 16) for value in result["load_interval_end_exclusive"])
    result["inside_one_advertised_bank"] = any(
        int(low, 16) <= start < end <= int(high, 16) for low, high in static["ram_banks"]
    )
    result["overlapping_reservations"] = [
        row["node"] for row in static["reservations"]
        if build111.intersect((start, end), tuple(int(value, 16) for value in row["interval"]))
    ]
    return result


def match_header(actual, expected):
    build111.require(all(actual[key] == expected[key] for key in expected), "Header evidence mismatch")


def verify_memory_dtb(blob, profile, static):
    nodes = parse_fdt(blob)["nodes"]
    reserved = "/reserved-memory"
    cells = struct.pack(">I", 2)
    build111.require(all(nodes[node].get("#address-cells") == cells and
                         nodes[node].get("#size-cells") == cells for node in ("/", reserved)),
                     "Unexpected DTB cell widths")
    compatible = nodes["/"]["compatible"].split(b"\0")[0]
    build111.require(compatible == f"samsung,q60t-nikel-{profile}".encode(),
                     "Unexpected DTB profile")
    reserve_offset = struct.unpack_from(">I", blob, 16)[0]
    build111.require(blob[reserve_offset:reserve_offset + 16] == bytes(16)
                     and nodes[reserved].get("ranges") == b"", "Unexpected FDT reservations")

    banks = sorted((base, base + size) for path, props in nodes.items()
                   if path.count("/") == 1 and props.get("device_type") == b"memory\0"
                   for base, size in struct.iter_unpack(">QQ", props["reg"]))
    build111.require(intervals(banks) == static["ram_banks"], "DTB RAM banks differ from evidence")
    expected = {}
    for row in static["reservations"]:
        base, size = (int(row[key], 16) for key in ("base", "size"))
        props = {"reg": struct.pack(">QQ", base, size)}
        if row["offline_dtb_no_map"]:
            props["no-map"] = b""
        expected[f"{reserved}/stock@{base:x}"] = props
    actual = {path: props for path, props in nodes.items() if path.startswith(reserved + "/")}
    build111.require(actual == expected, "DTB reserved-memory differs from evidence")


def measure_gzip_image(zimage, expected_bytes):
    build111.require(0 < expected_bytes <= 128 << 20, "Unexpected raw Image size")
    matches = []
    for marker in re.finditer(b"\x1f\x8b\x08", zimage):
        try:
            decoder = zlib.decompressobj(31)
            raw = decoder.decompress(zimage[marker.start():], expected_bytes + 1)
        except zlib.error:
            continue
        if decoder.eof and len(raw) == expected_bytes:
            matches.append(hashlib.sha256(raw).hexdigest())
    build111.require(len(matches) == 1, "Expected one valid gzip Image matching reported size")
    return matches[0]


def memory_report(stock=None, artifacts=None, archive=None):
    firmware = read_json(REPORTS / "hardware_2743.0_build004_final.json")
    kernel = read_json(REPORTS / "kernel_2743.0.json")
    legacy = read_json(REPORTS / "hardware_build050_evidence.json")["boot"]["legacy_image"]
    stock_header = {
        "load": int(legacy["load_address"], 16), "entry": int(legacy["entry_address"], 16),
        "arch": legacy["arch_id"], "payload_bytes": kernel["payload_size"],
    }
    if stock:
        actual = legacy_uimage.stock_header(stock.resolve(), kernel["uimage_sha256"])
        match_header(actual, stock_header)
        stock_header = actual

    stock_source = ("Original uImage SHA-256 and both CRCs" if stock else
                    "reports/hardware_build050_evidence.json and reports/kernel_2743.0.json")
    generated = {"load": LOAD, "entry": LOAD, "payload_bytes": 12030464}
    raw_bytes = None
    raw_sha256 = None
    raw_source = "UNKNOWN"
    profiles = {
        profile: static_map(profile, next(tree for tree in firmware["trees"]
                            if tree["offset_bytes"] == int(data["offset"], 16)))
        for profile, data in build111.STOCK.items()
    }
    files = build111.verify(archive) if archive else None
    if files:
        for profile, dtb in zip(("1g5", "2g"), build111.DTBS):
            measured = json.loads(files["report.json"])["profiles"][profile]
            for key in ("ram_banks", "free_intervals_static_only"):
                build111.require(measured[key] == profiles[profile][key],
                                 f"{dtb}: {key} differs from firmware evidence")

    if artifacts:
        names = (IMAGE, *build111.DTBS, "initramfs.cpio", "kernel.config", "build-report.json")
        packaged = {name: (artifacts / name).read_bytes() for name in names}
        build111.require((artifacts / "SHA256SUMS").read_bytes() == build111.sums(packaged),
                         "BUILD121 SHA256SUMS mismatch")
        header, payload = legacy_uimage.parse(packaged[IMAGE])
        match_header(header, dict(load=stock_header["load"], entry=stock_header["entry"],
                                 os=5, arch=2, type=2, compression=0))
        build111.require(payload[36:40] == bytes.fromhex("18286f01"), "Missing ARM zImage magic")
        artifact_report = json.loads(packaged["build-report.json"])
        build111.require(artifact_report["generated_header"] == header
                         and artifact_report["stock_uimage_sha256"] == kernel["uimage_sha256"],
                         "BUILD121 report header or stock identity mismatch")
        match_header(artifact_report["stock_header"], stock_header)
        if not stock:
            stock_header = artifact_report["stock_header"]
            stock_source = "BUILD121 build-report.json and repository firmware evidence"
        raw_bytes = artifact_report["sizes_bytes"]["Image"]
        build111.require(raw_bytes == BUILD121_IMAGE_BYTES, "BUILD121 raw Image size mismatch")
        raw_sha256 = measure_gzip_image(payload, raw_bytes)
        raw_source = "BUILD121 zImage embedded gzip, checked against BUILD121 build-report.json"
        for profile, dtb in zip(("1g5", "2g"), build111.DTBS):
            verify_memory_dtb(packaged[dtb], profile, profiles[profile])
        if files:
            build111.require(payload == files["zImage"] and all(
                packaged[name] == files[name] for name in names[1:-1]
            ), "BUILD121 payloads differ from verified BUILD111 archive")
        generated = header
    elif files:
        generated["payload_bytes"] = len(files["zImage"])

    if files:
        raw_bytes = len(files["Image"])
        raw_sha256 = hashlib.sha256(files["Image"]).hexdigest()
        raw_source = "BUILD111 Image verified against embedded gzip"

    for profile in profiles.values():
        profile["decompressed_image_capacity"] = {
            "required_bytes": raw_bytes or BUILD121_IMAGE_BYTES,
            "size_source": raw_source if raw_bytes else "BUILD121 reference size",
            "fits_in_largest_static_gap": profile["largest_static_gap_bytes"] >=
                                         (raw_bytes or BUILD121_IMAGE_BYTES),
            "runtime_placement": "UNKNOWN",
        }
        profile["stock_header_address_comparison"] = load_check(stock_header, profile)
        profile["generated_zimage_address_comparison"] = load_check(generated, profile)

    payload_files = packaged if artifacts else files
    return {
        "build": 122, "mode": "OFFLINE-ONLY", "hardware": "NO-GO",
        "address_translation": "UNKNOWN", "bootloader_handoff": "UNKNOWN",
        "stock_header": stock_header, "stock_uimage_sha256": kernel["uimage_sha256"],
        "stock_measurement_source": stock_source,
        "stock_binary_verified_locally": bool(stock),
        "generated_header_or_reference": generated,
        "generated_measurement_source": "verified BUILD121 uImage" if artifacts else
            "BUILD111 zImage length with reference addresses" if files else
            "requested BUILD121 payload length, binary unavailable",
        "payload_delta_bytes": generated["payload_bytes"] - stock_header["payload_bytes"],
        "memory_source": "reports/hardware_2743.0_build004_final.json and "
                         "porting/build111/stock-reservations.json",
        "compiled_dtb_verified": bool(files or artifacts),
        "uncompressed_image_bytes": raw_bytes, "uncompressed_image_sha256": raw_sha256,
        "uncompressed_image_source": raw_source,
        "decompression_destination": "UNKNOWN", "decompressor_workspace_bytes": None,
        "kernel_bss_and_runtime_footprint": "UNKNOWN",
        "dtb_placement": "UNKNOWN", "initramfs_placement": "UNKNOWN",
        "handoff_file_sizes_bytes": {name: len(payload_files[name])
                                     for name in (*build111.DTBS, "initramfs.cpio")}
                                    if payload_files else None,
        "profiles": profiles,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", type=Path)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = memory_report(args.stock, args.artifacts, args.archive)
    args.output.write_bytes((json.dumps(report, indent=2, sort_keys=True) + "\n").encode())


if __name__ == "__main__":
    main()
