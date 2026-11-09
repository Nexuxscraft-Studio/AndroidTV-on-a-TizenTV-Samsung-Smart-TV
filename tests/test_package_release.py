"""Offline tests for audited, deterministic source-only release packaging."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

import q60t_package_release as release


class SourceReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.out = self.root / "dist"
        self.source.mkdir()
        self.out.mkdir()
        (self.source / "README.md").write_text("Offline research only.\n", encoding="utf-8")
        (self.source / "q60t.py").write_text("print('synthetic')\n", encoding="utf-8")
        (self.source / "nested").mkdir()
        (self.source / "nested" / "notes.json").write_text('{"lab":true}\n', encoding="utf-8")

    def test_archive_contains_only_audited_sources(self) -> None:
        output = self.out / "source-v014.zip"
        result = release.package(self.source, output, "v0.14.0")
        self.assertEqual(result["status"], "PASS")
        with ZipFile(output) as zipfile:
            self.assertIsNone(zipfile.testzip())
            self.assertEqual(zipfile.namelist(), [
                "q60t-lineage-lab/README.md",
                "q60t-lineage-lab/nested/notes.json",
                "q60t-lineage-lab/q60t.py",
            ])
            self.assertEqual(zipfile.read("q60t-lineage-lab/README.md"),
                             b"Offline research only.\n")
            self.assertEqual(len(set(info.date_time for info in zipfile.infolist())), 1)
        manifest = json.loads((self.out / "source-v014.manifest.json").read_text())
        self.assertFalse(manifest["contains_flashable_image"])
        self.assertFalse(manifest["includes_vendor_kernel_or_firmware"])
        self.assertEqual(manifest["source_files"], 3)
        checksum = hashlib.sha256(output.read_bytes()).hexdigest()
        self.assertEqual(manifest["archive_sha256"], checksum)
        self.assertEqual((self.out / "source-v014.sha256").read_text(),
                         f"{checksum}  source-v014.zip\n")

    def test_reproducible_between_distinct_file_names(self) -> None:
        first = self.out / "first.zip"
        second = self.out / "second.zip"
        first_hash = release.package(self.source, first, "build014")["sha256"]
        second_hash = release.package(self.source, second, "build014")["sha256"]
        self.assertEqual(first_hash, second_hash)
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_existing_archive_is_never_overwritten(self) -> None:
        output = self.out / "existing.zip"
        output.write_bytes(b"original")
        with self.assertRaises(ValueError):
            release.package(self.source, output, "build014")
        self.assertEqual(output.read_bytes(), b"original")

    def test_existing_manifest_is_never_overwritten(self) -> None:
        output = self.out / "source.zip"
        manifest = self.out / "source.manifest.json"
        manifest.write_text("untouched")
        with self.assertRaises(ValueError):
            release.package(self.source, output, "build014")
        self.assertEqual(manifest.read_text(), "untouched")
        self.assertFalse(output.exists())

    def test_output_inside_source_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            release.package(self.source, self.source / "bad.zip", "build014")

    def test_invalid_label_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            release.package(self.source, self.out / "bad.zip", "../escape")

    def test_unsafe_binary_in_source_blocks_package(self) -> None:
        (self.source / "firmware.img").write_bytes(b"some firmware bytes")
        with self.assertRaisesRegex(ValueError, "Audit"):
            release.package(self.source, self.out / "unsafe.zip", "build014")
        self.assertFalse((self.out / "unsafe.zip").exists())

    def test_symlink_in_source_blocks_package(self) -> None:
        (self.source / "link.md").symlink_to(self.source / "README.md")
        with self.assertRaisesRegex(ValueError, "Audit"):
            release.package(self.source, self.out / "link.zip", "build014")
        self.assertFalse((self.out / "link.zip").exists())


if __name__ == "__main__":
    unittest.main()
