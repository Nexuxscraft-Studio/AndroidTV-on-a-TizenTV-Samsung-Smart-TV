"""Build077 offline synthetic tests. No proprietary input or TV needed."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "seret_deep_audit.py"
spec = importlib.util.spec_from_file_location("build077_seret_deep_audit", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixture_bytes():
    data = bytearray(mod.base.EXPECTED_SIZE)
    for offset, word in mod.base.EXPECTED_WORDS.items():
        struct.pack_into("<I", data, offset, word)
    for offset, word in mod.EXPECTED_INSTRUCTIONS.items():
        struct.pack_into("<I", data, offset, word)
    for offset, raw in mod.base.EXPECTED_STRINGS.items():
        data[offset: offset + len(raw)] = raw
    return bytes(data)


class SeretDeepAuditTests(unittest.TestCase):
    def test_arm_bl_to_embedded_zimage(self):
        edge = mod.decode_arm_branch(0xEB001E40, 0x6F8)
        self.assertEqual((edge["kind"], edge["to"]), ("BL", "0x8000"))

    def test_arm_negative_branch_displacement(self):
        edge = mod.decode_arm_branch(0xEAFFFFFD, 0x100)
        self.assertEqual((edge["kind"], edge["to"]), ("B", "0xfc"))

    def test_non_branch_word_is_ignored(self):
        self.assertIsNone(mod.decode_arm_branch(0xE1A00000, 0x100))

    def test_synthetic_control_flow_evidence(self):
        blob = fixture_bytes()
        report = mod.analyze_bytes(blob, expected_sha256=hashlib.sha256(blob).hexdigest())
        self.assertEqual(report["status"], "OFFLINE_STATIC_CONTROL_FLOW_CORROBORATED")
        self.assertEqual(report["relative_literal_location"], "0x7b0")
        self.assertEqual(report["computed_header_pointer"], "0x1a0cd8")
        self.assertEqual(report["container_type_word"], "0x2020")
        self.assertEqual(report["embedded_zimage_call_site"], "0x6f8")
        self.assertFalse(report["safe_to_flash"])

    def test_wrong_instruction_fails_closed(self):
        blob = bytearray(fixture_bytes())
        blob[mod.MOVW_AT] ^= 0x1
        data = bytes(blob)
        with self.assertRaisesRegex(ValueError, "A32 instruction mismatch"):
            mod.analyze_bytes(data, expected_sha256=hashlib.sha256(data).hexdigest())

    def test_default_reference_hash_fails_for_synthetic(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            mod.analyze_bytes(fixture_bytes())

    def test_byte_sample_entropy(self):
        self.assertEqual(mod.shannon_entropy(b"\x00" * 10), 0.0)
        self.assertEqual(mod.shannon_entropy(bytes(range(256))), 8.0)


if __name__ == "__main__":
    unittest.main()
