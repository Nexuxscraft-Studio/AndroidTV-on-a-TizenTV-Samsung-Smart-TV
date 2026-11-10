"""Host-only Build 050 tests: synthetic fixtures plus real repo baseline if available."""

import json
from pathlib import Path
import tempfile
import unittest

import q60t_build050_hardware_evidence as audit


DRIVERS = {
    "gpu": ("gpu", "arm,mali-midgard"),
    "display_drm": ("display", "samsung,sdp-drm"),
    "display_panel": ("display", "samsung,sdp1202-panel"),
    "display_frc": ("display", "samsung,sdp-frc-l"),
    "hdmi": ("display", "samsung,sdp-hdmi"),
    "video_decoder": ("video", "samsung,sdp-mfc"),
    "audio": ("audio", "samsung,sdp-mc-audio"),
    "input_ir": ("input", "samsung,sdp-mc-irb"),
    "storage": ("storage", "samsung,sdp-mmc"),
}


def fixtures():
    matrix = {}
    nodes = {}
    for category, compatible in DRIVERS.values():
        matrix.setdefault(category, []).append({
            "compatible": compatible, "classification": "MEDIA_CODE_REFERENCE",
            "kernel_references": [], "media_references": ["sdp/example.c"],
        })
        nodes.setdefault(category, []).append({"compatible": [compatible], "dt_status": "okay"})
    nodes["cpu"] = [{"compatible": ["arm,cortex-a57", "arm,armv8"]} for _ in range(4)]
    summary = {"root_compatible": ["samsung,sdp-nikel"], "hardware_categories": nodes,
               "memory_profile_label": "reference label", "memory_reg": {"sum_advertised_mib": 123},
               "bootargs_safe_subset": ["ro"]}
    hardware = {"type": "offline_hardware_device_tree_report",
                "dtb_bundle_sha256": audit.DTB_SHA256, "device_trees_found": 2,
                "trees": [{"offset_bytes": x, "dtb_sha256": "f" * 64, "summary": summary}
                          for x in (0, 86016)]}
    source = {"dtb_bundle_sha256": audit.DTB_SHA256,
              "source_kernel_version": "4.1.10", "compatibility_references": matrix}
    components = {"files": [{"name": "uImage", "sha256": audit.UIMAGE_SHA256,
                             "uimage": {"valid": True, "arch_id": 2,
                                        "name": "Linux-4.1.10", "header_crc_valid": True,
                                        "payload_crc_valid": True, "load_address": "0x80008000",
                                        "entry_address": "0x80008000"}}]}
    components["files"].extend({"name": name, "sha256": "b" * 64}
                               for name in ("sign.bin", "secos.bin", "seret.bin"))
    kernel = {"uimage_sha256": audit.UIMAGE_SHA256, "version_from_banner": "4.1.10",
              "security_symbols_found": ["SfdUepVerifyExecutableBinary"]}
    graphics = {"source_fdt_bundle_sha256": audit.DTB_SHA256,
                "source_kernel_uimage_sha256": audit.UIMAGE_SHA256}
    safety = {"status": "BLOCKED",
              "gates": [{"name": f"g{i}", "verified": False} for i in range(8)]}
    android_gap = {"kernel_version": "4.1.10", "defconfig_reference": "Nike.M-Tizen_release_defconfig",
                   "essential_sample": [{"symbol": "CONFIG_ANDROID_BINDER_IPC", "actual": "y"}],
                   "supporting_features": [{"symbol": "CONFIG_BPF_SYSCALL", "actual": "n"}]}
    return hardware, source, components, kernel, graphics, safety, android_gap


class Build050Tests(unittest.TestCase):
    def test_real_legacy_reports_if_available(self):
        root = Path(__file__).resolve().parent.parent
        if not (root / audit.DEFAULT_PATHS["hardware"]).exists():
            self.skipTest("Full historical report tree unavailable in isolated workspace")
        datasets = [audit.load_report(root / audit.DEFAULT_PATHS[n])[0]
                    for n in audit.DEFAULT_PATHS]
        result = audit.build_evidence(*datasets)
        self.assertEqual(result["cpu"]["reference_dtb_cortex_a57_count"], 4)
        self.assertEqual(result["boot"]["legacy_image"]["arch_id"], 2)
        self.assertEqual(result["peripherals"]["gpu"]["reference_profiles_containing_node"], 2)
        self.assertFalse(result["safe_to_flash"])

    def test_reference_can_be_inventoried_without_claiming_hardware_success(self):
        result = audit.build_evidence(*fixtures())
        self.assertEqual(result["soc"]["dt_compatible"], "samsung,sdp-nikel")
        self.assertEqual(result["cpu"]["running_stock_kernel_image_arch"],
                         "ARM32 (U-Boot IH_ARCH_ARM=2)")
        self.assertEqual(result["android_kernel"]["sample_nike_m_defconfig_symbols"]["CONFIG_BPF_SYSCALL"], "n")
        self.assertEqual(len(result["safety_gates"]), 8)
        self.assertTrue(all(not gate["verified"] for gate in result["safety_gates"]))
        self.assertFalse(result["soc"]["actual_target_board_identified"])

    def test_mixed_firmware_and_recovery_false_positive_are_refused(self):
        datasets = list(fixtures())
        datasets[1]["dtb_bundle_sha256"] = "x" * 64
        with self.assertRaisesRegex(ValueError, "provenance"):
            audit.build_evidence(*datasets)
        datasets = list(fixtures())
        datasets[5]["gates"][0]["verified"] = True
        with self.assertRaisesRegex(ValueError, "gates"):
            audit.build_evidence(*datasets)

    def test_report_file_is_bounded_and_no_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for (name, _), data in zip(audit.DEFAULT_PATHS.items(), fixtures()):
                (base / (name + ".json")).write_text(json.dumps(data))
            args = []
            for name in audit.DEFAULT_PATHS:
                args += ["--" + name.replace("_", "-"), str(base / (name + ".json"))]
            args += ["--output", str(base / "out.json")]
            self.assertEqual(audit.main(args), 0)
            self.assertEqual(audit.main(args), 2)
            out = json.loads((base / "out.json").read_text())
            self.assertFalse(out["safe_to_flash"])
            self.assertEqual(len(out["source_report_sha256"]), 7)

    def test_wrong_or_fake_zip_is_refused_without_unpack(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "20_DTV_NikeL.zip"
            archive.write_bytes(b"not actual vendor source")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                audit.archive_hash(archive)


if __name__ == "__main__":
    unittest.main()
