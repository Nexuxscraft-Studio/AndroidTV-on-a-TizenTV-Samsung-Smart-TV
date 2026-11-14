"""Exercise rejection paths without needing a second CI artifact."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "build095_audit", Path(__file__).resolve().parents[1] / "audit.py"
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class EvidenceTests(unittest.TestCase):
    def test_rejects_changed_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "evidence.zip"
            archive.write_bytes(b"untrusted replacement")
            with self.assertRaisesRegex(ValueError, "archive SHA-256 mismatch"):
                audit.audit(archive)

    def test_rejects_incomplete_module_inventory(self):
        with self.assertRaisesRegex(ValueError, "ELF evidence inventory"):
            audit.verify_modules({
                "kernel.config": b"",
                "kernel.log": b"",
                "cpu.log": b"",
                "elf.txt": b"vmlinux\nELF Header:\n",
            })

    def test_rejects_changed_dtb(self):
        files = {name: b"sample" for name in audit.DTBS}
        files["dtb.sha256"] = "\n".join(
            f"{audit.digest(data)}  {name}" for name, data in files.items()
        ).encode()
        files[audit.BOARDS[0]] = b"changed"
        with self.assertRaisesRegex(ValueError, "DTB checksum inventory"):
            audit.verify_dt(files)
