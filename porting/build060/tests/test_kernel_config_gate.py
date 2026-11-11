"""Resolved Linux ARM32 Kconfig gate regression tests."""

import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).resolve().parents[1] / "kernel_config_gate.py"
SPEC = importlib.util.spec_from_file_location("build060_kernel_gate", PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class KernelConfigTests(unittest.TestCase):
    def test_parser_handles_disabled_config(self):
        parsed = mod.parse_config("CONFIG_AEABI=y\n# CONFIG_ARM64 is not set\n")
        self.assertEqual(parsed["CONFIG_ARM64"], "n")

    def test_complete_static_config_passes_only_static_gate(self):
        cfg = {key: "y" for key in mod.CRITICAL}
        cfg["CONFIG_ARM64"] = "n"
        report = mod.inspect_config(cfg)
        self.assertEqual(report["status"], "PASS_STATIC_CONFIG_ONLY")
        self.assertEqual(report["runtime_validation"], "UNVERIFIED")

    def test_missing_binder_blocks(self):
        cfg = {key: "y" for key in mod.CRITICAL}
        del cfg["CONFIG_ANDROID_BINDER_IPC"]
        report = mod.inspect_config(cfg)
        self.assertEqual(report["status"], "BLOCKED_STATIC_CONFIG")

    def test_arm64_kernel_blocks(self):
        cfg = {key: "y" for key in mod.CRITICAL}
        cfg["CONFIG_ARM64"] = "y"
        report = mod.inspect_config(cfg)
        self.assertFalse(report["architecture_ok"])


if __name__ == "__main__":
    unittest.main()
