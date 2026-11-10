"""Guard against relaxing source-only release safety for kernel porting."""

from pathlib import Path
import tempfile
import unittest

import q60t_release_audit as release_audit


ROOT = Path(__file__).resolve().parents[1]


class SourceOnlyAllowlistTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, relative: str, content: bytes = b"// compile-only GPL source\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_existing_kernel_porting_files_have_exact_path_permission(self):
        """CI should not reject these known, reviewed nonstandard extensions."""
        for file in (ROOT / "porting").rglob("*"):
            if not file.is_file():
                continue
            relative = file.relative_to(ROOT).as_posix()
            if file.suffix in release_audit.ALLOWED_SUFFIXES:
                continue
            self.assertIn(relative, release_audit.ALLOWED_EXPLICIT_SOURCES)

    def test_all_reviewed_kernel_sources_pass_audit(self):
        for name in sorted(release_audit.ALLOWED_PORTING_SOURCES):
            self.put(name)
        result = release_audit.audit(self.root)
        self.assertEqual(result["status"], "PASS", result["problems"])
        self.assertEqual(result["files_checked"],
                         len(release_audit.ALLOWED_PORTING_SOURCES))

    def test_unknown_vendor_source_and_binary_stay_blocked(self):
        for path in (
            "porting/build058/integration/drm/unreviewed.c",
            "porting/build058/integration/drm/new-vendor.h",
            "porting/build058/new-driver.sh",
            "porting/build058/unreviewed-board.dts",
            "porting/build058/cpu/kernel/UnknownMakefile",
            "vendor/proprietary_driver.c",
            "firmware/Q60T.dtb",
            "firmware/sdp_gpu.ko",
            "firmware/upgrade.msd",
        ):
            with self.subTest(path=path):
                self.put(path)
                result = release_audit.audit(self.root)
                self.assertEqual(result["status"], "FAIL")
                self.assertIn(f"Disallowed file type: {path}", result["problems"])
                (self.root / path).unlink()

    def test_even_reviewed_source_cannot_hide_binary_or_secret(self):
        path = "porting/build058/integration/drm/sdp_drm_util.c"
        self.put(path, b"ok\x00binary")
        self.assertIn(f"Binary data inside source: {path}",
                      release_audit.audit(self.root)["problems"])
        self.put(path, b"-----BEGIN " + b"PRIVATE KEY-----\n")
        self.assertIn(f"Potential secret marker: {path}",
                      release_audit.audit(self.root)["problems"])

    def test_allowlisted_symlink_is_still_rejected(self):
        target = self.put("README.md", b"safe\n")
        link = self.root / "porting/build058/integration/drm/sdp_drm_util.h"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        self.assertIn("Symlink file: porting/build058/integration/drm/sdp_drm_util.h",
                      release_audit.audit(self.root)["problems"])


if __name__ == "__main__":
    unittest.main()
