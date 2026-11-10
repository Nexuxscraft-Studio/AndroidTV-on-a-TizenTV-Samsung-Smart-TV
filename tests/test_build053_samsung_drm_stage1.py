"""Reproducible, host-only checks for Build 053 partial Samsung source port."""

from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import q60t_build053_samsung_drm_stage1 as stage
from q60t_build050_stage1_source_fixes import fix_drm_safety


ROOT = Path(__file__).resolve().parent.parent
ORIGINAL = ROOT / "porting/build053/patches/0001-original-sdp-drm-gem-linux66-partial.patch"
AFTER_STAGE1 = ROOT / "porting/build053/patches/0002-after-build050-stage1-sdp-drm-gem-linux66-partial.patch"
MEDIA = ROOT / ".build050_vendor/srcarchives/tztv-media-nike.tgz"


class TestBuild053SourceMigration(unittest.TestCase):
    def test_patches_are_distinct_and_target_real_samsung_sources(self):
        for path in (ORIGINAL, AFTER_STAGE1):
            body = path.read_text()
            self.assertEqual(body.count("--- a/"), 2)
            self.assertIn("--- a/" + stage.DRM, body)
            self.assertIn("--- a/" + stage.GEM, body)
            self.assertIn("drm_dev_alloc(", body)
            self.assertIn("drm_dev_register(", body)
            self.assertIn("drm_gem_object_get(", body)
            self.assertIn("drm_gem_object_put(", body)
            self.assertIn('nover,compile-only-sdp-drm', body)
            self.assertNotIn("/dev/mmc", body)
            self.assertNotIn("fastboot flash", body)
        self.assertNotEqual(ORIGINAL.read_bytes(), AFTER_STAGE1.read_bytes())

    def test_source_drift_and_invalid_base_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Source drift"):
            stage.migrate_drm("not a Samsung DRM driver")
        with self.assertRaisesRegex(ValueError, "Source drift"):
            stage.migrate_gem("not Samsung GEM source")
        with self.assertRaisesRegex(ValueError, "Unknown patch base"):
            stage.make_patch("", "", base="not-an-option")

    def test_archive_identity_is_mandatory(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "fake.tgz"
            fake.write_bytes(b"not trusted Samsung media")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                stage.generate(fake)

    def test_no_clobber_on_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.patch"
            argv = ["--media-tgz", "unused", "--output", str(path)]
            with patch.object(stage, "generate", return_value="test-only\n"):
                self.assertEqual(stage.main(argv), 0)
                self.assertEqual(stage.main(argv), 2)
            self.assertEqual(path.read_text(), "test-only\n")

    def test_real_archives_both_patch_bases_apply_and_match_if_present(self):
        if not MEDIA.is_file():
            self.skipTest("Samsung original source archives are not in the public repo")
        with tarfile.open(MEDIA, "r:gz") as archive:
            originals = {}
            for member in (stage.DRM, stage.GEM):
                stream = archive.extractfile(member)
                self.assertIsNotNone(stream)
                originals[member] = stream.read().decode("utf-8")

        target_drm = stage.migrate_drm(fix_drm_safety(originals[stage.DRM]))
        target_gem = stage.migrate_gem(originals[stage.GEM])

        for base, patch_file in (("original", ORIGINAL), ("stage1", AFTER_STAGE1)):
            with self.subTest(base=base), tempfile.TemporaryDirectory() as directory:
                working = Path(directory)
                for member in (stage.DRM, stage.GEM):
                    output = working / member
                    output.parent.mkdir(parents=True, exist_ok=True)
                    body = originals[member]
                    if member == stage.DRM and base == "stage1":
                        body = fix_drm_safety(body)
                    output.write_text(body)

                regenerated = stage.generate(MEDIA, base=base)
                self.assertEqual(patch_file.read_text(), regenerated)
                for args in (("--dry-run", "--batch", "-p1", "-i", str(patch_file)),
                             ("--batch", "-p1", "-i", str(patch_file))):
                    result = subprocess.run(["patch", *args], cwd=directory,
                                            text=True, capture_output=True, check=False)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

                self.assertEqual((working / stage.DRM).read_text(), target_drm)
                self.assertEqual((working / stage.GEM).read_text(), target_gem)
                self.assertIn("return -ENODEV;", target_drm)
                self.assertNotIn('compatible = "samsung,sdp-drm"', target_drm)
                self.assertNotIn("drm_platform_init(", target_drm)
                self.assertNotIn("drm_gem_object_unreference", target_gem)
                self.assertNotIn("drm_gem_object_reference(", target_gem)


if __name__ == "__main__":
    unittest.main()
