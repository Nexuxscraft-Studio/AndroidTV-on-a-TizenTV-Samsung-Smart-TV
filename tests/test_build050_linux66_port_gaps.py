"""Synthetic, hardware-free tests of Linux 6.6 source portability gates."""

import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import q60t_build050_linux66_port_gaps as gaps


def fake_contents():
    files = {name: [] for name in gaps.SOURCE_MAP}
    for _, source, literal, _, _ in gaps.RULES:
        files[source].append(literal)
    files["panel"].extend([".clock = 150660,", ".hdisplay = 1920,",
                           ".htotal = 1920,", ".vdisplay = 1080,",
                           ".vtotal = 1080,", ".vrefresh = 60,"])
    return {name: "\n".join(lines) for name, lines in files.items()}


class TestLinux66Gaps(unittest.TestCase):
    def test_rules_identify_the_legacy_api_without_claiming_a_port(self):
        result = gaps.analyze(fake_contents())
        self.assertEqual(result["status"], "SOURCE_API_MIGRATION_REQUIRED")
        self.assertEqual(len(result["checks"]), len(gaps.RULES))
        self.assertTrue(all(x["detected"] for x in result["checks"]))
        self.assertFalse(result["safe_to_flash"])
        self.assertFalse(result["linux_6_6_driver_compiled"])
        self.assertFalse(result["arm64_compile_test_passed"])
        self.assertFalse(result["target_panel_verified"])

    def test_dummy_panel_timings_are_rejected(self):
        result = gaps.analyze(fake_contents())
        mode = result["dummy_panel_mode"]
        self.assertEqual((mode["hdisplay"], mode["vdisplay"]), (1920, 1080))
        self.assertTrue(mode["timing_has_no_horizontal_or_vertical_blanking"])
        self.assertGreater(mode["frequency_from_clock_and_totals_hz"], 72)
        self.assertFalse(mode["is_usable_q60t_panel_timing"])

    def test_missing_original_marker_refuses_misleading_report(self):
        sources = fake_contents()
        sources["drm"] = sources["drm"].replace("drm_platform_init(", "unexpected_api(")
        with self.assertRaisesRegex(ValueError, "legacy_drm_bus_init"):
            gaps.analyze(sources)

    def test_nonregular_member_refused_without_extracting(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "test.tgz"
            with tarfile.open(target, "w:gz") as archive:
                link = tarfile.TarInfo("vendor/unsafe.c")
                link.type = tarfile.SYMTYPE
                link.linkname = "/etc/passwd"
                archive.addfile(link)
            with self.assertRaisesRegex(ValueError, "non-regular"):
                gaps.read_original_text(target, "vendor/unsafe.c")

    def test_source_member_sha256_is_returned(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "test.tgz"
            data = b"Linux 4.1.10\n"
            with tarfile.open(target, "w:gz") as archive:
                info = tarfile.TarInfo("vendor/file.c")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            contents, digest = gaps.read_original_text(target, "vendor/file.c")
            self.assertEqual(contents, data.decode())
            self.assertEqual(len(digest), 64)

    def test_hash_pinning_refuses_unverified_kernel(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "not_vendor.tgz"
            target.write_bytes(b"fake")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                gaps.inspect_archives(target, target)

    def test_cli_refuses_to_overwrite_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.json"
            fixture = gaps.analyze(fake_contents())
            argv = ["--kernel-tgz", "not-used", "--media-tgz", "not-used", "--output", str(output)]
            with patch.object(gaps, "inspect_archives", return_value=fixture):
                self.assertEqual(gaps.main(argv), 0)
                self.assertEqual(gaps.main(argv), 2)
            stored = json.loads(output.read_text())
            self.assertFalse(stored["safe_to_flash"])


if __name__ == "__main__":
    unittest.main()
