#!/usr/bin/env python3
"""Build 024: pin the official LineageOS 21/Android 14 source for QEMU ARM64.

Validates a locally supplied manifest and checkout without cloning, updating,
selecting a Samsung release, or changing files in the source checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


LOCK_PATH = Path(__file__).with_name("porting") / "lineage_arm64/lineage21-source-lock.json"
REQUIRED_PROJECT_TREES = (
    "bionic", "system/core/init", "system/sepolicy", "build/soong",
    "frameworks/base", "system/libbase",
)
MAX_XML = 4 * 1024 * 1024
MAX_LOCK = 64 * 1024
SHA = re.compile(r"[a-f0-9]{40}\Z")


def limited_regular_bytes(path: Path, maximum: int) -> bytes:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > maximum:
        raise ValueError(f"Datei fehlt, ist verlinkt oder zu groß: {path}")
    return path.read_bytes()


def source_lock(path: Path = LOCK_PATH) -> dict:
    data = json.loads(limited_regular_bytes(path, MAX_LOCK))
    if (data.get("build") != "024" or data.get("branch") != "lineage-21.0" or
            data.get("android_api_level") != 34 or
            data.get("upstream") != "https://github.com/LineageOS/android.git" or
            data.get("lineage_tv_gsi_target") != "gsi_tv_arm64" or
            data.get("lineage_sdk_tv_arm64_emulator_target_exists") is not False or
            data.get("lineage_qemu_virt_device_target_exists") is not False or
            data.get("kernel6_6_is_android14_gki") is not False or
            data.get("safe_to_flash") is not False):
        raise ValueError("Unzulässige Änderung der Quellen- oder Hardwaregrenzen")
    for key in ("manifest_commit", "manifest_git_blob_sha1"):
        if not isinstance(data.get(key), str) or not SHA.fullmatch(data[key]):
            raise ValueError(f"Ungültiger Commit-/Blob-SHA: {key}")
    return data


def manifest_git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def verify_manifest(path: Path, lock: dict) -> dict:
    raw = limited_regular_bytes(path, MAX_XML)
    blob = manifest_git_blob(raw)
    if blob != lock["manifest_git_blob_sha1"]:
        raise ValueError(f"Manifest-Hash passt nicht zu gepinnter LineageOS-Revision: {blob}")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Manifest-DTD/Entity nicht erlaubt")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError(f"Ungültiges Manifest-XML: {exc}") from exc
    if root.tag != "manifest":
        raise ValueError("Ungültige Manifestwurzel")
    defaults = root.find("default")
    if defaults is None or defaults.get("revision") != "refs/heads/lineage-21.0":
        raise ValueError("Falsche LineageOS-Manifest-Default-Revision")
    aosp = next((r for r in root.findall("remote") if r.get("name") == "aosp"), None)
    if aosp is None or aosp.get("revision") != "refs/tags/android-14.0.0_r67":
        raise ValueError("Android-14-AOSP-Tag stimmt nicht")
    projects = root.findall("project")
    if len(projects) < 30:
        raise ValueError("Offizielles Manifest enthält unerwartet wenige Projekte")
    return {"status": "PINNED_TOP_LEVEL_MANIFEST_GIT_BLOB_VERIFIED",
            "manifest_blob_sha1": blob,
            "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "top_level_projects": len(projects),
            "all_project_revisions_pinned": False,
            "submanifests_and_includes_resolved": False}


def inspect_checkout(root: Path, lock: dict) -> dict:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("LineageOS-Quellverzeichnis fehlt/ist verlinkt")
    location = root / ".repo/manifests"
    manifest = location / "default.xml"
    checked = verify_manifest(manifest, lock)
    if not location.is_dir() or location.is_symlink():
        raise ValueError("Kein offizieller repo-Manifest-Checkout")
    git = shutil.which("git")
    if not git:
        raise ValueError("git für lesende Manifest-Commit-Prüfung fehlt")
    result = subprocess.run([git, "-C", str(location), "rev-parse", "HEAD"],
                            capture_output=True, text=True, timeout=15, check=False)
    if result.returncode or result.stdout.strip() != lock["manifest_commit"]:
        raise ValueError("Manifest-Checkout-HEAD stimmt nicht mit Quellen-Lock überein")
    trees = {part: (root / part).is_dir() and not (root / part).is_symlink()
             for part in REQUIRED_PROJECT_TREES}
    checked.update({"manifest_checkout_commit_verified": True,
                    "required_source_trees": trees,
                    "minimum_source_paths_present": all(trees.values()),
                    "official_source_checkout_complete": False,
                    "lineage_arm64_android_tv_build_proven": False})
    return checked


def evaluate(checkout: Path | None = None) -> dict:
    lock = source_lock()
    source = ({"status": "LOCAL_CHECKOUT_NOT_PROVIDED"} if checkout is None else
              inspect_checkout(checkout, lock))
    return {"type": "q60t_lineage21_arm64_qemu_source_preflight", "build": "024",
            "status": "QEMU_SOURCE_PLAN_ONLY_INIT_NOT_STARTED",
            "lineage_branch": lock["branch"],
            "aosp_tag": lock["aosp_tag_observed"],
            "manifest_commit": lock["manifest_commit"],
            "official_tv_gsi_target": lock["lineage_tv_gsi_target"],
            "qemu_virt_arm64_target_available": False,
            "kernel_6_6_162_is_android14_gki": False,
            "source_checkout": source,
            "android_init_executed": False,
            "selinux_policy_validated": False,
            "property_service_started": False,
            "samsung_arm64_hardware_verified": False,
            "safe_to_flash": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 024: offizieller LineageOS-21-ARM64-Quellstand")
    parser.add_argument("--checkout", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.checkout)
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(payload)
        print(payload, end="")
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"Build-024-Quellprüfung abgebrochen: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
