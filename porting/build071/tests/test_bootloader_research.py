"""Build071 synthetic-only regression tests; never touch a physical TV."""
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootloader_research as b  # noqa: E402


class ReadOnlyBootloaderResearchTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.evidence = self.root / "gates.json"
        self.evidence.write_text(json.dumps({name: False for name in b.GATES}))

    def test_all_gates_blocked(self):
        report = b.research(self.evidence)
        self.assertEqual(report["boot_safety"]["status"], "BLOCKED")
        self.assertEqual(len(report["boot_safety"]["unverified"]), 8)
        self.assertFalse(report["flash_authorized"])
        self.assertEqual(report["bootloader_identity"], "UNVERIFIED")

    def test_uimage_header_does_not_prove_real_bootloader(self):
        payload = b"synthetic kernel" * 8
        header = bytearray(struct.pack(
            ">7I4B32s", 0x27051956, 0, 0, len(payload),
            0x80008000, 0x80008000, zlib.crc32(payload), 5, 2, 2, 0,
            b"TEST" + b"\x00" * 28))
        struct.pack_into(">I", header, 4, zlib.crc32(header))
        image = self.root / "uImage"
        image.write_bytes(header + payload)
        report = b.research(self.evidence, uimage=image)
        self.assertTrue(report["uimage"]["valid"])
        self.assertTrue(report["uimage"]["payload_crc_valid"])
        self.assertEqual(report["bootloader_identity"], "UNVERIFIED")
        self.assertFalse(report["flash_authorized"])

    def test_uart_banner_candidate_is_not_identity_proof(self):
        capture = self.root / "serial.txt"
        capture.write_text(
            "U-Boot 2024.01\nSERIAL=SECRET123\nStarting kernel ...\n"
            "Linux version 6.6.162\nU-Boot 2025.01 kernel debug line\n")
        report = b.research(self.evidence, uart_log=capture)
        self.assertEqual(report["uart"]["banner_counts"]["U-Boot"], 1)
        self.assertTrue(report["uart"]["kernel_boundary_seen"])
        self.assertEqual(report["bootloader_identity"], "UNVERIFIED")
        self.assertNotIn("SECRET123", json.dumps(report))

    def test_kernel_only_log_is_not_bootloader_evidence(self):
        capture = self.root / "serial.txt"
        capture.write_text("Linux version 6.6.162\nU-Boot 2025.01 kernel log\n")
        report = b.research(self.evidence, uart_log=capture)
        self.assertEqual(report["uart"]["bootloader_candidates"], [])

    def test_symlinks_rejected(self):
        capture = self.root / "serial.txt"
        capture.write_text("U-Boot 2024.01")
        link = self.root / "link"
        link.symlink_to(capture)
        with self.assertRaises(ValueError):
            b.research(self.evidence, uart_log=link)

    def test_string_true_does_not_pass_safety(self):
        self.evidence.write_text(json.dumps({name: "true" for name in b.GATES}))
        report = b.research(self.evidence)
        self.assertEqual(report["boot_safety"]["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
