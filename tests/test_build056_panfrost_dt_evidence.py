"""Build 056 host-only evidence verification; optional binary integration tests."""

from pathlib import Path
import tempfile
import unittest

from q60t_build056_panfrost_dt_evidence import get_pinned_file, inspect, strings, words


PROJECT = Path(__file__).resolve().parents[1]
DTB = Path("/tmp/q60t-original-dtb-20261110.bin")
GPU = Path("/tmp/q60t-original-sdp_gpu-20261110.ko")
DRM = Path("/tmp/q60t-original-sdp_drm-20261110.ko")
HAS_VENDOR_FIXTURE = all(path.is_file() for path in (DTB, GPU, DRM))


class Build056PanfrostDeviceTreeTests(unittest.TestCase):
    @unittest.skipUnless(HAS_VENDOR_FIXTURE, "Original full-OS firmware bytes not supplied")
    def test_real_samsung_firmware_evidence(self):
        report = inspect(DTB, GPU, DRM)
        self.assertEqual(report["gpu_model_string_in_original_module"], "Mali-G51")
        self.assertEqual(report["original_gpu_module_version"],
                         "r11p0-01rel0 (UK version 11.6)")
        self.assertFalse(report["safe_to_flash"])
        self.assertFalse(report["real_tv_access_performed"])
        self.assertFalse(report["original_archive_sha256_verified"])
        self.assertEqual({item["label"] for item in report["variants"]},
                         {"nikel-2G", "nikel-1.5G"})
        for variant in report["variants"]:
            self.assertEqual(variant["cpu_count"], 4)
            self.assertEqual(variant["cpu_compatible"], "arm,cortex-a57")
            self.assertEqual(variant["gpu"]["register_base"], "0x00500000")
            self.assertEqual(variant["gpu"]["register_bytes"], 0x4000)
            self.assertEqual(variant["gpu"]["interrupt_specifiers_raw"],
                             [[0, 114, 0], [0, 113, 0], [0, 112, 0]])
            self.assertFalse(variant["gpu"]["has_clocks_property"])

    def test_read_only_dts_is_disabled_and_not_real_board(self):
        dts = (PROJECT / "porting/build056/panfrost-sdp-nikel-disabled.dts").read_text()
        self.assertIn('status = "disabled";', dts)
        self.assertIn('compatible = "arm,mali-bifrost";', dts)
        self.assertIn('compatible = "nover,offline-unbootable-gpu-reference";', dts)
        self.assertIn('reg = <0x00500000 0x00004000>;', dts)
        self.assertNotIn('status = "okay";', dts)

    def test_hash_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "untrusted.ko"
            path.write_bytes(b"not the original Samsung GPU module")
            with self.assertRaisesRegex(ValueError, "Hash mismatch"):
                get_pinned_file(path, "gpu")

    def test_raw_fdt_property_helpers(self):
        self.assertEqual(words(bytes.fromhex("000000720000007100000070")), [114, 113, 112])
        self.assertEqual(strings(b"JOB\0MMU\0GPU\0"), ["JOB", "MMU", "GPU"])
        with self.assertRaisesRegex(ValueError, "Non-cell-aligned"):
            words(b"bad")


if __name__ == "__main__":
    unittest.main()
