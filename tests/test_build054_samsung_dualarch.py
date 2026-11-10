"""Build 054: vendor source patch, legacy ARM32 evidence and safe test runners."""

from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from q60t_build050_linux66_port_gaps import read_original_text
from q60t_build050_stage1_source_fixes import fix_drm_safety
from q60t_build053_samsung_drm_stage1 import (
    DRM, GEM, make_patch as make_build053_patch,
    migrate_drm, migrate_gem,
)
import q60t_build054_arm32_original_evidence as arch
import q60t_build054_samsung_drm_stage2 as stage


BASE = Path(__file__).resolve().parents[1]
MEDIA = BASE / ".build050_vendor/srcarchives/tztv-media-nike.tgz"
KERNEL = BASE / ".build050_vendor/srcarchives/linux-4.1.10-tizen5.5.tgz"
BUILD053 = BASE / "porting/build053/patches"
BUILD054 = BASE / "porting/build054"
PATCH = BUILD054 / "patches/0003-after-build053-drm-headers-ioctl-flags.patch"


class TestBuild054(unittest.TestCase):
    def test_synthetic_stage2_migrations_preserve_authorization(self):
        original = ("static struct drm_ioctl_desc sdp_drm_ioctls[] = {\n"
                    + "\tDRM_UNLOCKED | DRM_AUTH\n" * 31
                    + "\tDRM_UNLOCKED\n};\n"
                    + "static const struct file_operations sdp_drm_driver_fops = {\n"
                    + "/* nover,compile-only-sdp-drm */\n"
                    + 'compatible = "nover,compile-only-sdp-drm";\n'
                    + "return -ENODEV;\n")
        migrated = stage.advance_drm_source(original)
        self.assertEqual(migrated.count("| DRM_AUTH"), original.count("| DRM_AUTH"))
        self.assertIn("0 | DRM_AUTH", migrated)
        self.assertNotIn("DRM_UNLOCKED | DRM_AUTH", migrated)
        self.assertIn("return -ENODEV;", migrated)

    def test_stage2_requires_no_vendor_source_drift(self):
        with self.assertRaises(ValueError):
            stage.advance_drm_header("#include <drm/drm_gem.h>")
        with self.assertRaises(ValueError):
            stage.advance_gem_header("#include <linux/reservation.h>")
        with self.assertRaises(ValueError):
            stage.advance_drm_source("static struct drm_ioctl_desc sdp_drm_ioctls[] = {\n};")

    @unittest.skipUnless(MEDIA.is_file(), "Samsung media archive not available")
    def test_stage2_patch_matches_real_vendor_source_after_either_build053(self):
        sources = {}
        for name in (DRM, GEM, stage.DRM_H, stage.GEM_H):
            sources[name] = read_original_text(MEDIA, name)[0]
        stage2_patch = stage.generate(MEDIA)
        self.assertEqual(PATCH.read_text(), stage2_patch)
        self.assertIn("--- a/" + stage.DRM_H, stage2_patch)
        self.assertIn("--- a/" + stage.GEM_H, stage2_patch)
        for baseline, patch_filename in (
            ("original", "0001-original-sdp-drm-gem-linux66-partial.patch"),
            ("stage1", "0002-after-build050-stage1-sdp-drm-gem-linux66-partial.patch"),
        ):
            with self.subTest(baseline=baseline), tempfile.TemporaryDirectory() as tmp:
                tree = Path(tmp)
                for name, content in sources.items():
                    target = tree / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if name == DRM and baseline == "stage1":
                        content = fix_drm_safety(content)
                    target.write_text(content)
                for diff in (BUILD053 / patch_filename, PATCH):
                    check = subprocess.run(
                        ["patch", "--batch", "--dry-run", "-p1", "-i", str(diff)],
                        cwd=tree, text=True, capture_output=True,
                    )
                    self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
                    apply = subprocess.run(
                        ["patch", "--batch", "-p1", "-i", str(diff)],
                        cwd=tree, text=True, capture_output=True,
                    )
                    self.assertEqual(apply.returncode, 0, apply.stdout + apply.stderr)
                self.assertEqual((tree / DRM).read_text(),
                                 stage.advance_drm_source(migrate_drm(fix_drm_safety(sources[DRM]))))
                self.assertEqual((tree / GEM).read_text(), migrate_gem(sources[GEM]))
                self.assertEqual((tree / stage.DRM_H).read_text(),
                                 stage.advance_drm_header(sources[stage.DRM_H]))
                self.assertEqual((tree / stage.GEM_H).read_text(),
                                 stage.advance_gem_header(sources[stage.GEM_H]))
                self.assertIn("return -ENODEV;", (tree / DRM).read_text())

    @unittest.skipUnless(KERNEL.is_file() and MEDIA.is_file(), "GPL archives unavailable")
    def test_original_architecture_is_arm32_cortex_a15_not_verified_tv(self):
        report = arch.arch_evidence(KERNEL, MEDIA)
        self.assertEqual(report["samsung_original_baseline"]["config_arch"], "arm (32-bit)")
        self.assertEqual(report["samsung_original_baseline"]["config_cpu"], "ARMv7 Cortex-A15")
        self.assertFalse(report["q60t_hypothesis_unverified"]["hardware_confirmed_on_this_tv"])
        self.assertFalse(report["safe_to_flash"])
        self.assertTrue(report["samsung_original_baseline"]["media_makefile_uses_external_kernel_interfaces"])
        self.assertIn("linux-4.1.10/include/drm/drm_tztv.h",
                      report["samsung_original_baseline"]["unavailable_external_vendor_headers"])
        self.assertEqual(report, json.loads((BASE / "reports/build054-arm32-vendor-source-evidence.json").read_text()))
        with patch.object(arch, "sha256_file", return_value="wrong"):
            with self.assertRaises(ValueError):
                arch.arch_evidence(KERNEL, MEDIA)

    def test_runner_scripts_parse_and_are_compile_only(self):
        for name in ("run-arm32-probe.sh", "run-arm32-vendor-diagnostic.sh"):
            script = BUILD054 / "scripts" / name
            result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        probe = (BUILD054 / "arm32-probe/nover_arm32_probe.c").read_text()
        self.assertIn("return -ENODEV;", probe)
        self.assertIn("#ifndef CONFIG_CPU_V7", probe)
        self.assertIn("obj-m += nover_arm32_probe.o",
                      (BUILD054 / "arm32-probe/Kbuild").read_text())


if __name__ == "__main__":
    unittest.main()
