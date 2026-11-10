#!/usr/bin/env python3
"""Minimal flattened-device-tree (DTB) to DTS text decompiler.

Standard library only, so it runs where `dtc` is not installed. The output is
meant for reading and diffing; for round-trip builds use the real `dtc`.

Usage: fdt2dts.py input.dtb [output.dts]
"""
import struct
import sys

FDT_MAGIC = 0xD00DFEED
FDT_BEGIN_NODE, FDT_END_NODE, FDT_PROP, FDT_NOP, FDT_END = 1, 2, 3, 4, 9


def _is_string_list(data: bytes) -> bool:
    if not data or data[-1] != 0:
        return False
    parts = data[:-1].split(b"\0")
    return all(p and all(32 <= c < 127 for c in p) for p in parts)


def _fmt_value(data: bytes) -> str:
    if not data:
        return ""
    if _is_string_list(data):
        parts = data[:-1].split(b"\0")
        return " = " + ", ".join('"%s"' % p.decode().replace('"', '\\"') for p in parts)
    if len(data) % 4 == 0:
        cells = struct.unpack(">%dI" % (len(data) // 4), data)
        return " = <" + " ".join("0x%x" % c for c in cells) + ">"
    return " = [" + " ".join("%02x" % b for b in data) + "]"


def decompile(blob: bytes) -> str:
    magic, totalsize, off_struct, off_strings, off_rsv, version, _, _, size_strings, size_struct = \
        struct.unpack(">10I", blob[:40])
    if magic != FDT_MAGIC:
        raise ValueError("not a DTB (bad magic 0x%08x)" % magic)
    strings = blob[off_strings:off_strings + size_strings]

    def string_at(off: int) -> str:
        end = strings.index(b"\0", off)
        return strings[off:end].decode()

    out = ["/dts-v1/;", ""]
    # memory reservation map
    p = off_rsv
    while True:
        addr, size = struct.unpack(">QQ", blob[p:p + 16])
        p += 16
        if addr == 0 and size == 0:
            break
        out.append("/memreserve/ 0x%x 0x%x;" % (addr, size))

    p = off_struct
    depth = 0
    while True:
        (tag,) = struct.unpack(">I", blob[p:p + 4])
        p += 4
        if tag == FDT_BEGIN_NODE:
            end = blob.index(b"\0", p)
            name = blob[p:end].decode() or "/"
            p = (end + 4) & ~3
            out.append("\t" * depth + "%s {" % name)
            depth += 1
        elif tag == FDT_END_NODE:
            depth -= 1
            out.append("\t" * depth + "};")
        elif tag == FDT_PROP:
            length, nameoff = struct.unpack(">II", blob[p:p + 8])
            p += 8
            data = blob[p:p + length]
            p = (p + length + 3) & ~3
            out.append("\t" * depth + "%s%s;" % (string_at(nameoff), _fmt_value(data)))
        elif tag == FDT_NOP:
            continue
        elif tag == FDT_END:
            break
        else:
            raise ValueError("unknown FDT tag %d at 0x%x" % (tag, p - 4))
    return "\n".join(out) + "\n"


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__, file=sys.stderr)
        return 2
    text = decompile(open(sys.argv[1], "rb").read())
    if len(sys.argv) == 3:
        open(sys.argv[2], "w").write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
