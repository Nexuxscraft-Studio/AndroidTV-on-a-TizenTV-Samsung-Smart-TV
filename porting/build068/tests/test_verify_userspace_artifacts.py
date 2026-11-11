"""Synthetic tests for the Build 068 artifact verifier (no Android build needed)."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_userspace_artifacts as v  # noqa: E402


def fake_elf(path: Path, elf_class: int, machine: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    head = bytearray(52)
    head[0:4] = b"\x7fELF"
    head[4] = elf_class
    head[5] = 1  # little endian
    head[18:20] = machine.to_bytes(2, "little")
    path.write_bytes(bytes(head))


SYSTEM_PROPS = """\
# synthetic
ro.build.version.release=15
ro.build.version.sdk=35
ro.system.product.cpu.abilist=armeabi-v7a,armeabi
ro.system.product.cpu.abilist32=armeabi-v7a,armeabi
ro.system.product.cpu.abilist64=
ro.product.system.name=lineage_sdk_tv_arm
ro.zygote=zygote32
"""

VENDOR_PROPS = """\
ro.product.cpu.abi=armeabi-v7a
ro.vendor.product.cpu.abilist=armeabi-v7a,armeabi
ro.vendor.product.cpu.abilist64=
"""

LEANBACK = '<permissions><feature name="android.software.leanback" /></permissions>\n'


def make_good_tree(root: Path) -> None:
    (root / "system").mkdir(parents=True)
    (root / "system/build.prop").write_text(SYSTEM_PROPS)
    (root / "vendor").mkdir()
    (root / "vendor/build.prop").write_text(VENDOR_PROPS)
    perm = root / "system/etc/permissions"
    perm.mkdir(parents=True)
    (perm / "android.software.leanback.xml").write_text(LEANBACK)
    for rel in ("system/bin/app_process32", "system/bin/servicemanager",
                "system/bin/init", "system/bin/linker"):
        fake_elf(root / rel, v.ELFCLASS32, v.EM_ARM)
    (root / "system.img").write_bytes(b"\0")


class VerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def status(self, report: dict, name: str) -> str:
        return next(c["status"] for c in report["checks"] if c["check"] == name)

    def test_pure_arm32_tv_tree_passes(self) -> None:
        make_good_tree(self.root)
        report = v.check(self.root)
        self.assertEqual(report["overall"], "PASS", json.dumps(report, indent=1))
        self.assertTrue(report["images_present"]["system.img"])
        self.assertFalse(report["images_present"]["kernel-ranchu"])

    def test_empty_dir_is_incomplete_not_pass(self) -> None:
        report = v.check(self.root)
        self.assertEqual(report["overall"], "INCOMPLETE")
        self.assertNotIn("PASS", {c["status"] for c in report["checks"]})

    def test_arm64_binary_fails(self) -> None:
        make_good_tree(self.root)
        fake_elf(self.root / "system/bin/app_process32", v.ELFCLASS64, v.EM_AARCH64)
        report = v.check(self.root)
        self.assertEqual(self.status(report, "elf32_arm:app_process32"), "FAIL")
        self.assertEqual(report["overall"], "FAIL")

    def test_64bit_abi_list_fails(self) -> None:
        make_good_tree(self.root)
        (self.root / "vendor/build.prop").write_text(
            VENDOR_PROPS.replace("abilist64=", "abilist64=arm64-v8a"))
        report = v.check(self.root)
        self.assertEqual(self.status(report, "no_64bit_abi"), "FAIL")

    def test_lib64_dir_fails(self) -> None:
        make_good_tree(self.root)
        (self.root / "system/lib64").mkdir()
        report = v.check(self.root)
        self.assertEqual(self.status(report, "no_64bit_userspace_paths"), "FAIL")

    def test_zygote64_32_fails(self) -> None:
        make_good_tree(self.root)
        (self.root / "system/build.prop").write_text(
            SYSTEM_PROPS.replace("zygote32", "zygote64_32"))
        report = v.check(self.root)
        self.assertEqual(self.status(report, "zygote32"), "FAIL")

    def test_missing_leanback_fails(self) -> None:
        make_good_tree(self.root)
        (self.root / "system/etc/permissions/android.software.leanback.xml").unlink()
        report = v.check(self.root)
        self.assertEqual(self.status(report, "leanback_feature"), "FAIL")

    def test_wrong_android_version_fails(self) -> None:
        make_good_tree(self.root)
        (self.root / "system/build.prop").write_text(
            SYSTEM_PROPS.replace("release=15", "release=14").replace("sdk=35", "sdk=34"))
        report = v.check(self.root)
        self.assertEqual(self.status(report, "android_15"), "FAIL")

    def test_gsi_without_vendor_uses_system_abilist(self) -> None:
        make_good_tree(self.root)
        (self.root / "vendor/build.prop").unlink()
        report = v.check(self.root)
        self.assertEqual(self.status(report, "primary_abi_armeabi_v7a"), "PASS")
        self.assertEqual(report["overall"], "PASS")

    def test_gsi_without_zygote_is_na(self) -> None:
        make_good_tree(self.root)
        (self.root / "vendor/build.prop").unlink()
        (self.root / "system/build.prop").write_text(
            SYSTEM_PROPS.replace("ro.zygote=zygote32\n", ""))
        report = v.check(self.root)
        self.assertEqual(self.status(report, "zygote32"), "N/A")
        self.assertEqual(report["overall"], "PASS")

    def test_device_build_without_zygote_is_missing(self) -> None:
        make_good_tree(self.root)
        (self.root / "system/build.prop").write_text(
            SYSTEM_PROPS.replace("ro.zygote=zygote32\n", ""))
        report = v.check(self.root)
        self.assertEqual(self.status(report, "zygote32"), "MISSING")

    def test_linker_from_symbols_apex(self) -> None:
        make_good_tree(self.root)
        (self.root / "system/bin/linker").unlink()
        v_path = self.root / "symbols/apex/com.android.runtime/bin/linker"
        fake_elf(v_path, v.ELFCLASS32, v.EM_ARM)
        report = v.check(self.root)
        self.assertEqual(self.status(report, "elf32_arm:linker"), "PASS")

    def test_parse_props_ignores_comments_and_imports(self) -> None:
        props = v.parse_props("# c\nimport /x.prop\na=1\n b = 2 \nnoeq\n")
        self.assertEqual(props, {"a": "1", "b": "2"})

    def test_non_elf_is_not_elf(self) -> None:
        p = self.root / "x"
        p.write_bytes(b"#!/bin/sh\n")
        self.assertIsNone(v.elf_ident(p))

    def test_cli_exit_codes(self) -> None:
        self.assertEqual(v.main([str(self.root), "--json"]), 2)
        make_good_tree(self.root)
        self.assertEqual(v.main([str(self.root)]), 0)


if __name__ == "__main__":
    unittest.main()
