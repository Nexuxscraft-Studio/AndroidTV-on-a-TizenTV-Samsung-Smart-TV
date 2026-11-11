#!/usr/bin/env python3
"""Synthetic unit tests for build061 bootchain_forensics.

Uses ONLY artificial byte sequences. No Samsung firmware is read or shipped.
"""
import struct
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bootchain_forensics as bf  # noqa: E402


class TestHelpers(unittest.TestCase):
    def test_entropy_bounds(self):
        self.assertEqual(bf.entropy(b""), 0.0)
        self.assertAlmostEqual(bf.entropy(b"\x00" * 100), 0.0)
        # uniform over 256 symbols -> ~8 bits
        self.assertGreater(bf.entropy(bytes(range(256)) * 4), 7.9)

    def test_find_str(self):
        data = b"....Linux version 9.9\x00tail"
        hit = bf.find_str(data, b"Linux version")
        self.assertIsNotNone(hit)
        self.assertTrue(hit["text"].startswith("Linux version 9.9"))
        self.assertIsNone(bf.find_str(data, b"absent-token"))

    def test_ascii_strings_minlen(self):
        data = b"\x01ab\x02longenough\x03"
        got = [s for _, s in bf.ascii_strings(data, minlen=4)]
        self.assertIn(b"longenough", got)
        self.assertNotIn(b"ab", got)


class TestUimage(unittest.TestCase):
    def _fake_uimage(self, arch, comp):
        # 64-byte big-endian U-Boot header + tiny payload
        hdr = bytearray(64)
        struct.pack_into(">I", hdr, 0, bf.UBOOT_MAGIC)
        struct.pack_into(">I", hdr, 0x0C, 16)          # size
        struct.pack_into(">I", hdr, 0x10, 0x80008000)  # load
        struct.pack_into(">I", hdr, 0x14, 0x80008000)  # entry
        hdr[0x1C] = 5          # Linux
        hdr[0x1D] = arch
        hdr[0x1E] = 2          # kernel
        hdr[0x1F] = comp
        hdr[0x20:0x2C] = b"Linux-4.1.10"
        payload = b"\x00" * 0x24 + b"\x1a\x90\x29\xe2" + b"xx"  # HYP eor marker at 0x24
        payload += b"Linux version 4.1.10 (test)\x00"
        return bytes(hdr) + payload

    def test_arm32_kernel(self):
        rec = bf.analyze_uimage(self._fake_uimage(arch=2, comp=0))
        self.assertTrue(rec["valid_uboot"])
        self.assertEqual(rec["arch_name"], "ARM (AArch32)")
        self.assertEqual(rec["compression"], 0)
        self.assertTrue(rec["payload_entry_is_hyp_aware_stext"])
        self.assertIn("4.1.10", rec["linux_version"])

    def test_arm64_arch_id(self):
        rec = bf.analyze_uimage(self._fake_uimage(arch=22, comp=0))
        self.assertEqual(rec["arch_name"], "ARM64")

    def test_rejects_non_uboot(self):
        self.assertFalse(bf.analyze_uimage(b"not a uimage")["valid_uboot"])


class TestSign(unittest.TestCase):
    def test_salted_detected(self):
        blob = b"\x00" * 8 + b"Salted__" + b"ABCDEFGH" + b"\xaa" * 32 + b"\x10" * 16
        rec = bf.analyze_sign(blob)
        self.assertTrue(rec["is_openssl_enc"])
        self.assertEqual(rec["salt"], b"ABCDEFGH".hex())
        self.assertTrue(rec["pkcs7_pad_tail"])


class TestDtb(unittest.TestCase):
    def test_fdt_header(self):
        blob = bytearray(128)
        struct.pack_into(">I", blob, 0, bf.FDT_MAGIC)
        struct.pack_into(">I", blob, 4, 120)   # totalsize
        struct.pack_into(">I", blob, 20, 17)   # version
        blob += b"samsung,dtv\x00"
        rec = bf.analyze_dtb(bytes(blob))
        self.assertTrue(rec["valid_fdt"])
        self.assertEqual(rec["version"], 17)

    def test_rejects_non_fdt(self):
        self.assertFalse(bf.analyze_dtb(b"nope")["valid_fdt"])


if __name__ == "__main__":
    unittest.main()
