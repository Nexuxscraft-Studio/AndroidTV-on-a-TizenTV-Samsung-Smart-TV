import hashlib
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
import zlib

from legacy_uimage import HEADER, MAGIC, parse, placement, stock_header, wrap


def legacy(payload=b"test", trailer=b""):
    header = HEADER.pack(MAGIC, 0, 0, len(payload), 0x1000, 0x1000,
                         zlib.crc32(payload), 5, 2, 2, 0, b"fixture")
    return header[:4] + struct.pack(">I", zlib.crc32(header)) + header[8:] + payload + trailer


class LegacyImageTests(unittest.TestCase):
    def test_requires_both_crcs_and_complete_payload(self):
        valid = legacy()
        self.assertEqual(parse(valid)[1], b"test")
        for broken in (valid[:10], valid[:20] + b"x" + valid[21:],
                       valid[:-1], valid[:-1] + b"x"):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                parse(broken)

    def test_stock_reference_pinned_and_read_only_with_vendor_trailer(self):
        blob = legacy(trailer=b"vendor")
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "stock"
            path.write_bytes(blob)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                stock_header(path, "0" * 64)
            self.assertEqual(stock_header(path, hashlib.sha256(blob).hexdigest())["trailing_bytes"], 6)
            self.assertEqual(path.read_bytes(), blob)
        with self.assertRaisesRegex(ValueError, "trailer"):
            parse(blob)

    def test_static_range_requires_single_free_span(self):
        header, _ = parse(legacy())
        self.assertTrue(placement(header, [("0x1000", "0x1004")])["inside_static_free_ram"])
        self.assertFalse(placement(header, [("0x1000", "0x1002"), ("0x1003", "0x2000")])
                         ["inside_static_free_ram"])
        self.assertFalse(placement({**header, "entry": 0x1004}, [])["entry_in_payload"])
        self.assertFalse(placement({**header, "load": 0xffffffff}, [])["within_arm32"])

    @unittest.skipUnless(shutil.which("mkimage"), "requires mkimage")
    def test_mkimage_produces_identical_wrappers(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            payload = bytes(36) + bytes.fromhex("18286f01")
            stock, _ = parse(legacy())
            for label in ("a", "b"):
                source = root / f"zImage-{label}"
                source.write_bytes(payload)
                wrap(source, root / f"uImage-{label}", stock)
            self.assertEqual((root / "uImage-a").read_bytes(), (root / "uImage-b").read_bytes())


if __name__ == "__main__":
    unittest.main()
