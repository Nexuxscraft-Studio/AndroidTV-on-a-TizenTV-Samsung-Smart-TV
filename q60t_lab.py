#!/usr/bin/env python3
"""Offline-only Q60T firmware reconnaissance. Python standard library only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import struct
import sys
import zipfile
import zlib


REFERENCE = {
    "family": "T-NKLDEUC",
    "version": "2743.0",
    "model": "GQ55Q60TGUXZG (original download/analysis reference)",
    "confirmed_target_model": "GQ50Q60TGUXZG",
    "confirmed_target_support": "https://www.samsung.com/de/support/model/GQ50Q60TGUXZG/",
    "target_model_firmware_family_officially_listed": True,
    "sha256": "cb717ed98daf9580eb5b84bccbad5adac82f75dd021ed028f1ee1bb6c4abde32",
    "source": "https://github.com/sebastianspicker/tiz0wn/blob/main/docs/firmware-analysis.md",
}
TARGET_FILES = {
    "uImage", "dtb.bin", "ddr.init", "seret.bin", "sign.bin",
    "secos.bin", "secos_drv.bin", "platform.img", "factory_peq.img",
}
CHUNK = 4 * 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def unsafe_zip_member(member: zipfile.ZipInfo) -> list[str]:
    """Reject path escapes, Windows drive names, duplicate path separators, symlinks."""
    name = member.filename
    reasons = []
    posix = PurePosixPath(name)
    if name.startswith("/") or "\\" in name or re.match(r"^[A-Za-z]:", name):
        reasons.append("absolute, drive-prefixed or backslash path")
    if ".." in posix.parts or "" in name.split("/")[:-1]:
        reasons.append("path traversal or empty path component")
    mode = (member.external_attr >> 16) & 0o170000
    if mode == stat.S_IFLNK:
        reasons.append("symbolic link")
    return reasons


def inspect_firmware_zip(path: Path) -> dict:
    if not path.is_file():
        raise ValueError("Firmware ZIP nicht gefunden")
    report = {
        "type": "samsung_zip_offline_inspection",
        "input": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "reference": REFERENCE,
        "reference_sha256_match": None,
        "members": [],
        "metadata": {},
        "msdu11_magic": None,
        "warnings": [],
        "writes_to_tv": False,
    }
    report["reference_sha256_match"] = report["sha256"] == REFERENCE["sha256"]
    if not report["reference_sha256_match"]:
        report["warnings"].append(
            "ZIP-Hash weicht vom publizierten 55-Zoll-Referenzimage ab; "
            "das allein ist keine Fehler- oder Kompatibilitätsaussage."
        )
    with zipfile.ZipFile(path) as archive:
        names = set()
        for item in archive.infolist():
            issues = unsafe_zip_member(item)
            if item.filename in names:
                issues.append("duplicate member name")
            names.add(item.filename)
            report["members"].append({
                "name": item.filename,
                "size_bytes": item.file_size,
                "compressed_bytes": item.compress_size,
                "crc32": f"{item.CRC:08x}",
                "issues": issues,
            })
            if issues:
                report["warnings"].append(
                    f"Nicht vertrauenswürdiger ZIP-Eintrag {item.filename!r}: {', '.join(issues)}"
                )

        # Samsung distributes both flat archives and archives under T-NKLDEUC/.
        info = next((x for x in archive.infolist() if
                     x.filename == "image/info.txt" or
                     x.filename.endswith("/image/info.txt")), None)
        if info and info.file_size <= 1024 * 1024:
            with archive.open(info) as handle:
                raw = handle.read(1024 * 1024 + 1)
            info_text = raw.decode("utf-8", "replace")
            report["metadata"]["info_txt"] = info_text
            family = re.search(r"\bT-[A-Z0-9]+\b", info_text)
            version = re.search(r"\b\d{4}\.\d+\b", info_text)
            major = re.search(r"^major version:\s*(\d+)\s*$", info_text, re.M | re.I)
            minor = re.search(r"^minor version:\s*(\d+)\s*$", info_text, re.M | re.I)
            report["metadata"]["detected_family"] = family.group() if family else None
            detected_version = (
                f"{int(major.group(1))}.{int(minor.group(1))}" if major and minor
                else version.group() if version else None
            )
            report["metadata"]["detected_version"] = detected_version
            if family and family.group() != REFERENCE["family"]:
                report["warnings"].append("Andere Firmwarefamilie als T-NKLDEUC erkannt")
            if detected_version and detected_version != REFERENCE["version"]:
                report["warnings"].append("Andere Firmwareversion als 2743.0 erkannt")
        else:
            report["warnings"].append("image/info.txt fehlt oder ist über 1 MiB")

        msd = next((x for x in archive.infolist() if
                    x.filename == "image/upgrade.msd" or
                    x.filename.endswith("/image/upgrade.msd")), None)
        if msd:
            with archive.open(msd) as handle:
                magic = handle.read(6)
            report["msdu11_magic"] = magic == b"MSDU11"
            if not report["msdu11_magic"]:
                report["warnings"].append("upgrade.msd hat keinen erwarteten MSDU11-Header")
        else:
            report["warnings"].append("image/upgrade.msd fehlt")
    return report


def extract_zip_member(zip_path: Path, member_name: str, destination: Path) -> dict:
    """Checked streaming extraction to a new local file (never to the TV)."""
    if destination.exists() or destination.is_symlink():
        raise ValueError("Zieldatei existiert bereits; sie wird nicht überschrieben")
    if not destination.parent.is_dir():
        raise ValueError("Zielverzeichnis existiert nicht")
    created = False
    try:
        with zipfile.ZipFile(zip_path) as archive:
            info = archive.getinfo(member_name)
            if unsafe_zip_member(info) or info.is_dir():
                raise ValueError("Unsicherer oder ungültiger ZIP-Eintrag")
            if info.file_size > 4 * 1024 ** 3:
                raise ValueError("ZIP-Eintrag überschreitet 4-GiB-Sicherheitsgrenze")
            crc = 0
            digest = hashlib.sha256()
            size = 0
            with archive.open(info) as source, destination.open("xb") as target:
                created = True
                for block in iter(lambda: source.read(CHUNK), b""):
                    target.write(block)
                    size += len(block)
                    crc = zlib.crc32(block, crc)
                    digest.update(block)
                target.flush()
                os.fsync(target.fileno())
            if size != info.file_size or (crc & 0xFFFFFFFF) != info.CRC:
                raise ValueError("Größe oder CRC der extrahierten Daten stimmt nicht")
        return {"type": "verified_local_extraction", "member": member_name,
                "output": str(destination.resolve()), "size_bytes": size,
                "sha256": digest.hexdigest(), "crc32": f"{crc & 0xFFFFFFFF:08x}",
                "writes_to_tv": False}
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise


def inspect_uimage(path: Path) -> dict:
    """Read U-Boot's 64-byte legacy header and verify CRCs without executing code."""
    output = {"format": "u_boot_legacy_uimage", "valid": False}
    with path.open("rb") as handle:
        header = handle.read(64)
        if len(header) != 64:
            output["error"] = "header shorter than 64 bytes"
            return output
        values = struct.unpack(">7I4B32s", header)
        magic, hcrc, timestamp, size, load, entry, dcrc, os_id, arch, typ, comp, raw_name = values
        output.update({
            "magic": f"0x{magic:08x}",
            "payload_size": size,
            "load_address": f"0x{load:08x}",
            "entry_address": f"0x{entry:08x}",
            "timestamp_unix": timestamp,
            "os_id": os_id,
            "arch_id": arch,
            "image_type": typ,
            "compression_id": comp,
            "name": raw_name.split(b"\x00", 1)[0].decode("ascii", "replace"),
        })
        if magic != 0x27051956:
            output["error"] = "not a U-Boot legacy uImage"
            return output
        test_header = header[:4] + b"\x00\x00\x00\x00" + header[8:]
        output["header_crc_valid"] = zlib.crc32(test_header) & 0xFFFFFFFF == hcrc
        if path.stat().st_size < 64 + size:
            output["payload_crc_valid"] = False
            output["error"] = "declared payload extends beyond file"
            return output
        remaining = size
        crc = 0
        while remaining:
            block = handle.read(min(CHUNK, remaining))
            if not block:
                break
            crc = zlib.crc32(block, crc)
            remaining -= len(block)
        output["payload_crc_valid"] = remaining == 0 and (crc & 0xFFFFFFFF) == dcrc
        output["valid"] = output["header_crc_valid"] and output["payload_crc_valid"]
    return output


def inspect_dtb(path: Path) -> dict:
    """Inspect FDT header plus model/compatible properties without executing code."""
    with path.open("rb") as handle:
        blob = handle.read(32 * 1024 * 1024 + 1)
    return inspect_dtb_bytes(blob)


def inspect_dtb_bytes(blob: bytes) -> dict:
    """Read a standalone or embedded DTB from the first byte of blob."""
    output = {"format": "flattened_device_tree", "valid": False}
    header = blob[:40]
    if len(header) != 40:
        output["error"] = "header shorter than 40 bytes"
        return output
    (magic, total, struct_offset, strings_offset, rsv_offset, version,
     last_comp, boot_cpu, strings_size, struct_size) = struct.unpack(">10I", header)
    output.update({
        "magic": f"0x{magic:08x}", "total_size": total,
        "struct_offset": struct_offset, "strings_offset": strings_offset,
        "reserved_map_offset": rsv_offset, "version": version,
        "last_compatible_version": last_comp, "boot_cpu": boot_cpu,
        "strings_size": strings_size, "struct_size": struct_size,
    })
    real_size = len(blob)
    output["valid"] = (
        magic == 0xD00DFEED and 40 <= total <= real_size
        and 40 <= struct_offset < total
        and 40 <= strings_offset < total
        and 40 <= rsv_offset < total
        and struct_offset + struct_size <= total
        and strings_offset + strings_size <= total
        and 16 <= version <= 17 and last_comp <= version
    )
    if not output["valid"]:
        output["error"] = "invalid or unsupported FDT header / offsets"
    elif total > 32 * 1024 * 1024:
        output["tree_note"] = "Tree too large for bounded metadata parsing (32 MiB)"
    else:
        try:
            output["hardware"] = parse_dtb_hardware(
                blob[:total], struct_offset, struct_size, strings_offset, strings_size
            )
        except ValueError as exc:
            output["tree_note"] = f"FDT structure needs further analysis: {exc}"
    return output


def scan_embedded_dtbs(path: Path) -> list[dict]:
    """Find multiple FDTs in a bundled dtb.bin; false-positive headers are discarded."""
    if path.stat().st_size > 32 * 1024 * 1024:
        return []
    blob = path.read_bytes()
    magic = b"\xd0\x0d\xfe\xed"
    found = []
    start = 0
    while len(found) < 64:
        offset = blob.find(magic, start)
        if offset < 0:
            break
        report = inspect_dtb_bytes(blob[offset:])
        if report["valid"]:
            found.append({"offset_bytes": offset, "dtb": report})
        start = offset + 4
    return found


def parse_dtb_hardware(blob: bytes, struct_offset: int, struct_size: int,
                       strings_offset: int, strings_size: int) -> dict:
    """Parse only /model and compatible values; never include serial/MAC properties."""
    data = memoryview(blob)
    end = struct_offset + struct_size
    strings = data[strings_offset:strings_offset + strings_size].tobytes()
    offset = struct_offset
    nodes = []
    compat = []
    model = None
    tokens = 0
    finished = False
    while offset + 4 <= end and tokens < 100_000:
        (token,) = struct.unpack_from(">I", data, offset)
        offset += 4
        tokens += 1
        if token == 1:  # FDT_BEGIN_NODE
            name_end = blob.find(b"\x00", offset, end)
            if name_end < 0:
                raise ValueError("unterminated node name")
            name = blob[offset:name_end].decode("ascii", "replace")
            nodes.append(name)
            offset = (name_end + 4) & ~3
        elif token == 2:  # FDT_END_NODE
            if not nodes:
                raise ValueError("unexpected end node")
            nodes.pop()
        elif token == 3:  # FDT_PROP
            if offset + 8 > end:
                raise ValueError("truncated property header")
            length, name_offset = struct.unpack_from(">II", data, offset)
            offset += 8
            if offset + length > end or name_offset >= len(strings):
                raise ValueError("property beyond declared section")
            name_end = strings.find(b"\x00", name_offset)
            if name_end < 0:
                raise ValueError("unterminated property name")
            name = strings[name_offset:name_end].decode("ascii", "replace")
            value = data[offset:offset + length].tobytes()
            offset = (offset + length + 3) & ~3
            if name in ("model", "compatible"):
                parts = [v.decode("utf-8", "replace") for v in value.split(b"\x00")
                         if v and len(v) <= 256]
                if name == "model" and len(nodes) == 1 and parts:
                    model = parts[0]
                elif name == "compatible":
                    for part in parts:
                        if part not in compat and len(compat) < 100:
                            compat.append(part)
        elif token == 4:  # FDT_NOP
            continue
        elif token == 9:  # FDT_END
            finished = True
            break
        else:
            raise ValueError(f"unknown FDT token {token}")
    if not finished:
        raise ValueError("missing end marker or token limit exceeded")
    return {"model": model, "compatible": compat,
            "note": "Only model/compatible properties; not a full DTB validation"}


def inventory(directory: Path, max_hash_mib: int = 128) -> dict:
    if not directory.is_dir():
        raise ValueError("Verzeichnis nicht gefunden")
    report = {
        "type": "extracted_firmware_inventory",
        "directory": str(directory.resolve()),
        "max_hash_mib": max_hash_mib,
        "files": [],
        "warnings": [],
        "writes_to_tv": False,
    }
    for root, dirs, files in os.walk(directory, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not (Path(root) / d).is_symlink())
        for filename in sorted(files):
            path = Path(root) / filename
            if path.is_symlink() or filename not in TARGET_FILES:
                continue
            size = path.stat().st_size
            record = {
                "name": filename, "path": str(path.resolve()),
                "size_bytes": size, "sha256": None,
            }
            if size <= max_hash_mib * 1024 * 1024:
                record["sha256"] = sha256_file(path)
            else:
                record["note"] = "hash skipped (size limit)"
            if filename == "uImage":
                record["uimage"] = inspect_uimage(path)
            if filename == "dtb.bin":
                record["dtb"] = inspect_dtb(path)
                record["embedded_device_trees"] = scan_embedded_dtbs(path)
            report["files"].append(record)
    if not report["files"]:
        report["warnings"].append("Keine bekannten extrahierten Firmwarekomponenten gefunden")
    return report


def rea_plan(directory: Path) -> dict:
    result = inventory(directory)
    steps = []
    for item in result["files"]:
        quoted = shlex.quote(item["path"])
        if item["name"] == "dtb.bin" and item["dtb"]["valid"]:
            steps.append({
                "component": "dtb.bin", "command_linux": f"rea inspect-devicetree {quoted}",
                "note": "Read-only Hardwarebaum; vor Ausführung REA-CLI prüfen",
            })
        elif item["name"] == "uImage" and item["uimage"]["valid"]:
            steps.append({
                "component": "uImage", "command_linux": None,
                "note": "Header/CRC durch dieses Tool validiert. Die getestete REA-Version weist "
                        "das rohe uImage als unsupported binary format zurück; "
                        "für Disassembly erst Payload/Architektur vorbereiten.",
            })
    return {
        "type": "rea_commands_not_executed", "steps": steps,
        "warnings": result["warnings"],
        "next": "Unsignierte Firmware wird nicht auf den Fernseher geschrieben.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Samsung Q60T Firmware 2743.0: ausschließlich Offline-Analyse"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("firmware-info", "inventory", "rea-plan", "hardware-report", "kernel-report", "rootfs-strings"):
        command = sub.add_parser(name)
        command.add_argument("path", type=Path)
        command.add_argument("--output", type=Path, help="lokale JSON-Ausgabe (optional)")
        if name == "inventory":
            command.add_argument("--max-hash-mib", type=int, default=128)
    extract = sub.add_parser("extract-member", help="Lokalen ZIP-Eintrag mit CRC prüfen")
    extract.add_argument("path", type=Path, help="ZIP-Datei")
    extract.add_argument("--member", required=True, help="exakter ZIP-Eintragsname")
    extract.add_argument("--output", type=Path, required=True, help="neue lokale Zieldatei")
    args = parser.parse_args(argv)
    try:
        if args.command == "firmware-info":
            result = inspect_firmware_zip(args.path)
        elif args.command == "extract-member":
            result = extract_zip_member(args.path, args.member, args.output)
        elif args.command == "inventory":
            if args.max_hash_mib < 0:
                raise ValueError("--max-hash-mib muss >= 0 sein")
            result = inventory(args.path, args.max_hash_mib)
        elif args.command == "hardware-report":
            from q60t_hardware import hardware_report
            result = hardware_report(args.path)
        elif args.command == "kernel-report":
            from q60t_hardware import inspect_kernel
            result = inspect_kernel(args.path)
        elif args.command == "rootfs-strings":
            from q60t_rootfs import scan_rootfs_strings
            result = scan_rootfs_strings(args.path)
        else:
            result = rea_plan(args.path)
        result_json = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.command == "extract-member":
            print(result_json, end="")
        elif args.output:
            # Reports should not replace any unrelated user file by accident.
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(result_json)
            print(f"Bericht gespeichert: {args.output}")
        else:
            print(result_json, end="")
        return 0
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
