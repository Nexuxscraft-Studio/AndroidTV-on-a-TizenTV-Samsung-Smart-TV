#!/usr/bin/env python3
"""Build 021: build an isolated QEMU initramfs with *real* Bionic runtime.

Only consumes previously validated SDK-derived ARM32 binaries and compiles a
static PID 1 using the Linaro ARM32 cross toolchain. No root/mount/TV access.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

from q60t_aosp_runtime import RUNTIME_FILES, check_runtime_files, sha256
from q60t_bionic_elf import read_elf32_arm
from q60t_initramfs_lab import newc_entry, validate_arm32_static_elf


MAX_ARCHIVE = 64 * 1024 * 1024
DEFAULT_INIT = Path(__file__).with_name("q60t_bionic_init.c")
TEST_BINARY_PATH = "system/bin/q60t_bionic_hello"


def verify_runtime(rootfs: Path) -> dict:
    if not rootfs.is_dir() or rootfs.is_symlink():
        raise ValueError("Bionic-Staging-Verzeichnis fehlt oder ist verlinkt")
    manifest_path = rootfs / "runtime-manifest.json"
    if (not manifest_path.is_file() or manifest_path.is_symlink() or
            manifest_path.stat().st_size > 128 * 1024):
        raise ValueError("Offline-Runtime-Manifest fehlt")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("sdk_package_id") != "system-images;android-24;default;armeabi-v7a"
            or manifest.get("status") != "BIONIC_RUNTIME_STAGED_OFFLINE_NOT_EXECUTED"):
        raise ValueError("Falsches oder unbestätigtes Runtime-Manifest")
    files = {}
    for name in RUNTIME_FILES:
        file = rootfs / name
        if (not file.is_file() or file.is_symlink() or
                not file.resolve().is_relative_to(rootfs.resolve())):
            raise ValueError(f"Runtime-Datei fehlt oder ist verlinkt: {name}")
        record = manifest.get("files", {}).get(name, {})
        if file.stat().st_size != record.get("size_bytes") or sha256(file) != record.get("sha256"):
            raise ValueError(f"Runtime-Datei seit Export verändert: {name}")
        files[name] = file
    checked = check_runtime_files(files)
    for name, record in checked.items():
        if record["elf"] != manifest["files"][name]["elf"]:
            raise ValueError(f"Runtime-ELF-Metadaten stimmen nicht: {name}")
    return manifest


def create_archive(init_elf: bytes, executable: bytes, library_blobs: dict[str, bytes]) -> bytes:
    validate_arm32_static_elf(init_elf)
    entries = [
        ("dev", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("proc", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("sys", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("tmp", stat.S_IFDIR | 0o1777, b"", 0, 0),
        ("system", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("system/bin", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("system/lib", stat.S_IFDIR | 0o755, b"", 0, 0),
        ("dev/console", stat.S_IFCHR | 0o600, b"", 5, 1),
        ("init", stat.S_IFREG | 0o755, init_elf, 0, 0),
        (TEST_BINARY_PATH, stat.S_IFREG | 0o755, executable, 0, 0),
    ]
    for name, blob in sorted(library_blobs.items()):
        mode = 0o755 if name.endswith("/linker") else 0o644
        entries.append((name, stat.S_IFREG | mode, blob, 0, 0))
    archive = bytearray()
    for ino, (name, mode, payload, major, minor) in enumerate(entries, 1):
        archive.extend(newc_entry(name, mode, payload, ino, major, minor))
    archive.extend(newc_entry("TRAILER!!!", 0, ino=len(entries) + 1))
    result = gzip.compress(bytes(archive), compresslevel=9, mtime=0)
    if len(result) > MAX_ARCHIVE:
        raise ValueError("Initramfs überschreitet 64 MiB")
    return result


def build(rootfs: Path, program: Path, output: Path, cross_prefix: str) -> dict:
    runtime_manifest = verify_runtime(rootfs)
    if not program.is_file() or program.is_symlink():
        raise ValueError("Bionic-Testprogramm fehlt oder ist verlinkt")
    elf = read_elf32_arm(program, require_interpreter=True)
    needed = set(elf["needed"])
    if not {"libc.so", "libdl.so"}.issubset(needed):
        raise ValueError("Testprogramm benötigt nicht die erwarteten libc.so/libdl.so")
    available = {Path(name).name for name in RUNTIME_FILES if name.startswith("system/lib/")}
    if not needed.issubset(available):
        raise ValueError(f"Nicht gestagte Android-Dependencies: {sorted(needed - available)}")
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("Initramfs-Ziel existiert schon oder Elternverzeichnis fehlt")
    compiler = shutil.which(cross_prefix + "gcc")
    if not compiler:
        raise ValueError("ARM32-Compiler für statisches /init nicht gefunden")
    if not DEFAULT_INIT.is_file() or DEFAULT_INIT.is_symlink():
        raise ValueError("Build-021-Gast-Launcher fehlt")
    with tempfile.TemporaryDirectory(prefix="q60t-bionic-init-") as temp:
        compiled = Path(temp) / "init"
        result = subprocess.run([compiler, "-std=gnu11", "-static", "-Os",
                                 "-Wall", "-Wextra", "-Werror", "-o",
                                 str(compiled), str(DEFAULT_INIT)],
                                capture_output=True, text=True, timeout=120,
                                check=False)
        if result.returncode:
            raise ValueError("ARM32-Launcher konnte nicht kompiliert werden: " + result.stderr[-1800:])
        init_elf = compiled.read_bytes()
        library_blobs = {name: (rootfs / name).read_bytes() for name in RUNTIME_FILES}
        payload = create_archive(init_elf, program.read_bytes(), library_blobs)
    with output.open("xb") as handle:
        handle.write(payload)
    return {
        "build": "021", "status": "BIONIC_QEMU_INITRAMFS_BUILT_NOT_BOOTED",
        "initramfs": str(output), "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload), "program_elf": elf,
        "program_sha256": sha256(program),
        "runtime_sdk_package_id": runtime_manifest["sdk_package_id"],
        "runtime_sdk_revision": runtime_manifest["sdk_revision"],
        "runtime_binary_sha256": {name: runtime_manifest["files"][name]["sha256"]
                                  for name in RUNTIME_FILES},
        "android_bionic_executed": False, "tv_accessed": False,
        "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 021: lokales Bionic-ARM32-QEMU-Initramfs")
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--program", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cross-prefix", required=True)
    args = parser.parse_args(argv)
    try:
        report = build(args.runtime_root, args.program, args.output, args.cross_prefix)
    except (ValueError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"Build-021-Initramfs abgebrochen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
