"""Exercise userspace_pipeline.sh stages against a fake LineageOS tree.

No network, no repo, no real Android build: build/envsetup.sh is a stub that
defines breakfast/get_build_var/mka, so the pipeline's own logic (target check,
pure-32-bit guard, verify hand-off, emulator SKIP, handback) is what is tested.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
SCRIPT = HERE / "userspace_pipeline.sh"
sys.path.insert(0, str(HERE / "tests"))
from test_verify_userspace_artifacts import make_good_tree  # noqa: E402

PRODUCTS_MK = """\
PRODUCT_MAKEFILES := \\
    $(LOCAL_DIR)/lineage_gsi_tv_arm.mk \\
    $(LOCAL_DIR)/lineage_sdk_tv_arm.mk
"""

ENVSETUP = """\
# stub envsetup for tests
breakfast() { echo "lunch lineage_$1-bp1a-$2"; export T_PRODUCT="lineage_$1"; }
lunch() { echo "lunch $1"; export T_PRODUCT="${1%%-*}"; }
get_build_var() {
  case "$1" in
    TARGET_PRODUCT) echo "$T_PRODUCT" ;;
    TARGET_RELEASE) echo bp1a ;;
    TARGET_BUILD_VARIANT) echo eng ;;
    TARGET_ARCH) echo "${FAKE_ARCH:-arm}" ;;
    TARGET_2ND_ARCH) echo "${FAKE_ARCH2:-}" ;;
    TARGET_ARCH_VARIANT) echo armv7-a-neon ;;
    TARGET_CPU_ABI) echo armeabi-v7a ;;
    PRODUCT_OUT) echo out/target/product/generic ;;
  esac
}
mka() { echo "mka $*" > "$PWD/mka-called"; return "${FAKE_MKA_RC:-0}"; }
"""


def fake_tree(root: Path) -> None:
    prod = root / "vendor/lineage/build/target/product"
    prod.mkdir(parents=True)
    (prod / "AndroidProducts.mk").write_text(PRODUCTS_MK)
    (prod / "lineage_sdk_tv_arm.mk").write_text("# stub\n")
    (prod / "lineage_gsi_tv_arm.mk").write_text("# stub\n")
    (root / "vendor/lineage/vars").mkdir(parents=True)
    (root / "vendor/lineage/vars/aosp_target_release").write_text(
        "# Updated manually\naosp_target_release=bp1a\n")
    atv = root / "device/google/atv/products"
    atv.mkdir(parents=True)
    (atv / "sdk_atv_armv7.mk").write_text("# stub\n")
    (atv / "aosp_tv_arm.mk").write_text("# stub\n")
    (root / "build").mkdir()
    (root / "build/envsetup.sh").write_text(ENVSETUP)
    make_good_tree(root / "out/target/product/generic")


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.los = base / "los"
        self.work = base / "work"
        self.los.mkdir()
        fake_tree(self.los)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_pipeline(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        e = dict(os.environ)
        e.update(env or {})
        return subprocess.run(
            ["bash", str(SCRIPT), "--los-dir", str(self.los), "--work-dir",
             str(self.work), *args],
            capture_output=True, text=True, env=e, timeout=120)

    def test_help_and_bad_option(self) -> None:
        self.assertEqual(subprocess.run(["bash", str(SCRIPT), "--help"],
                                        capture_output=True).returncode, 0)
        self.assertEqual(self.run_pipeline("--bogus").returncode, 64)
        self.assertEqual(self.run_pipeline("--target", "sdk_tv_arm64").returncode, 64)
        self.assertEqual(self.run_pipeline("--only", "nope").returncode, 64)

    def test_dry_run_changes_nothing(self) -> None:
        r = self.run_pipeline("--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("repo init", r.stderr.replace("'", ""))
        self.assertIn('lunch "lineage_sdk_tv_arm-${release}-eng"', r.stderr)
        self.assertFalse(self.work.exists())

    def test_check_build_verify_emulator_handback(self) -> None:
        for stage in ("check-target", "build", "verify", "emulator", "handback"):
            r = self.run_pipeline("--only", stage)
            self.assertEqual(r.returncode, 0, f"{stage}: {r.stderr}")
        ct = (self.work / "check-target.json").read_text()
        self.assertIn('"lunch": "lineage_sdk_tv_arm-bp1a-eng"', ct)
        self.assertIn('"goldfish_arm32_kernel_board": "absent"', ct)
        self.assertTrue((self.los / "mka-called").exists())
        self.assertIn('"overall": "PASS"', (self.work / "verify.json").read_text())
        self.assertTrue((self.work / "emulator.txt").read_text().startswith("SKIPPED"))
        tars = list(self.work.glob("handback-*.tar.gz"))
        self.assertEqual(len(tars), 1)
        with tarfile.open(tars[0]) as tf:
            names = tf.getnames()
        self.assertIn("handback/verify.json", names)
        self.assertIn("handback/system_build.prop", names)
        # stage markers -> rerun skips
        r = self.run_pipeline("--only", "build")
        self.assertIn("already done", r.stderr)

    def _fake_surfaceflinger(self) -> Path:
        """frameworks/native git project with the lines los-patch 0001 touches."""
        import subprocess
        proj = self.los / "frameworks/native"
        sf = proj / "services/surfaceflinger/SurfaceFlinger.cpp"
        sf.parent.mkdir(parents=True, exist_ok=True)
        lines = ["// l%d" % i for i in range(1, 3817)] + [
            "    ui::PixelFormat pixelFormat = static_cast<ui::PixelFormat>(PIXEL_FORMAT_UNKNOWN);",
            "    if (state.physical) {",
            "        resolution = state.physical->activeMode->getResolution();",
            "        pixelFormat = static_cast<ui::PixelFormat>(PIXEL_FORMAT_RGBA_8888);",
            "    } else if (state.surface != nullptr) {",
            "        int status = state.surface->query(NATIVE_WINDOW_WIDTH, &resolution.width);",
            '        ALOGE_IF(status != NO_ERROR, "Unable to query width (%d)", status);',
            "// end"]
        sf.write_text("\n".join(lines) + "\n")
        subprocess.run(["git", "init", "-q", str(proj)], check=True)
        return sf

    def test_qemu_arm_tv_device_is_installed_from_repo(self) -> None:
        (self.los / "device/google/atv/products/atv_generic_system.mk").write_text("# stub\n")
        sf = self._fake_surfaceflinger()
        r = self.run_pipeline("--only", "check-target", "--target", "qemu_arm_tv")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pixelFormat = defaultCompositionPixelFormat;", sf.read_text())
        self.assertIn("los-patch applied", r.stderr)
        # second run: patch is recognised as applied, not applied twice
        r = self.run_pipeline("--only", "check-target", "--target", "qemu_arm_tv", "--force")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("los-patch already applied", r.stderr)
        dev = self.los / "device/nexuxscraft/qemu_arm_tv"
        self.assertTrue((dev / "BoardConfig.mk").is_file())
        self.assertIn("lineage_qemu_arm_tv.mk", (dev / "AndroidProducts.mk").read_text())
        ct = (self.work / "check-target.json").read_text()
        self.assertIn('"lunch": "lineage_qemu_arm_tv-bp1a-userdebug"', ct)

    def test_missing_target_is_rejected(self) -> None:
        (self.los / "vendor/lineage/build/target/product/AndroidProducts.mk").write_text(
            "PRODUCT_MAKEFILES :=\n")
        r = self.run_pipeline("--only", "check-target")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("NOT in", r.stderr)

    def test_build_guard_rejects_multilib(self) -> None:
        r = self.run_pipeline("--only", "build", env={"FAKE_ARCH2": "arm"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("exit 94", r.stderr)
        self.assertFalse((self.los / "mka-called").exists())

    def test_build_guard_rejects_arm64(self) -> None:
        r = self.run_pipeline("--only", "build", env={"FAKE_ARCH": "arm64"})
        self.assertIn("exit 93", r.stderr)

    def test_mka_failure_propagates(self) -> None:
        r = self.run_pipeline("--only", "build", env={"FAKE_MKA_RC": "1"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("exit 95", r.stderr)
        self.assertFalse((self.work / "state/build.done").exists())

    def test_verify_fail_stops(self) -> None:
        self.assertEqual(self.run_pipeline("--only", "build").returncode, 0)
        (self.los / "out/target/product/generic/system/lib64").mkdir()
        r = self.run_pipeline("--only", "verify")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("verify: FAIL", r.stderr)


if __name__ == "__main__":
    unittest.main()
