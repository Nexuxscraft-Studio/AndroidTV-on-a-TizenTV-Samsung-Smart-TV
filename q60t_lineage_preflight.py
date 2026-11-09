#!/usr/bin/env python3
"""Build 022: offline LineageOS source and QEMU ARM32 kernel *preflight*.

No source sync, guest execution, TV access or release/version selection occurs.
This tool records checked evidence and intentionally cannot certify a boot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "porting/lineage_virtual/lineage-source-candidates.json"
VIRT = ROOT / "porting/lineage_virtual/qemu-virt-arm32.json"
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_CONFIG_BYTES = 4 * 1024 * 1024
SHA1_RE = re.compile(r"[a-f0-9]{40}\Z")

# Evidence, NOT a claim that these switches alone satisfy Android requirements.
# Built-in availability is distinguished from a module that initramfs cannot load.
KERNEL_FEATURES = {
    "device_nodes": "CONFIG_DEVTMPFS",
    "procfs": "CONFIG_PROC_FS",
    "sysfs": "CONFIG_SYSFS",
    "tmpfs": "CONFIG_TMPFS",
    "binder": "CONFIG_ANDROID_BINDER_IPC",
    "ashmem_legacy": "CONFIG_ASHMEM",
    "ion_legacy": "CONFIG_ION",
    "cgroups": "CONFIG_CGROUPS",
    "namespaces": "CONFIG_NAMESPACES",
    "seccomp": "CONFIG_SECCOMP",
    "seccomp_filter": "CONFIG_SECCOMP_FILTER",
    "selinux": "CONFIG_SECURITY_SELINUX",
}


def regular_limited_file(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Keine reguläre Eingabedatei: {path}")
    if path.stat().st_size > limit:
        raise ValueError(f"Datei überschreitet Größenlimit: {path}")
    return path.read_bytes()


def load_candidates(metadata: Path = SOURCES) -> dict:
    document = json.loads(regular_limited_file(metadata, 64 * 1024))
    if (document.get("build") != "022" or document.get("selected_branch") is not None or
            document.get("upstream_repo") != "https://github.com/LineageOS/android.git" or
            document.get("manifest_path") != "default.xml" or
            document.get("research_only_no_flash") is not True):
        raise ValueError("Build-022-Quelldaten müssen neutral und ausschließlich forschend bleiben")
    candidates = document.get("candidates")
    if not isinstance(candidates, list) or len(candidates) < 2:
        raise ValueError("LineageOS-Kandidatenliste fehlt")
    seen = set()
    for candidate in candidates:
        branch = candidate.get("branch")
        if (not isinstance(branch, str) or
                not re.fullmatch(r"(?:cm-14\.1|lineage-(?:15\.1|16\.0|17\.1))", branch) or
                branch in seen or candidate.get("source_ref_verified") is not True or
                candidate.get("qemu_virt_compatibility_verified") is not False or
                candidate.get("qemu_virt_compatible") is not False or
                type(candidate.get("android_api_level")) is not int):
            raise ValueError("Ungültiger oder als kompatibel vorgegebener LineageOS-Kandidat")
        for key in ("branch_head_sha", "manifest_git_blob_sha"):
            if not isinstance(candidate.get(key), str) or not SHA1_RE.fullmatch(candidate[key]):
                raise ValueError(f"Ungültiger Quellen-SHA: {branch}/{key}")
        seen.add(branch)
    return document


def load_virtual_board(board: Path = VIRT) -> dict:
    spec = json.loads(regular_limited_file(board, 64 * 1024))
    if (spec.get("build") != "022" or spec.get("board_target") != "virt,highmem=off" or
            spec.get("architecture") != "arm" or spec.get("pointer_width") != 32 or
            spec.get("qemu_only") is not True or spec.get("samsung_hardware_verified") is not False or
            spec.get("lineage_product_lunch_target_available") is not False or
            spec.get("flash_authorized") is not False):
        raise ValueError("QEMU-Profil ist nicht isoliert oder behauptet einen fertigen Port")
    return spec


def git_blob_sha1(content: bytes) -> str:
    # Git object IDs hash `blob <size>\0` plus the exact on-disk file bytes.
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\x00" + content).hexdigest()


def check_official_manifest(path: Path, expected_blob: str) -> dict:
    content = regular_limited_file(path, MAX_MANIFEST_BYTES)
    actual = git_blob_sha1(content)
    if actual != expected_blob:
        raise ValueError(f"Manifest-Blob-SHA stimmt nicht: erwartet {expected_blob}, erhalten {actual}")
    # No external entity resolution, DTD or Android repo 'include' expansion.
    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise ValueError("Manifest enthält eine hier nicht erlaubte DTD/Entity")
    try:
        document = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError(f"Fehlerhaftes XML-Manifest: {exc}") from exc
    if document.tag != "manifest" or not document.findall("project"):
        raise ValueError("Kein offizielles repo-Manifest mit Projekten")
    # Includes may still exist; only the pinned top-level manifest is validated.
    return {
        "status": "VERIFIED_PINNED_GIT_BLOB_NOT_FULL_SOURCE_CHECKOUT",
        "manifest_blob_sha1": actual,
        "sha256": hashlib.sha256(content).hexdigest(),
        "projects_in_top_level_manifest": len(document.findall("project")),
        "includes_resolved": False,
        "source_repositories_synced": False,
    }


def inspect_kernel_config(path: Path) -> dict:
    raw = regular_limited_file(path, MAX_CONFIG_BYTES)
    text = raw.decode("ascii", errors="replace")
    options = {}
    for line in text.splitlines():
        if re.fullmatch(r"CONFIG_[A-Z0-9_]+=[A-Za-z0-9_\"./+-]+", line):
            key, val = line.split("=", 1)
            options[key] = val
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            options[line[2:-11]] = "n"
    features = {}
    for name, config_key in KERNEL_FEATURES.items():
        value = options.get(config_key)
        if value == "y":
            status = "BUILT_IN"
        elif value == "m":
            status = "MODULE_ONLY_NOT_AUTOMATICALLY_LOADABLE"
        elif value == "n":
            status = "DISABLED"
        else:
            status = "UNKNOWN_OR_ABSENT"
        features[name] = {"config": config_key, "value": value, "status": status}
    return {
        "status": "INSPECTED_NOT_ANDROID_COMPATIBILITY_CERTIFIED",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "features": features,
        "all_feature_switches_built_in": all(x["status"] == "BUILT_IN" for x in features.values()),
    }


def evaluate(candidate_branch: str, *, source_manifest: Path | None = None,
             kernel_config: Path | None = None,
             metadata: Path = SOURCES, board_path: Path = VIRT) -> dict:
    source = load_candidates(metadata)
    machine = load_virtual_board(board_path)
    candidate = next((c for c in source["candidates"] if c["branch"] == candidate_branch), None)
    if candidate is None:
        raise ValueError("Nicht erfasster LineageOS-Branch: " + candidate_branch)
    manifest = ({"status": "NOT_PROVIDED", "source_repositories_synced": False}
                if source_manifest is None else
                check_official_manifest(source_manifest, candidate["manifest_git_blob_sha"]))
    config = ({"status": "NOT_PROVIDED"} if kernel_config is None else
              inspect_kernel_config(kernel_config))
    return {
        "type": "q60t_lineage_arm32_qemu_preflight",
        "build": "022",
        "status": "PREFLIGHT_ONLY_ANDROID_INIT_NOT_PROVEN",
        "candidate_evaluated": candidate_branch,
        "android_api_level": candidate["android_api_level"],
        "candidate_branch_head_sha": candidate["branch_head_sha"],
        "lineage_version_selected": False,
        "android_tv_build_ready": False,
        "source_manifest": manifest,
        "kernel_config": config,
        "machine": {
            "qemu_target": machine["board_target"], "cpu": machine["cpu"],
            "architecture": machine["architecture"], "kernel_version": machine["kernel_version"],
        },
        "unverified_gates": [
            "QEMU-virt-spezifische LineageOS ARM32 Device- und Product-Konfiguration",
            "Android-Init-Abhängigkeiten, Mountpunkte und ELF-Loader",
            "Property Service, ueventd, SELinux-Policy und enforcing Boot",
            "Service Manager, logd sowie sonstige Android-Systemdienste",
            "VINTF/HAL- und Treble-Anforderungen je Android-Version",
            "Echte Samsung-SoC-/Bootloader-/Mali-GPU-Hardware", 
        ],
        "guest_android_init_executed": False,
        "guest_android_services_executed": False,
        "samsung_tv_accessed": False,
        "safe_to_flash": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 022: Offline LineageOS/QEMU-ARM32-Vorprüfung")
    parser.add_argument("--candidate", required=True, help="Nur geprüfter Kandidat; KEINE Versionsauswahl")
    parser.add_argument("--source-manifest", type=Path, help="Originales offizielles default.xml, unverändert")
    parser.add_argument("--kernel-config", type=Path, help="Tatsächliche .config des QEMU-Kernels")
    parser.add_argument("--output", type=Path, help="Neuer JSON-Report, existierende Datei bleibt unverändert")
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.candidate, source_manifest=args.source_manifest,
                          kernel_config=args.kernel_config)
        result = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(result)
        print(result, end="")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Build-022-Preflight abgebrochen: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
