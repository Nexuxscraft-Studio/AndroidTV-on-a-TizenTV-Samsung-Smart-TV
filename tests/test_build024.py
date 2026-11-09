"""Build 024 source/boot/policy gates, synthetic fixtures only (no ROM)."""

import gzip
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import q60t_lineage_arm64_source as sources
import q60t_lineage_arm64_sepolicy as sepolicy
import q60t_lineage_arm64_initramfs as initrd
import q60t_lineage_arm64_init_result as result


def elf64_static():
    data = bytearray(256)
    data[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<HH", data, 16, 2, 183)
    struct.pack_into("<Q", data, 32, 64)
    struct.pack_into("<HH", data, 54, 56, 1)
    struct.pack_into("<I", data, 64, 1)
    return bytes(data)


def dummy_logs():
    return b"Linux version 6.6.162 #1\n[    0.55] init: init first stage started!\n"


def records(log):
    sha = hashlib.sha256(log).hexdigest()
    initrd_sha = "a" * 64
    lock = sources.source_lock()
    return ({"build": "023", "type": "q60t_arm64_virt_qemu_run",
             "log_sha256": sha, "initramfs_sha256": initrd_sha,
             "qemu_only": True, "safe_to_flash": False},
            {"type": "q60t_lineage21_arm64_first_stage_initramfs",
             "status": "REAL_SOURCE_BUILT_ARM64_INIT_STAGED_NOT_BOOTED",
             "lineage_branch": lock["branch"],
             "lineage_manifest_commit": lock["manifest_commit"],
             "lineage_manifest_blob_sha1": lock["manifest_git_blob_sha1"],
             "initramfs_sha256": initrd_sha,
             "qemu_only": True, "safe_to_flash": False})


class Build024Tests(unittest.TestCase):
    def test_locked_official_version_and_qemu_target_constraints(self):
        lock = sources.source_lock()
        self.assertEqual(lock["branch"], "lineage-21.0")
        self.assertEqual(lock["android_api_level"], 34)
        self.assertEqual(lock["lineage_tv_gsi_target"], "gsi_tv_arm64")
        self.assertFalse(lock["lineage_qemu_virt_device_target_exists"])
        self.assertFalse(lock["kernel6_6_is_android14_gki"])
        self.assertFalse(lock["safe_to_flash"])

    def test_source_plan_no_checkout_does_not_claim_success(self):
        plan = sources.evaluate()
        self.assertEqual(plan["source_checkout"]["status"], "LOCAL_CHECKOUT_NOT_PROVIDED")
        self.assertFalse(plan["android_init_executed"])
        self.assertFalse(plan["qemu_virt_arm64_target_available"])

    def test_official_manifest_hash_is_exact_and_xml_checked(self):
        xml = (b'<manifest><remote name="aosp" revision="refs/tags/android-14.0.0_r67"/>'
               b'<default revision="refs/heads/lineage-21.0"/>' +
               b''.join(f'<project path="item/{i}" name="x/{i}"/>'.encode() for i in range(31)) +
               b'</manifest>')
        lock = sources.source_lock()
        lock["manifest_git_blob_sha1"] = sources.manifest_git_blob(xml)
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder) / "default.xml"
            manifest.write_bytes(xml)
            self.assertEqual(sources.verify_manifest(manifest, lock)["top_level_projects"], 31)
            manifest.write_bytes(xml + b"\n")
            with self.assertRaisesRegex(ValueError, "Manifest-Hash"):
                sources.verify_manifest(manifest, lock)

    def test_source_dtd_rejected_even_if_hash_matches(self):
        xml = (b'<!DOCTYPE manifest [<!ENTITY x "oops">]><manifest/>' )
        lock = sources.source_lock()
        lock["manifest_git_blob_sha1"] = sources.manifest_git_blob(xml)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "default.xml"
            path.write_bytes(xml)
            with self.assertRaisesRegex(ValueError, "DTD"):
                sources.verify_manifest(path, lock)

    def test_bootstrap_archive_contains_real_elf_and_is_deterministic(self):
        raw = initrd.archive_from_init(elf64_static())
        self.assertEqual(raw, initrd.archive_from_init(elf64_static()))
        unzipped = gzip.decompress(raw)
        self.assertIn(b"init\0", unzipped)
        self.assertIn(b"first_stage_ramdisk\0", unzipped)
        self.assertIn(b"dev/console\0", unzipped)
        self.assertIn(b"TRAILER!!!\0", unzipped)

    def test_bootstrap_rejects_arm32_pid1_or_dynamic_elf(self):
        raw = bytearray(elf64_static())
        struct.pack_into("<H", raw, 18, 40)
        with self.assertRaisesRegex(ValueError, "AArch64"):
            initrd.archive_from_init(bytes(raw))
        raw = bytearray(elf64_static())
        struct.pack_into("<I", raw, 64, 3)
        with self.assertRaisesRegex(ValueError, "PT_INTERP"):
            initrd.archive_from_init(bytes(raw))

    def test_selinux_policy_missing_vendor_does_not_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            platform = root / "system/etc/selinux/plat_sepolicy.cil"
            platform.parent.mkdir(parents=True)
            platform.write_text("(class process (fork))")
            report = sepolicy.inspect(root)
            self.assertFalse(report["platform_and_vendor_inputs_present"])
            self.assertEqual(report["policy_files"]["platform_cil"]["status"],
                             "FILE_EXISTS_NOT_POLICY_VALIDATED")
            self.assertEqual(report["policy_files"]["vendor_cil"]["status"], "NOT_PROVIDED")
            self.assertFalse(report["selinux_enforcing_android_boot_verified"])

    def test_full_policy_file_presence_still_not_compiled_or_validated(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for relative in sepolicy.POLICY_FILES.values():
                item = root / relative
                item.parent.mkdir(parents=True, exist_ok=True)
                item.write_bytes(b"synthetic")
            report = sepolicy.inspect(root)
            self.assertTrue(report["platform_and_vendor_inputs_present"])
            self.assertFalse(report["secilc_compiled_verified"])
            self.assertFalse(report["sepolicy_neverallow_checks_passed"])

    def test_android_init_log_claim_requires_qemu_and_staging_hash(self):
        log = dummy_logs()
        qemu, staged = records(log)
        seen = result.inspect(log, qemu, staged)
        self.assertTrue(seen["real_lineage21_first_stage_init_banner_reported"])
        self.assertFalse(seen["first_stage_init_completed"])
        self.assertFalse(seen["property_service_proven"])
        self.assertFalse(seen["lineage_android_tv_booted"])
        self.assertFalse(seen["safe_to_flash"])
        qemu["initramfs_sha256"] = "b" * 64
        self.assertFalse(result.inspect(log, qemu, staged)["real_lineage21_first_stage_init_banner_reported"])

    def test_android_init_first_stage_is_not_second_stage(self):
        log = dummy_logs() + (b"init: init second stage started!\n"
                              b"init: property service started\n"
                              b"init: starting service 'logd'...\n")
        qemu, staged = records(log)
        seen = result.inspect(log, qemu, staged)
        self.assertTrue(seen["second_stage_init_log_hint_seen"])
        self.assertTrue(seen["property_service_log_hint_seen"])
        self.assertTrue(seen["service_start_log_hints_seen"]["logd"])
        self.assertFalse(seen["second_stage_init_proven"])
        self.assertFalse(seen["property_service_proven"])
        self.assertFalse(seen["system_services_proven_running"])


if __name__ == "__main__":
    unittest.main()
