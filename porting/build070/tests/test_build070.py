"""Offline tests for the Build 070 tools (no network, no kernel tree)."""
import io
import re
import struct
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

B070 = Path(__file__).resolve().parents[1]
REPO = B070.parents[1]
sys.path.insert(0, str(B070 / "tools"))
import dt_nodes  # noqa: E402
import fetch_sources  # noqa: E402


def make_dtb(nodes):
    """Tiny FDT builder: nodes = [(path, {prop: bytes})] in tree order."""
    strings, offs = bytearray(), {}

    def soff(name):
        if name not in offs:
            offs[name] = len(strings)
            strings.extend(name.encode() + b"\0")
        return offs[name]

    def pad(b):
        while len(b) % 4:
            b.append(0)

    st, depth_stack = bytearray(), []
    for path, props in nodes:
        parts = [p for p in path.split("/") if p]
        while len(depth_stack) > len(parts) or (depth_stack and depth_stack != parts[:len(depth_stack)]):
            st += struct.pack(">I", 2)
            depth_stack.pop()
        name = parts[-1] if parts else ""
        st += struct.pack(">I", 1) + name.encode() + b"\0"
        pad(st)
        depth_stack.append(name) if parts else None
        for k, v in props.items():
            st += struct.pack(">III", 3, len(v), soff(k)) + v
            pad(st)
    for _ in depth_stack:
        st += struct.pack(">I", 2)
    st += struct.pack(">I", 2) + struct.pack(">I", 9)   # end root, FDT_END
    rsv = b"\0" * 16
    off_rsv = 40
    off_struct = off_rsv + len(rsv)
    off_strings = off_struct + len(st)
    total = off_strings + len(strings)
    hdr = struct.pack(">10I", 0xD00DFEED, total, off_struct, off_strings, off_rsv,
                      17, 16, 0, len(strings), len(st))
    return hdr + rsv + bytes(st) + bytes(strings)


def cells(*v):
    return struct.pack(">%dI" % len(v), *v)


SAMPLE = [
    ("/", {"compatible": b"samsung,dtv\0samsung,sdp-nikel\0", "dtsversion": b"nikel-2G\0"}),
    ("/soc", {"compatible": b"simple-bus\0"}),
    ("/soc/sdp_drm@1000", {"compatible": b"samsung,sdp-drm\0", "reg": cells(0, 0x1000, 0, 0x100),
                           "status": b"okay\0"}),
    ("/soc/serial@190a00", {"compatible": b"samsung,sdp-uart2\0"}),
]


class DtbTest(unittest.TestCase):
    def test_parse_and_format(self):
        nodes = dt_nodes.parse(make_dtb(SAMPLE))
        self.assertEqual(list(nodes), ["/", "/soc", "/soc/sdp_drm@1000", "/soc/serial@190a00"])
        self.assertEqual(dt_nodes.fmt(nodes["/soc/sdp_drm@1000"]["reg"]), "<0x0 0x1000 0x0 0x100>")
        self.assertEqual(dt_nodes.fmt(nodes["/"]["compatible"]), '"samsung,dtv", "samsung,sdp-nikel"')

    def test_driver_patterns_select_display_not_uart(self):
        nodes = dt_nodes.parse(make_dtb(SAMPLE))
        sel = [p for p, pr in nodes.items() if dt_nodes.matches(p, pr, dt_nodes.DRIVER_PATTERNS)]
        self.assertIn("/soc/sdp_drm@1000", sel)
        self.assertNotIn("/soc/serial@190a00", sel)

    def test_split_dtbs_finds_both_at_offsets(self):
        a, b = make_dtb(SAMPLE), make_dtb(SAMPLE[:2])
        blob = a + b"\0" * (4096 - len(a)) + b + b"\xff" * 100
        found = fetch_sources.split_dtbs(blob)
        self.assertEqual([o for o, _ in found], [0, 4096])
        self.assertEqual(found[1][1], b)

    def test_split_ignores_fake_magic(self):
        self.assertEqual(fetch_sources.split_dtbs(b"\xd0\x0d\xfe\xed" + b"\0" * 60), [])

    def test_known_hashes_from_build004(self):
        known = fetch_sources.known_dtb_hashes()
        self.assertEqual(sorted(known), [0, 86016])
        self.assertTrue(known[0].startswith("0189cc94"))

    def test_range_file_reads_zip_member(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("decrypted/other.bin", b"x" * 5000)
            z.writestr("decrypted/dtb.bin", make_dtb(SAMPLE))
        data = buf.getvalue()

        class Resp(io.BytesIO):
            def __init__(self, body, start, total):
                super().__init__(body)
                self.status = 206
                self.headers = {"Content-Range": "bytes %d-%d/%d" % (start, start + len(body) - 1, total)}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(req, timeout=None):
            m = re.match(r"bytes=(\d+)-(\d+)", req.headers["Range"])
            s, e = int(m.group(1)), int(m.group(2))
            return Resp(data[s:e + 1], s, len(data))

        f = fetch_sources.HttpRangeFile("https://example.invalid/x.zip", opener=opener)
        f.BLOCK = 512
        self.assertEqual(f.size, len(data))
        with zipfile.ZipFile(f) as z:
            self.assertEqual(z.read("decrypted/dtb.bin"), make_dtb(SAMPLE))


class DownloadTest(unittest.TestCase):
    def test_resumes_after_short_reads(self):
        import tempfile
        payload = bytes(range(256)) * 400          # 102400 bytes
        calls = []

        class Resp(io.BytesIO):
            status = 206

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake(req, timeout=None):
            s, e = map(int, re.match(r"bytes=(\d+)-(\d+)", req.headers["Range"]).groups())
            calls.append(s)
            # every response is cut short after 30000 bytes, like run 43177164692
            return Resp(payload[s:min(e + 1, s + 30000)])

        orig = fetch_sources.urlopen_verbose
        fetch_sources.urlopen_verbose = fake
        try:
            with tempfile.TemporaryDirectory() as d:
                dest = Path(d) / "x.tgz"
                fetch_sources.download("https://example.invalid/x.tgz", dest, len(payload), chunk=50000)
                self.assertEqual(dest.read_bytes(), payload)
        finally:
            fetch_sources.urlopen_verbose = orig
        self.assertEqual(calls[:3], [0, 30000, 60000])


class RunnerContractTest(unittest.TestCase):
    def test_request_env(self):
        txt = (B070 / "runner" / "request.env").read_text()
        kv = dict(l.split("=", 1) for l in txt.splitlines() if l and not l.startswith("#"))
        self.assertIn(kv["MODE"], ("sources", "show", "kernel"))
        self.assertTrue(kv["GPL_DIR"].startswith("/mnt/github-runner/"))
        self.assertRegex(kv["SHOW_LINES"], r"^\d+-\d+$")
        self.assertTrue(kv["REQUEST_ID"])

    def test_workflow_shares_runner_group(self):
        wf = (REPO / ".github" / "workflows" / "build070-drivers.yml").read_text()
        self.assertIn("group: build068-selfhosted-v2", wf)
        self.assertIn("cancel-in-progress: false", wf)
        self.assertIn("paths: ['porting/build070/runner/request.env']", wf)
        self.assertNotIn("ubuntu-", wf)          # GitHub-hosted runners are blocked
        self.assertNotIn("source porting", wf)   # request.env is parsed, never sourced

    def test_scripts_parse(self):
        for s in ("kernel_build.sh", "tools/gpl_inventory.sh"):
            subprocess.run(["bash", "-n", str(B070 / s)], check=True)

    def test_kernel_build_uses_shared_profile(self):
        txt = (B070 / "kernel_build.sh").read_text()
        self.assertIn('build059/kernel/build.sh" "$KSRC" arm android', txt)
        self.assertIn("LINUX_COMMIT=5139929c698c273e07cb0635732f6a918a7b8e78", txt)
        self.assertIn("W=1", txt)


class NikelDeviceTest(unittest.TestCase):
    def test_memfd_instead_of_ashmem(self):
        rc = (REPO / "porting" / "device" / "samsung" / "nikel" / "init.nikel.rc").read_text()
        self.assertIn("setprop sys.use_memfd true", rc)
        self.assertIn("on property:sys.use_memfd=false", rc)
        mk = (REPO / "porting" / "device" / "samsung" / "nikel" / "device.mk").read_text()
        self.assertIn("init.nikel.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.nikel.rc", mk)
        board = (REPO / "porting" / "device" / "samsung" / "nikel" / "BoardConfig.mk").read_text()
        self.assertIn("$(error", board)   # build lock stays


if __name__ == "__main__":
    unittest.main()
