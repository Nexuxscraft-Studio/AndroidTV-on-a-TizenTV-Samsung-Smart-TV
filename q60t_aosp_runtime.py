#!/usr/bin/env python3
"""Stage a minimal *real* Bionic runtime from an official SDK ARM32 system.img.

No downloading or license acceptance is automated. The caller must have
installed system-images;android-24;default;armeabi-v7a using Google's SDK
manager. Extraction is offline, read-only, and never touches Samsung files.
The resulting binary files stay local: do not commit them to GitHub.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

from q60t_bionic_elf import read_elf32_arm


PACKAGE_ID = "system-images;android-24;default;armeabi-v7a"
RUNTIME_FILES = {
    "system/bin/linker": "bin/linker",
    "system/lib/libc.so": "lib/libc.so",
    "system/lib/libdl.so": "lib/libdl.so",
    "system/lib/libm.so": "lib/libm.so",
}
MAX_IMAGE_BYTES = 8 * 1024 ** 3


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for part in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def parse_source_properties(path: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 64 * 1024:
        raise ValueError("SDK source.properties fehlt/ist unsicher")
    fields = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip()
    if (fields.get("AndroidVersion.ApiLevel") != "24" or
            fields.get("SystemImage.Abi") != "armeabi-v7a" or
            fields.get("SystemImage.TagId") != "default"):
        raise ValueError("Falsches SDK-Image: API 24, default/armeabi-v7a erforderlich")
    if not fields.get("Pkg.Revision"):
        raise ValueError("SDK-Paketrevision fehlt")
    return fields


def inspect_image_dir(image_dir: Path) -> tuple[Path, Path, dict[str, str]]:
    if not image_dir.is_dir() or image_dir.is_symlink():
        raise ValueError("SDK-Systemimage-Verzeichnis fehlt")
    # Prevent accidental ingestion of NDK link stubs or a mismatched ABI.
    if tuple(image_dir.parts[-4:]) != ("system-images", "android-24", "default", "armeabi-v7a"):
        raise ValueError("SDK-Verzeichnis muss system-images/android-24/default/armeabi-v7a sein")
    props = image_dir / "source.properties"
    image = image_dir / "system.img"
    metadata = parse_source_properties(props)
    if (not image.is_file() or image.is_symlink() or
            not 4096 <= image.stat().st_size <= MAX_IMAGE_BYTES):
        raise ValueError("Reguläres Android system.img fehlt oder ist auffällig")
    return props, image, metadata


def raw_ext4_image(image: Path, temporary: Path) -> Path:
    with image.open("rb") as stream:
        prefix = stream.read(4)
    if prefix != struct.pack("<I", 0xED26FF3A):
        return image  # debugfs will validate ext4/superblock before reading.
    binary = shutil.which("simg2img")
    if not binary:
        raise ValueError("Android sparse image: 'simg2img' fehlt")
    raw = temporary / "system.raw.ext4"
    result = subprocess.run([binary, str(image), str(raw)], capture_output=True,
                            text=True, timeout=1800, check=False)
    if result.returncode or not raw.is_file():
        raise ValueError("simg2img fehlgeschlagen: " + result.stderr[-500:])
    return raw


def extract_from_ext4(image: Path, destination: Path) -> dict[str, Path]:
    binary = shutil.which("debugfs")
    if not binary:
        raise ValueError("'debugfs' fehlt (e2fsprogs); keine Mount-Rechte notwendig")
    extracted = {}
    for output_name, relative in RUNTIME_FILES.items():
        target = destination / output_name
        target.parent.mkdir(parents=True, exist_ok=True)
        for source in ("/" + relative, "/system/" + relative):
            result = subprocess.run([binary, "-R", f"dump {source} {target}", str(image)],
                                    capture_output=True, text=True, timeout=120,
                                    check=False)
            if result.returncode == 0 and target.is_file() and target.stat().st_size > 52:
                break
        if not target.is_file() or target.stat().st_size <= 52:
            raise ValueError(f"Bionic-Binärdatei im Systemimage nicht gefunden: {relative}")
        extracted[output_name] = target
    return extracted


def check_runtime_files(files: dict[str, Path]) -> dict:
    records = {}
    provided = {Path(name).name for name in files if name.startswith("system/lib/")}
    for name, path in files.items():
        elf = read_elf32_arm(path)
        # Some historical Android linkers are themselves ELF executables
        # with a self-referential PT_INTERP. The kernel does not recursively
        # load PT_INTERP for the interpreter it has already loaded. Only
        # accept the expected /system/bin/linker path for this one file.
        if name == "system/bin/linker":
            if elf["interpreter"] not in (None, "/system/bin/linker"):
                raise ValueError(
                    f"Unerwarteter Android-Linker-Interpreter: {elf['interpreter']}")
        elif elf["interpreter"] is not None:
            raise ValueError(f"Runtime-Library hat unerwarteten PT_INTERP: {name}")
        if not name.endswith("/linker") and elf["type"] != "ET_DYN":
            raise ValueError(f"Runtime-Library ist nicht ET_DYN: {name}")
        if name.startswith("system/lib/"):
            # Dependencies on the dynamic linker itself are not DT_NEEDED.
            missing = set(elf["needed"]) - provided
            if missing:
                raise ValueError(f"Bionic-Abhängigkeiten fehlen ({name}): {sorted(missing)}")
        records[name] = {"sha256": sha256(path), "size_bytes": path.stat().st_size,
                         "elf": elf}
    return records


def stage(image_dir: Path, output: Path) -> dict:
    props, image, metadata = inspect_image_dir(image_dir)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("Ziel existiert bereits oder Elternverzeichnis fehlt")
    if output.resolve().is_relative_to(image_dir.resolve()) or image_dir.resolve().is_relative_to(output.resolve()):
        raise ValueError("Ausgabe darf SDK-Quelle nicht überlappen")

    with tempfile.TemporaryDirectory(prefix="q60t-bionic-stage-", dir=output.parent) as temp:
        temporary = Path(temp)
        rootfs = temporary / "rootfs"
        rootfs.mkdir()
        raw = raw_ext4_image(image, temporary)
        files = extract_from_ext4(raw, rootfs)
        records = check_runtime_files(files)
        report = {
            "build": "021", "status": "BIONIC_RUNTIME_STAGED_OFFLINE_NOT_EXECUTED",
            "sdk_package_id": PACKAGE_ID, "sdk_revision": metadata["Pkg.Revision"],
            "sdk_source_properties_sha256": sha256(props),
            "sdk_system_image_sha256": sha256(image),
            "sdk_image_name": image.name, "sdk_acquired_by_script": False,
            "sdk_manager_origin_not_cryptographically_verified_by_this_tool": True,
            "files": records, "bionic_process_executed": False,
            "tv_accessed": False, "safe_to_flash": False,
        }
        (rootfs / "runtime-manifest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rootfs.rename(output)
        return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline-Export echter AOSP-ARM32-Bionic-Runtime")
    parser.add_argument("--sdk-image-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = stage(args.sdk_image_dir, args.output)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"Build-021-Runtime-Export abgebrochen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
