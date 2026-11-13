"""Build076 evidence-check tests; use synthetic bytes, not Samsung firmware."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest

SRC = Path(__file__).resolve().parents[1] / "seret_audit.py"
spec = importlib.util.spec_from_file_location("build076_seret_audit", SRC)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def synthetic_reference():
    data = bytearray(audit.EXPECTED_SIZE)
    for pos, word in audit.EXPECTED_WORDS.items():
        struct.pack_into("<I", data, pos, word)
    for pos, literal in audit.EXPECTED_STRINGS.items():
        data[pos:pos + len(literal)] = literal
    return bytes(data)


class AuditTests(unittest.TestCase):
    def test_synthetic_fixture_matches_exact_offsets(self):
        data = synthetic_reference()
        digest = hashlib.sha256(data).hexdigest()
        report = audit.audit_bytes(data, expected_sha256=digest)
        self.assertEqual(report["appended_header_offset"], "0x1a0cd8")
        self.assertEqual(report["trailing_data_size_bytes"], 1430328)
        self.assertTrue(report["pc_relative_pointer_matches_appended_header"])
        self.assertFalse(report["safe_to_flash"])

    def test_real_provenance_hash_must_match_by_default(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            audit.audit_bytes(synthetic_reference())

    def test_changed_header_is_rejected(self):
        data = bytearray(synthetic_reference())
        data[audit.EXPECTED_APPENDED] = 0x30
        data = bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        with self.assertRaisesRegex(ValueError, "Header/literal mismatch"):
            audit.audit_bytes(data, digest)

    def test_changed_fdt_string_is_rejected(self):
        data = bytearray(synthetic_reference())
        data[0x24E0] = 0x21
        data = bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        with self.assertRaisesRegex(ValueError, "String mismatch"):
            audit.audit_bytes(data, digest)

    def test_wrong_size_is_rejected(self):
        data = synthetic_reference()[:-1]
        with self.assertRaisesRegex(ValueError, "Unexpected reference size"):
            audit.audit_bytes(data, hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    unittest.main()
