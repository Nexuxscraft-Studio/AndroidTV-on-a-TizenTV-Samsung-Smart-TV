"""Read-only driver source inventory tests."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


PATH = Path(__file__).resolve().parents[1] / "driver_audit.py"
SPEC = importlib.util.spec_from_file_location("build060_driver_audit", PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class DriverAuditTests(unittest.TestCase):
    def test_sources_are_not_runtime_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "porting/build058/integration/drm/sdp_drm_fence.c"
            source.parent.mkdir(parents=True)
            source.write_text("/* sample */", encoding="utf-8")
            report = mod.inspect(root)
            fence = report["components"]["drm_fence"]
            self.assertTrue(fence["source_present"])
            self.assertEqual(fence["boot_and_runtime"], "UNVERIFIED")
            self.assertFalse(report["components"]["samsung_drm_core_and_gem"]["source_present"])

    def test_optional_external_samsung_media_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "vendor/sdp_drm_nike/sdp_drm_drv.c"
            source.parent.mkdir(parents=True)
            source.write_text("/* vendor source stub */", encoding="utf-8")
            report = mod.inspect(root, root / "vendor")
            core = report["components"]["samsung_drm_core_and_gem"]
            self.assertEqual(core["external_samsung_source_candidates"],
                             ["sdp_drm_nike/sdp_drm_drv.c"])
            self.assertFalse(core["source_present"])


if __name__ == "__main__":
    unittest.main()
