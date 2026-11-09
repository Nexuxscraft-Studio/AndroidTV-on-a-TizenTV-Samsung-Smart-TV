#!/usr/bin/env python3
"""Pack an isolated static ARM32 Binder-ABI /init into a Linux newc initramfs.

Only creates host files under the caller's explicit output path. No TV, boot,
firmware, networking, root access, or kernel-tree modifications are involved.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile


MAX_INIT_SIZE = 32 * 1024 * 1024


def validate_arm32_static_elf(blob: bytes) -> None:
    """Reject wrong-architecture or dynamically-interpreted /init binaries."""
    if (len(blob) < 52 or blob[:6] != b"\x7fELF\x01\x01"):
        raise ValueError("/init ist keine ELF32-Little-Endian-Datei")
    kind, machine = struct.unpack_from("<HH", blob, 16)
    if kind not in (2, 3) or machine != 40:
        raise ValueError("/init muss ein ARM32-ELF-Executable sein")
    header_offset = struct.unpack_from("<I", blob, 28)[0]
    entry_size, count = struct.unpack_from("<HH", blob, 42)
    if entry_size < 32 or count == 0 or count > 512:
        raise ValueError("Ungültige ELF32-Programmheader")
    if header_offset + entry_size * count > len(blob):
        raise ValueError("ELF32-Programmheader unvollständig")
    for index in range(count):
        program_type = struct.unpack_from("<I", blob, header_offset + index * entry_size)[0]
        if program_type == 3:  # PT_INTERP: depends on guest dynamic loader
            raise ValueError("/init ist dynamisch gelinkt; -static ist erforderlich")


def newc_entry(name: str, mode: int, payload: bytes = b"", ino: int = 1,
               rdev_major: int = 0, rdev_minor: int = 0) -> bytes:
    """Create one Linux cpio newc record with correctly padded fields."""
    if not name or name.startswith("/") or ".." in name.split("/"):
        raise ValueError("Unsicherer cpio-Pfad")
    encoded_name = name.encode("ascii") + b"\x00"
    fields = (ino, mode, 0, 0, 2 if stat.S_ISDIR(mode) else 1, 0,
              len(payload), 0, 0, rdev_major, rdev_minor, len(encoded_name), 0)
    header = b"070701" + b"".join(f"{number:08x}".encode("ascii") for number in fields)
    record = header + encoded_name
    record += b"\x00" * ((-len(record)) % 4)
    record += payload
    return record + b"\x00" * ((-len(payload)) % 4)


def build_initramfs(init_elf: bytes) -> bytes:
    validate_arm32_static_elf(init_elf)
    entries = [
        ("dev", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("proc", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("sys", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("tmp", stat.S_IFDIR | 0o1777, b"", 0, 0),
        ("dev/console", stat.S_IFCHR | 0o600, b"", 5, 1),
        ("init", stat.S_IFREG | 0o755, init_elf, 0, 0),
    ]
    archive = bytearray()
    for ino, (name, mode, payload, major, minor) in enumerate(entries, start=1):
        archive.extend(newc_entry(name, mode, payload, ino, major, minor))
    archive.extend(newc_entry("TRAILER!!!", 0, ino=len(entries) + 1))
    return gzip.compress(bytes(archive), compresslevel=9, mtime=0)


def run(cross_prefix: str, output: Path, source: Path) -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError("Initramfs-Ziel existiert bereits: niemals überschreiben")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError("Ausgabeverzeichnis fehlt oder ist ein Symlink")
    if not source.is_file() or source.is_symlink():
        raise ValueError("C-Quelltext fehlt oder ist ein Symlink")
    compiler = shutil.which(cross_prefix + "gcc")
    if not compiler:
        raise ValueError("ARM32-Cross-Compiler nicht gefunden")
    with tempfile.TemporaryDirectory(prefix="q60t-binder-init-") as temporary:
        compiled = Path(temporary) / "init"
        command = [compiler, "-std=gnu11", "-static", "-Os", "-Wall", "-Wextra",
                   "-o", str(compiled), str(source)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=120,
                                check=False)
        if result.returncode:
            raise ValueError("ARM32-/init-Compile fehlgeschlagen:\n" + result.stderr[-4000:])
        if compiled.stat().st_size > MAX_INIT_SIZE:
            raise ValueError("ARM32-/init ist unerwartet groß")
        init_elf = compiled.read_bytes()
        archive = build_initramfs(init_elf)
    # Exclusive creation; preserve pre-existing user files even on a race.
    with output.open("xb") as destination:
        destination.write(archive)
    return {
        "type": "q60t_build018_arm32_binder_initramfs",
        "status": "HOST_ONLY_INITRAMFS_BUILT_NOT_BOOT_TESTED",
        "output": str(output),
        "size_bytes": len(archive),
        "sha256": hashlib.sha256(archive).hexdigest(),
        "init_elf_sha256": hashlib.sha256(init_elf).hexdigest(),
        "compiler": compiler,
        "tv_accessed": False,
        "safe_to_flash": False,
        "binder_runtime_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Isoliertes ARM32-Binder-Initramfs für QEMU")
    parser.add_argument("--cross-prefix", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).with_name("q60t_binder_init.c"))
    args = parser.parse_args(argv)
    try:
        report = run(args.cross_prefix, args.output, args.source)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"Build-018-Initramfs-Prüfung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
