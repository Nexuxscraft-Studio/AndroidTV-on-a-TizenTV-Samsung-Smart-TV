"""Host-only assertions for the non-loadable Build 052 DRM/GEM API contract."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "porting/build052/contract"
SOURCE = CONTRACT_DIR / "nover_sdp_linux66_contract.c"
README = ROOT / "porting/build052/README.md"
BUILD051_PATCH = ROOT / "porting/build050/patches/0001-nike-linux66-stage1-compile-only.patch"


class TestBuild052DRMContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text()
        cls.readme = README.read_text()

    def test_compiles_as_separate_object_and_does_not_patch_build051(self):
        self.assertEqual((CONTRACT_DIR / "Makefile").read_text().strip().splitlines()[-1],
                         "obj-m += nover_sdp_linux66_contract.o")
        self.assertIn('M="$PWD" nover_sdp_linux66_contract.o', self.readme)
        self.assertTrue(BUILD051_PATCH.is_file())
        self.assertIn("#include <drm/drm_device.h>", BUILD051_PATCH.read_text())

    def test_failed_module_init_prevents_any_driver_registration(self):
        self.assertIn("return -ENODEV;", self.source)
        self.assertIn("module_init(nover_sdp52_contract_init);", self.source)
        self.assertNotIn("module_platform_driver(", self.source)
        self.assertNotIn("platform_driver_register(", self.source)
        self.assertNotIn(".of_match_table", self.source)
        self.assertNotIn('compatible = "samsung', self.source)
        self.assertNotIn("sdp_dp_init(", self.source)
        self.assertNotIn("drm_platform_init(", self.source)

    def test_modern_gem_lifetime_functions_are_structurally_present(self):
        for required in (
            "struct drm_gem_object_funcs", ".free = nover_sdp52_gem_free,",
            "drm_gem_object_init(drm, object, size)",
            "drm_gem_object_release(object)",
            "object->funcs = &nover_sdp52_gem_ops;",
            ".gem_create_object = nover_sdp52_gem_create,",
            "DEFINE_DRM_GEM_FOPS(nover_sdp52_file_ops)",
        ):
            self.assertIn(required, self.source)
        for obsolete in ("drmP.h", ".gem_free_object", ".gem_vm_ops", ".gem_prime_vmap"):
            self.assertNotIn(obsolete, self.source)

    def test_registration_sketch_is_unreachable_from_module_init(self):
        self.assertIn("static int __maybe_unused nover_sdp52_registration_contract", self.source)
        for step in ("drm_dev_alloc(", "drm_dev_register(",
                     "drm_dev_unregister(", "drm_dev_put("):
            self.assertIn(step, self.source)
        init_body = self.source.split("static int __init nover_sdp52_contract_init", 1)[1]
        self.assertIn("return -ENODEV;", init_body.split("module_init", 1)[0])

    def test_explicit_no_hardware_claims(self):
        self.assertIn("Das ist **nicht** der Samsung-Treiber", self.readme)
        self.assertIn("nicht flashbar", self.readme)
        self.assertIn("Build 051 bleibt unverändert", self.readme)
        self.assertIn("Module.symvers", self.readme)


if __name__ == "__main__":
    unittest.main()
