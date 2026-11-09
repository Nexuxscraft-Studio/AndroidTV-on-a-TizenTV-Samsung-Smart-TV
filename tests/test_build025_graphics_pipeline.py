"""Build 025: Samsung graphics pipeline static evidence regression checks."""

import json
from pathlib import Path
import tempfile
import unittest

import q60t_build025_graphics_pipeline as graphics


def sample_evidence():
    categories = {}
    source_groups = {}
    for category, compatible, role in graphics.DEVICES:
        status = "disabled" if role == "hdmi_cec" else "okay"
        categories.setdefault(category, []).append({"path": "/soc/" + role,
                                                     "compatible": [compatible],
                                                     "dt_status": status})
        source_groups.setdefault(category, []).append({
            "compatible": compatible, "classification": "MEDIA_CODE_REFERENCE",
            "kernel_references": [], "media_references": ["sdp_gpu_nike/gpu_driver.c"]})
    hardware = {"dtb_bundle_sha256": graphics.DTB_BUNDLE_SHA256,
                "device_trees_found": 2,
                "trees": [{"offset_bytes": offset, "summary": {"hardware_categories": categories}}
                          for offset in (0, 86016)]}
    source = {"type": "q60t_offline_compatible_source_matrix",
              "dtb_bundle_sha256": graphics.DTB_BUNDLE_SHA256,
              "source_kernel_version": "4.1.10",
              "source_matches_firmware_2743_0": False,
              "compatibility_references": source_groups}
    return hardware, source


class GraphicsPipelineTests(unittest.TestCase):
    def test_all_stages_still_blocked_with_two_reference_profiles(self):
        hardware, source = sample_evidence()
        report = graphics.pipeline_report(hardware, source)
        self.assertEqual(report["status"], "HOST_ONLY_GRAPHICS_AND_HAL_UNVERIFIED")
        self.assertEqual(len(report["hardware_rows"]), len(graphics.DEVICES))
        self.assertFalse(report["android_display_rendered"])
        self.assertFalse(report["flash_authorized"])
        self.assertTrue(all(not x["verified"] for x in report["android_display_stages"]))
        self.assertTrue(all(x["present_in_both_reference_profiles"] for x in report["hardware_rows"]))
        cec = [x for x in report["hardware_rows"] if x["role"] == "hdmi_cec"][0]
        self.assertTrue(cec["disabled_in_reference"])
        self.assertFalse(cec["runtime_verified"])

    def test_incomplete_second_reference_does_not_get_assumed_present(self):
        hardware, source = sample_evidence()
        hardware["trees"][1]["summary"]["hardware_categories"]["gpu"] = []
        report = graphics.pipeline_report(hardware, source)
        self.assertFalse(report["hardware_rows"][0]["present_in_both_reference_profiles"])
        self.assertFalse(report["hardware_rows"][0]["runtime_verified"])

    def test_firmware_mismatch_is_rejected(self):
        hardware, source = sample_evidence()
        hardware["dtb_bundle_sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "approved reference"):
            graphics.validate_reports(hardware, source)
        hardware, source = sample_evidence()
        source["source_matches_firmware_2743_0"] = True
        with self.assertRaisesRegex(ValueError, "not proven"):
            graphics.validate_reports(hardware, source)

    def test_api_symbol_references_are_not_abi_or_porting_proof(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sdp_gpu_nike").mkdir()
            (root / "sdp_gpu_nike/gpu_driver.c").write_text(
                "ion_alloc(); dma_buf_attach(); pm_runtime_get_sync();\n"
            )
            findings = graphics.inspect_source_interfaces(root, ["sdp_gpu_nike/gpu_driver.c"])
            self.assertEqual(findings["files_read"], 1)
            self.assertEqual(findings["interfaces"]["legacy_ion"], ["sdp_gpu_nike/gpu_driver.c"])
            self.assertEqual(findings["interfaces"]["dma_buf"], ["sdp_gpu_nike/gpu_driver.c"])
            self.assertEqual(findings["interfaces"]["clocks_power"], ["sdp_gpu_nike/gpu_driver.c"])
            self.assertIn("NO_BUILD_OR_ABI_VERIFICATION", findings["status"])
            hardware, source = sample_evidence()
            report = graphics.pipeline_report(hardware, source, root)
            self.assertFalse(report["hal_sources_built"])

    def test_path_traversal_and_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "Unsafe source"):
                graphics.safe_source(root, "../outside.c")
            (root / "alias.c").symlink_to("missing.c")
            with self.assertRaisesRegex(ValueError, "symlink"):
                graphics.safe_source(root, "alias.c")

    def test_output_is_create_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            hardware, source = sample_evidence()
            (root / "hardware.json").write_text(json.dumps(hardware))
            (root / "source.json").write_text(json.dumps(source))
            args = ["--hardware-report", str(root / "hardware.json"),
                    "--legacy-source-report", str(root / "source.json"),
                    "--output", str(root / "report.json")]
            self.assertEqual(graphics.main(args), 0)
            self.assertEqual(graphics.main(args), 2)

    def test_project_reports_when_full_git_checkout_available(self):
        base = Path(__file__).resolve().parent.parent / "reports"
        hardware = base / "hardware_2743.0_build004_final.json"
        source = base / "source_compat_build011.json"
        if not hardware.is_file() or not source.is_file():
            self.skipTest("Samsung reference reports absent from isolated test workspace")
        actual = graphics.pipeline_report(graphics.read_report(hardware), graphics.read_report(source))
        self.assertTrue(all(not row["runtime_verified"] for row in actual["hardware_rows"]))
        self.assertTrue(any(x["role"] == "gpu_render" and x["present_in_both_reference_profiles"]
                            for x in actual["hardware_rows"]))
        self.assertFalse(actual["flash_authorized"])


if __name__ == "__main__":
    unittest.main()
