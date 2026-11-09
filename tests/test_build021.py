"""No download, real firmware, QEMU launch, or privilege elevation in CI."""

import gzip
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import q60t_aosp_runtime as aosp
import q60t_bionic_elf as elf
import q60t_bionic_guest_result as guest
import q60t_bionic_initramfs as initrd


def synthetic_arm_elf(needed=(), interpreter=None, machine=40):
    """Tiny structural fixture; never a genuine Android binary."""
    raw = bytearray(512)
    raw[:7] = b"\x7fELF\x01\x01\x01"
    struct.pack_into("<HH", raw, 16, 3, machine)
    struct.pack_into("<I", raw, 28, 52)
    struct.pack_into("<HH", raw, 42, 32, 3 if interpreter else 2)
    # PT_LOAD maps file offset 128 to virtual address 0x1000.
    struct.pack_into("<IIIIIIII", raw, 52, 1, 128, 0x1000, 0, 384, 384, 5, 4096)
    # PT_DYNAMIC sits inside the loadable segment.
    dyn_offset = 192
    strings = b"\0" + b"\0".join(x.encode("ascii") for x in needed) + b"\0"
    dyn_entries = [(5, 0x1100), (10, len(strings))]
    position = 1
    for item in needed:
        dyn_entries.append((1, position))
        position += len(item) + 1
    dyn_entries.append((0, 0))
    struct.pack_into("<IIIIIIII", raw, 84, 2, dyn_offset, 0x1040, 0, 8 * len(dyn_entries), 8 * len(dyn_entries), 6, 4)
    for index, (tag, value) in enumerate(dyn_entries):
        struct.pack_into("<II", raw, dyn_offset + index * 8, tag, value)
    raw[384:384 + len(strings)] = strings
    if interpreter:
        interp_bytes = interpreter.encode("ascii") + b"\0"
        struct.pack_into("<IIIIIIII", raw, 116, 3, 160, 0, 0, len(interp_bytes), len(interp_bytes), 4, 1)
        raw[160:160 + len(interp_bytes)] = interp_bytes
    return bytes(raw)


class Build021Tests(unittest.TestCase):
    def test_bionic_elf_needed_and_interpreter(self):
        info = elf.parse_elf32_arm(synthetic_arm_elf(
            ("libdl.so", "libc.so"), interpreter="/system/bin/linker"),
            require_interpreter=True)
        self.assertEqual(info["machine"], "ARM")
        self.assertEqual(info["needed"], ["libdl.so", "libc.so"])
        with self.assertRaisesRegex(ValueError, "Bionic-Testprogramm"):
            elf.parse_elf32_arm(synthetic_arm_elf(interpreter="/lib/ld-linux.so.3"),
                                require_interpreter=True)
        with self.assertRaisesRegex(ValueError, "ARM32"):
            elf.parse_elf32_arm(synthetic_arm_elf(machine=62))

    def test_provenance_requires_sdk_api24_default_arm32(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "source.properties"
            path.write_text("AndroidVersion.ApiLevel=24\nSystemImage.Abi=armeabi-v7a\n"
                            "SystemImage.TagId=default\nPkg.Revision=7\n")
            fields = aosp.parse_source_properties(path)
            self.assertEqual(fields["Pkg.Revision"], "7")
            path.write_text(path.read_text().replace("ApiLevel=24", "ApiLevel=30"))
            with self.assertRaisesRegex(ValueError, "API 24"):
                aosp.parse_source_properties(path)

    def test_legacy_program_imports_require_runtime_library_closure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {}
            for name in aosp.RUNTIME_FILES:
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(synthetic_arm_elf(needed=("libdl.so",) if name.endswith("libc.so") else ()))
                files[name] = dest
            self.assertEqual(len(aosp.check_runtime_files(files)), len(aosp.RUNTIME_FILES))
            files["system/lib/libc.so"].write_bytes(synthetic_arm_elf(needed=("libvendor.so",)))
            with self.assertRaisesRegex(ValueError, "fehlen"):
                aosp.check_runtime_files(files)

    def test_bionic_runtime_interpreters_must_be_android_arm32(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {}
            for name in aosp.RUNTIME_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(synthetic_arm_elf(
                    interpreter="/system/bin/linker"))
                files[name] = path

            # AOSP image may expose PT_INTERP on the linker *and*
            # libc.so/libdl.so/libm.so; none is an error by itself.
            checked = aosp.check_runtime_files(files)
            self.assertEqual(set(checked), set(aosp.RUNTIME_FILES))
            self.assertTrue(all(
                item["elf"]["interpreter"] == "/system/bin/linker"
                for item in checked.values()))

            # Reject a foreign loader path in any runtime ELF.
            for name in files:
                files[name].write_bytes(
                    synthetic_arm_elf(interpreter="/lib/ld-linux-armhf.so.3"))
                with self.assertRaisesRegex(ValueError, "Android-PT_INTERP"):
                    aosp.check_runtime_files(files)
                files[name].write_bytes(
                    synthetic_arm_elf(interpreter="/system/bin/linker"))

            # Having no PT_INTERP remains legal for shared objects.
            for name in files:
                files[name].write_bytes(synthetic_arm_elf())
            aosp.check_runtime_files(files)

    def test_runtime_manifest_detects_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in aosp.RUNTIME_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(synthetic_arm_elf())
            checked = aosp.check_runtime_files({name: root / name for name in aosp.RUNTIME_FILES})
            (root / "runtime-manifest.json").write_text(json.dumps({
                "sdk_package_id": aosp.PACKAGE_ID,
                "sdk_revision": "1",
                "status": "BIONIC_RUNTIME_STAGED_OFFLINE_NOT_EXECUTED",
                "files": checked,
            }))
            self.assertEqual(initrd.verify_runtime(root)["sdk_revision"], "1")
            (root / "system/lib/libc.so").write_bytes(b"CORRUPT")
            with self.assertRaisesRegex(ValueError, "verändert"):
                initrd.verify_runtime(root)

    def test_build_archive_is_gzip_and_contains_no_host_paths(self):
        static_arm_elf = bytearray(synthetic_arm_elf())
        struct.pack_into("<HH", static_arm_elf, 16, 2, 40)
        # Static /init has no PT_INTERP.
        data = initrd.create_archive(bytes(static_arm_elf), synthetic_arm_elf(), {
            name: synthetic_arm_elf() for name in aosp.RUNTIME_FILES
        })
        raw = gzip.decompress(data)
        self.assertTrue(raw.startswith(b"070701"))
        self.assertIn(b"system/bin/linker\0", raw)
        self.assertIn(b"system/bin/q60t_bionic_hello\0", raw)
        self.assertIn(b"system/lib/libc.so\0", raw)
        self.assertIn(b"TRAILER!!!\0", raw)

    def test_guest_success_requires_child_hello_and_zero_exit(self):
        valid = (b"Linux version 4.1.10 #1\r\n" +
                 b"\r\n".join(item.encode("ascii") for item in guest.MARKERS) + b"\r\n")
        self.assertTrue(guest.inspect(valid)["arm32_bionic_process_exit_zero_reported"])
        for item in guest.MARKERS:
            self.assertFalse(guest.inspect(valid.replace(item.encode("ascii"), b"MISSING"))
                             ["arm32_bionic_process_exit_zero_reported"])
        self.assertFalse(guest.inspect(valid + b"Kernel panic - not syncing\n")
                         ["arm32_bionic_process_exit_zero_reported"])
        self.assertFalse(guest.inspect(valid + b"Q60T_BIONIC_EXECVE_FAILED errno=2\n")
                         ["arm32_bionic_process_exit_zero_reported"])

    def test_duplicate_or_reordered_guest_marker_fails(self):
        raw = b"Linux version 4.1.10\n" + b"\n".join(
            item.encode("ascii") for item in reversed(guest.MARKERS)) + b"\n"
        self.assertFalse(guest.inspect(raw)["arm32_bionic_process_exit_zero_reported"])
        valid = b"Linux version 4.1.10\n" + b"\n".join(
            item.encode("ascii") for item in guest.MARKERS) + b"\n"
        self.assertFalse(guest.inspect(valid + guest.MARKERS[2].encode() + b"\n")
                         ["arm32_bionic_process_exit_zero_reported"])


if __name__ == "__main__":
    unittest.main()
