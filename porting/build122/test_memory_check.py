import unittest

from memory_check import HERE, load_check, memory_report, read_json


class MemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = memory_report()

    def test_reference_report(self):
        self.assertEqual(self.report, read_json(HERE / "memory-report.json"))
        self.assertEqual(self.report["hardware"], "NO-GO")
        self.assertEqual(self.report["address_translation"], "UNKNOWN")
        self.assertEqual(self.report["payload_delta_bytes"], 4989504)
        self.assertIsNone(self.report["uncompressed_image_bytes"])

    def test_exact_bank_ranges(self):
        expected = {
            "2g": [["0x40000000", "0x54000000"], ["0xa2000000", "0xdfc00000"],
                   ["0xe4000000", "0xed880000"]],
            "1g5": [["0x40000000", "0x47800000"], ["0x4f000000", "0x5fc00000"],
                    ["0xa2000000", "0xc0000000"], ["0xca000000", "0xd9a40000"]],
        }
        for name, profile in self.report["profiles"].items():
            with self.subTest(profile=name):
                self.assertEqual(profile["ram_banks"], expected[name])
                capacity = profile["decompressed_image_capacity"]
                self.assertEqual(capacity["required_bytes"], 34070520)
                self.assertTrue(capacity["fits_in_largest_static_gap"])
                self.assertEqual(capacity["runtime_placement"], "UNKNOWN")
                self.assertEqual(sum(row["offline_dtb_no_map"] for row in profile["reservations"]), 2)
                for key in ("stock_header_address_comparison", "generated_zimage_address_comparison"):
                    check = profile[key]
                    self.assertTrue(check["entry_at_zimage_start"])
                    self.assertFalse(check["inside_one_advertised_bank"])
                    self.assertFalse(check["inside_static_free_ram"])

    def test_half_open_boundaries_and_reserved_holes(self):
        for name, profile in self.report["profiles"].items():
            with self.subTest(profile=name):
                start, end = (int(value, 16) for value in profile["free_intervals_static_only"][0])
                def check(low, high):
                    return load_check({"load": low, "entry": low, "payload_bytes": high - low}, profile)
                self.assertTrue(check(start, end)["inside_static_free_ram"])
                self.assertFalse(check(start, end + 1)["inside_static_free_ram"])
                reserved = check(0xa2000000, 0xa2000004)
                self.assertTrue(reserved["inside_one_advertised_bank"])
                self.assertFalse(reserved["inside_static_free_ram"])
                self.assertEqual(reserved["overlapping_reservations"], ["cma@0xB0000000"])


if __name__ == "__main__":
    unittest.main()
