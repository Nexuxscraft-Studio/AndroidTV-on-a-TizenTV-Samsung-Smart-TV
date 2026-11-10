"""Build 058 offline, fail-closed Samsung Nike-L GPU provider checks."""

from pathlib import Path
import unittest

from q60t_build058_nikel_clkrst_contract import (
    ROOT, DTS, SOURCE, definition, inspect, verify_provider,
)


MEDIA = ROOT / ".build050_vendor/srcarchives/tztv-media-nike.tgz"
DTB = Path("/tmp/q60t-original-dtb-20261110.bin")
GPU = Path("/tmp/q60t-original-sdp_gpu-20261110.ko")
DRM = Path("/tmp/q60t-original-sdp_drm-20261110.ko")
HAS_FIXTURES = all(p.is_file() for p in (MEDIA, DTB, GPU, DRM))


class Build058ClockResetTests(unittest.TestCase):
    def setUp(self):
        self.code = SOURCE.read_text(encoding="utf-8")
        self.dts = DTS.read_text(encoding="utf-8")

    def test_provider_is_hard_blocked_and_dts_disabled(self):
        sequences = verify_provider(self.code, self.dts)
        self.assertEqual(4, len(sequences["on"]))
        self.assertEqual(5, len(sequences["off_with_rollback"]))
        self.assertIn("Build 058 compile-only; Nike-L hardware access blocked", self.code)

    def test_missing_guard_is_rejected(self):
        changed = self.code.replace("#define SDP_NIKEL_BUILD058_HARDWARE_DISABLED 1",
                                    "#define SDP_NIKEL_BUILD058_HARDWARE_DISABLED 0")
        with self.assertRaisesRegex(ValueError, "hard-disabled"):
            verify_provider(changed, self.dts)

    def test_dt_enablement_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not disabled"):
            verify_provider(self.code, self.dts.replace('status = "disabled";',
                                                        'status = "okay";'))

    def test_wrong_bit_mask_is_detected(self):
        wrong = self.code.replace("#define SDP_NIKEL_GPU_CORE_RESET        BIT(28)",
                                  "#define SDP_NIKEL_GPU_CORE_RESET        BIT(27)")
        self.assertEqual(1 << 27, definition(wrong, "SDP_NIKEL_GPU_CORE_RESET"))
        self.assertNotEqual(definition(self.code, "SDP_NIKEL_GPU_CORE_RESET"),
                            definition(wrong, "SDP_NIKEL_GPU_CORE_RESET"))

    def test_original_samsung_sequence_matched(self):
        if not HAS_FIXTURES:
            self.skipTest("Original Samsung source/firmware fixtures unavailable")
        report = inspect(MEDIA, DTB, GPU, DRM)
        self.assertEqual("PROTOTYPE_FAIL_CLOSED_OFFLINE", report["status"])
        self.assertEqual("0x00f507f8", report["registers_original_source_crosschecked"]
                         ["GPU_BUSIF_SW_RESET"]["address"])
        self.assertEqual("0x00f507f8", report["registers_original_source_crosschecked"]
                         ["GPU_CORE_SW_RESET"]["address"])
        self.assertTrue(report["hard_probe_block"])
        self.assertFalse(report["hardware_access_performed"])


if __name__ == "__main__":
    unittest.main()
