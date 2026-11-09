import tempfile
import unittest
from pathlib import Path

import q60t_binder_lab as binder


class BinderLabTests(unittest.TestCase):
    def test_exact_source_hash_required(self):
        with self.assertRaisesRegex(ValueError, "Originalstand"):
            binder.transform('struct binder_proc { /* malicious or wrong vendor file */ };')

    def test_marker_absent_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "gefunden: 0"):
            binder.replace_once("no matches", "needle", "replacement")

    def test_marker_ambiguous_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "gefunden: 2"):
            binder.replace_once("abc abc", "abc", "replacement")

    def test_shadow_must_have_regular_binder_file(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "shadow"
            (source / "drivers/android").mkdir(parents=True)
            (source / "drivers/android/binder.c").symlink_to("/tmp/no-binder")
            with self.assertRaisesRegex(ValueError, "Symlink"):
                binder.patch_shadow(source, base)

    def test_unknown_binder_source_not_modified(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "shadow"
            (source / "drivers/android").mkdir(parents=True)
            f = source / "drivers/android/binder.c"
            f.write_text("not the Samsung source")
            with self.assertRaisesRegex(ValueError, "Originalstand"):
                binder.patch_shadow(source, base)
            self.assertEqual(f.read_text(), "not the Samsung source")
            self.assertFalse((base / "binder-multicontext-lab.patch").exists())


if __name__ == "__main__":
    unittest.main()
