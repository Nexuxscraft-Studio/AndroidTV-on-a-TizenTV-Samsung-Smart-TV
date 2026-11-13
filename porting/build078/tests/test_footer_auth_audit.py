"""Build078 tests using only synthetic bytes (no proprietary firmware)."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "footer_auth_audit.py"
spec = importlib.util.spec_from_file_location("build078_footer_auth_audit", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fake_component(name: str, zeros: bool = False, valid_pad: bool = True) -> bytes:
    body = bytearray(144)
    if name == "uImage":
        body[:4] = bytes.fromhex("27051956")
        struct.pack_into(">I", body, 12, 80)
    window = bytes(256) if zeros else bytes(range(256))
    return bytes(body) + window + (bytes([16]) * 16 if valid_pad else bytes([0]) * 16)


class FooterAuthAuditTests(unittest.TestCase):
    def test_zeroed_sign_window_is_not_validated_signature(self):
        result = mod.inspect_bytes("sign.bin", fake_component("sign.bin", zeros=True))
        self.assertEqual(result["window256_zero_bytes"], 256)
        self.assertEqual(result["window256_entropy_bits_per_byte"], 0.0)
        self.assertTrue(result["terminal_16_bytes_equal_0x10"])
        self.assertFalse(result["crypto_signature_verified"])

    def test_uniform_256_values_has_entropy_8(self):
        result = mod.inspect_bytes("secos.bin", fake_component("secos.bin"))
        self.assertEqual(result["window256_entropy_bits_per_byte"], 8.0)

    def test_uimage_declared_payload_end(self):
        result = mod.inspect_bytes("uImage", fake_component("uImage"))
        self.assertTrue(result["legacy_uimage_header_detected"])
        self.assertTrue(result["272_byte_end_window_begins_at_declared_payload_end"])
        self.assertEqual(result["declared_payload_end"], "0x90")

    def test_trailing_suffix_must_match(self):
        result = mod.inspect_bytes("ddr.init", fake_component("ddr.init", valid_pad=False))
        self.assertFalse(result["terminal_16_bytes_equal_0x10"])

    def test_too_small_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "too small"):
            mod.inspect_bytes("sign.bin", b"empty")

    def test_directory_uses_reference_fingerprints(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            synthetic_expected = {}
            for name in mod.EXPECTED:
                blob = fake_component(name, zeros=name == "sign.bin")
                (directory / name).write_bytes(blob)
                synthetic_expected[name] = (len(blob), hashlib.sha256(blob[-272:-16]).hexdigest())
            with patch.dict(mod.EXPECTED, synthetic_expected, clear=True):
                result = mod.audit_directory(directory)
            self.assertEqual(result["status"], "SIX_COMPONENT_FOOTER_MATCH")
            self.assertEqual(len(result["components"]), 6)
            self.assertFalse(result["conclusions"]["tv_signature_verification_identified"])

    def test_missing_reference_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = mod.audit_directory(Path(tmp))
            self.assertEqual(result["status"], "INCOMPLETE_OR_DIFFERENT_REFERENCE")
            self.assertEqual(len(result["components"]), 6)


if __name__ == "__main__":
    unittest.main()
