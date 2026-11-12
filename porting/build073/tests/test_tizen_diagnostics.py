"""Offline structural tests for the read-only Samsung TV 5.5 diagnostic app."""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / "tizen-diagnostics"
XMLNS = {
    "w": "http://www.w3.org/ns/widgets",
    "t": "http://tizen.org/ns/widgets",
}


class TizenDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = ET.parse(ROOT / "config.xml").getroot()
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.script = (ROOT / "js/app.js").read_text(encoding="utf-8")
        cls.style = (ROOT / "css/style.css").read_text(encoding="utf-8")

    def test_manifest_has_correct_target(self):
        app = self.manifest.find("t:application", XMLNS)
        profile = self.manifest.find("t:profile", XMLNS)
        self.assertIsNotNone(app)
        self.assertEqual(app.get("id"), "NvxQ60T073.Diagnostics")
        self.assertEqual(app.get("package"), "NvxQ60T073")
        self.assertEqual(len(app.get("package")), 10)
        self.assertEqual(app.get("required_version"), "5.5")
        self.assertEqual(profile.get("name"), "tv-samsung")

    def test_only_public_read_privileges(self):
        privileges = {elem.get("name") for elem in
                      self.manifest.findall("t:privilege", XMLNS)}
        self.assertEqual(privileges, {
            "http://tizen.org/privilege/system",
            "http://developer.samsung.com/privilege/productinfo",
        })

    def test_assets_exist(self):
        self.assertIn('src="js/app.js"', self.html)
        self.assertIn('href="css/style.css"', self.html)
        self.assertIn('src="$WEBAPIS/webapis/webapis.js"', self.html)
        self.assertTrue(self.script.strip().endswith("}());"))
        self.assertIn("@media", self.style)

    def test_only_known_public_system_properties(self):
        requested = re.findall(r'\{\s*id:\s*"([A-Z_]+)"\s*,\s*fields:', self.script)
        self.assertEqual(requested, ["BUILD", "CPU", "MEMORY", "DISPLAY", "PANEL"])
        self.assertIn("tizen.systeminfo.getPropertyValue(", self.script)

    def test_no_unsafe_side_effects_or_unique_identifiers(self):
        self.assertNotIn('safeProductCall(api, "getDuid"', self.script)
        self.assertNotIn('"http://tizen.org/system/tizenid"', self.script)
        for prohibited in ("XMLHttpRequest", "fetch(", "WebSocket(",
                           "kexec", "sdb shell", "getSystemConfig(",
                           "setSystemConfig(", "localStorage.", "getDuid()"):
            self.assertNotIn(prohibited, self.script)

    def test_unavailable_explicit(self):
        self.assertIn("Nicht verfügbar", self.script)
        self.assertIn("Nicht unterstützt", self.script)
        self.assertIn("API meldet nur Speicherdruck", self.script)
        self.assertIn("Keine offizielle API", self.script)

    def test_remote_key_handling(self):
        self.assertIn("code === 10009", self.script)
        self.assertIn("code === 38 || code === 40", self.script)
        self.assertIn('getElementById("refresh")', self.script)


if __name__ == "__main__":
    unittest.main()
