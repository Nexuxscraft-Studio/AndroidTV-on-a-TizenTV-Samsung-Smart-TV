"""Host-side regression tests for Build 025: no TV, QEMU, or firmware needed."""

import json
from pathlib import Path
import tempfile
import unittest

import q60t_build025_kernel_gap as gap


def reference_report():
    matrix = {}
    for category, compatible, _ in gap.TARGETS:
        matrix.setdefault(category, []).append({
            "compatible": compatible,
            "classification": "MEDIA_CODE_REFERENCE",
            "kernel_references": [],
            "media_references": ["sdp_nike/example_driver.c"],
        })
    return {
        "type": "q60t_offline_compatible_source_matrix",
        "dtb_bundle_sha256": gap.EXPECTED_REFERENCE_DTB,
        "source_kernel_version": "4.1.10",
        "source_matches_firmware_2743_0": False,
        "compatibility_references": matrix,
    }


class Build025Tests(unittest.TestCase):
    def test_real_build011_report_when_full_repository_is_available(self):
        reference = Path(__file__).resolve().parent.parent / "reports/source_compat_build011.json"
        if not reference.is_file():
            self.skipTest("Repository baseline report not present in isolated test directory")
        report = gap.load_json(reference)
        found = gap.validate_legacy(report)
        self.assertIn(("cpu", "arm,cortex-a57"), found)
        self.assertIn(("gpu", "arm,mali-midgard"), found)
        result = gap.build_report(report, None, gap.inspect_hal_manifest(None))
        self.assertFalse(result["flash_authorized"])
        self.assertEqual(result["status"], "HARDWARE_BOOT_BLOCKED_HOST_ONLY")

    def test_complete_legacy_reference_remains_blocked(self):
        data = gap.build_report(reference_report(), None, gap.inspect_hal_manifest(None))
        self.assertEqual(data["status"], "HARDWARE_BOOT_BLOCKED_HOST_ONLY")
        self.assertFalse(data["flash_authorized"])
        self.assertFalse(data["aarch64_hardware_boot_proven"])
        self.assertFalse(data["recovery_proven"])
        self.assertEqual(len(data["subsystem_rows"]), len(gap.TARGETS))
        self.assertTrue(all(x["source_reference_status"] == "LINUX_6_6_NOT_SCANNED"
                            for x in data["subsystem_rows"]))

    def test_reference_hash_and_firmware_provenance_are_strict(self):
        report = reference_report()
        report["dtb_bundle_sha256"] = "bad"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            gap.validate_legacy(report)
        report = reference_report()
        report["source_matches_firmware_2743_0"] = True
        with self.assertRaisesRegex(ValueError, "exact firmware match"):
            gap.validate_legacy(report)

    def test_lite_modern_kernel_source_matrix_and_no_false_driver_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Makefile").write_text("VERSION = 6\nPATCHLEVEL = 6\nSUBLEVEL = 162\n")
            (root / "drivers/gpu").mkdir(parents=True)
            (root / "arch/arm64/boot/dts/sdp").mkdir(parents=True)
            (root / "drivers/gpu/sdp.c").write_text('static const char *test = "arm,mali-midgard";')
            (root / "arch/arm64/boot/dts/sdp/test.dts").write_text('compatible = "samsung,sdp-drm";')
            result = gap.source_literals(root, {name for _, name, _ in gap.TARGETS})
            self.assertEqual(result["kernel_version"], "6.6.162")
            report = gap.build_report(reference_report(), result, gap.inspect_hal_manifest(None))
            rows = {x["compatible"]: x for x in report["subsystem_rows"]}
            self.assertEqual(rows["arm,mali-midgard"]["source_reference_status"], "MODERN_CODE_LITERAL_ONLY")
            self.assertEqual(rows["samsung,sdp-drm"]["source_reference_status"], "MODERN_DTS_LITERAL_ONLY")
            self.assertEqual(rows["samsung,sdp-mfc"]["source_reference_status"], "NO_MODERN_LITERAL_REFERENCE")
            self.assertFalse(rows["arm,mali-midgard"]["driver_binds_on_q60t_verified"])
            self.assertFalse(report["flash_authorized"])

    def test_wrong_kernel_series_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Makefile").write_text("VERSION = 6\nPATCHLEVEL = 1\nSUBLEVEL = 99\n")
            with self.assertRaisesRegex(ValueError, "6.6.x"):
                gap.linux_version(root)

    def test_device_manifest_is_not_implementation_proof(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.xml"
            path.write_text('<manifest version="2.0" type="device">'
                            '<hal format="aidl"><name>android.hardware.graphics.composer3</name>'
                            '<fqname>IComposer/default</fqname></hal></manifest>')
            manifest = gap.inspect_hal_manifest(path)
            self.assertIn("android.hardware.graphics.composer3", manifest["declared"])
            self.assertFalse(manifest["services_running"])
            self.assertFalse(manifest["vintf_compatibility_verified"])
            path.write_text('<!DOCTYPE manifest [<!ENTITY dangerous SYSTEM "file:///etc/passwd">]>'
                            '<manifest type="device"/>')
            with self.assertRaisesRegex(ValueError, "DTD"):
                gap.inspect_hal_manifest(path)

    def test_invalid_and_oversized_json_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.json"
            path.write_text(json.dumps([1, 2, 3]))
            with self.assertRaisesRegex(ValueError, "object"):
                gap.load_json(path)
            path.write_bytes(b"x" * (gap.MAX_JSON + 1))
            with self.assertRaisesRegex(ValueError, "bounded JSON"):
                gap.load_json(path)

    def test_cli_never_overwrites_old_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "build011.json"
            output = Path(temp) / "build025.json"
            source.write_text(json.dumps(reference_report()))
            self.assertEqual(gap.main(["--legacy-report", str(source), "--output", str(output)]), 0)
            self.assertTrue(output.is_file())
            self.assertEqual(gap.main(["--legacy-report", str(source), "--output", str(output)]), 2)


if __name__ == "__main__":
    unittest.main()
