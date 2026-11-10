"""Tests for the read-only Build 055 Samsung GPU evidence audit."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from q60t_build055_gpu_panfrost_evidence import branch_defines, inspect, REGISTER_NAMES


ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / ".build050_vendor/srcarchives/tztv-media-nike.tgz"


class Build055PanfrostEvidenceTests(unittest.TestCase):
    def test_original_gpu_evidence_pins_vendor_nike_l_branch(self):
        report = inspect(MEDIA)
        gpu = report["samsung_source"]
        self.assertEqual(report["status"], "SOURCE_REFERENCE_VALIDATED_BOARD_UNVERIFIED")
        self.assertEqual(report["upstream_references"]["model_marker"], "GPU_MODEL(g51, 0x7000)")
        self.assertEqual(gpu["nike_l_registers"]["SDP_REG_GPU_CLK_MASK"], "0x00f5088c")
        self.assertEqual(gpu["nike_m_registers"]["SDP_REG_GPU_CLK_MASK"], "0x00f50898")
        self.assertEqual(gpu["nike_l_registers"]["SDP_REG_GPU_BUSIF_SW_RESET"], "0x00f507f8")
        self.assertEqual(set(gpu["nike_l_registers"]), set(REGISTER_NAMES))
        self.assertTrue(gpu["markers"]["vendor_gpu_clock_reset_writes"])

    def test_not_hardware_verification(self):
        report = inspect(MEDIA)
        self.assertFalse(report["safe_to_flash"])
        self.assertFalse(report["hardware_access_performed"])
        self.assertFalse(report["tv_gpu_model_verified"])
        self.assertFalse(report["module_binary_supplied"])
        self.assertIsNone(report["target"]["gpu_id_read_from_this_tv"])

    def test_unpinned_archive_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            unknown = Path(directory) / "other-media.tgz"
            unknown.write_bytes(b"not a Samsung media archive")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                inspect(unknown)

    def test_missing_soc_branch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "SoC branch"):
            branch_defines("", "#ifdef CONFIG_SOC_CHIP_NIKEL", "#else")

    def test_offline_shell_syntax_and_missing_module(self):
        script = ROOT / "porting/build055/inspect-sdp-gpu-ko.sh"
        checked = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        missing = subprocess.run(["bash", str(script), "/no/such/sdp_gpu.ko"],
                                 capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
