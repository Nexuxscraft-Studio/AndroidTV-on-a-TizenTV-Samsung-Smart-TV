"""No-network, no-ROM tests for the opt-in Android TV build orchestrator."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


PATH = Path(__file__).resolve().parents[1] / "lineage_build.py"
SPEC = importlib.util.spec_from_file_location("build060_lineage_build", PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class LineageBuildTests(unittest.TestCase):
    def test_require_synced_source_landmarks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(set(mod.validate_source(root)),
                             {".repo", "build/envsetup.sh", "vendor/lineage/config"})
            (root / ".repo").mkdir()
            (root / "build").mkdir()
            (root / "build/envsetup.sh").touch()
            (root / "vendor/lineage/config").mkdir(parents=True)
            self.assertEqual(mod.validate_source(root), [])

    def test_command_pins_arm32_emulator_product(self):
        command = mod.command(Path("/tmp/lineage test"), "check")
        self.assertEqual(command[-2:], ["/tmp/lineage test", "check"])
        self.assertIn("breakfast sdk_tv_arm eng", command[2])
        self.assertIn('"$target_arch" != arm', command[2])
        self.assertNotIn("repo sync", command[2])

    def test_deny_unknown_mode(self):
        with self.assertRaises(ValueError):
            mod.command(Path("/tmp"), "flash")

    def test_build_requires_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".repo").mkdir()
            (root / "build").mkdir()
            (root / "build/envsetup.sh").touch()
            (root / "vendor/lineage/config").mkdir(parents=True)
            with self.assertRaises(SystemExit) as caught:
                mod.main(["--source", tmp, "--mode", "build"])
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
