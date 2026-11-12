#!/usr/bin/env python3
"""Build 070: fetch the read-only sources for the driver port onto the runner.

Standard library only. Nothing is written to a TV; files land in OUT_DIR.

  fetch_sources.py dtb URL OUT_DIR
      Reads decrypted/dtb.bin from the FullOS ZIP with HTTP range requests
      (no 1.1 GB download), splits it into the contained DTBs, checks their
      SHA-256 against the values recorded in Build 004
      (reports/hardware_2743.0_build004_final.json) and writes
      OUT_DIR/dtb<N>.dtb + OUT_DIR/dtb<N>.dts + OUT_DIR/dtb-manifest.json.

  fetch_sources.py get URL OUT_DIR
      Downloads one file (e.g. linux-4.1.10-tizen5.5.tgz from the team's
      file share) into OUT_DIR, skips it if the same size is already there,
      records size + SHA-256 in OUT_DIR/files-manifest.json. Exit code 3 if
      the server answers 404 (file not uploaded yet).

  fetch_sources.py dtb URL OUT_DIR   (URL may also point to a bare dtb.bin)

  fetch_sources.py gpl URL OUT_DIR
      Downloads Samsung's GPL package 20_DTV_NikeL.zip (outer ZIP, once),
      extracts the inner 20_DTV_NikeL.zip and from it
      linux-4.1.10-tizen5.5.tgz and tztv-media-nike.tgz into OUT_DIR, plus
      OUT_DIR/gpl-inner-listing.txt and OUT_DIR/gpl-manifest.json.
"""
import hashlib
import io
import json
import os
import struct
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FDT_MAGIC = b"\xd0\x0d\xfe\xed"
GPL_OUTER_SIZE = 743308262          # claude/samsung-gpl-20_DTV_NikeL.md
# Identify as a download tool, not as the default "Python-urllib/x.y" (some
# hosters block it; run 43174876384 got HTTP 403 before the files moved).
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) q60t-build070-fetch/1.0"
GPL_MEMBERS = ("linux-4.1.10-tizen5.5.tgz", "tztv-media-nike.tgz")
DTB_MEMBER = "decrypted/dtb.bin"


def request(url, headers=None):
    h = {"User-Agent": USER_AGENT}
    h.update(headers or {})
    return urllib.request.Request(url, headers=h)


def urlopen_verbose(req, timeout):
    """urlopen that prints status and headers of an HTTP error before raising."""
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        print("HTTP %d for %s" % (e.code, req.full_url), file=sys.stderr)
        for k, v in e.headers.items():
            print("  %s: %s" % (k, v), file=sys.stderr)
        print("  body: %r" % e.read(300), file=sys.stderr)
        raise


class HttpRangeFile(io.RawIOBase):
    """Seekable read-only file over HTTP range requests (block cache)."""

    BLOCK = 1 << 20

    def __init__(self, url, opener=None):
        super().__init__()
        self.url = url
        self.open = opener or urlopen_verbose
        self.pos = 0
        self.cache = {}
        # total size from a one-byte range request ("Content-Range: bytes 0-0/N")
        req = request(url, {"Range": "bytes=0-0"})
        with self.open(req, timeout=60) as r:
            if r.status != 206:
                raise IOError("server does not support Range requests (HTTP %d)" % r.status)
            self.size = int(r.headers["Content-Range"].rsplit("/", 1)[1])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = max(0, base + off)
        return self.pos

    def _block(self, n):
        if n not in self.cache:
            start = n * self.BLOCK
            end = min(self.size, start + self.BLOCK) - 1
            req = request(self.url, {"Range": "bytes=%d-%d" % (start, end)})
            with self.open(req, timeout=120) as r:
                if r.status != 206:
                    raise IOError("server ignored Range request (HTTP %d)" % r.status)
                data = r.read()
            if len(data) != end - start + 1:
                raise IOError("short range read at %d" % start)
            if len(self.cache) > 64:
                self.cache.clear()
            self.cache[n] = data
        return self.cache[n]

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        out = bytearray()
        while n > 0:
            blk = self._block(self.pos // self.BLOCK)
            off = self.pos % self.BLOCK
            chunk = blk[off:off + n]
            out += chunk
            self.pos += len(chunk)
            n -= len(chunk)
        return bytes(out)

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def split_dtbs(blob):
    """Return [(offset, dtb_bytes)] for every valid FDT header in blob."""
    found, pos = [], 0
    while True:
        i = blob.find(FDT_MAGIC, pos)
        if i < 0:
            return found
        if len(blob) - i >= 40:
            _, total, off_struct, off_strings, _, version = struct.unpack(">6I", blob[i:i + 24])
            if (16 <= version <= 17 and 40 <= off_struct < total and off_strings < total
                    and i + total <= len(blob)):
                found.append((i, blob[i:i + total]))
                pos = i + total
                continue
        pos = i + 4


def known_dtb_hashes():
    rep = REPO / "reports" / "hardware_2743.0_build004_final.json"
    data = json.loads(rep.read_text())
    return {t["offset_bytes"]: t["dtb_sha256"] for t in data["trees"]}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def cmd_dtb(url, out):
    sys.path.insert(0, str(REPO / "porting" / "build059" / "tools"))
    import fdt2dts  # noqa: E402  (repo tool, standard library only)

    if url.endswith(".bin"):
        rf = HttpRangeFile(url)
        blob = rf.read()
        print("dtb.bin (direct): %d bytes, sha256 %s" % (len(blob), sha256(blob)))
    else:
        zf = zipfile.ZipFile(HttpRangeFile(url))
        info = zf.getinfo(DTB_MEMBER)
        blob = zf.read(info)
        print("dtb.bin: %d bytes (compressed %d), CRC ok, sha256 %s"
              % (len(blob), info.compress_size, sha256(blob)))
    known = known_dtb_hashes()
    manifest = {"source": url, "member": DTB_MEMBER, "dtb_bin_sha256": sha256(blob), "dtbs": []}
    for n, (off, dtb) in enumerate(split_dtbs(blob)):
        h = sha256(dtb)
        want = known.get(off)
        status = "MATCH Build 004" if want == h else ("MISMATCH (Build 004: %s)" % want if want else "not recorded")
        print("dtb%d @%d: %d bytes sha256 %s  %s" % (n, off, len(dtb), h, status))
        (out / ("dtb%d.dtb" % n)).write_bytes(dtb)
        (out / ("dtb%d.dts" % n)).write_text(fdt2dts.decompile(dtb))
        manifest["dtbs"].append({"name": "dtb%d" % n, "offset": off, "size": len(dtb),
                                 "sha256": h, "build004": status})
        if want and want != h:
            raise SystemExit("dtb%d does not match the Build 004 record" % n)
    if not manifest["dtbs"]:
        raise SystemExit("no DTB found in dtb.bin")
    (out / "dtb-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def remote_size(url):
    req = request(url, {"Range": "bytes=0-0"})
    with urlopen_verbose(req, timeout=60) as r:
        if r.status == 206:
            return int(r.headers["Content-Range"].rsplit("/", 1)[1])
        return int(r.headers["Content-Length"])


def cmd_get(url, out):
    name = url.rsplit("/", 1)[-1]
    try:
        size = remote_size(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("NOT AVAILABLE (404): %s" % url)
            raise SystemExit(3)
        raise
    dest = out / name
    download(url, dest, size)
    mpath = out / "files-manifest.json"
    manifest = json.loads(mpath.read_text()) if mpath.exists() else {}
    manifest[name] = {"source": url, "size": size, "sha256": file_sha256(dest)}
    mpath.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("%s: %d bytes sha256 %s" % (name, size, manifest[name]["sha256"]))


def download(url, dest, size):
    if dest.exists() and dest.stat().st_size == size:
        print("cached %s (%d bytes)" % (dest, size))
        return
    tmp = dest.with_suffix(".part")
    with urlopen_verbose(request(url), timeout=120) as r, open(tmp, "wb") as f:
        done = 0
        while True:
            chunk = r.read(8 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if done % (128 << 20) < (8 << 20):
                print("  %d MiB" % (done >> 20), flush=True)
    if tmp.stat().st_size != size:
        raise SystemExit("download size %d, expected %d" % (tmp.stat().st_size, size))
    tmp.rename(dest)


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cmd_gpl(url, out):
    outer = out / "20_DTV_NikeL.outer.zip"
    download(url, outer, GPL_OUTER_SIZE)
    manifest = {"source": url, "outer_sha256": file_sha256(outer), "members": {}}
    with zipfile.ZipFile(outer) as zo:
        inner_name = next(n for n in zo.namelist() if n.lower().endswith(".zip"))
        inner = out / "20_DTV_NikeL.inner.zip"
        with zo.open(inner_name) as src, open(inner, "wb") as dst:
            while True:
                chunk = src.read(8 << 20)
                if not chunk:
                    break
                dst.write(chunk)
    with zipfile.ZipFile(inner) as zi:
        names = zi.namelist()
        (out / "gpl-inner-listing.txt").write_text(
            "".join("%12d  %s\n" % (zi.getinfo(n).file_size, n) for n in names))
        for want in GPL_MEMBERS:
            match = [n for n in names if n.rsplit("/", 1)[-1] == want]
            if len(match) != 1:
                raise SystemExit("inner ZIP: %s found %d times" % (want, len(match)))
            dest = out / want
            with zi.open(match[0]) as src, open(dest, "wb") as dst:
                while True:
                    chunk = src.read(8 << 20)
                    if not chunk:
                        break
                    dst.write(chunk)
            manifest["members"][want] = {"inner_path": match[0], "size": dest.stat().st_size,
                                         "sha256": file_sha256(dest)}
            print("%s: %d bytes sha256 %s" % (want, dest.stat().st_size, manifest["members"][want]["sha256"]))
    inner.unlink()
    (out / "gpl-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main(argv):
    if len(argv) != 4 or argv[1] not in ("dtb", "gpl", "get"):
        print(__doc__)
        return 2
    out = Path(argv[3])
    out.mkdir(parents=True, exist_ok=True)
    {"dtb": cmd_dtb, "gpl": cmd_gpl, "get": cmd_get}[argv[1]](argv[2], out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
