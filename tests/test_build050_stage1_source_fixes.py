"""Test first-stage, non-flashable Linux 6.6 Samsung source fixes."""

from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import q60t_build050_stage1_source_fixes as stage


PANEL_FIXTURE = """#include <drm/drmP.h>
\t.vrefresh = 60,
static int sdp_panel_get_modes(struct drm_panel *panel)
\tstruct drm_connector *connector = p->base.connector;
\tstruct drm_device *drm = p->base.drm;
\t\t\t\tm->hdisplay, m->vdisplay, m->vrefresh);
\tint ret;
\tdrm_panel_init(&panel->base);
\tpanel->base.dev = &pdev->dev;
\tpanel->base.funcs = &sdp_panel_funcs;
\tret = drm_panel_add(&panel->base);
\tif (ret < 0)
\t\tgoto err;
\treturn 0;
err:
\tif (panel->backlight)
\t\tput_device(&panel->backlight->dev);

\treturn ret;
\tdrm_panel_detach(&panel->base);
\t{ .compatible = "samsung,sdp1202-panel", },
"""

DRM_FIXTURE = """\t\t/* return -ENXIO; */
static void sdp_drm_lastclose(struct drm_device *dev)
{
\tstruct sdp_drm_private *priv = dev->dev_private;
\tdrm_fbdev_cma_restore_mode(priv->fbdev);
}

\t.lastclose\t\t= sdp_drm_lastclose,
"""


class TestStage1SourceFixes(unittest.TestCase):
    def test_panel_api_migration_is_compile_only(self):
        fixed = stage.migrate_panel(PANEL_FIXTURE)
        self.assertIn("drm_panel_init(&panel->base, &pdev->dev", fixed)
        self.assertIn("drm_mode_vrefresh(m)", fixed)
        self.assertIn("drm_panel_add(&panel->base);", fixed)
        self.assertIn('"nover,compile-only-sdp-panel"', fixed)
        for old in ("drmP.h", "drm_panel_detach", "p->base.connector", "p->base.drm",
                    "samsung,sdp1202-panel", "m->vrefresh"):
            self.assertNotIn(old, fixed)

    def test_drm_guards_fail_closed_and_remove_obsolete_fbdev(self):
        fixed = stage.fix_drm_safety(DRM_FIXTURE)
        self.assertIn("return -ENXIO", fixed)
        self.assertNotIn("drm_fbdev_cma_restore_mode", fixed)
        self.assertNotIn(".lastclose", fixed)

    def test_repeated_patch_or_changed_source_refused(self):
        fixed = stage.migrate_panel(PANEL_FIXTURE)
        with self.assertRaisesRegex(ValueError, "Source drift"):
            stage.migrate_panel(fixed)
        with self.assertRaisesRegex(ValueError, "Source drift"):
            stage.fix_drm_safety("unrelated text")

    def test_unified_patch_targets_only_two_original_files(self):
        generated = stage.make_patch({stage.PANEL: PANEL_FIXTURE, stage.DRM: DRM_FIXTURE})
        self.assertEqual(generated.count("--- a/"), 2)
        self.assertEqual(generated.count("+++ b/"), 2)
        self.assertNotIn("/dev/mmc", generated)
        self.assertIn('nover,compile-only-sdp-panel', generated)

    def test_unverified_archives_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "fake.tgz"
            fake.write_bytes(b"invalid Samsung source")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                stage.generate(fake, fake)

    def test_cli_no_clobber(self):
        with tempfile.TemporaryDirectory() as directory:
            outfile = Path(directory) / "fix.patch"
            args = ["--kernel-tgz", "dummy", "--media-tgz", "dummy", "--output", str(outfile)]
            with patch.object(stage, "generate", return_value="compile-only patch\n"):
                self.assertEqual(stage.main(args), 0)
                self.assertEqual(stage.main(args), 2)
            self.assertEqual(outfile.read_text(), "compile-only patch\n")

    def test_real_vendor_patch_dry_run_when_source_archives_exist(self):
        root = Path(__file__).resolve().parent.parent
        kernel = root / ".build050_vendor/srcarchives/linux-4.1.10-tizen5.5.tgz"
        media = root / ".build050_vendor/srcarchives/tztv-media-nike.tgz"
        if not kernel.exists() or not media.exists():
            self.skipTest("Original Samsung source archives not distributed in repository")
        content = stage.generate(kernel, media)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for archive_path, member in ((kernel, stage.PANEL), (media, stage.DRM)):
                with tarfile.open(archive_path, "r:gz") as archive:
                    reader = archive.extractfile(member)
                    self.assertIsNotNone(reader)
                    target = base / member
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(reader.read())
            patchfile = base / "stage1.patch"
            patchfile.write_text(content)
            test = subprocess.run(["patch", "--dry-run", "--batch", "-p1", "-i", str(patchfile)],
                                  cwd=base, capture_output=True, text=True, check=False)
            self.assertEqual(test.returncode, 0, test.stdout + test.stderr)


if __name__ == "__main__":
    unittest.main()
