"""Guard tests for Build 057 clock/reset source reconstruction."""

from pathlib import Path
import tempfile
import unittest

from q60t_build057_gpu_power_dependencies import (
    extract_power_sequences, inspect, macro_value, verify_original_call_order,
)


PROJECT = Path(__file__).resolve().parents[1]
MEDIA = PROJECT / ".build050_vendor/srcarchives/tztv-media-nike.tgz"
DTB = Path("/tmp/q60t-original-dtb-20261110.bin")
GPU = Path("/tmp/q60t-original-sdp_gpu-20261110.ko")
DRM = Path("/tmp/q60t-original-sdp_drm-20261110.ko")
HAS_ALL_FIXTURES = MEDIA.is_file() and all(p.is_file() for p in (DTB, GPU, DRM))


class Build057OfflinePowerTests(unittest.TestCase):
    @unittest.skipUnless(HAS_ALL_FIXTURES, "Pinned Samsung OSS/firmware artifacts absent")
    def test_power_sequence_nikel_bit_positions_and_order(self):
        report = inspect(MEDIA, DTB, GPU, DRM)
        self.assertEqual(report["status"], "ORIGINAL_POWER_SEQUENCE_CROSSCHECKED_OFFLINE")
        self.assertEqual(report["firmware_variants_checked"], ["nikel-2G", "nikel-1.5G"])
        sequence = report["power_sequence"]
        on = sequence["on"]
        self.assertEqual([(x["control"], x["bit"], x["written_bit_value"]) for x in on], [
            ("GPU_CLK_MASK", 12, 1), ("GPU_BUSIF_SW_RESET", 24, 1),
            ("GPU_CORE_SW_RESET", 28, 1), ("GPU_POWER_REQ_IDLE", 0, 0),
        ])
        off = sequence["off"]
        self.assertEqual(off[1]["action"], "wait_until_idle")
        self.assertFalse(off[1]["has_timeout"])
        self.assertIn("logical AND", off[1]["operator_in_original"])
        self.assertEqual(off[2]["register"], off[3]["register"])
        self.assertEqual(off[2]["mask"], "0x01000000")
        self.assertEqual(off[3]["mask"], "0x10000000")
        self.assertEqual(report["clock_controller"], {"base": "0x00f50000", "size": 0x3000})
        self.assertFalse(report["hardware_access_performed"])
        self.assertFalse(report["safe_to_flash"])
        self.assertFalse(report["device_tree_binding_validated"])

    def test_samsung_power_code_missing_raises_error(self):
        with self.assertRaisesRegex(ValueError, "power-control function missing"):
            extract_power_sequences("", "", {})

    def test_wrong_macro_mask_refused(self):
        with self.assertRaisesRegex(ValueError, "Missing Samsung register"):
            macro_value("", "SDP_MASK_GPU_CLK_MASK")

    def test_original_kbase_order_must_be_present(self):
        with self.assertRaisesRegex(ValueError, "suspend/resume order changed"):
            verify_original_call_order("kbase_pm_resume(kbdev);")

    def test_compile_only_gpu_dts_remains_disabled(self):
        dts = (PROJECT / "porting/build056/panfrost-sdp-nikel-disabled.dts").read_text()
        self.assertIn('status = "disabled";', dts)
        self.assertNotIn('status = "okay";', dts)


if __name__ == "__main__":
    unittest.main()
