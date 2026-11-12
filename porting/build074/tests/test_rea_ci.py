"""Synthetic checks for fail-closed Q60T REA evidence sanitization.

No REA, firmware, Samsung TV, privileged operations or network needed.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rea_ci


def example_evidence(sha: str, crc=True, payload=7040960):
    return {
        "operation": "inspect_artifact",
        "subject": {"digest": {"sha256": sha}},
        "normalized_result": {
            "substeps": [{
                "status": "completed",
                "evidence": {"normalized_result": {"occurrences": [{
                    "format_metadata": {
                        "kind": "uimage",
                        "arch_name": "arm", "type_name": "kernel",
                        "crc_verified": crc,
                        "name": "Linux-4.1.10",
                        "timestamp": 1782982023,
                        "payload_size": payload,
                        "load_address": 2147516416,
                        "entry_point": 2147516416,
                        "header_crc32": 3665780938,
                        "data_crc32": 2093582832,
                        "compression_name": "none",
                    }
                }]}}
            }]
        }
    }


class Q60TREAOfflineTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 64

    def test_samsung_sample_272_extra_bytes(self):
        r = rea_ci.sanitized_report(
            example_evidence(self.sha), "uimage", self.sha, 7041296
        )
        self.assertEqual(r["uimage"]["extra_bytes_after_payload"], 272)
        self.assertEqual(r["uimage"]["load_address"], "0x80008000")
        self.assertEqual(r["uimage"]["entry_point"], "0x80008000")
        self.assertEqual(r["uimage"]["kernel_header_name"], "Linux-4.1.10")
        self.assertTrue(r["uimage"]["crc_verified"])
        self.assertFalse(r["ram_boot_demonstrated"])
        self.assertFalse(r["firmware_modification"])
        self.assertEqual(r["uimage"]["extra_bytes_meaning"][:7], "UNKNOWN")

    def test_crc_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "CRC"):
            rea_ci.sanitized_report(
                example_evidence(self.sha, crc=False), "uimage",
                self.sha, 7041296,
            )

    def test_sha_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "identity"):
            rea_ci.sanitized_report(
                example_evidence(self.sha), "uimage", "b" * 64, 7041296
            )

    def test_invalid_payload_length_rejected(self):
        with self.assertRaisesRegex(ValueError, "beyond"):
            rea_ci.sanitized_report(
                example_evidence(self.sha, payload=7041296),
                "uimage", self.sha, 7041296,
            )

    def test_unrecognized_operation_rejected(self):
        evidence = example_evidence(self.sha)
        evidence["operation"] = "execute"
        with self.assertRaisesRegex(ValueError, "operation"):
            rea_ci.sanitized_report(evidence, "uimage", self.sha, 7041296)

    def test_dtb_report_never_exports_raw_properties(self):
        evidence = {
            "operation": "inspect_devicetree",
            "subject": {"digest": {"sha256": self.sha}},
            "normalized_result": {
                "nodes": [{"properties": [{"device-secret": "example-private-text"}]}],
            },
        }
        r = rea_ci.sanitized_report(evidence, "dtb", self.sha, 96)
        self.assertNotIn("example-private-text", str(r))
        self.assertFalse(r["devicetree"]["node_properties_in_report"])

    def test_source_validation_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "original.uImage"
            source.write_bytes(rea_ci.UIMAGE_MAGIC + bytes(60))
            path, size, sha = rea_ci.validated_source(source, root, "uimage")
            self.assertEqual(path, source)
            self.assertEqual(size, 64)
            self.assertEqual(sha, hashlib.sha256(source.read_bytes()).hexdigest())
            alias = root / "alias.uImage"
            try:
                alias.symlink_to(source)
            except OSError:
                self.skipTest("Platform does not support symlinks")
            with self.assertRaisesRegex(ValueError, "Symlinks"):
                rea_ci.validated_source(alias, root, "uimage")

    def test_misidentified_dtb_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "wrong.dtb"
            source.write_bytes(rea_ci.UIMAGE_MAGIC + bytes(60))
            with self.assertRaisesRegex(ValueError, "magic"):
                rea_ci.validated_source(source, root, "dtb")


if __name__ == "__main__":
    unittest.main()
