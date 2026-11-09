"""Synthetic, host-only tests: never run ARM kernels or access TVs."""

import gzip
from pathlib import Path
import stat
import struct
import tempfile
import unittest

import q60t_initramfs_lab as lab


def fake_arm_elf(*, machine=40, program_type=1):
    """Minimal synthetic ELF32 file, not executable machine code."""
    data = bytearray(84)
    data[:16] = b"\x7fELF\x01\x01\x01" + b"\x00" * 9
    struct.pack_into("<HH", data, 16, 2, machine)
    struct.pack_into("<I", data, 28, 52)
    struct.pack_into("<HH", data, 42, 32, 1)
    struct.pack_into("<I", data, 52, program_type)
    return bytes(data)


def parse_newc(blob):
    """Check header/name/data alignment without relying on host cpio."""
    entries = []
    cursor = 0
    while cursor < len(blob):
        header = blob[cursor:cursor + 110]
        if len(header) != 110 or header[:6] != b"070701":
            raise AssertionError("invalid newc header")
        fields = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
        cursor += 110
        size, name_size = fields[6], fields[11]
        name = blob[cursor:cursor + name_size]
        assert name.endswith(b"\0")
        cursor += name_size
        cursor = (cursor + 3) & ~3
        payload = blob[cursor:cursor + size]
        cursor += size
        cursor = (cursor + 3) & ~3
        entries.append((name[:-1].decode("ascii"), fields, payload))
        if name == b"TRAILER!!!\0":
            break
    return entries


class InitramfsLabTests(unittest.TestCase):
    def test_static_arm32_elf_is_accepted(self):
        lab.validate_arm32_static_elf(fake_arm_elf())

    def test_reject_wrong_architecture(self):
        with self.assertRaisesRegex(ValueError, "ARM32"):
            lab.validate_arm32_static_elf(fake_arm_elf(machine=3))

    def test_reject_dynamic_interpreter(self):
        with self.assertRaisesRegex(ValueError, "dynamisch"):
            lab.validate_arm32_static_elf(fake_arm_elf(program_type=3))

    def test_reject_incomplete_program_headers(self):
        with self.assertRaisesRegex(ValueError, "unvollständig"):
            lab.validate_arm32_static_elf(fake_arm_elf()[:60])

    def test_pack_arm32_init_and_dev_console(self):
        executable = fake_arm_elf()
        archive = lab.build_initramfs(executable)
        entries = parse_newc(gzip.decompress(archive))
        by_name = {name: (fields, payload) for name, fields, payload in entries}
        self.assertEqual(entries[-1][0], "TRAILER!!!")
        self.assertEqual(by_name["init"][1], executable)
        self.assertEqual(by_name["init"][0][1], stat.S_IFREG | 0o755)
        self.assertEqual(by_name["dev/console"][0][9:11], [5, 1])
        self.assertEqual(by_name["dev/console"][0][1], stat.S_IFCHR | 0o600)
        self.assertIn("proc", by_name)
        self.assertIn("sys", by_name)
        self.assertEqual(archive, lab.build_initramfs(executable))

    def test_reject_unsafe_archive_filename(self):
        with self.assertRaisesRegex(ValueError, "Unsicherer"):
            lab.newc_entry("../outside", stat.S_IFREG | 0o644)

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "lab.cpio.gz"
            output.write_bytes(b"KEEP")
            with self.assertRaisesRegex(ValueError, "niemals überschreiben"):
                lab.run("fake-", output, Path(__file__))
            self.assertEqual(output.read_bytes(), b"KEEP")


if __name__ == "__main__":
    unittest.main()
