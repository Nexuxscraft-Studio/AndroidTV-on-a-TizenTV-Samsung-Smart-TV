import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
