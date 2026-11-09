"""Synthetic host-only checks for Build 018; never launch QEMU in CI."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import q60t_qemu_runtime as runner


class QemuRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / runner.EXPECTED_ARTIFACT
        self.image.parent.mkdir(parents=True)
        self.image.write_bytes(b"FAKE ARM32 IMAGE ONLY - NOT A KERNEL")
        self.config = self.root / "output/.config"
        self.config.write_text("\n".join(
            (f"CONFIG_{key}={value}" if value != "n"
             else f"# CONFIG_{key} is not set")
            for key, value in runner.REQUIRED_CONFIG.items()) + "\n")
        self.report = self.root / "compile-report.json"
        self.document = {
            "profile": "qemu-binder-lab",
            "status": "HOST_KERNEL_COMPILED_NOT_BOOTABLE_VALIDATED",
            "resolved_config": {"verified": True},
            "artifact": {
                "path_within_workspace": runner.EXPECTED_ARTIFACT,
                "size_bytes": self.image.stat().st_size,
                "sha256": hashlib.sha256(self.image.read_bytes()).hexdigest(),
            },
        }
        self.save_report()

    def save_report(self):
        self.report.write_text(json.dumps(self.document), encoding="utf-8")

    def test_accept_verified_qemu_compiler_artifact(self):
        self.assertEqual(runner.validate_workspace(self.root), self.image)

    def test_reject_unverified_vendor_profile(self):
        self.document["profile"] = "binder-lab"
        self.save_report()
        with self.assertRaisesRegex(ValueError, "QEMU-Binder-Lab"):
            runner.validate_workspace(self.root)

    def test_reject_modified_image(self):
        self.image.write_bytes(b"ALTERED")
        with self.assertRaisesRegex(ValueError, "nicht mehr"):
            runner.validate_workspace(self.root)

    def test_reject_samsung_architecture(self):
        self.config.write_text(self.config.read_text() + "CONFIG_ARCH_SDP=y\n")
        with self.assertRaisesRegex(ValueError, "ARCH_SDP"):
            runner.validate_workspace(self.root)

    def test_command_disables_network_and_storage(self):
        command = runner.qemu_command("qemu-system-arm", self.image, None)
        self.assertIn("virt,highmem=off", command)
        self.assertIn("cortex-a15", command)
        self.assertEqual(command[command.index("-nic") + 1], "none")
        self.assertNotIn("-drive", command)
        self.assertNotIn("-initrd", command)
        self.assertNotIn("-enable-kvm", command)
        self.assertNotIn("-S", command)

    def test_optional_initrd_is_attached(self):
        initrd = self.root / "initrd.gz"
        initrd.write_bytes(b"synthetic")
        command = runner.qemu_command("qemu-system-arm", self.image, initrd)
        self.assertEqual(command[-2:], ["-initrd", str(initrd)])

    def test_no_fake_binder_runtime_success_from_banner(self):
        log = self.root / "console.log"
        log.write_bytes(b"Linux version 4.1.10-custom #1\nFreeing unused kernel memory\n")
        findings = runner.inspect_console(log)
        self.assertEqual(findings["status"], "KERNEL_INIT_PROGRESS_OBSERVED")
        self.assertTrue(findings["kernel_4_1_10_banner_seen"])
        self.assertFalse(findings["binder_transactions_executed"])
        self.assertFalse(findings["android_userspace_compatible"])

    def test_panic_overrides_banner_and_not_flashable(self):
        log = self.root / "console.log"
        log.write_bytes(b"Linux version 4.1.10 #1\nKernel panic - not syncing\n")
        findings = runner.inspect_console(log)
        self.assertEqual(findings["status"], "KERNEL_PANIC_OBSERVED")
        self.assertFalse(findings["safe_to_flash"])

    def test_dry_run_does_not_create_any_output(self):
        result = runner.run_probe(self.root, None, 10, binary=sys.executable,
                                  dry_run=True)
        self.assertEqual(result["status"], "QEMU_COMMAND_VALIDATED_NOT_EXECUTED")
        self.assertFalse(result["binder_runtime_verified"])
        self.assertFalse((self.root / "qemu-serial.log").exists())

    def test_reject_preexisting_log(self):
        (self.root / "qemu-serial.log").write_text("KEEP")
        with self.assertRaisesRegex(ValueError, "niemals überschreiben"):
            runner.run_probe(self.root, None, 10, binary=sys.executable)


if __name__ == "__main__":
    unittest.main()
