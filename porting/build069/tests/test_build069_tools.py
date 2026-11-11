"""Offline tests for Build 069 helpers (no QEMU, no Android build)."""

from __future__ import annotations

import gzip
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import boot_milestones as bm  # noqa: E402
import ramdisk_tool as rt  # noqa: E402


def sample_entries() -> list[dict]:
    return [
        {"name": "first_stage_ramdisk", "mode": rt.S_IFDIR | 0o755, "uid": 0, "gid": 0,
         "nlink": 2, "mtime": 0, "data": b""},
        {"name": "init", "mode": rt.S_IFREG | 0o750, "uid": 0, "gid": 2000,
         "nlink": 1, "mtime": 0, "data": b"\x7fELF fake init"},
        {"name": "system", "mode": 0o120777, "uid": 0, "gid": 0,
         "nlink": 1, "mtime": 0, "data": b"/system"},
    ]


class RamdiskToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self._t = tempfile.TemporaryDirectory()
        self.d = Path(self._t.name)

    def tearDown(self) -> None:
        self._t.cleanup()

    def test_roundtrip_uncompressed(self) -> None:
        blob = rt.build(sample_entries())
        self.assertEqual(rt.detect(blob), "none")
        back = rt.parse(blob)
        self.assertEqual([e["name"] for e in back], ["first_stage_ramdisk", "init", "system"])
        self.assertEqual(back[1]["data"], b"\x7fELF fake init")
        self.assertEqual(back[1]["gid"], 2000)

    def test_add_gzip_keeps_format_and_input(self) -> None:
        src = self.d / "ramdisk.img"
        src.write_bytes(gzip.compress(rt.build(sample_entries())))
        before = src.read_bytes()
        fstab = self.d / "fstab"
        fstab.write_bytes(b"/dev/block/vda /system ext4 ro wait,first_stage_mount\n")
        out = self.d / "out.img"
        rc = rt.main(["add", str(src), str(out), "--file", f"fstab.qemuarm={fstab}",
                      "--file-if-dir", f"first_stage_ramdisk:first_stage_ramdisk/fstab.qemuarm={fstab}",
                      "--file-if-dir", f"nope:nope/fstab.qemuarm={fstab}"])
        self.assertEqual(rc, 0)
        self.assertEqual(src.read_bytes(), before)
        data, kind = rt.decompress(out.read_bytes())
        self.assertEqual(kind, "gzip")
        names = {e["name"]: e for e in rt.parse(data)}
        self.assertIn("fstab.qemuarm", names)
        self.assertIn("first_stage_ramdisk/fstab.qemuarm", names)
        self.assertNotIn("nope/fstab.qemuarm", names)
        self.assertIn(b"first_stage_mount", names["fstab.qemuarm"]["data"])
        self.assertEqual(names["system"]["mode"], 0o120777)

    def test_add_creates_parent_dirs(self) -> None:
        res = rt.add_files(sample_entries(), [("a/b/c.txt", b"x")])
        names = [e["name"] for e in res]
        self.assertIn("a", names)
        self.assertIn("a/b", names)

    def test_refuses_in_place(self) -> None:
        src = self.d / "r.img"
        src.write_bytes(rt.build(sample_entries()))
        with self.assertRaises(SystemExit):
            rt.main(["add", str(src), str(src)])

    @unittest.skipUnless(shutil.which("lz4"), "lz4 CLI not installed")
    def test_lz4_legacy_roundtrip(self) -> None:
        packed = rt.compress(rt.build(sample_entries()), "lz4")
        self.assertEqual(rt.detect(packed), "lz4")
        data, kind = rt.decompress(packed)
        self.assertEqual(kind, "lz4")
        self.assertEqual(len(rt.parse(data)), 3)

    def test_unknown_format(self) -> None:
        with self.assertRaises(ValueError):
            rt.detect(b"garbage!")


SAMPLE_LOG = """\
[    0.000000] Booting Linux on physical CPU 0x0
[    2.100000] Run /init as init process
[    2.300000] init: init first stage started!
[    2.400000] init: [libfs_mgr] Failed to mount required partitions early ...
[    2.500000] init: InitFatalReboot: signal 6
[    2.600000] reboot: Restarting system
"""


class MilestoneTests(unittest.TestCase):
    def test_first_stage_failure(self) -> None:
        r = bm.analyse(SAMPLE_LOG)
        self.assertEqual(r["highest_milestone"], "first_stage_init")
        self.assertFalse(r["second_stage_reached"])
        self.assertTrue(r["failures"])
        self.assertIn("Failed to mount", r["failures"][0]["context"][-3])

    def test_second_stage(self) -> None:
        log = SAMPLE_LOG.splitlines()[:3] + [
            "init: Switching root to '/system'",
            "init: init second stage started!",
            "init: starting service 'servicemanager'...",
        ]
        r = bm.analyse("\n".join(log))
        self.assertTrue(r["second_stage_reached"])
        self.assertEqual(r["highest_milestone"], "servicemanager")

    def test_empty_log(self) -> None:
        r = bm.analyse("")
        self.assertIsNone(r["highest_milestone"])


if __name__ == "__main__":
    unittest.main()
