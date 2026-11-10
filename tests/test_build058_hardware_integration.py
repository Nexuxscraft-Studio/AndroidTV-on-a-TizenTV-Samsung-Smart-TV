"""Static/offline checks; these are NOT substitutes for ARM32 kernel builds."""
from pathlib import Path
import hashlib
import subprocess
import tarfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "porting/build058/integration"
MEDIA = ROOT / ".build050_vendor/srcarchives/tztv-media-nike.tgz"


class Build058Integration(unittest.TestCase):
    def test_pinned_samsung_media(self):
        if not MEDIA.is_file():
            self.skipTest("local vendor archive absent; validated at runner entry")
        h = hashlib.sha256()
        with MEDIA.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                h.update(chunk)
        self.assertEqual(h.hexdigest(),
                         "40c2a25eba331b8b04d8d81baf76061493f15f228a74893c7f825f7a1da724b6")
        with tarfile.open(MEDIA) as archive:
            for name in ("sdp_drm_util.c", "sdp_drm_drv.c", "sdp_drm_gem.c"):
                self.assertIsNotNone(archive.getmember(f"tztv-media-nike/sdp_drm_nike/{name}"))

    def test_script_syntax(self):
        runner = DIR / "run-arm32-compile-only.sh"
        subprocess.run(["bash", "-n", str(runner)], check=True)

    def test_refuses_missing_parameters(self):
        runner = DIR / "run-arm32-compile-only.sh"
        proc = subprocess.run(["bash", str(runner)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Linux", proc.stderr.lower().replace("linux", "Linux"))

    def test_runner_guards_and_real_panfrost(self):
        src = (DIR / "run-arm32-compile-only.sh").read_text()
        self.assertIn("6.6.162", src)
        self.assertIn("CONFIG_DRM_PANFROST=m", src)
        self.assertIn("drivers/gpu/drm/panfrost/panfrost.o", src)
        self.assertIn("check_arm_object", src)
        self.assertIn("Refusing to overwrite existing output directory", src)
        self.assertIn("original_drm_extract", src)
        self.assertIn("samsung_drm_stage1", src)
        self.assertIn("samsung_drm_stage2", src)
        self.assertNotIn("insmod ", src)
        self.assertNotIn("modprobe ", src)

    def test_samsung_utility_real_api_port(self):
        c_src = (DIR / "drm/sdp_drm_util.c").read_text()
        header = (DIR / "drm/sdp_drm_util.h").read_text()
        self.assertNotIn("drmP.h", header)
        self.assertIn("copy_from_user", c_src)
        self.assertIn("copy_to_user", c_src)
        self.assertIn("msleep(msecs)", c_src)
        self.assertIn("readl_mask2", c_src)
        self.assertIn("EXPORT_SYMBOL_GPL", c_src)
        self.assertIn("(mask >> 32)", c_src)
        self.assertNotIn("asm volatile", c_src)
        self.assertIn("GPL-2.0-only", c_src)

    def test_samsung_dma_fence_port(self):
        c_src = (DIR / "drm/sdp_drm_fence.c").read_text()
        header = (DIR / "drm/sdp_drm_fence.h").read_text()
        self.assertIn("struct dma_fence", header)
        self.assertIn("dma_fence_context_alloc", c_src)
        self.assertIn("dma_fence_init", c_src)
        self.assertIn("dma_fence_default_wait", c_src)
        self.assertIn("kref_put", c_src)
        self.assertNotIn("linux/fence.h", header)
        self.assertNotIn("drmP.h", header)

    def test_preserves_offline_prototypes(self):
        for file in (
            ROOT / "porting/build058/kernel/sdp_nikel_gpu_clkrst.c",
            ROOT / "porting/build058/cpu/kernel/sdp_nikel_cpu_clk.c",
            ROOT / "porting/build058/cpu/kernel/sdp_nikel_cpufreq.c",
            ROOT / "porting/build058/cpu/kernel/sdp_nikel_thermal.c",
        ):
            self.assertTrue(file.is_file())
            self.assertIn("return dev_err_probe(", file.read_text())


if __name__ == "__main__":
    unittest.main()
