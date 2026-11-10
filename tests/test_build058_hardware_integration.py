"""Static/offline checks; these are NOT substitutes for ARM32 kernel builds."""
from pathlib import Path
import hashlib
import subprocess
import tarfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "porting/build058/integration"
MEDIA = ROOT / ".build050_vendor/srcarchives/tztv-media-nike.tgz"
ORIGINAL_KERNEL = ROOT / ".build050_vendor/srcarchives/linux-4.1.10-tizen5.5.tgz"


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
        self.assertIn("required_objects=(", src)
        self.assertIn("Still blocked:", src)
        self.assertIn("Refusing to overwrite existing output directory", src)
        self.assertIn("original_drm_extract", src)
        self.assertIn("samsung_drm_stage1", src)
        self.assertIn("samsung_drm_stage2", src)
        self.assertNotIn("insmod ", src)
        self.assertNotIn("modprobe ", src)

    def test_objects_and_modpost_are_reported_independently(self):
        src = (DIR / "run-arm32-compile-only.sh").read_text()
        self.assertIn('"${name}.o"', src)
        self.assertIn('"${label}_modpost"', src)
        self.assertIn("SKIPPED_OBJECT_ONLY", src)
        self.assertIn("BLOCKED_NO_SYMVERS", src)
        self.assertIn("Module.symvers", src)
        self.assertIn("BUILD058_FULL_KERNEL", src)
        self.assertIn("arm32_full_kernel_for_symvers", src)
        self.assertIn("samsung_drm_tztv_header", src)

    def test_cpufreq_6_6_api_and_name_size(self):
        src = (ROOT / "porting/build058/cpu/kernel/sdp_nikel_cpufreq.c").read_text()
        self.assertIn("nikel_cpu_verify(struct cpufreq_policy_data *policy)", src)
        self.assertNotIn("nikel_cpu_verify(struct cpufreq_policy *policy)", src)
        self.assertIn('.name = "sdp-nikel-off"', src)
        self.assertLess(len("sdp-nikel-off"), 16)
        self.assertIn("NIKEL_CPU_BUILD058_OFFLINE_ONLY 1", src)

    def test_original_early_header_recovered_without_fake_vendor_abi(self):
        compatibility = DIR / "drm/legacy-include/trace/early.h"
        code = compatibility.read_text()
        self.assertIn("2014 Roman Pen", code)
        self.assertIn("trace_early_message", code)
        self.assertFalse((DIR / "drm/legacy-include/drm/drm_tztv.h").exists())
        if ORIGINAL_KERNEL.is_file():
            with tarfile.open(ORIGINAL_KERNEL) as archive:
                old = archive.extractfile("linux-4.1.10/include/trace/early.h").read().decode()
                self.assertIn("trace_early_message", old)

    def test_published_archives_do_not_contain_missing_vendor_abi(self):
        for path in (MEDIA, ORIGINAL_KERNEL):
            if not path.is_file():
                self.skipTest("local Samsung source archives unavailable")
            with tarfile.open(path) as archive:
                self.assertFalse(any(name.endswith("/drm_tztv.h")
                                     for name in archive.getnames()))

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
