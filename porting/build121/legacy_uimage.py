"""Wrap verified Build 111 zImages in a U-Boot legacy header for offline review."""

import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import zlib

HEADER = struct.Struct(">7I4B32s")
MAGIC = 0x27051956
LINUX_ARM_KERNEL = (5, 2, 2)
EPOCH = 1735689600
MAX_IMAGE_BYTES = 128 << 20
ARCHIVE = "BUILD111-Q60T-OFFLINE-ONLY.zip"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse(blob, *, allow_trailer=False):
    require(len(blob) >= HEADER.size, "Truncated legacy header")
    magic, hcrc, timestamp, size, load, entry, dcrc, os_id, arch, kind, comp, name = (
        HEADER.unpack_from(blob)
    )
    require(magic == MAGIC, "Invalid legacy image magic")
    require(zlib.crc32(blob[:4] + bytes(4) + blob[8:HEADER.size]) == hcrc,
            "Invalid legacy header CRC32")
    end = HEADER.size + size
    require(size > 0 and end <= len(blob), "Invalid legacy payload size")
    require(allow_trailer or end == len(blob), "Unexpected legacy image trailer")
    payload = blob[HEADER.size:end]
    require(zlib.crc32(payload) == dcrc, "Invalid legacy payload CRC32")
    return {
        "magic": hex(magic), "header_bytes": HEADER.size, "timestamp": timestamp,
        "header_crc32": hex(hcrc), "payload_crc32": hex(dcrc), "payload_bytes": size,
        "load": load, "entry": entry, "os": os_id, "arch": arch, "type": kind,
        "compression": comp, "name": name.split(b"\0", 1)[0].decode("ascii", "replace"),
        "trailing_bytes": len(blob) - end,
    }, payload


def stock_header(path, digest):
    require(path.is_absolute() and path.is_file(), "Set an absolute stock uImage path")
    require(re.fullmatch(r"[0-9a-fA-F]{64}", digest), "Set the stock uImage SHA-256")
    with path.open("rb") as source:
        blob = source.read(MAX_IMAGE_BYTES + 1)
    require(len(blob) <= MAX_IMAGE_BYTES, "Stock reference exceeds inspection size limit")
    require(hashlib.sha256(blob).hexdigest() == digest.lower(), "Stock uImage SHA-256 mismatch")
    header, _ = parse(blob, allow_trailer=True)
    require(tuple(header[key] for key in ("os", "arch", "type")) == LINUX_ARM_KERNEL,
            "Stock header must describe a Linux ARM32 kernel")
    return header


def wrap(zimage, target, stock):
    payload = zimage.read_bytes()
    require(payload[36:40] == bytes.fromhex("18286f01"), "Missing ARM zImage magic")
    subprocess.run([
        "mkimage", "-A", "arm", "-O", "linux", "-T", "kernel", "-C", "none",
        "-a", hex(stock["load"]), "-e", hex(stock["entry"]),
        "-n", "BUILD121 Q60T offline", "-d", str(zimage), str(target),
    ], check=True, env={**os.environ, "SOURCE_DATE_EPOCH": str(EPOCH), "TZ": "UTC"})
    image = target.read_bytes()
    header, wrapped = parse(image)
    require(wrapped == payload and header["timestamp"] == EPOCH, "Unexpected mkimage output")
    require(tuple(header[key] for key in ("os", "arch", "type")) == LINUX_ARM_KERNEL
            and header["compression"] == 0
            and all(header[key] == stock[key] for key in ("load", "entry")),
            "Unexpected mkimage header fields")
    return header


def placement(header, free_ranges):
    start = header["load"]
    end = start + header["payload_bytes"]
    entry = header["entry"]
    within_arm32 = 0 <= start < end <= 1 << 32
    return {
        "load_interval_end_exclusive": [hex(start), hex(end)],
        "within_arm32": within_arm32,
        "entry_in_payload": start <= entry < end,
        "entry_at_zimage_start": entry == start and entry % 4 == 0,
        "inside_static_free_ram": within_arm32 and any(
            int(low, 16) <= start and end <= int(high, 16) for low, high in free_ranges
        ),
    }


def package(work, stock, digest):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build111"))
    import package as build111

    targets = []
    for pass_name in ("a", "b"):
        tree = work / pass_name
        files = build111.verify(tree / ARCHIVE)
        kernel = tree / "zImage"
        kernel.write_bytes(files["zImage"])
        target = tree / "uImage"
        header = wrap(kernel, target, stock)
        targets.append(target.read_bytes())
    require(targets[0] == targets[1], "Legacy uImages differ between build trees")

    out = work / "artifacts"
    out.mkdir()
    image = out / "BUILD121-Q60T-OFFLINE-ONLY.uImage"
    image.write_bytes(targets[0])
    for name in (*build111.DTBS, "initramfs.cpio", "kernel.config"):
        (out / name).write_bytes(files[name])

    report = json.loads(files["report.json"])
    for profile in report["profiles"].values():
        profile["legacy_load_check"] = placement(header, profile["free_intervals_static_only"])

    report.update({
        "build": 121, "mode": "OFFLINE-ONLY",
        "stock_uimage_sha256": digest.lower(),
        "stock_header": stock, "generated_header": header,
        "matching_header_fields": {key: stock[key] == header[key] for key in
                                   ("magic", "os", "arch", "type", "compression", "load", "entry")},
        "uimage_identical_across_two_builds": True,
        "mkimage_version": subprocess.check_output(["mkimage", "-V"], text=True).strip(),
        "mkimage_listing": subprocess.check_output(["mkimage", "-l", str(image)], text=True),
        "file_types": subprocess.check_output(
            ["file", "-b", str(image)], text=True).strip(),
        "limitations": [
            "Legacy uImage format compatibility does not establish boot or Secure Boot success.",
            "Addresses are copied from stock header metadata for offline comparison only.",
            "Static checks cover the zImage load span. Decompression, relocation, and DTB/initramfs placement remain unverified.",
        ],
    })
    (out / "build-report.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "SHA256SUMS").write_bytes(build111.sums({
        path.name: path.read_bytes() for path in out.iterdir()
    }))


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock", type=Path)
    parser.add_argument("stock_sha256")
    parser.add_argument("work", type=Path, nargs="?")
    args = parser.parse_args()
    try:
        stock = stock_header(args.stock, args.stock_sha256)
        if args.work is not None:
            package(args.work, stock, args.stock_sha256)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"BUILD121: {error}\n")


if __name__ == "__main__":
    main()
