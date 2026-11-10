"""Synthetic fixtures for the read-only Build 050 Samsung source audit."""

import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import q60t_build050_vendor_code_audit as audit


class TestBuild050DirectSource(unittest.TestCase):
    def _fixtures(self, root):
        paths = {}
        for family, members in audit.MEMBERS.items():
            archive_path = root / f"{family}.tgz"
            with tarfile.open(archive_path, "w:gz") as archive:
                for key, member in members.items():
                    body = (
                        "samsung,sdp-nikel\nDT_MACHINE_START\n"
                        "sdp_secondary_startup\nu32 entry\n"
                        "drm_platform_init\n.load\n.unload\n"
                        "kbase_api_get_ddk_version\n"
                        "# CONFIG_ANDROID_BINDER_IPC is not set\n"
                        "# CONFIG_SECURITY_SELINUX is not set\n"
                        "CONFIG_SECURITY_SMACK=y\n"
                    ).encode()
                    info = tarfile.TarInfo(member)
                    info.size = len(body)
                    archive.addfile(info, io.BytesIO(body))
            paths[family] = archive_path
        return paths

    def test_raw_defconfig_distinct_from_modified_test(self):
        parsed = audit.config_status(
            "# CONFIG_ANDROID_BINDER_IPC is not set\n"
            "# CONFIG_SECURITY_SELINUX is not set\n"
            "# CONFIG_ION is not set\nCONFIG_SECURITY_SMACK=y\n"
        )
        self.assertEqual(parsed["CONFIG_ANDROID_BINDER_IPC"], "n")
        self.assertEqual(parsed["CONFIG_SECURITY_SELINUX"], "n")
        self.assertEqual(parsed["CONFIG_ION"], "n")
        self.assertEqual(parsed["CONFIG_SECURITY_SMACK"], "y")

    def test_markers_are_literal_and_numbered(self):
        parsed = audit.markers_in("first\nsecond-first\nfirst\n", ["first", "third"])
        self.assertEqual(parsed["first"], [1, 2, 3])
        self.assertEqual(parsed["third"], [])

    def test_synthetic_archives_never_grant_flash_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._fixtures(Path(directory))
            result = audit.inspect_sources(paths, verify_hashes=False)
            self.assertEqual(result["status"], "SOURCE_CODE_CONFIRMED_TV_UNVERIFIED")
            self.assertFalse(result["safe_to_flash"])
            self.assertFalse(result["hardware_boot_tested"])
            self.assertFalse(result["linux_6_6_driver_compiled"])
            self.assertEqual(len(result["source_files"]), 13)
            self.assertFalse(result["archives"]["kernel"]["expected_source_hash_matches"])

    def test_pinned_hash_refuses_untrusted_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._fixtures(Path(directory))
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                audit.inspect_sources(paths)

    def test_source_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.tgz"
            target.write_bytes(b"fixture")
            alias = Path(directory) / "alias.tgz"
            alias.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlinks"):
                audit.sha256_file(alias)

    def test_non_regular_tar_member_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._fixtures(Path(directory))
            with tarfile.open(paths["bootmode"], "w:gz") as archive:
                member = tarfile.TarInfo(audit.MEMBERS["bootmode"]["tizen_bootmode_module"])
                member.type = tarfile.SYMTYPE
                member.linkname = "/etc/passwd"
                archive.addfile(member)
            with self.assertRaisesRegex(ValueError, "Nonregular"):
                audit.inspect_sources(paths, verify_hashes=False)


if __name__ == "__main__":
    unittest.main()
