"""Build 024: synthetic, offline, no Android binary execution or TV access."""

import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

import q60t_lineageos_preflight as preflight
import q60t_lineageos_initramfs as initramfs
import q60t_lineageos_guest_result as guest


def fake_arm64_elf(machine=183, interpreter=False, needed=False):
    blob = bytearray(256)
    blob[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<HH", blob, 16, 2, machine)
    struct.pack_into("<Q", blob, 32, 64)
    struct.pack_into("<HH", blob, 54, 56, 1)
    struct.pack_into("<I", blob, 64, 3 if interpreter else (2 if needed else 1))
    if needed:
        struct.pack_into("<Q", blob, 64 + 8, 128)
        struct.pack_into("<Q", blob, 64 + 32, 32)
        struct.pack_into("<QQ", blob, 128, 1, 0)
    return bytes(blob)


def run_git(source, *args):
    return subprocess.run(["git", "-C", str(source), *args], capture_output=True,
                          text=True, check=True)


def fake_lineageos_source(base):
    source = base / "system-core"
    source.mkdir()
    run_git(source, "init", "-b", "lineage-22.2")
    run_git(source, "remote", "add", "origin",
            "https://github.com/LineageOS/android_system_core.git")
    for name in preflight.SOURCE_FILES:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("// synthetic source; not real LineageOS\n", encoding="utf-8")
    run_git(source, "add", ".")
    run_git(source, "-c", "user.name=Q60T Test", "-c", "user.email=test@example.invalid",
            "commit", "-m", "synthetic test only")
    return source


class Build024Tests(unittest.TestCase):
    def test_lineageos_remote_restricts_official_repo(self):
        self.assertEqual(preflight.canonical_remote(
            "git@github.com:LineageOS/android_system_core.git"),
            "LineageOS/android_system_core")
        self.assertIsNone(preflight.canonical_remote(
            "https://github.com/untrusted/android_system_core.git"))

    def test_arm64_static_elf_rejects_dynamic_arm32_and_truncated(self):
        info = preflight.inspect_static_arm64_init(fake_arm64_elf())
        self.assertEqual(info["machine"], "AArch64")
        with self.assertRaisesRegex(ValueError, "AArch64"):
            preflight.inspect_static_arm64_init(fake_arm64_elf(machine=40))
        with self.assertRaisesRegex(ValueError, "PT_INTERP"):
            preflight.inspect_static_arm64_init(fake_arm64_elf(interpreter=True))
        with self.assertRaisesRegex(ValueError, "DT_NEEDED"):
            preflight.inspect_static_arm64_init(fake_arm64_elf(needed=True))
        with self.assertRaisesRegex(ValueError, "ELF64"):
            preflight.inspect_static_arm64_init(b"\x7fELF\x01")

    def test_source_audit_records_commit_but_no_signature_attestation(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = fake_lineageos_source(Path(temporary))
            report = preflight.preflight(source, None, None)
            self.assertEqual(report["status"], "LINEAGEOS_SOURCE_AUDITED_INIT_BINARY_NOT_SUPPLIED")
            self.assertRegex(report["source"]["commit"], "^[a-f0-9]{40}$")
            self.assertFalse(report["source"]["git_commit_signature_verified"])
            self.assertFalse(report["staging_ready"])

    def test_source_audit_rejects_wrong_branch_or_remote(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = fake_lineageos_source(Path(temporary))
            run_git(source, "remote", "set-url", "origin", "https://github.com/bad/source.git")
            with self.assertRaisesRegex(ValueError, "offizielle"):
                preflight.inspect_source(source)
            run_git(source, "remote", "set-url", "origin",
                    "https://github.com/LineageOS/android_system_core.git")
            run_git(source, "switch", "-c", "unrelated-branch")
            with self.assertRaisesRegex(ValueError, "Falscher"):
                preflight.inspect_source(source)

    def test_preflight_requires_exact_explicit_binary_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = fake_lineageos_source(root)
            binary = root / "init"
            binary.write_bytes(fake_arm64_elf())
            with self.assertRaisesRegex(ValueError, "expected-init-sha256"):
                preflight.preflight(source, binary, None)
            with self.assertRaisesRegex(ValueError, "stimmt nicht"):
                preflight.preflight(source, binary, "a" * 64)
            result = preflight.preflight(source, binary, hashlib.sha256(binary.read_bytes()).hexdigest())
            self.assertTrue(result["staging_ready"])
            self.assertFalse(result["binary_provenance_cryptographically_verified"])

    def test_initramfs_is_deterministic_and_contains_original_init_bytes(self):
        elf = fake_arm64_elf()
        blob = initramfs.archive_init(elf)
        self.assertEqual(blob, initramfs.archive_init(elf))
        unpacked = gzip.decompress(blob)
        self.assertIn(elf, unpacked)
        self.assertIn(b"dev/console\x00", unpacked)
        self.assertIn(b"first_stage_ramdisk\x00", unpacked)
        self.assertIn(b"TRAILER!!!\x00", unpacked)

    def test_stage_fails_closed_on_unstaged_preflight_or_changed_binary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "init"
            binary.write_bytes(fake_arm64_elf())
            path = root / "preflight.json"
            info = {"type": "q60t_build024_lineageos_first_stage_init_preflight",
                    "build": "024", "staging_ready": False,
                    "binary_provenance_cryptographically_verified": False,
                    "safe_to_flash": False, "arm64_init_elf": None}
            path.write_text(json.dumps(info), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Preflight|nicht für"):
                initramfs.stage(binary, path, root / "stage.cpio.gz", root / "stage.json")
            self.assertFalse((root / "stage.cpio.gz").exists())
            info.update(staging_ready=True, arm64_init_elf={"sha256": "a" * 64})
            path.write_text(json.dumps(info), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "verändert"):
                initramfs.stage(binary, path, root / "stage.cpio.gz", root / "stage.json")

    def test_stage_writes_fresh_pinned_archive_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "init"
            binary.write_bytes(fake_arm64_elf())
            source = fake_lineageos_source(root)
            info = preflight.preflight(source, binary, hashlib.sha256(binary.read_bytes()).hexdigest())
            preflight_path = root / "preflight.json"
            preflight_path.write_text(json.dumps(info), encoding="utf-8")
            archive = root / "init.cpio.gz"
            report = root / "stage.json"
            stage = initramfs.stage(binary, preflight_path, archive, report)
            self.assertEqual(stage["archive_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertFalse(stage["android_booted"])
            with self.assertRaisesRegex(ValueError, "Ausgabepfad"):
                initramfs.stage(binary, preflight_path, archive, report)

    def test_guest_report_never_claims_lineageos_or_samsung_compatibility(self):
        log = b"Linux version 6.6.162 #1\ninit: init first stage started!\n"
        raw = json.dumps({"type": "q60t_build024_lineageos_first_stage_init_preflight",
                          "staging_ready": True, "arm64_init_elf": {"sha256": "1" * 64}}).encode()
        stage = {"type": "q60t_build024_lineageos_arm64_initramfs_stage",
                 "build": "024", "safe_to_flash": False, "archive_sha256": "2" * 64,
                 "init_elf_sha256": "1" * 64,
                 "preflight_report_sha256": hashlib.sha256(raw).hexdigest()}
        qemu = {"type": "q60t_arm64_virt_qemu_run", "build": "023",
                "qemu_only": True, "samsung_tv_accessed": False, "safe_to_flash": False,
                "log_sha256": hashlib.sha256(log).hexdigest(),
                "initramfs_sha256": "2" * 64}
        report = guest.inspect(log, qemu, stage, raw)
        self.assertTrue(report["android_first_stage_init_log_reported"])
        self.assertFalse(report["android_init_executed_attested"])
        self.assertFalse(report["lineageos_booted"])
        self.assertFalse(report["safe_to_flash"])
        report_bad = guest.inspect(log + b"tampered\n", qemu, stage, raw)
        self.assertFalse(report_bad["android_first_stage_init_log_reported"])
        self.assertFalse(report_bad["log_and_artifact_hash_chain_valid"])


if __name__ == "__main__":
    unittest.main()
