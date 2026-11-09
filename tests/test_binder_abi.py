"""Synthetic fail-closed checks of the frozen AOSP Binder UAPI comparison."""

from contextlib import redirect_stderr
import io
from pathlib import Path
import json
import tempfile
import unittest

import q60t_binder_abi as binder_abi


class BinderAbiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "src"
        (self.source / "include/uapi/linux/android").mkdir(parents=True)
        (self.source / "drivers/android").mkdir(parents=True)
        (self.source / "arch/arm").mkdir(parents=True)
        (self.source / "arch/arm/Makefile").write_text("# synthetic ARM tree\n")
        (self.source / "Makefile").write_text(
            "VERSION = 4\nPATCHLEVEL = 1\nSUBLEVEL = 10\n")
        self.header = self.source / "include/uapi/linux/android/binder.h"
        self.header.write_text(
            "#define BINDER_CURRENT_PROTOCOL_VERSION 7\n"
            "#define BINDER_CURRENT_PROTOCOL_VERSION 8\n"
            "#define BINDER_WRITE_READ _IOWR('b', 1, int)\n"
            "#define BINDER_SET_IDLE_TIMEOUT _IOW('b', 3, int)\n"
            "#define BINDER_VERSION _IOWR('b', 9, int)\n"
            "enum x { TF_ONE_WAY = 1 };\n")
        self.driver = self.source / "drivers/android/binder.c"
        self.driver.write_text(
            "static struct binder_node *binder_context_mgr_node;\n"
            "switch (cmd) { case BINDER_WRITE_READ: break;\n"
            "case BINDER_VERSION: break; }\n")

    def test_abi_declared_but_not_handled(self):
        r = binder_abi.audit(self.source)
        self.assertEqual(r["protocol_versions_found_in_text"], [7, 8])
        self.assertTrue(r["core_ioctl_in_header"]["BINDER_SET_IDLE_TIMEOUT"])
        self.assertFalse(r["core_ioctl_handlers_in_driver"]["BINDER_SET_IDLE_TIMEOUT"])
        self.assertIn("BINDER_SET_IDLE_TIMEOUT", r["ioctl_declared_but_no_handler"])
        self.assertFalse(r["flash_authorized"])
        self.assertFalse(r["android_userspace_compatible"])

    def test_comments_are_not_driver_handler_evidence(self):
        self.driver.write_text("/* case BINDER_VERSION: */\n")
        r = binder_abi.audit(self.source)
        self.assertFalse(r["core_ioctl_handlers_in_driver"]["BINDER_VERSION"])
        self.assertFalse(binder_abi.symbols(
            "/* #define BINDER_FREEZE _IOW('b', 14, int) */\n",
            ("BINDER_FREEZE",), "ioctl")["BINDER_FREEZE"])

    def test_experimental_scaffold_does_not_prove_runtime(self):
        self.driver.write_text(
            'struct binder_context { int mgr_node; };\n'
            '"hwbinder" "vndbinder"\n'
            'proc->context->mgr_node;\n'
            'target_proc->context != proc->context;\n')
        r = binder_abi.audit(self.source)
        self.assertTrue(r["experimental_three_context_source_detected"])
        self.assertFalse(r["runtime_verified"])

    def test_refuse_unknown_kernel_version(self):
        (self.source / "Makefile").write_text("VERSION = 5\nPATCHLEVEL = 4\nSUBLEVEL = 0\n")
        with self.assertRaisesRegex(ValueError, "4.1.10"):
            binder_abi.audit(self.source)

    def test_do_not_overwrite_report(self):
        target = self.root / "existing.json"
        target.write_text('{"unchanged": true}')
        with redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(binder_abi.main([
                "--source", str(self.source), "--output", str(target)
            ]), 2)
        self.assertIn("Binder-ABI-Survey fehlgeschlagen:", errors.getvalue())
        self.assertEqual(json.loads(target.read_text()), {"unchanged": True})

    def test_refuse_symlinked_header(self):
        self.header.unlink()
        self.header.symlink_to(self.root / "absent")
        with self.assertRaisesRegex(ValueError, "Eingabedatei"):
            binder_abi.audit(self.source)


if __name__ == "__main__":
    unittest.main()
