"""Synthetic verification tests for the one-line Binder Kconfig experiment."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import q60t_kconfig_verify as checker


class KconfigVerifyTests(unittest.TestCase):
    def fixture(self, folder: Path) -> tuple[Path, Path, Path, Path]:
        source = folder / "old.Kconfig"
        patched = folder / "new.Kconfig"
        source.write_text(checker.OLD_BLOCK + "\n", encoding="utf-8")
        patched.write_text(checker.NEW_BLOCK + "\n", encoding="utf-8")
        before = folder / "old.config"
        after = folder / "new.config"
        common = "CONFIG_SECURITY_SMACK=y\nCONFIG_SECURITY_SFD=y\n"
        for key, value in checker.REQUIRED.items():
            if key == "ANDROID_BINDER_IPC_32BIT":
                continue
            common += f"CONFIG_{key}={value}\n"
        before.write_text(
            common + "CONFIG_ANDROID_BINDER_IPC_32BIT=y\n",
            encoding="utf-8",
        )
        after.write_text(
            common + "# CONFIG_ANDROID_BINDER_IPC_32BIT is not set\n",
            encoding="utf-8",
        )
        return source, patched, before, after

    def test_exact_kconfig_result_passes(self):
        with TemporaryDirectory() as tmp:
            paths = self.fixture(Path(tmp))
            result = checker.verify(*paths)
            self.assertEqual(result["status"],
                             "KCONFIG_RESULT_VERIFIED_IN_ISOLATED_HOST_TREE")
            self.assertTrue(result["vendor_security_unchanged_between_runs"])
            self.assertFalse(result["kernel_compiled"])
            self.assertFalse(result["flash_authorized"])

    def test_extra_kconfig_change_rejected(self):
        with TemporaryDirectory() as tmp:
            source, patched, before, after = self.fixture(Path(tmp))
            patched.write_text(
                checker.NEW_BLOCK + "\nconfig OTHER\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "extra source"):
                checker.verify(source, patched, before, after)

    def test_unrelated_config_delta_rejected(self):
        with TemporaryDirectory() as tmp:
            source, patched, before, after = self.fixture(Path(tmp))
            with after.open("a", encoding="utf-8") as handle:
                handle.write("CONFIG_EXTRA=y\n")
            with self.assertRaisesRegex(ValueError, "more than"):
                checker.verify(source, patched, before, after)

    def test_vendor_security_change_rejected(self):
        with TemporaryDirectory() as tmp:
            source, patched, before, after = self.fixture(Path(tmp))
            text = after.read_text(encoding="utf-8")
            after.write_text(text.replace("CONFIG_SECURITY_SFD=y",
                                          "# CONFIG_SECURITY_SFD is not set"),
                             encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "security"):
                checker.verify(source, patched, before, after)


if __name__ == "__main__":
    unittest.main()
