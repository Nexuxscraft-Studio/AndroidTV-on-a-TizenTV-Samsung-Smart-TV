"""Synthetic tests for static Android-kernel blockers and evidence boundaries."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import q60t_kernel_readiness as readiness
import q60t_android_kernel as bridge


class KernelReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.config = self.root / "resolved.config"
        (self.source / "arch/arm/configs").mkdir(parents=True)
        (self.source / "arch/arm/Makefile").write_text("# ARM target\n")
        (self.source / "Makefile").write_text(
            "VERSION = 4\nPATCHLEVEL = 1\nSUBLEVEL = 10\n")
        (self.source / "arch/arm/configs" / bridge.REFERENCE_PROFILE).write_text(
            "CONFIG_SECURITY_SMACK=y\n")
        (self.source / "drivers/android").mkdir(parents=True)
        (self.source / "drivers/android/Kconfig").write_text(
            "config ANDROID_BINDER_IPC\n\tbool \"Binder\"\n")
        (self.source / "drivers/android/binder.c").write_text(
            'static struct miscdevice binder_miscdev = { .name = "binder" };\n')
        (self.source / "include/uapi/linux/android").mkdir(parents=True)
        (self.source / "include/uapi/linux/android/binder.h").write_text(
            "#define BINDER_CURRENT_PROTOCOL_VERSION 7\n"
            "#define BINDER_CURRENT_PROTOCOL_VERSION 8\n")
        self.config.write_text(
            "CONFIG_ANDROID_BINDER_IPC=y\nCONFIG_AUDIT=y\n"
            "CONFIG_SECURITY_SMACK=y\nCONFIG_SECURITY_SFD=y\n"
            "# CONFIG_SECURITY_SELINUX is not set\n"
            'CONFIG_DEFAULT_SECURITY="smack"\n')

    def test_reports_missing_modern_binder_and_selinux(self) -> None:
        result = readiness.audit(self.source, self.config)
        self.assertEqual(result["status"], "GAPS_FOUND_NOT_ANDROID_READY")
        self.assertFalse(result["flash_authorized"])
        self.assertFalse(result["supported_android14_kernel"])
        self.assertTrue(result["binder"]["single_misc_binder_declared"])
        self.assertFalse(result["binder"]["hwbinder_and_vndbinder_proven"])
        self.assertEqual(result["binder"]["protocol_versions_in_source"], [7, 8])
        self.assertFalse(result["security"]["selinux_compiled"])

    def test_selinux_config_still_not_an_android_compatible_rom(self) -> None:
        self.config.write_text(
            self.config.read_text().replace(
                "# CONFIG_SECURITY_SELINUX is not set", "CONFIG_SECURITY_SELINUX=y")
            .replace('CONFIG_DEFAULT_SECURITY="smack"',
                     'CONFIG_DEFAULT_SECURITY="selinux"')
            + "CONFIG_DEFAULT_SECURITY_SELINUX=y\n")
        result = readiness.audit(self.source, self.config)
        self.assertTrue(result["security"]["selinux_compiled"])
        self.assertTrue(result["security"]["selinux_default"])
        self.assertFalse(result["binder"]["hwbinder_and_vndbinder_proven"])
        self.assertFalse(result["security"]["android_policy_compatible"])

    def test_wrong_version_is_rejected(self) -> None:
        (self.source / "Makefile").write_text(
            "VERSION = 5\nPATCHLEVEL = 4\nSUBLEVEL = 0\n")
        with self.assertRaisesRegex(ValueError, "Linux 4.1.10"):
            readiness.audit(self.source, self.config)

    def test_no_overwriting_reports(self) -> None:
        report = self.root / "existing.json"
        report.write_text(json.dumps({"safe": True}))
        exit_code = readiness.main([
            "--source", str(self.source), "--config", str(self.config),
            "--output", str(report)])
        self.assertEqual(exit_code, 2)
        self.assertEqual(json.loads(report.read_text()), {"safe": True})


if __name__ == "__main__":
    unittest.main()
