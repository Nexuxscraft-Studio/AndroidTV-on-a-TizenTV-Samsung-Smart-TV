"""Synthetic host checks for Build 020, never a real kernel or Android boot."""

import json
from pathlib import Path
import struct
import tempfile
import unittest

import q60t_bionic_preflight as bionic
import q60t_compile_probe as compiler
import q60t_ion_result as ion
import q60t_qemu_runtime as runtime
import q60t_selinux_preflight as selinux


ION_GOOD = (
    b"Linux version 4.1.10\r\n"
    b"Q60T_ANDROID_PROBE_BEGIN version=020 host_only=1 no_flash=1\r\n"
    b"Q60T_ION_TEST stage=open result=pass\r\n"
    b"Q60T_ION_TEST stage=alloc result=pass bytes=4096\r\n"
    b"Q60T_ION_TEST stage=free result=pass\r\n"
    b"Q60T_ANDROID_PROBE_FEATURE name=ion result=pass\r\n"
    b"Q60T_ANDROID_PROBE_END version=020\r\n"
)


def elf32(interpreter="/system/bin/linker", kind=3, machine=40):
    raw = bytearray(256)
    raw[:6] = b"\x7fELF\x01\x01"
    struct.pack_into("<HH", raw, 16, kind, machine)
    struct.pack_into("<I", raw, 28, 52)
    struct.pack_into("<HH", raw, 42, 32, 1)
    data = interpreter.encode("ascii") + b"\x00"
    struct.pack_into("<IIIII", raw, 52, 3, 128, 0, 0, len(data))
    raw[128:128 + len(data)] = data
    return bytes(raw)


class Build020Tests(unittest.TestCase):
    def test_ion_requires_real_guest_4k_alloc_and_free(self):
        self.assertTrue(ion.inspect(ION_GOOD)["ion_4k_allocation_verified_in_guest_log"])
        for missing in (b"stage=alloc", b"stage=free", b"name=ion result=pass",
                        b"version=020 host_only=1"):
            changed = b"\n".join(line for line in ION_GOOD.splitlines() if missing not in line)
            self.assertFalse(ion.inspect(changed)["ion_4k_allocation_verified_in_guest_log"])
        self.assertFalse(ion.inspect(ION_GOOD.replace(b"bytes=4096", b"bytes=0"))
                         ["ion_4k_allocation_verified_in_guest_log"])
        self.assertFalse(ion.inspect(ION_GOOD + b"Kernel panic\n")
                         ["ion_4k_allocation_verified_in_guest_log"])

    def test_ion_duplicate_stage_rejected(self):
        with self.assertRaisesRegex(ValueError, "Doppelte"):
            ion.inspect(ION_GOOD + b"Q60T_ION_TEST stage=alloc result=pass bytes=4096\n")

    def test_only_build020_profile_adds_dummy(self):
        self.assertNotIn("ION_DUMMY", compiler.QEMU_VIRT_OVERLAY)
        self.assertEqual(compiler.QEMU_ION_OVERLAY["ION_DUMMY"], "y")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / ".config").write_text("CONFIG_ION=y\n# CONFIG_ION_DUMMY is not set\n")
            (output / "STAGE_MANIFEST.json").write_text(json.dumps({}))
            compiler.apply_research_overlay(output, "qemu-ion-lab")
            self.assertIn("CONFIG_ION_DUMMY=y", (output / ".config").read_text())
            self.assertEqual(json.loads((output / "STAGE_MANIFEST.json").read_text())
                             ["profile"], "qemu-ion-lab")
            self.assertIn("ION_DUMMY", compiler.verify_config(output, "qemu-ion-lab")["checked"])

    def test_ion_vendor_source_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "ION-Dummy fehlt"):
                compiler.validate_ion_dummy_source(root)
            folder = root / "drivers/staging/android/ion"
            folder.mkdir(parents=True)
            (folder / "Kconfig").write_text("config ION_DUMMY\n bool 'Dummy'\n")
            (folder / "Makefile").write_text("obj-$(CONFIG_ION_DUMMY) += ion_dummy_driver.o\n")
            (folder / "ion_dummy_driver.c").write_text(
                "ion_device_create(NULL); ion_device_add_heap(dev, heap);\n")
            uapi = root / "drivers/staging/android/uapi/ion.h"
            uapi.parent.mkdir(parents=True)
            uapi.write_text("struct ion_allocation_data { size_t len; size_t align; "
                            "unsigned int heap_id_mask; ion_user_handle_t handle; }; "
                            "ION_IOC_ALLOC ION_IOC_FREE\n")
            compiler.validate_ion_dummy_source(root)
            (folder / "Makefile").write_text("obj-y += some_other.o\n")
            with self.assertRaisesRegex(ValueError, "Makefile"):
                compiler.validate_ion_dummy_source(root)

    def test_bionic_arm32_and_loader_are_checked(self):
        good = bionic.inspect_elf(elf32())
        self.assertEqual(good["interpreter"], "/system/bin/linker")
        with self.assertRaisesRegex(ValueError, "kein Android"):
            bionic.inspect_elf(elf32("/lib/ld-linux-armhf.so.3"))
        with self.assertRaisesRegex(ValueError, "ARM32"):
            bionic.inspect_elf(elf32(machine=62))
        with self.assertRaisesRegex(ValueError, "ARM32"):
            bionic.inspect_elf(elf32(kind=2))

    def test_bionic_elf_is_not_reported_as_executed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bionic_hello"
            path.write_bytes(elf32())
            finding = bionic.inspect(path)
            self.assertFalse(finding["ready_to_execute_in_guest"])
            self.assertFalse(finding["android_userspace_running"])

    def test_selinux_does_not_treat_permissive_as_android_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            (workspace / "output").mkdir()
            (workspace / "output/.config").write_text(
                "CONFIG_SECURITY_SELINUX=y\nCONFIG_DEFAULT_SECURITY_SELINUX=y\n"
                "# CONFIG_SECURITY_SFD is not set\n")
            log = workspace / "serial.log"
            log.write_text("Q60T_ANDROID_PROBE_FEATURE name=selinux_enforcing result=fail\n")
            finding = selinux.inspect(workspace, guest_log=log)
            self.assertTrue(finding["kernel_selinux_compiled_and_selected"])
            self.assertEqual(finding["guest_selinux_mode"], "permissive_reported")
            self.assertFalse(finding["android_selinux_enforcement_ready"])
            self.assertFalse(finding["policy_loaded_into_guest_verified"])

    def test_qemu_runtime_rejects_ion_profile_without_dummy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / runtime.EXPECTED_ARTIFACT
            image.parent.mkdir(parents=True)
            image.write_bytes(b"FAKE-NOT-BOOTABLE")
            (root / "output/.config").write_text("\n".join(
                f"CONFIG_{k}={v}" if v == "y" else f"# CONFIG_{k} is not set"
                for k, v in runtime.REQUIRED_CONFIG.items()) + "\n")
            (root / "compile-report.json").write_text(json.dumps({
                "profile": "qemu-ion-lab", "status": "HOST_KERNEL_COMPILED_NOT_BOOTABLE_VALIDATED",
                "resolved_config": {"verified": True},
                "artifact": {"path_within_workspace": runtime.EXPECTED_ARTIFACT,
                             "size_bytes": image.stat().st_size,
                             "sha256": runtime.sha256(image)},
            }))
            with self.assertRaisesRegex(ValueError, "ION_DUMMY"):
                runtime.validate_workspace(root)
            with (root / "output/.config").open("a") as stream:
                stream.write("CONFIG_ION_DUMMY=y\n")
            self.assertEqual(runtime.validate_workspace(root), image)


if __name__ == "__main__":
    unittest.main()
