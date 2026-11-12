#!/usr/bin/env python3
"""Build 069: list / extend an Android ramdisk.img (newc cpio, gzip or lz4).

Used to add a minimal ``fstab.<hardware>`` to a COPY of the GSI ramdisk so
first-stage init can mount /system on QEMU. The input file is never modified.

  ramdisk_tool.py list IN
  ramdisk_tool.py add IN OUT --file DEST=SRC [--file DEST=SRC ...]
                             [--file-if-dir DIR:DEST=SRC ...]

``--file-if-dir`` adds DEST only when the ramdisk already contains DIR
(e.g. ``first_stage_ramdisk``). Compression of OUT matches IN; lz4 uses the
legacy frame format the kernel expects (``lz4 -l``, needs the lz4 CLI).
"""

from __future__ import annotations

import argparse
import gzip
from pathlib import Path
import shutil
import subprocess
import sys

NEWC = b"070701"
GZIP_MAGIC = b"\x1f\x8b"
LZ4_LEGACY_MAGIC = b"\x02\x21\x4c\x18"
S_IFDIR, S_IFREG = 0o040000, 0o100000


def detect(data: bytes) -> str:
    if data[:6] == NEWC:
        return "none"
    if data[:2] == GZIP_MAGIC:
        return "gzip"
    if data[:4] == LZ4_LEGACY_MAGIC:
        return "lz4"
    raise ValueError(f"unknown ramdisk format, magic {data[:6].hex()}")


def _lz4() -> str:
    exe = shutil.which("lz4")
    if not exe:
        raise RuntimeError("lz4 CLI not found (needed for lz4 ramdisks)")
    return exe


def decompress(data: bytes) -> tuple[bytes, str]:
    kind = detect(data)
    if kind == "none":
        return data, kind
    if kind == "gzip":
        return gzip.decompress(data), kind
    out = subprocess.run([_lz4(), "-dc"], input=data, capture_output=True, check=True)
    return out.stdout, kind


def compress(data: bytes, kind: str) -> bytes:
    if kind == "none":
        return data
    if kind == "gzip":
        return gzip.compress(data, compresslevel=9, mtime=0)
    out = subprocess.run([_lz4(), "-l", "-12", "-c"], input=data,
                         capture_output=True, check=True)
    return out.stdout


def _pad(n: int) -> int:
    return (4 - n % 4) % 4


def parse(cpio: bytes) -> list[dict]:
    entries, off = [], 0
    while True:
        if cpio[off:off + 6] != NEWC:
            raise ValueError(f"bad cpio header at {off}")
        f = [int(cpio[off + 6 + i * 8: off + 14 + i * 8], 16) for i in range(13)]
        ino, mode, uid, gid, nlink, mtime, size = f[0:7]
        namesize = f[11]
        noff = off + 110
        name = cpio[noff:noff + namesize - 1].decode()
        doff = noff + namesize
        doff += _pad(doff)
        data = cpio[doff:doff + size]
        off = doff + size
        off += _pad(off)
        if name == "TRAILER!!!":
            return entries
        entries.append({"name": name, "mode": mode, "uid": uid, "gid": gid,
                        "nlink": nlink, "mtime": mtime, "data": data,
                        "rdevmajor": f[9], "rdevminor": f[10], "ino": ino})


def build(entries: list[dict]) -> bytes:
    out = bytearray()

    def emit(e: dict, ino: int) -> None:
        name = e["name"].encode() + b"\0"
        fields = [ino, e["mode"], e["uid"], e["gid"], e["nlink"], e["mtime"],
                  len(e["data"]), 0, 0, e.get("rdevmajor", 0),
                  e.get("rdevminor", 0), len(name), 0]
        out.extend(NEWC + b"".join(b"%08x" % v for v in fields))
        out.extend(name)
        out.extend(b"\0" * _pad(len(out)))
        out.extend(e["data"])
        out.extend(b"\0" * _pad(len(out)))

    for i, e in enumerate(entries, start=300000):
        emit(e, i)
    emit({"name": "TRAILER!!!", "mode": 0, "uid": 0, "gid": 0, "nlink": 1,
          "mtime": 0, "data": b""}, 0)
    out.extend(b"\0" * _pad(len(out)))
    return bytes(out)


def describe(e: dict) -> str:
    kind = {S_IFDIR: "d", S_IFREG: "-"}.get(e["mode"] & 0o170000, "?")
    if e["mode"] & 0o170000 == 0o120000:
        return f"l {e['name']} -> {e['data'].decode(errors='replace')}"
    return f"{kind} {oct(e['mode'] & 0o7777)} {len(e['data']):>9} {e['name']}"


def add_files(entries: list[dict], files: list[tuple[str, bytes]]) -> list[dict]:
    names = {e["name"] for e in entries}
    result = [e for e in entries if e["name"] not in {d for d, _ in files}]
    for dest, data in files:
        parts = dest.split("/")
        for i in range(1, len(parts)):
            d = "/".join(parts[:i])
            if d not in names:
                result.append({"name": d, "mode": S_IFDIR | 0o755, "uid": 0,
                               "gid": 0, "nlink": 2, "mtime": 0, "data": b""})
                names.add(d)
        result.append({"name": dest, "mode": S_IFREG | 0o644, "uid": 0, "gid": 0,
                       "nlink": 1, "mtime": 0, "data": data})
        names.add(dest)
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("list")
    pl.add_argument("src", type=Path)
    pa = sub.add_parser("add")
    pa.add_argument("src", type=Path)
    pa.add_argument("dst", type=Path)
    pa.add_argument("--file", action="append", default=[], metavar="DEST=SRC")
    pa.add_argument("--file-if-dir", action="append", default=[],
                    metavar="DIR:DEST=SRC")
    a = p.parse_args(argv)

    cpio, kind = decompress(a.src.read_bytes())
    entries = parse(cpio)
    if a.cmd == "list":
        print(f"# format={kind} entries={len(entries)}")
        for e in entries:
            print(describe(e))
        return 0

    names = {e["name"] for e in entries}
    files: list[tuple[str, bytes]] = []
    for spec in a.file:
        dest, _, src = spec.partition("=")
        files.append((dest.strip("/"), Path(src).read_bytes()))
    for spec in a.file_if_dir:
        cond, _, rest = spec.partition(":")
        dest, _, src = rest.partition("=")
        if cond.strip("/") in names:
            files.append((dest.strip("/"), Path(src).read_bytes()))
    if a.dst.resolve() == a.src.resolve():
        p.error("refusing to overwrite the input ramdisk")
    a.dst.write_bytes(compress(build(add_files(entries, files)), kind))
    print(f"ramdisk_tool: {a.dst} ({kind}, +{len(files)} file(s): "
          f"{', '.join(d for d, _ in files)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
