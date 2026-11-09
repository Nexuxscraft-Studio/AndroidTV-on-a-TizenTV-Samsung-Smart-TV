#!/usr/bin/env python3
"""Build 023: generate a genuine static ARM64 QEMU-virt PID1 initramfs.

Requires a local AArch64 cross-compiler, but does not use root, mount, network,
Samsung firmware or Android libraries. Builds only to an unused output path.
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

from q60t_initramfs_lab import newc_entry


DEFAULT_SOURCE = Path(__file__).with_name("q60t_arm64_probe_init.c")
MAX_INIT_BYTES = 32 * 1024 * 1024


def validate_static_aarch64_elf(blob: bytes) -> None:
    if len(blob) < 64 or blob[:6] != b"\x7fELF\x02\x01":
        raise ValueError("/init muss ELF64 Little Endian sein")
    kind, machine = struct.unpack_from("<HH", blob, 16)
    if kind not in (2, 3) or machine != 183:
        raise ValueError("/init muss ein AArch64-ELF sein")
    phoff = struct.unpack_from("<Q", blob, 32)[0]
    phentsize, phnum = struct.unpack_from("<HH", blob, 54)
    if phnum == 0 or phnum > 256 or phentsize < 56:
        raise ValueError("ARM64-Programmheader fehlen/ungültig")
    if phoff + phentsize * phnum > len(blob):
        raise ValueError("ARM64-Programmheader überschreiten Datei")
    for index in range(phnum):
        typ = struct.unpack_from("<I", blob, phoff + index * phentsize)[0]
        if typ == 3:  # PT_INTERP, i.e. not a fully static guest /init.
            raise ValueError("ARM64-/init hat PT_INTERP: statisches ELF erforderlich")


def create_archive(elf: bytes) -> bytes:
    validate_static_aarch64_elf(elf)
    entries = [
        ("dev", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("dev/dma_heap", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("proc", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("sys", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("sys/fs", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("sys/fs/selinux", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("tmp", stat.S_IFDIR | 0o1777, b"", 0, 0),
        ("dev/console", stat.S_IFCHR | 0o600, b"", 5, 1),
        ("init", stat.S_IFREG | 0o755, elf, 0, 0),
    ]
    payload = bytearray()
    for ino, (name, mode, content, rmajor, rminor) in enumerate(entries, 1):
        payload.extend(newc_entry(name, mode, content, ino, rmajor, rminor))
    payload.extend(newc_entry("TRAILER!!!", 0, ino=len(entries) + 1))
    return gzip.compress(bytes(payload), compresslevel=9, mtime=0)


def build(output: Path, *, cross_prefix: str = "aarch64-linux-gnu-",
          source: Path = DEFAULT_SOURCE) -> dict:
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError("Initramfs-Ausgabepfad muss neu sein; Parent muss existieren")
    if not source.is_file() or source.is_symlink():
        raise ValueError("Init-Quelltext ist nicht vorhanden oder ist ein Symlink")
    compiler = shutil.which(cross_prefix + "gcc")
    if compiler is None:
        raise ValueError("AArch64-GNU-Cross-Compiler fehlt")
    with tempfile.TemporaryDirectory(prefix="q60t-arm64-init-") as folder:
        elf_path = Path(folder) / "init"
        cmd = [compiler, "-std=gnu11", "-static", "-no-pie", "-Os", "-Wall", "-Wextra",
               "-Werror", "-o", str(elf_path), str(source)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)
        if result.returncode:
            raise ValueError("ARM64-Init-Compile fehlgeschlagen: " + result.stderr[-1600:])
        if elf_path.stat().st_size > MAX_INIT_BYTES:
            raise ValueError("Statisches ARM64-/init ist zu groß")
        elf = elf_path.read_bytes()
        payload = create_archive(elf)
    with output.open("xb") as dst:
        dst.write(payload)
    return {
        "type": "q60t_arm64_qemu_probe_initramfs", "build": "023",
        "status": "HOST_ARM64_INITRAMFS_BUILT_NOT_EXECUTED",
        "archive_sha256": hashlib.sha256(payload).hexdigest(),
        "init_elf_sha256": hashlib.sha256(elf).hexdigest(),
        "size_bytes": len(payload), "output": str(output),
        "qemu_only": True, "android_init_executed": False, "samsung_tv_accessed": False,
        "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 023: statisches ARM64 /init für QEMU virt")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cross-prefix", default="aarch64-linux-gnu-")
    args = parser.parse_args(argv)
    try:
        report = build(args.output, cross_prefix=args.cross_prefix)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"Build-023-Initramfs fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
