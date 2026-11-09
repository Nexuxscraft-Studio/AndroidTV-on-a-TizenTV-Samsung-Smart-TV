"""Test reproducible host staging without ever invoking Kbuild."""

from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import unittest

import q60t_android_kernel as bridge
import q60t_kernel_stage as stage


class KernelStageTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path]:
        source = root / "kernel"
        config_dir = source / "arch/arm/configs"
        config_dir.mkdir(parents=True)
        (source / "arch/arm/Makefile").write_text("", encoding="utf-8")
        (source / "Makefile").write_text(
            "VERSION = 4\nPATCHLEVEL = 1\nSUBLEVEL = 10\n", encoding="utf-8"
        )
        (config_dir / bridge.REFERENCE_PROFILE).write_text(
            "CONFIG_ARM=y\n"
            "# CONFIG_ANDROID_BINDER_IPC is not set\n"
            "CONFIG_SECURITY_SMACK=y\nCONFIG_SECURITY_SFD=y\n",
            encoding="utf-8",
        )
        fragment = root / "candidate.cfg"
        fragment.write_text(
            "# Host-only config\n"
            "CONFIG_ANDROID_BINDER_IPC=y\n"
            "# CONFIG_ANDROID_BINDER_IPC_32BIT is not set\n",
            encoding="utf-8",
        )
        return source, fragment

    def test_fragment_parser_understands_off_notation(self):
        with TemporaryDirectory() as tmp:
            _, fragment = self.fixture(Path(tmp))
            parsed = stage.parse_fragment(fragment)
            self.assertEqual(parsed["ANDROID_BINDER_IPC"], "y")
            self.assertEqual(parsed["ANDROID_BINDER_IPC_32BIT"], "n")

    def test_rejects_vendor_security_changes(self):
        with TemporaryDirectory() as tmp:
            _, fragment = self.fixture(Path(tmp))
            fragment.write_text(
                "CONFIG_ANDROID_BINDER_IPC=y\n# CONFIG_SECURITY_SFD is not set\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                stage.parse_fragment(fragment)

    def test_rejects_legacy_binder_enablement(self):
        with TemporaryDirectory() as tmp:
            _, fragment = self.fixture(Path(tmp))
            fragment.write_text(
                "CONFIG_ANDROID_BINDER_IPC=y\nCONFIG_ANDROID_BINDER_IPC_32BIT=y\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "legacy"):
                stage.parse_fragment(fragment)

    def test_rejects_missing_binder_abi_override(self):
        with TemporaryDirectory() as tmp:
            source, fragment = self.fixture(Path(tmp))
            fragment.write_text("CONFIG_ANDROID_BINDER_IPC=y\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ABI"):
                stage.stage(source, fragment, Path(tmp) / "stage")

    def test_output_is_separate_and_vendor_config_untouched(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, fragment = self.fixture(root)
            vendor_config = source / "arch/arm/configs" / bridge.REFERENCE_PROFILE
            before = hashlib.sha256(vendor_config.read_bytes()).hexdigest()
            output = root / "stage"
            manifest = stage.stage(source, fragment, output)
            self.assertEqual(before, hashlib.sha256(vendor_config.read_bytes()).hexdigest())
            self.assertEqual(manifest["status"], "STAGED_NOT_KCONFIG_VALIDATED")
            self.assertFalse(manifest["cross_compile_executed"])
            self.assertFalse(manifest["flash_authorized"])
            self.assertIn("CONFIG_ANDROID_BINDER_IPC=y",
                          (output / ".config").read_text(encoding="utf-8"))
            self.assertIn("CONFIG_SECURITY_SFD=y",
                          (output / ".config").read_text(encoding="utf-8"))
            self.assertEqual(json.loads(
                (output / "STAGE_MANIFEST.json").read_text(encoding="utf-8")
            )["staged_config_sha256"], manifest["staged_config_sha256"])
            with self.assertRaisesRegex(ValueError, "already exists"):
                stage.stage(source, fragment, output)

    def test_rejects_staging_inside_vendor_source(self):
        with TemporaryDirectory() as tmp:
            source, fragment = self.fixture(Path(tmp))
            with self.assertRaisesRegex(ValueError, "outside vendor"):
                stage.stage(source, fragment, source / "build")

    def test_fragment_duplicate_symbol_rejected(self):
        with TemporaryDirectory() as tmp:
            _, fragment = self.fixture(Path(tmp))
            fragment.write_text("CONFIG_ION=y\nCONFIG_ION=y\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                stage.parse_fragment(fragment)


if __name__ == "__main__":
    unittest.main()
