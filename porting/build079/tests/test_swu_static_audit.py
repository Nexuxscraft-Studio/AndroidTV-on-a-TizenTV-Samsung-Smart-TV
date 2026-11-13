"""Build 079 synthetic unit tests: no original firmware or TV access."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / "swu_static_audit.py"
spec = importlib.util.spec_from_file_location("build079_swu_static_audit", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fake_elf(marker=b"RSAValidation"):
    data = bytearray(128)
    data[:4] = b"\x7fELF"
    data[4] = 1
    data[5] = 1
    struct.pack_into("<H", data, 18, 40)
    data.extend(marker)
    data.extend(b"\x00UpgradeGraph13AESEncryption\x00")
    return bytes(data)


class StaticAuditTests(unittest.TestCase):
    def test_arm32_and_static_symbol_detection(self):
        x = mod.inspect_blob(fake_elf())
        self.assertTrue(x["machine_arm32"])
        self.assertEqual(x["elf_class"], "ELF32")
        self.assertTrue(x["string_markers"]["RSAValidation"]["present"])
        self.assertTrue(x["string_markers"]["AESEncryption"]["present"])
        self.assertFalse(x["string_markers"]["EVP_PKEY_verify"]["present"])

    def test_binary_rejection(self):
        with self.assertRaisesRegex(ValueError, "Not an ELF"):
            mod.inspect_blob(b"not elf")

    def test_unit_parser_selects_dependencies_and_skips_comments(self):
        x = mod.parse_unit(
            "[Unit]\nAfter=swu-verifier-tv.service deviced.service\n"
            "Requisite=swu-verifier-tv.service deviced.service\n"
            "# Requires=ignored\n[Service]\n"
            "ExecStart=/usr/bin/SWUCoreTV --idle-timeout 30\n"
            "Environment=THIS_MUST_NOT_BE_INCLUDED=yes\n"
        )
        self.assertEqual(x["Unit"]["After"], ["swu-verifier-tv.service deviced.service"])
        self.assertEqual(x["Unit"]["Requisite"], ["swu-verifier-tv.service deviced.service"])
        self.assertEqual(x["Service"]["ExecStart"], ["/usr/bin/SWUCoreTV --idle-timeout 30"])
        self.assertNotIn("Environment", x["Service"])

    def test_readelf_dynamic_dependencies_and_symbols_are_only_metadata(self):
        dynamic = SimpleNamespace(returncode=0, stdout="0x1 (NEEDED) Shared library: [libSWUProductionConfig.so]\n")
        symbols = SimpleNamespace(returncode=0, stdout=(
            "Symbol table '.dynsym' contains 1 entries:\n"
            "  Num:    Value  Size Type Bind Vis Ndx Name\n"
            "  123: 00000000 0 OBJECT GLOBAL DEFAULT UND _ZTSUpgradeGraph13RSAValidation\n"
        ))
        with patch.object(mod.subprocess, "run", side_effect=[dynamic, symbols]):
            x = mod.readelf_metadata(Path("/synthetic/elf"))
        self.assertEqual(x["needed_libraries"], ["libSWUProductionConfig.so"])
        self.assertEqual(x["interesting_dynsyms"][0]["type"], "OBJECT")
        self.assertTrue(x["interesting_dynsyms"][0]["name"].endswith("RSAValidation"))

    def test_report_uses_only_local_files_and_preserves_unverified_gates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / mod.ROOT_REL_BINARY
            path.parent.mkdir(parents=True)
            path.write_bytes(fake_elf())
            unit = root / mod.UNITS_DIR / "swu-verifier-tv.service"
            unit.parent.mkdir(parents=True)
            unit.write_text(
                "[Service]\nType=dbus\nBusName=org.tizen.tv.swu.verifier.TV\n"
                "ExecStart=/usr/bin/SWUVerifierTV\n"
            )
            with patch.object(mod, "readelf_metadata", return_value={"tool_available": False}):
                x = mod.analyze(root)
        self.assertEqual(x["status"], "STATIC_ELF_AND_SYSTEMD_METADATA_ONLY")
        self.assertTrue(x["systemd_units"]["swu-verifier-tv.service"]["exists"])
        self.assertFalse(x["rsa_validation_confirmed"])
        self.assertFalse(x["safe_to_flash"])

    def test_missing_binary_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Missing binary"):
                mod.analyze(Path(temp))


if __name__ == "__main__":
    unittest.main()
