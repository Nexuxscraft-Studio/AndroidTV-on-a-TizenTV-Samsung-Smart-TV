"""Host-only checks for Build 059 (no kernel tree, no toolchain needed)."""
import json
import re
import struct
import sys
import unittest
from pathlib import Path

B059 = Path(__file__).resolve().parents[1]
REPO = B059.parents[1]
sys.path.insert(0, str(B059 / "tools"))

import fdt2dts  # noqa: E402


def make_fdt(nodes):
    """Build a tiny DTB: nodes = [(name, [(prop, bytes), ...], children)]."""
    strings = bytearray()
    struct_blk = bytearray()

    def stroff(name):
        key = name.encode() + b"\0"
        idx = strings.find(key)
        if idx < 0:
            idx = len(strings)
            strings.extend(key)
        return idx

    def emit(node):
        name, props, children = node
        struct_blk.extend(struct.pack(">I", 1))
        nb = name.encode() + b"\0"
        struct_blk.extend(nb + b"\0" * ((4 - len(nb) % 4) % 4))
        for pname, val in props:
            struct_blk.extend(struct.pack(">III", 3, len(val), stroff(pname)))
            struct_blk.extend(val + b"\0" * ((4 - len(val) % 4) % 4))
        for c in children:
            emit(c)
        struct_blk.extend(struct.pack(">I", 2))

    for n in nodes:
        emit(n)
    struct_blk.extend(struct.pack(">I", 9))
    rsv = struct.pack(">QQ", 0, 0)
    off_rsv = 40
    off_struct = off_rsv + len(rsv)
    off_strings = off_struct + len(struct_blk)
    total = off_strings + len(strings)
    hdr = struct.pack(">10I", 0xD00DFEED, total, off_struct, off_strings, off_rsv,
                      17, 16, 0, len(strings), len(struct_blk))
    return hdr + rsv + bytes(struct_blk) + bytes(strings)


class Fdt2DtsTest(unittest.TestCase):
    def test_decompile_basic(self):
        blob = make_fdt([("", [("compatible", b"samsung,dtv\0samsung,sdp-nikel\0"),
                               ("#address-cells", struct.pack(">I", 2))],
                          [("memory", [("reg", struct.pack(">4I", 0, 0x40000000, 0, 0x07800000))], [])])])
        text = fdt2dts.decompile(blob)
        self.assertIn('compatible = "samsung,dtv", "samsung,sdp-nikel";', text)
        self.assertIn("#address-cells = <0x2>;", text)
        self.assertIn("reg = <0x0 0x40000000 0x0 0x7800000>;", text)
        self.assertTrue(text.startswith("/dts-v1/;"))

    def test_rejects_non_dtb(self):
        with self.assertRaises(ValueError):
            fdt2dts.decompile(b"\0" * 64)


class PatchSeriesTest(unittest.TestCase):
    PATCHES = B059 / "kernel" / "patches"

    def _patch_text(self, needle):
        for p in sorted(self.PATCHES.glob("*.patch")):
            if needle in p.name:
                return p.read_text()
        self.fail("patch %s missing" % needle)

    def test_series_order(self):
        names = [p.name for p in sorted(self.PATCHES.glob("*.patch"))]
        self.assertEqual(len(names), 6)
        self.assertTrue(names[0].startswith("0001-serial"))

    def test_memory_matches_firmware_profiles(self):
        dts = self._patch_text("dts")
        for profile, fname in (("nikel-1_5g", "sdp-nikel-q60t-1g5.dts"),
                               ("nikel-2g", "sdp-nikel-q60t-2g.dts")):
            # extract the added file from the patch
            m = re.search(r"\+\+\+ b/arch/arm64/boot/dts/samsung-sdp/%s\n@@[^\n]*\n(.*?)(?=\ndiff --git|\Z)"
                          % re.escape(fname), dts, re.S)
            self.assertIsNotNone(m, fname)
            body = "\n".join(l[1:] for l in m.group(1).split("\n") if l.startswith("+"))
            mib = dts_memory_mib_text(body)
            ref = json.loads((REPO / "porting" / "profiles" / (profile + ".json")).read_text())
            self.assertAlmostEqual(mib, ref["fdt_memory_reg_advertised_mib"], places=2)

    def test_uart_irq_order_documented(self):
        drv = self._patch_text("serial")
        self.assertIn("platform_get_irq(pdev, 0)", drv)
        self.assertIn("index 0 = TX, index 1 = RX", drv)

    def test_fragments_require_uart_console(self):
        req = (B059 / "kernel" / "configs" / "required-symbols.txt").read_text()
        for sym in ("CONFIG_ARCH_SDP", "CONFIG_SERIAL_SDP_CONSOLE", "CONFIG_ARM_PSCI_FW"):
            self.assertIn(sym, req)


def dts_memory_mib_text(text):
    m = re.search(r"memory@40000000\s*{.*?reg\s*=\s*(.*?);", text, re.S)
    cells = [int(x, 16) for x in re.findall(r"0x[0-9a-fA-F]+", m.group(1))]
    sizes = [(cells[i + 2] << 32) | cells[i + 3] for i in range(0, len(cells), 4)]
    return sum(sizes) / (1 << 20)


if __name__ == "__main__":
    unittest.main()
