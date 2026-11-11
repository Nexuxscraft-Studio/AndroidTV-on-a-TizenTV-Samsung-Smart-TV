#!/usr/bin/env python3
"""Synthetic unit tests for build063 driver_coverage. Artificial data only."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import driver_coverage as dc  # noqa: E402


class TestParseConfig(unittest.TestCase):
    def test_parses_config_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.config"
            p.write_text("# comment\nCONFIG_DRM_SDP=m\nCONFIG_DRM=y\nnoise\n")
            got = dc.parse_config(p)
            self.assertEqual(got["CONFIG_DRM_SDP"], "m")
            self.assertEqual(got["CONFIG_DRM"], "y")
            self.assertNotIn("noise", got)

    def test_missing_file(self):
        self.assertEqual(dc.parse_config(Path("/nope/x.config")), {})


class TestCoverage(unittest.TestCase):
    def test_real_tree_all_present(self):
        root = Path(__file__).resolve().parent.parent
        rep = dc.coverage(root)
        self.assertTrue(rep["all_scaffolds_present"], rep)
        self.assertEqual(
            rep["subsystems"]["display"]["config_symbols"].get("CONFIG_DRM_SDP"),
            "m")
        self.assertEqual(
            rep["subsystems"]["gpu"]["config_symbols"].get("CONFIG_DRM_PANFROST"),
            "m")

    def test_incomplete_detected(self):
        with tempfile.TemporaryDirectory() as d:
            rep = dc.coverage(Path(d))  # empty tree -> everything missing
            self.assertFalse(rep["all_scaffolds_present"])
            self.assertEqual(rep["subsystems"]["display"]["status"], "INCOMPLETE")

    def test_disclaimer_present(self):
        rep = dc.coverage(Path(__file__).resolve().parent.parent)
        self.assertIn("does NOT mean a driver", rep["disclaimer"])


if __name__ == "__main__":
    unittest.main()
