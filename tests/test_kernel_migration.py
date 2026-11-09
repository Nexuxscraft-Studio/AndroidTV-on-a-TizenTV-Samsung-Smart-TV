"""Build-022 offline migration triage regression and fail-closed tests."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import q60t_kernel_migration as migration


HASH = "a" * 64


def sample_hardware(armv8=True):
    cpu = ["arm,cortex-a57", "arm,armv8"] if armv8 else ["arm,cortex-a9"]
    trees = []
    for index in (0, 1):
        trees.append({
            "dtb_sha256": f"{index + 1:064x}",
            "summary": {
                "model": "Samsung DTV based on Nike-L SoC",
                "memory_profile_label": "2 GiB" if index == 0 else "1.5 GiB",
                "hardware_categories": {
                    "cpu": [{"path": f"/cpus/cpu@{n}", "compatible": cpu} for n in range(4)],
                    "gpu": [{"compatible": ["arm,mali-midgard"]}],
                },
            },
        })
    return {
        "type": "offline_hardware_device_tree_report",
        "dtb_bundle_sha256": HASH,
        "device_trees_found": len(trees),
        "trees": trees,
        "writes_to_tv": False,
    }


def sample_source():
    return {
        "type": "q60t_offline_compatible_source_matrix",
        "dtb_bundle_sha256": HASH,
        "firmware_device_tree_count": 2,
        "source_kernel_version": "4.1.10",
        "source_matches_firmware_2743_0": True,  # untrusted claim must not enable a gate
        "compatibility_references": {
            "gpu": [{"compatible": "arm,mali-midgard",
                     "classification": "MEDIA_CODE_REFERENCE"}],
            "board": [{"compatible": "samsung,sdp-nikel",
                       "classification": "KERNEL_CODE_REFERENCE"}],
        },
    }


class Build022AuditTests(unittest.TestCase):
    def test_armv8_is_reference_evidence_not_device_proof(self):
        report = migration.analyze(sample_hardware(), "b" * 64,
                                   sample_source(), "c" * 64, HASH)
        self.assertTrue(report["cpu_architecture"]["reference_dts_indicate_armv8"])
        self.assertEqual(report["cpu_architecture"]["profiles"][0]["cpu_nodes"], 4)
        self.assertFalse(report["cpu_architecture"]["arm64_hardware_on_exact_tv_verified"])
        self.assertFalse(report["cpu_architecture"]["bootloader_64bit_entry_verified"])
        self.assertFalse(report["safe_to_flash"])
        self.assertFalse(report["flash_authorized"])
        self.assertFalse(report["lineageos_built"])
        self.assertFalse(report["hardware_test_performed"])
        self.assertEqual(report["evidence"]["stock_kernel_source_version_candidate"], "4.1.10")
        self.assertFalse(report["evidence"]["source_matches_firmware_2743_0"])
        self.assertFalse(report["evidence"]["raw_reference_dtb_bytes_verified_in_this_run"])

    def test_code_reference_not_modern_driver(self):
        report = migration.analyze(sample_hardware(), HASH, sample_source(), HASH, HASH)
        gpu = report["device_driver_evidence"]["gpu"][0]
        self.assertEqual(gpu["source_reference_classification"], "MEDIA_CODE_REFERENCE")
        self.assertFalse(gpu["driver_ported_to_modern_kernel"])
        self.assertFalse(gpu["android_hal_verified"])
        self.assertEqual(report["future_gki_reference_only"]["examples_by_android_version"]["16"],
                         "android16-6.12")
        self.assertFalse(report["future_gki_reference_only"]["kernel_selected_for_lineageos"])

    def test_missing_armv8_is_not_upgraded_by_some_other_profile(self):
        hardware = sample_hardware()
        hardware["trees"][1]["summary"]["hardware_categories"]["cpu"][0]["compatible"] = [
            "arm,cortex-a9"]
        report = migration.analyze(hardware, HASH, expected_dtb_sha256=HASH)
        self.assertFalse(report["cpu_architecture"]["reference_dts_indicate_armv8"])
        self.assertIn("armv8_not_confirmed_in_all_reference_cpu_nodes", report["blocking_gates"])

    def test_mismatched_dtb_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            migration.analyze(sample_hardware(), HASH, expected_dtb_sha256="b" * 64)

    def test_source_dtb_mismatch_is_rejected(self):
        source = sample_source()
        source["dtb_bundle_sha256"] = "d" * 64
        with self.assertRaisesRegex(ValueError, "different DTB"):
            migration.analyze(sample_hardware(), HASH, source, HASH, HASH)

    def test_report_tree_count_mismatch_is_rejected(self):
        data = sample_hardware()
        data["device_trees_found"] = 7
        with self.assertRaisesRegex(ValueError, "count inconsistent"):
            migration.analyze(data, HASH, expected_dtb_sha256=HASH)

    def test_without_source_matrix_never_claims_driver_port(self):
        report = migration.analyze(sample_hardware(), HASH, expected_dtb_sha256=HASH)
        self.assertIsNone(report["evidence"]["source_report_sha256"])
        self.assertEqual(report["device_driver_evidence"]["gpu"][0]
                         ["source_reference_classification"], "UNVERIFIED")
        self.assertFalse(report["checks"]["modern_soc_display_and_gpu_drivers_ported"])

    def test_cli_creates_report_but_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            hardware = base / "hardware.json"
            source = base / "source.json"
            output = base / "analysis.json"
            hardware.write_text(json.dumps(sample_hardware()))
            source.write_text(json.dumps(sample_source()))
            args = ["--hardware-report", str(hardware),
                    "--source-compat-report", str(source),
                    "--expected-dtb-sha256", HASH, "--output", str(output)]
            self.assertEqual(migration.main(args), 0)
            data = json.loads(output.read_text())
            self.assertTrue(data["status"].startswith("HOST_ONLY"))
            self.assertFalse(data["tv_accessed"])
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(migration.main(args), 2)

    def test_symlink_report_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            orig, link = root / "a.json", root / "link.json"
            orig.write_text(json.dumps(sample_hardware()))
            link.symlink_to(orig)
            with self.assertRaisesRegex(ValueError, "linked"):
                migration.read_json_report(link)

    def test_raw_dtb_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "reference.dtb"
            fake.write_bytes(b"not a Samsung DTB")
            with self.assertRaisesRegex(ValueError, "Raw reference DTB SHA-256 mismatch"):
                migration.verify_raw_reference_dtb(fake, HASH, sample_hardware())


if __name__ == "__main__":
    unittest.main()
