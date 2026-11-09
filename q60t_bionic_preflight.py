#!/usr/bin/env python3
"""Host-only Build 020 ARM32 Bionic ELF/linker staging audit.

This does not execute a Bionic program, populate Android partitions, or boot.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys


MAX_ELF = 64 * 1024 * 1024
ANDROID_INTERPRETERS = frozenset((
    "/system/bin/linker", "/apex/com.android.runtime/bin/linker",
))


def inspect_elf(raw: bytes) -> dict:
    if len(raw) < 52 or len(raw) > MAX_ELF or raw[:6] != b"\x7fELF\x01\x01":
        raise ValueError("Erwartet ARM32 ELF32 Little-Endian")
    kind, machine = struct.unpack_from("<HH", raw, 16)
    if kind != 3 or machine != 40:
        raise ValueError("ARM32-Bionic-PIE erwartet: ET_DYN, EM_ARM=40")
    offset = struct.unpack_from("<I", raw, 28)[0]
    header_size, count = struct.unpack_from("<HH", raw, 42)
    if header_size < 32 or count == 0 or count > 512 or offset + header_size * count > len(raw):
        raise ValueError("Ungültige ELF-Programmheader")
    interpreters = []
    for number in range(count):
        entry = offset + number * header_size
        program_type, file_offset, _, _, file_size = struct.unpack_from("<IIIII", raw, entry)
        if program_type == 3:  # PT_INTERP
            if file_size < 2 or file_size > 512 or file_offset + file_size > len(raw):
                raise ValueError("Ungültiger PT_INTERP")
            name = raw[file_offset:file_offset + file_size]
            if not name.endswith(b"\x00"):
                raise ValueError("PT_INTERP ohne Nullterminierung")
            try:
                interpreters.append(name[:-1].decode("ascii"))
            except UnicodeDecodeError as exc:
                raise ValueError("PT_INTERP nicht ASCII") from exc
    if len(interpreters) != 1 or interpreters[0] not in ANDROID_INTERPRETERS:
        raise ValueError("ELF ist kein Android-ARM32-PIE mit Bionic-Linker")
    return {"elf_class": "ELF32", "machine": "ARM", "type": "ET_DYN",
            "interpreter": interpreters[0], "bionic_linker_path_expected": True}


def inspect(path: Path, rootfs: Path | None = None) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_ELF:
        raise ValueError("Fehlendes, verlinktes oder zu großes Programm")
    elf = inspect_elf(path.read_bytes())
    staged = {"linker": False, "libc": False}
    if rootfs is not None:
        if not rootfs.is_dir() or rootfs.is_symlink():
            raise ValueError("Ungültiger Android-Staging-Rootfs")
        paths = {"linker": elf["interpreter"].lstrip("/"),
                 "libc": "system/lib/libc.so"}
        for item, relative in paths.items():
            file = rootfs / relative
            staged[item] = (file.is_file() and not file.is_symlink() and
                            file.resolve().is_relative_to(rootfs.resolve()) and
                            file.stat().st_size > 0)
    return {"build": "020", "status": "ARM32_BIONIC_ELF_VALIDATED_NOT_EXECUTED",
            "elf": elf, "runtime_files_staged": staged,
            "ready_to_execute_in_guest": False,
            "android_userspace_running": False, "tv_accessed": False,
            "safe_to_flash": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 020 Android-ARM32-Bionic-Prüfung")
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--rootfs", type=Path)
    args = parser.parse_args(argv)
    try:
        report = inspect(args.elf, args.rootfs)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
