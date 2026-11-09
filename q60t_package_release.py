#!/usr/bin/env python3
"""Deterministic, source-only Q60T lab archive for GitHub Actions.

Runs the existing disclosure audit before touching the destination.
Never downloads, compiles, signs or bundles Samsung firmware or zImages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import q60t_release_audit


LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ARCHIVE_ROOT = "q60t-lineage-lab/"
FIXED_TIME = (2020, 1, 1, 0, 0, 0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_outputs(source: Path, output: Path, label: str) -> tuple[Path, Path]:
    if not LABEL.fullmatch(label) or label in {".", ".."}:
        raise ValueError("Release-Kennung muss ein einfacher Name ohne Pfad sein")
    source = source.resolve()
    parent = output.parent.resolve()
    if not parent.is_dir():
        raise ValueError("Release-Zielverzeichnis fehlt")
    if parent == source or parent.is_relative_to(source):
        raise ValueError("Release-Archive müssen außerhalb des Quellbaums liegen")
    if not output.name.endswith(".zip"):
        raise ValueError("Ausgabedatei muss auf .zip enden")
    manifest = output.with_suffix(".manifest.json")
    checksum = output.with_suffix(".sha256")
    for path in (output, manifest, checksum):
        if path.exists() or path.is_symlink():
            raise ValueError(f"Ausgabedatei existiert bereits: {path.name}")
    return manifest, checksum


def zip_info(relative: str) -> ZipInfo:
    info = ZipInfo(ARCHIVE_ROOT + relative, date_time=FIXED_TIME)
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.compress_type = ZIP_DEFLATED
    return info


def package(source: Path, output: Path, label: str) -> dict:
    manifest_path, checksum_path = safe_outputs(source, output, label)
    audit = q60t_release_audit.audit(source)
    if audit["status"] != "PASS":
        raise ValueError("Quell-Audit fehlgeschlagen: " + "; ".join(audit["problems"]))

    items = sorted(audit["file_hashes"], key=lambda item: item["path"])
    # A temporary archive in the destination directory is atomically linked
    # into place only after ZIP integrity and hashes have been checked.
    temp_name: str | None = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=".q60t-source-", suffix=".tmp",
                                         dir=output.parent)
        os.close(fd)
        with ZipFile(temp_name, mode="w", compression=ZIP_DEFLATED,
                     compresslevel=9) as archive:
            for entry in items:
                path = source / entry["path"]
                if not path.is_file() or path.is_symlink():
                    raise ValueError("Quellpfad während des Packens geändert")
                contents = path.read_bytes()
                if hashlib.sha256(contents).hexdigest() != entry["sha256"]:
                    raise ValueError("SHA-256 hat sich nach dem Audit geändert: " + entry["path"])
                archive.writestr(zip_info(entry["path"]), contents)
        with ZipFile(temp_name, "r") as archive:
            if archive.testzip() is not None:
                raise ValueError("Release-ZIP-CRC-Prüfung fehlgeschlagen")
            if archive.namelist() != [ARCHIVE_ROOT + item["path"] for item in items]:
                raise ValueError("Release-ZIP-Inventar unerwartet")
        zip_sha256 = sha256_file(Path(temp_name))
        # Atomic no-overwrite publication: never clobber previous artifacts.
        os.link(temp_name, output)
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)

    manifest = {
        "type": "q60t_source_only_release",
        "label": label,
        "archive_name": output.name,
        "archive_sha256": zip_sha256,
        "archive_bytes": output.stat().st_size,
        "source_files": len(items),
        "source_audit": "PASS",
        "files": items,
        "includes_vendor_kernel_or_firmware": False,
        "contains_flashable_image": False,
        "warning": "Offline development material only. Never flash an image from this project to a TV.",
    }
    # The output directory is new in CI; the x modes still reject re-runs
    # that would silently replace an earlier version.
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    with checksum_path.open("x", encoding="ascii") as stream:
        stream.write(f"{zip_sha256}  {output.name}\n")
    return {"status": "PASS", "archive": output.name,
            "sha256": zip_sha256, "source_files": len(items),
            "manifest": manifest_path.name, "checksum": checksum_path.name}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create audited Q60T source-only ZIP")
    parser.add_argument("--source", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args(argv)
    try:
        result = package(args.source, args.output, args.label)
    except (OSError, ValueError) as exc:
        print(f"Build-014-Paketierung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
