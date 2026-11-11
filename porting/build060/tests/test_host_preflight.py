"""Offline host preflight unit tests (no build or hardware access)."""

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "host_preflight.py"
SPEC = importlib.util.spec_from_file_location("build060_host_preflight", MODULE_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class PreflightTests(unittest.TestCase):
    def test_memtotal_kib_conversion(self):
        self.assertEqual(mod.memory_gib("MemTotal: 67108864 kB\n"), 64.0)

    def test_missing_memtotal(self):
        with self.assertRaises(ValueError):
            mod.memory_gib("MemFree: 5 kB\n")

    def test_good_amd64_host(self):
        result = mod.check_host(Path("/opt/lineage"), 64, 400, "x86_64",
                                {name: True for name in mod.TOOLS})
        self.assertTrue(result["ready"])

    def test_4g_ram_rejected(self):
        result = mod.check_host(Path("/opt/lineage"), 4, 500, "x86_64",
                                {name: True for name in mod.TOOLS})
        self.assertFalse(result["ready"])
        self.assertFalse(result["checks"]["ram"])

    def test_missing_tools_rejected(self):
        tools = {name: True for name in mod.TOOLS}
        tools["repo"] = False
        result = mod.check_host(Path("/opt/lineage"), 64, 400, "x86_64", tools)
        self.assertFalse(result["ready"])


if __name__ == "__main__":
    unittest.main()
