#!/usr/bin/env python3
"""Build 024: read-only LineageOS 22.2 ARM64 first-stage init preflight.

This never downloads a source tree, runs an Android binary, accesses Samsung
hardware, or treats a plausible ELF as proof of LineageOS provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys


VERSION = "22.2"
BRANCH = "lineage-22.2"
EXPECTED_REPOSITORY = "LineageOS/android_system_core"
SOURCE_FILES = ("init/first_stage_init.cpp", "init/init.cpp", "init/Android.bp")
MAX_INIT_BYTES = 64 * 1024 * 1024
SHA256_RE = re.compile(r"[0-9a-fA-F]{64}\Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_remote(url: str) -> str | None:
    url = url.strip().removesuffix(".git").rstrip("/")
    valid = (
        "https://github.com/LineageOS/android_system_core",
        "git@github.com:LineageOS/android_system_core",
        "ssh://git@github.com/LineageOS/android_system_core",
    )
    return EXPECTED_REPOSITORY if url in valid else None


def git_read(source: Path, *args: str) -> str:
    if shutil.which("git") is None:
        raise ValueError("git ist nicht installiert")
    proc = subprocess.run(["git", "-C", str(source), *args],
                          capture_output=True, text=True, timeout=10, check=False)
    if proc.returncode:
        raise ValueError("Git-Quellprüfung fehlgeschlagen: " + " ".join(args))
    return proc.stdout.strip()


def inspect_source(source: Path) -> dict:
    if not source.is_dir() or source.is_symlink():
        raise ValueError("LineageOS system/core Quellverzeichnis fehlt oder ist ein Symlink")
    remote = git_read(source, "config", "--get", "remote.origin.url")
    if canonical_remote(remote) != EXPECTED_REPOSITORY:
        raise ValueError("Quelle ist nicht das offizielle LineageOS android_system_core Repository")
    commit = git_read(source, "rev-parse", "HEAD")
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Quellcommit ist nicht eindeutig")
    branch_result = subprocess.run(["git", "-C", str(source), "symbolic-ref",
                                    "--quiet", "--short", "HEAD"],
                                   capture_output=True, text=True, timeout=10,
                                   check=False)
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
    if branch is not None and branch != BRANCH:
        raise ValueError("Falscher LineageOS-Quellbranch: " + branch)
    observed = {}
    for item in SOURCE_FILES:
        path = source / item
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("LineageOS-Quelldatei fehlt/ist unsicher: " + item)
        observed[item] = sha256(path.read_bytes())
    return {
        "repository": EXPECTED_REPOSITORY,
        "origin_remote": remote,
        "branch": branch,
        "detached_head": branch is None,
        "commit": commit,
        "files_sha256": observed,
        "git_commit_signature_verified": False,
        "lineageos_full_manifest_verified": False,
    }


def inspect_static_arm64_init(blob: bytes) -> dict:
    if not 64 <= len(blob) <= MAX_INIT_BYTES or blob[:6] != b"\x7fELF\x02\x01":
        raise ValueError("Android /init muss ELF64 Little Endian sein (maximal 64 MiB)")
    elf_type, machine = struct.unpack_from("<HH", blob, 16)
    if elf_type not in (2, 3) or machine != 183:
        raise ValueError("Android /init muss ein ausführbares AArch64-ELF sein")
    phoff = struct.unpack_from("<Q", blob, 32)[0]
    phentsize, phnum = struct.unpack_from("<HH", blob, 54)
    if phnum < 1 or phnum > 256 or phentsize < 56 or phoff + phentsize * phnum > len(blob):
        raise ValueError("ELF-Programmheader fehlen oder überschreiten die Datei")
    dynamic_segments = []
    for index in range(phnum):
        offset = phoff + index * phentsize
        kind = struct.unpack_from("<I", blob, offset)[0]
        if kind == 3:
            raise ValueError("Android /init benötigt PT_INTERP: isolierter Start nicht möglich")
        if kind == 2:
            segment_offset, segment_size = struct.unpack_from("<Q", blob, offset + 8)[0], \
                                           struct.unpack_from("<Q", blob, offset + 32)[0]
            if segment_offset + segment_size > len(blob) or segment_size % 16:
                raise ValueError("Ungültiges ELF PT_DYNAMIC Segment")
            dynamic_segments.append((segment_offset, segment_size))
    for offset, size in dynamic_segments:
        for pos in range(offset, offset + size, 16):
            tag = struct.unpack_from("<Q", blob, pos)[0]
            if tag == 0:
                break
            if tag == 1:
                raise ValueError("Android /init hat DT_NEEDED-Bibliotheken")
    return {"elf_class": "ELF64", "machine": "AArch64", "type": "ET_DYN" if elf_type == 3 else "ET_EXEC",
            "pt_interp": False, "dt_needed": False, "size_bytes": len(blob),
            "sha256": sha256(blob)}


def preflight(source: Path, init_binary: Path | None,
              expected_init_sha256: str | None) -> dict:
    source_data = inspect_source(source)
    elf_data = None
    if init_binary is not None:
        if not init_binary.is_file() or init_binary.is_symlink():
            raise ValueError("Android-init-Binärdatei fehlt oder ist ein Symlink")
        if not expected_init_sha256 or not SHA256_RE.fullmatch(expected_init_sha256):
            raise ValueError("--expected-init-sha256 ist für Binärdateien erforderlich")
        if init_binary.stat().st_size > MAX_INIT_BYTES:
            raise ValueError("Android-init-Binärdatei ist zu groß")
        elf_data = inspect_static_arm64_init(init_binary.read_bytes())
        if elf_data["sha256"] != expected_init_sha256.lower():
            raise ValueError("Android-init-SHA256 stimmt nicht mit dem erwarteten Hash überein")
    elif expected_init_sha256 is not None:
        raise ValueError("--expected-init-sha256 ohne --init-binary")
    return {
        "type": "q60t_build024_lineageos_first_stage_init_preflight", "build": "024",
        "lineageos_reference": VERSION, "android_reference": "15",
        "source": source_data,
        "arm64_init_elf": elf_data,
        "staging_ready": elf_data is not None,
        "status": "ARM64_INIT_ELF_AUDITED_READY_TO_STAGE" if elf_data else
                  "LINEAGEOS_SOURCE_AUDITED_INIT_BINARY_NOT_SUPPLIED",
        "binary_provenance_cryptographically_verified": False,
        "android_init_executed": False, "lineageos_booted": False,
        "samsung_hardware_compatible": False, "tv_accessed": False, "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 024: LineageOS 22.2 /init host-only ABI audit")
    parser.add_argument("--source", type=Path, required=True,
                        help="Offizieller LineageOS android_system_core Quellcheckout")
    parser.add_argument("--init-binary", type=Path)
    parser.add_argument("--expected-init-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.output.is_symlink() or not args.output.parent.is_dir():
            raise ValueError("Neuer Reportpfad erforderlich; keine vorhandenen Reports überschreiben")
        report = preflight(args.source, args.init_binary, args.expected_init_sha256)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print("Build-024-Preflight abgebrochen: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
