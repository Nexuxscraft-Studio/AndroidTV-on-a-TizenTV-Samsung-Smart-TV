"""Synthetic tests only; never compile or launch vendor kernel code."""

from contextlib import redirect_stderr
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

import q60t_android_kernel as bridge


class KernelBridgeTests(unittest.TestCase):
    def make_source(self, folder: Path) -> Path:
        source = folder / "linux-4.1.10"
        (source / "arch/arm/configs").mkdir(parents=True)
        (source / "drivers/android").mkdir(parents=True)
        (source / "arch/x86").mkdir(parents=True)
        (source / "Makefile").write_text(
            "VERSION = 4\nPATCHLEVEL = 1\nSUBLEVEL = 10\n", encoding="utf-8"
        )
        (source / "arch/arm/Makefile").write_text("", encoding="utf-8")
        (source / "drivers/android/Kconfig").write_text(
            "config ANDROID_BINDER_IPC\n\ttristate \"Binder\"\n"
            "config ANDROID_BINDER_IPC_32BIT\n"
            "\tbool\n\tdefault y\n"
            "\t  Note: enabling this will break newer Android user-space.\n"
            "config ASHMEM\n\tbool \"Ashmem\"\n"
            "config MEMCG\n\tbool \"Memory cgroups\"\n",
            encoding="utf-8",
        )
        (source / "arch/x86/Kconfig").write_text(
            "config ANDROID_BINDERFS\n\tbool \"x86 only\"\n", encoding="utf-8"
        )
        (source / "arch/arm/configs" / bridge.REFERENCE_PROFILE).write_text(
            "CONFIG_ARM=y\nCONFIG_AEABI=y\n"
            "# CONFIG_ANDROID_BINDER_IPC is not set\n"
            "# CONFIG_ASHMEM is not set\n"
            "# CONFIG_MEMCG is not set\n"
            "CONFIG_SECURITY_SMACK=y\n"
            "CONFIG_SECURITY_SFD=y\n",
            encoding="utf-8",
        )
        return source

    def test_config_parser_distinguishes_off_and_absent(self):
        with TemporaryDirectory() as tmp:
            config = Path(tmp) / "config"
            config.write_text("CONFIG_ARM=y\n# CONFIG_ASHMEM is not set\n",
                              encoding="utf-8")
            result = bridge.read_config(config)
            self.assertEqual(result["symbols"]["ASHMEM"], "n")
            self.assertNotIn("ION", result["symbols"])

    def test_conflicting_values_are_rejected(self):
        with TemporaryDirectory() as tmp:
            config = Path(tmp) / "config"
            config.write_text("CONFIG_ASHMEM=y\n# CONFIG_ASHMEM is not set\n",
                              encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                bridge.read_config(config)

    def test_kconfig_does_not_use_x86_only_declaration(self):
        with TemporaryDirectory() as tmp:
            source = self.make_source(Path(tmp))
            scan = bridge.read_kconfig_definitions(source)
            self.assertIn("ANDROID_BINDER_IPC", scan["declarations"])
            self.assertNotIn("ANDROID_BINDERFS", scan["declarations"])

    def test_proposes_only_available_non_security_symbols(self):
        with TemporaryDirectory() as tmp:
            source = self.make_source(Path(tmp))
            report = bridge.compute_report(source)
            self.assertIn("CONFIG_ANDROID_BINDER_IPC=y",
                          report["fragment_proposals"])
            self.assertIn("CONFIG_ASHMEM=y", report["fragment_proposals"])
            self.assertIn("# CONFIG_ANDROID_BINDER_IPC_32BIT is not set",
                          report["fragment_proposals"])
            self.assertNotIn("CONFIG_SECURITY_SELINUX=y",
                             report["fragment_proposals"])
            self.assertNotIn("CONFIG_ANDROID_BINDERFS=y",
                             report["fragment_proposals"])
            self.assertTrue(report["vendor_security_review"]["smack_enabled"])
            self.assertFalse(report["flash_authorized"])
            self.assertFalse(report["kernel_built"])
            self.assertEqual(report["status"], "OFFLINE_ANALYSIS_ONLY")

    def test_no_unsupported_symbols_in_fragment(self):
        with TemporaryDirectory() as tmp:
            source = self.make_source(Path(tmp))
            report = bridge.compute_report(source)
            candidate = bridge.fragment(report)
            self.assertIn("CONFIG_ANDROID_BINDER_IPC=y\n", candidate)
            self.assertIn("# CONFIG_ANDROID_BINDER_IPC_32BIT is not set",
                          candidate)
            self.assertNotIn("CONFIG_ANDROID_BINDERFS=y", candidate)
            self.assertNotIn("CONFIG_SECURITY_SMACK=n", candidate)
            self.assertIn("NOT disabled.", candidate)

    def test_configuration_symlinks_are_rejected(self):
        with TemporaryDirectory() as tmp:
            source = self.make_source(Path(tmp))
            config = source / "arch/arm/configs" / bridge.REFERENCE_PROFILE
            config.unlink()
            config.symlink_to(source / "Makefile")
            with self.assertRaisesRegex(ValueError, "linked"):
                bridge.compute_report(source)

    def test_kernel_version_mismatch_is_blocked(self):
        with TemporaryDirectory() as tmp:
            source = self.make_source(Path(tmp))
            (source / "Makefile").write_text(
                "VERSION = 5\nPATCHLEVEL = 10\nSUBLEVEL = 1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "4.1.10"):
                bridge.compute_report(source)

    def test_cli_creates_two_outputs_and_never_overwrites(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self.make_source(root)
            report = root / "report.json"
            fragment = root / "fragment.cfg"
            args = ["--source", str(source), "--report", str(report),
                    "--fragment-out", str(fragment)]
            self.assertEqual(bridge.main(args), 0)
            info = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(info["source_version"], "4.1.10")
            self.assertTrue(fragment.exists())
            with redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(bridge.main(args), 2)
            self.assertIn("Refusing to overwrite output", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
