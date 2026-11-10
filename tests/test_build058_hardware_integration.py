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
        self.assertIn("sdp_drm_drv sdp_drm_gem", src)

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


class Build058RunnerModes(unittest.TestCase):
    """Runner argument/toolchain guards, executed against a fake kernel tree.

    These tests never compile anything; they prove the runner refuses bad
    input *before* creating an output directory.
    """

    RUNNER = DIR / "run-arm32-compile-only.sh"

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        kernel = self.tmp / "linux"
        (kernel / "drivers/gpu/drm/panfrost").mkdir(parents=True)
        (kernel / "drivers/gpu/drm/panfrost/Kconfig").write_text("# fake\n")
        (kernel / "Makefile").write_text("kernelversion:\n\t@echo 6.6.162\n")
        self.kernel = kernel

    def tearDown(self):
        self._tmp.cleanup()

    def run_runner(self, vendor, out, **env_overrides):
        import os
        env = {k: v for k, v in os.environ.items()
               if k not in ("CROSS_COMPILE", "BUILD058_TOOLCHAIN", "LLVM")}
        env.update(env_overrides)
        return subprocess.run(["bash", str(self.RUNNER), str(self.kernel), vendor, str(out)],
                              capture_output=True, text=True, env=env)

    def test_rejects_unknown_toolchain_without_output(self):
        out = self.tmp / "out"
        proc = self.run_runner("--no-vendor-drm", out, BUILD058_TOOLCHAIN="msvc")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("BUILD058_TOOLCHAIN must be gcc or llvm", proc.stderr)
        self.assertFalse(out.exists())

    def test_missing_gcc_cross_compiler_is_refused(self):
        out = self.tmp / "out"
        proc = self.run_runner("--no-vendor-drm", out, BUILD058_TOOLCHAIN="gcc",
                               CROSS_COMPILE="q60t-nonexistent-")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Missing required tool: q60t-nonexistent-gcc", proc.stderr)
        self.assertFalse(out.exists())

    def test_vendor_archive_still_pinned(self):
        bogus = self.tmp / "tztv-media-nike.tgz"
        bogus.write_bytes(b"not the Samsung archive")
        out = self.tmp / "out"
        proc = self.run_runner(str(bogus), out)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("SHA256 mismatch", proc.stderr)
        self.assertFalse(out.exists())

    def test_refuses_existing_output(self):
        out = self.tmp / "out"
        out.mkdir()
        proc = self.run_runner("--no-vendor-drm", out)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Refusing to overwrite", proc.stderr)

    def test_no_vendor_mode_never_claims_samsung_drm(self):
        src = self.RUNNER.read_text()
        self.assertIn("SKIPPED_NO_VENDOR_ARCHIVE", src)
        self.assertIn("REPO_OBJECTS_ONLY", src)
        self.assertIn("Samsung DRM Core/GEM was NOT attempted", src)
        # Vendor objects remain required whenever the archive is supplied.
        self.assertIn('required_objects+=(sdp_drm_drv_elf sdp_drm_gem_elf)', src)

    def test_llvm_environment_is_not_inherited(self):
        src = self.RUNNER.read_text()
        # Kbuild enables LLVM for any non-empty value, including LLVM=0.
        self.assertIn("env -u LLVM -u LLVM_IAS make", src)
        self.assertIn("make_toolchain=(LLVM=1)", src)
        self.assertIn("Class:[[:space:]]*ELF32", src)


class Build058SdpDrmAbiInventory(unittest.TestCase):
    """Synthetic archive only; never contains Samsung code."""

    TOOL = DIR / "inventory-sdp-drm-abi.py"

    def make_archive(self, tmp: Path) -> Path:
        import io
        files = {
            "tztv-media-nike/sdp_drm_nike/sdp_drm_drv.h":
                "#define DRM_SDP_VBLANK_DP 3\n"
                "enum sdp_inst {\n  DRM_DPINST_MAIN = 0,\n  DRM_DPINST_SUB,\n};\n",
            "tztv-media-nike/sdp_drm_nike/sdp_drm_drv.c":
                "#include <drm/drm_tztv.h>\n#include \"sdp_drm_drv.h\"\n"
                "/* DRM_SDP_IN_COMMENT_ONLY */\n"
                "int f(void) { return g(DRM_DPINST_MAIN,\n   DRM_SDP_COLOR_HDR,\n 0)"
                " + DRM_SDP_VBLANK_DP + DRM_IOCTL_SDP_QPI_GET_POST_CRC; }\n",
            "tztv-media-nike/sdp_drm_nike/drm_gem_cma_helper.h": "struct x { int num_slots; };\n",
        }
        path = tmp / "synthetic.tgz"
        with tarfile.open(path, "w:gz") as archive:
            for name, text in files.items():
                data = text.encode()
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        return path

    def run_tool(self, *args):
        return subprocess.run(["python3", "-I", str(self.TOOL), *map(str, args)],
                              capture_output=True, text=True)

    def test_separates_defined_from_candidate_identifiers(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            archive = self.make_archive(tmp)
            out = tmp / "report.json"
            proc = self.run_tool(archive, out, "--allow-unpinned")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(out.read_text())
        undefined = report["identifiers_used_but_undefined"]
        defined = report["identifiers_defined_in_archive"]
        self.assertIn("DRM_SDP_VBLANK_DP", defined)
        self.assertIn("DRM_DPINST_MAIN", defined)
        self.assertIn("DRM_DPINST_SUB", defined)
        # A call-argument continuation line is NOT an enum definition.
        self.assertIn("DRM_SDP_COLOR_HDR", undefined)
        self.assertIn("DRM_IOCTL_SDP_QPI_GET_POST_CRC", undefined)
        self.assertNotIn("DRM_SDP_IN_COMMENT_ONLY", undefined)
        self.assertEqual(report["files_including_drm_tztv_h"], ["sdp_drm_drv.c"])
        self.assertEqual(report["samsung_local_cma_helper"], ["drm_gem_cma_helper.h"])
        self.assertFalse(report["archive_sha256_pinned"])
        self.assertNotIn("value", json.dumps(undefined))

    def test_refuses_unpinned_archive_and_existing_output(self):
        import tempfile
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            archive = self.make_archive(tmp)
            proc = self.run_tool(archive, tmp / "r.json")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("SHA256 mismatch", proc.stderr)
            existing = tmp / "exists.json"
            existing.write_text("{}")
            proc = self.run_tool(archive, existing, "--allow-unpinned")
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(existing.read_text(), "{}")


class Build058CompileWorkflow(unittest.TestCase):
    WORKFLOW = ROOT / ".github/workflows/build058-arm32-compile.yml"

    def test_workflow_pins_kernel_and_skips_vendor(self):
        text = self.WORKFLOW.read_text()
        self.assertIn("LINUX_TAG: v6.6.162", text)
        self.assertIn("LINUX_COMMIT: 5139929c698c273e07cb0635732f6a918a7b8e78", text)
        self.assertIn('test "$actual" = "$LINUX_COMMIT"', text)
        self.assertIn("--no-vendor-drm", text)
        self.assertIn("toolchain: [gcc, llvm]", text)
        self.assertIn("contents: read", text)
        for forbidden in ("insmod", "modprobe", "tztv-media-nike.tgz", "secrets."):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
