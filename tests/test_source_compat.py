"""Synthetic tests: no Samsung firmware, secrets or original binaries."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import q60t_source_compat as subject  # noqa: E402


class SourceCompatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "kernel" / "drivers").mkdir(parents=True)
        (self.root / "media").mkdir()

    def test_finds_exact_references_without_prefix_false_positive(self):
        (self.root / "kernel/drivers/foo.c").write_text(
            'static const char *compat = "samsung,sdp-nikel";\n'
            'static const char *not_foo = "samsung,sdp-mac-x";\n')
        found = subject.scan_source(self.root / "kernel", {
            "samsung,sdp-nikel", "samsung,sdp-mac"})
        self.assertEqual(found["matches"]["samsung,sdp-nikel"], ["drivers/foo.c"])
        self.assertEqual(found["matches"]["samsung,sdp-mac"], [])

    def test_mali_source_only_in_dts_is_not_driver_match(self):
        (self.root / "kernel/drivers/test.dts").write_text(
            'compatible = "arm,mali-midgard";\n')
        found = subject.scan_source(self.root / "kernel", {"arm,mali-midgard"})
        self.assertEqual(subject._classification(
            found["matches"]["arm,mali-midgard"], []), "DTS_DECLARATION_ONLY")

    def test_no_symlink_escape_scanned(self):
        outside = self.root / "external.c"
        outside.write_text('"samsung,sdp-nikel"\n')
        (self.root / "kernel/drivers/evil.c").symlink_to(outside)
        found = subject.scan_source(self.root / "kernel", {"samsung,sdp-nikel"})
        self.assertEqual(found["matches"]["samsung,sdp-nikel"], [])
        self.assertEqual(found["symlinks_skipped"], 1)

    def test_categorized_source_matrix_has_no_flash_success_claim(self):
        (self.root / "kernel/drivers/nike.c").write_text('"samsung,sdp-nikel"')
        (self.root / "media/nike.c").write_text('"samsung,sdp-video"')
        hardware = {"dtb_bundle_sha256": "a" * 64, "device_trees_found": 1,
                    "trees": [{"summary": {
                        "root_compatible": ["samsung,sdp-nikel"],
                        "hardware_categories": {"video": [
                            {"compatible": ["samsung,sdp-video"]}]}}}]}
        report = subject.comparison(hardware, self.root / "kernel", self.root / "media")
        self.assertEqual(report["classification_counts"]["KERNEL_CODE_REFERENCE"], 1)
        self.assertEqual(report["classification_counts"]["MEDIA_CODE_REFERENCE"], 1)
        self.assertFalse(report["flash_authorized"])
        self.assertFalse(report["source_matches_firmware_2743_0"])

    def test_malformed_or_excessive_identifiers_ignored_or_rejected(self):
        hardware = {"trees": [{"summary": {
            "root_compatible": ["samsung,sdp-nikel", "bad key\nPRIVATE"]}}]}
        self.assertEqual(subject.selected_compatibles(hardware)["board"],
                         ["samsung,sdp-nikel"])


if __name__ == "__main__":
    unittest.main()
