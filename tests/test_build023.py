"""Build 023: synthetic-only ARM64 source/QEMU/driver preflight tests."""

import gzip
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import q60t_arm64_initramfs as initrd
import q60t_arm64_kernel as kernel
import q60t_arm64_qemu as runner
import q60t_arm64_guest_result as guest
import q60t_samsung_driver_audit as samsung


def fake_arm64_elf(interpreter=False, machine=183):
    image = bytearray(256)
    image[:7] = b"\x7fELF\x02\x01\x01"
    struct.pack_into("<HH", image, 16, 2, machine)
    struct.pack_into("<Q", image, 32, 64)
    struct.pack_into("<HH", image, 54, 56, 1)
    struct.pack_into("<I", image, 64, 3 if interpreter else 1)
    return bytes(image)


def fake_guest_serial():
    return b"\n".join((
        b"Linux version 6.6.162 #1",
        guest.BEGIN,
        b"Q60T_ARM64_UNAME machine=aarch64 release=6.6.162",
        b"Q60T_ARM64_MOUNT name=devtmpfs status=pass",
        b"Q60T_ARM64_BINDER name=binder status=pass protocol=8",
        b"Q60T_ARM64_BINDER name=hwbinder status=pass protocol=8",
        b"Q60T_ARM64_BINDER name=vndbinder status=pass protocol=8",
        b"Q60T_ARM64_SELINUX status=pass enforce=0 policy_loaded=unverified",
        b"Q60T_ARM64_MEMFD status=pass bytes=4096",
        b"Q60T_ARM64_DMA_HEAP status=pass bytes=4096",
        guest.END,
    )) + b"\n"


def fake_meta(data):
    return {
        "build": "023", "type": "q60t_arm64_virt_qemu_run",
        "log_sha256": hashlib.sha256(data).hexdigest(),
        "qemu_only": True, "samsung_tv_accessed": False, "safe_to_flash": False,
    }


class Build023Tests(unittest.TestCase):
    def test_arm64_elf_validator_rejects_arm32_and_dynamic_linker(self):
        initrd.validate_static_aarch64_elf(fake_arm64_elf())
        with self.assertRaisesRegex(ValueError, "AArch64"):
            initrd.validate_static_aarch64_elf(fake_arm64_elf(machine=40))
        with self.assertRaisesRegex(ValueError, "PT_INTERP"):
            initrd.validate_static_aarch64_elf(fake_arm64_elf(interpreter=True))
        with self.assertRaisesRegex(ValueError, "ELF64"):
            initrd.validate_static_aarch64_elf(b"\x7fELF\x01\x01")

    def test_arm64_initramfs_is_deterministic_and_has_console_and_pid1(self):
        first = initrd.create_archive(fake_arm64_elf())
        self.assertEqual(first, initrd.create_archive(fake_arm64_elf()))
        archive = gzip.decompress(first)
        self.assertTrue(archive.startswith(b"070701"))
        self.assertIn(b"dev/console\x00", archive)
        self.assertIn(b"sys/fs/selinux\x00", archive)
        self.assertIn(b"TRAILER!!!\x00", archive)

    def test_kernel_config_marks_missing_options_and_binder_device_names(self):
        flags = kernel.inspect_config("CONFIG_ANDROID_BINDER_IPC=y\n"
                                      'CONFIG_ANDROID_BINDER_DEVICES="binder,hwbinder,vndbinder"\n'
                                      "# CONFIG_SECURITY_SELINUX is not set\n")
        self.assertEqual(flags["required"]["CONFIG_ANDROID_BINDER_IPC"], "y")
        self.assertIn("CONFIG_SECURITY_SELINUX", flags["missing_required"])
        self.assertTrue(flags["binder_device_names_match"])

    def test_selinux_kernel_prerequisites_are_required_not_optional(self):
        # Linux 6.6 SELinux depends on SECURITY_NETWORK, AUDIT, NET and INET.
        for option in ("SECURITY", "SECURITY_NETWORK", "AUDIT", "NET", "INET"):
            self.assertIn(option, kernel.REQUESTED_BUILTINS)
            self.assertNotIn(option, kernel.OPTIONAL_BUILTINS)

    def test_selinux_is_selected_in_lsm_order_and_verified(self):
        original = 'CONFIG_LSM="landlock,lockdown,bpf"\\n'
        self.assertEqual(kernel.add_selinux_lsm(original),
                         "landlock,lockdown,selinux,bpf")
        self.assertEqual(kernel.add_selinux_lsm('CONFIG_LSM="selinux,bpf"\\n'),
                         "selinux,bpf")
        with self.assertRaisesRegex(ValueError, "CONFIG_LSM"):
            kernel.add_selinux_lsm("CONFIG_SECURITY_SELINUX=y\\n")
        self.assertTrue(kernel.inspect_config('CONFIG_LSM="selinux,bpf"\\n')
                        ["selinux_lsm_selected"])
        self.assertFalse(kernel.inspect_config('CONFIG_LSM="landlock,bpf"\\n')
                         ["selinux_lsm_selected"])

    def test_binderfs_devices_created_in_guest_probe(self):
        source = initrd.DEFAULT_SOURCE.read_text(encoding="utf-8")
        self.assertIn("BINDER_CTL_ADD", source)
        self.assertIn('binderfs_setup();', source)
        self.assertIn('"/dev/binderfs/%s"', source)

    def test_kernel_version_exact_and_uses_distinct_source_and_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            source.mkdir()
            (source / "Makefile").write_text("VERSION = 6\nPATCHLEVEL = 6\nSUBLEVEL = 162\n")
            self.assertEqual(kernel.source_version(source), kernel.VERSION)
            with self.assertRaisesRegex(ValueError, "Build-Werkzeuge"):
                kernel.build(source, root / "output")
            self.assertFalse((root / "output").exists())
            (source / "Makefile").write_text("VERSION = 4\nPATCHLEVEL = 1\nSUBLEVEL = 10\n")
            with self.assertRaisesRegex(ValueError, "6.6.162"):
                kernel.build(source, root / "output")

    def test_qemu_command_has_no_network_storage_or_host_device_access(self):
        args = runner.qemu_command("/usr/bin/qemu-system-aarch64", Path("Image"), Path("initrd.gz"))
        self.assertIn("-nic", args)
        self.assertEqual(args[args.index("-nic") + 1], "none")
        self.assertIn("-nodefaults", args)
        self.assertIn("-accel", args)
        self.assertEqual(args[args.index("-accel") + 1], "tcg")
        for forbidden in ("-drive", "-hda", "-net", "-device", "-enable-kvm"):
            self.assertNotIn(forbidden, args)

    def test_reported_arm64_boot_with_all_facilities_is_not_android(self):
        log = fake_guest_serial()
        result = guest.inspect(log, fake_meta(log))
        self.assertTrue(result["arm64_qemu_kernel_boot_reported"])
        self.assertTrue(result["arm64_android_kernel_facilities_reported"])
        self.assertFalse(result["selinux_android_policy_verified"])
        self.assertFalse(result["android_init_executed"])
        self.assertFalse(result["lineageos_booted"])
        self.assertFalse(result["safe_to_flash"])

    def test_qemu_marker_forgery_or_bad_hash_cannot_pass(self):
        original = fake_guest_serial()
        self.assertFalse(guest.inspect(original, None)["arm64_qemu_kernel_boot_reported"])
        tampered = original.replace(b"protocol=8", b"protocol=0")
        self.assertFalse(guest.inspect(tampered, fake_meta(original))["arm64_android_kernel_facilities_reported"])
        duplicated = original + guest.END + b"\n"
        self.assertFalse(guest.inspect(duplicated, fake_meta(duplicated))["arm64_qemu_kernel_boot_reported"])
        crashed = original + b"Kernel panic - not syncing\n"
        self.assertFalse(guest.inspect(crashed, fake_meta(crashed))["arm64_qemu_kernel_boot_reported"])

    def test_kernel_banner_and_arm64_uname_both_required(self):
        log = fake_guest_serial().replace(b"machine=aarch64", b"machine=armv7l")
        self.assertFalse(guest.inspect(log, fake_meta(log))["arm64_qemu_kernel_boot_reported"])
        log = fake_guest_serial().replace(b"Linux version 6.6.162", b"Linux version 4.1.10")
        self.assertFalse(guest.inspect(log, fake_meta(log))["arm64_qemu_kernel_boot_reported"])

    def test_driver_inventory_reports_paths_but_never_portability_success(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            (source / "Makefile").write_text("VERSION = 4\nPATCHLEVEL = 1\nSUBLEVEL = 10\n")
            folder_name = source / "arch/arm/boot/dts"
            folder_name.mkdir(parents=True)
            (folder_name / "nike.dts").write_text("/* synthetic */")
            result = samsung.audit(source)
            self.assertEqual(result["observations"]["arm32_device_trees"]["file_count"], 1)
            self.assertEqual(result["observations"]["arm64_device_trees"]["file_count"], 0)
            self.assertFalse(result["samsung_hardware_arm64_verified"])
            self.assertFalse(result["safe_to_flash"])

    def test_driver_inventory_rejects_wrong_kernel_version(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            (source / "Makefile").write_text("VERSION = 6\nPATCHLEVEL = 6\nSUBLEVEL = 162\n")
            with self.assertRaisesRegex(ValueError, "4.1.10"):
                samsung.audit(source)


if __name__ == "__main__":
    unittest.main()
