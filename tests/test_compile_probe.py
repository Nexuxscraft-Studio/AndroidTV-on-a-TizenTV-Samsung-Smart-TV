import tempfile
import unittest
from pathlib import Path
import json

import q60t_compile_probe as probe


class CompileProbeTests(unittest.TestCase):
    def test_refuse_to_overlap_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            with self.assertRaisesRegex(ValueError, "überlappen"):
                probe.validate_directories(source, source / "output")

    def test_refuse_to_reuse_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            workspace = Path(temp) / "output"
            workspace.mkdir()
            with self.assertRaisesRegex(ValueError, "bereits"):
                probe.validate_directories(source, workspace)

    def test_reject_external_source_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            (source / "escape").symlink_to(Path(temp), target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Symlink"):
                probe.check_source_symlinks(source)

    def test_allow_internal_source_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            (source / "internal").mkdir()
            (source / "link").symlink_to("internal", target_is_directory=True)
            self.assertEqual(probe.check_source_symlinks(source), 1)

    def test_detect_compile_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "build.log"
            log.write_text("CC file.o\nmissing.h: fatal error: missing header\n"
                           "make: *** target Error 2\n", encoding="utf-8")
            self.assertEqual(len(probe.diagnostics(log)), 2)

    def test_header_explicitly_non_firmware(self):
        self.assertIn("NO_FLASH", probe.GENERATED_HEADER)
        self.assertIn("HOST_ONLY_TEST", probe.GENERATED_HEADER)

    def test_older_gcc_keeps_compat_include(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            (source / "kernel/t2ddebugd/include").mkdir(parents=True)
            args = probe.make_args(source, Path(temp) / "out", "arm-linux-gnueabi-", 3, 6, "zImage")
            self.assertIn("-j3", args)
            self.assertTrue(any("-I" in flag and "t2ddebugd" in flag for flag in args))
            self.assertFalse(any("Wno-error" in flag for flag in args))

    def test_modern_gcc_compat_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            args = probe.make_args(Path(temp), Path(temp) / "out", "arm-linux-gnueabi-", 1, 13, "olddefconfig")
            self.assertIn("KCFLAGS=-Wno-error=attributes", args)

    def test_experimental_profile_is_opt_in(self):
        self.assertEqual(probe.PROFILES, {"tizen", "selinux-lab", "android-bootlab", "binder-lab"})
        with self.assertRaisesRegex(ValueError, "Unbekanntes"):
            probe.execute(Path("."), Path("/some/unique/output"), "arm-", 1,
                          60, preflight_only=True, profile="unsafe")

    def test_selinux_overlay_only_changes_staged_config(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            baseline = (
                "# CONFIG_SECURITY_SELINUX is not set\n"
                "CONFIG_SECURITY_SMACK=y\nCONFIG_SECURITY_SFD=y\n"
                "CONFIG_DEFAULT_SECURITY_SMACK=y\nCONFIG_DEFAULT_SECURITY=\"smack\"\n"
            )
            (output / ".config").write_text(baseline)
            (output / "STAGE_MANIFEST.json").write_text(json.dumps({
                "status": "STAGED_NOT_KCONFIG_VALIDATED", "vendor_security_untouched": True
            }))
            probe.apply_selinux_lab_overlay(output)
            patched = (output / ".config").read_text()
            self.assertIn("CONFIG_SECURITY_SELINUX=y", patched)
            self.assertIn("CONFIG_DEFAULT_SECURITY_SELINUX=y", patched)
            self.assertIn("# CONFIG_DEFAULT_SECURITY_SMACK is not set", patched)
            self.assertIn("CONFIG_SECURITY_SMACK=y", patched)
            self.assertIn("CONFIG_SECURITY_SFD=y", patched)
            report = json.loads((output / "STAGE_MANIFEST.json").read_text())
            self.assertFalse(report["vendor_security_untouched"])
            self.assertEqual(report["profile"], "selinux-lab")

    def test_selinux_profile_does_not_accept_smack_as_default(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            all_features = probe.RESEARCH_FEATURES | probe.RESEARCH_SECURITY
            (output / ".config").write_text("\n".join(
                f"CONFIG_{name}={value}" if value != "n" else f"# CONFIG_{name} is not set"
                for name, value in all_features.items()
            ) + "\n")
            self.assertTrue(probe.verify_config(output, "tizen")["verified"])
            other = probe.verify_config(output, "selinux-lab")
            self.assertFalse(other["verified"])
            self.assertIn("SECURITY_SELINUX", other["differences"])

    def test_android_bootlab_requires_initrd_and_kernel_config(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / ".config").write_text(
                "CONFIG_SECURITY_SMACK=y\nCONFIG_SECURITY_SFD=y\n"
                "# CONFIG_SECURITY_SELINUX is not set\n"
                "# CONFIG_BLK_DEV_INITRD is not set\n"
                "# CONFIG_IKCONFIG is not set\n"
                "# CONFIG_IKCONFIG_PROC is not set\n")
            (output / "STAGE_MANIFEST.json").write_text(json.dumps({
                "status": "STAGED_NOT_KCONFIG_VALIDATED", "vendor_security_untouched": True
            }))
            probe.apply_research_overlay(output, "android-bootlab")
            staged = (output / ".config").read_text()
            for symbol in ("BLK_DEV_INITRD", "IKCONFIG", "IKCONFIG_PROC"):
                self.assertIn(f"CONFIG_{symbol}=y", staged)
            manifest = json.loads((output / "STAGE_MANIFEST.json").read_text())
            self.assertEqual(manifest["profile"], "android-bootlab")
            self.assertEqual(manifest["experimental_config_changes"]["IKCONFIG"], "y")

    def test_binder_lab_keeps_all_android_boot_features(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / ".config").write_text(
                "CONFIG_SECURITY_SMACK=y\nCONFIG_SECURITY_SFD=y\n"
                "# CONFIG_SECURITY_SELINUX is not set\n"
                "# CONFIG_BLK_DEV_INITRD is not set\n"
                "# CONFIG_IKCONFIG is not set\n"
                "# CONFIG_IKCONFIG_PROC is not set\n")
            (output / "STAGE_MANIFEST.json").write_text(json.dumps({
                "vendor_security_untouched": True
            }))
            probe.apply_research_overlay(output, "binder-lab")
            staged = (output / ".config").read_text()
            for symbol in ("SECURITY_SELINUX", "BLK_DEV_INITRD", "IKCONFIG", "IKCONFIG_PROC"):
                self.assertIn(f"CONFIG_{symbol}=y", staged)
            self.assertEqual(json.loads((output / "STAGE_MANIFEST.json").read_text())["profile"], "binder-lab")


if __name__ == "__main__":
    unittest.main()
