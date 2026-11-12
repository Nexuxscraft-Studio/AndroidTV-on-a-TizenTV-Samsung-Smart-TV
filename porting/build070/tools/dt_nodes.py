#!/usr/bin/env python3
"""Build 070: list firmware DT nodes as the "Fundstelle" for driver DT nodes.

Standard library only. Usage:

  dt_nodes.py table  DTB            one line per node: path, compatible, reg,
                                    interrupts, status (the index)
  dt_nodes.py detail DTB [PATTERN]  every property of the nodes whose path or
                                    compatible contains one of the driver
                                    patterns (default: DRIVER_PATTERNS)
  dt_nodes.py diff   DTB_A DTB_B    paths/properties that differ (nikel-2G vs
                                    nikel-1.5G profile)

Every printed line starts with the DTB label and the node path, so a value
used in a 6.6 DT can be cited as e.g. "dtb0 (nikel-2G) /soc/sdp_drm@... reg".
"""
import hashlib
import struct
import sys

FDT_MAGIC = 0xD00DFEED
FDT_BEGIN_NODE, FDT_END_NODE, FDT_PROP, FDT_NOP, FDT_END = 1, 2, 3, 4, 9

# Build 070 driver order: display first, then IR, Ethernet, audio, CEC;
# plus GPU/CPU/thermal/memory needed by the shared kernel.
DRIVER_PATTERNS = (
    "sdp-drm", "sdp_drm", "drm", "panel", "tcon", "frc", "sdp1202", "framebuffer",
    "logo", "mali", "gpu", "hdmi", "cec", "irb", "irs", "mac", "emac", "audio",
    "alsa", "sound", "i2s", "tas57", "mfc", "tmu", "thermal", "opp", "cpufreq",
    "clock-controller", "reserved-memory", "memory", "smem", "cma", "chosen",
)


def parse(blob):
    """Return {path: {prop: bytes}} in tree order (dict keeps insertion)."""
    (magic, total, off_struct, off_strings, _rsv, version, _lcv, _boot,
     size_strings, size_struct) = struct.unpack(">10I", blob[:40])
    if magic != FDT_MAGIC:
        raise ValueError("not a DTB (bad magic 0x%08x)" % magic)
    strings = blob[off_strings:off_strings + size_strings]
    pos, end = off_struct, off_struct + size_struct
    stack, nodes = [], {}
    while pos < end:
        (tok,) = struct.unpack(">I", blob[pos:pos + 4])
        pos += 4
        if tok == FDT_BEGIN_NODE:
            nul = blob.index(b"\0", pos)
            name = blob[pos:nul].decode()
            pos = (nul + 4) & ~3
            stack.append(name)
            path = "/" + "/".join(s for s in stack if s)
            nodes[path] = {}
        elif tok == FDT_END_NODE:
            stack.pop()
        elif tok == FDT_PROP:
            ln, nameoff = struct.unpack(">II", blob[pos:pos + 8])
            pos += 8
            pname = strings[nameoff:strings.index(b"\0", nameoff)].decode()
            path = "/" + "/".join(s for s in stack if s)
            nodes[path][pname] = blob[pos:pos + ln]
            pos = (pos + ln + 3) & ~3
        elif tok == FDT_NOP:
            continue
        elif tok == FDT_END:
            break
        else:
            raise ValueError("bad FDT token %d at %d" % (tok, pos - 4))
    return nodes


def fmt(data):
    if not data:
        return "<empty>"
    if data[-1] == 0:
        parts = data[:-1].split(b"\0")
        if all(p and all(32 <= c < 127 for c in p) for p in parts):
            return ", ".join('"%s"' % p.decode() for p in parts)
    if len(data) % 4 == 0:
        return "<" + " ".join("0x%x" % c for c in struct.unpack(">%dI" % (len(data) // 4), data)) + ">"
    return "[" + " ".join("%02x" % b for b in data) + "]"


def label(path, blob, nodes):
    prof = nodes.get("/", {}).get("dtsversion")
    prof = fmt(prof).strip('"') if prof else "?"
    name = path.rsplit("/", 1)[-1]
    return "%s (%s, sha256 %s)" % (name, prof, hashlib.sha256(blob).hexdigest()[:12])


def short(nodes, path, prop):
    v = nodes[path].get(prop)
    return fmt(v) if v is not None else "-"


def cmd_table(dtb):
    blob = open(dtb, "rb").read()
    nodes = parse(blob)
    print("# %s: %d nodes" % (label(dtb, blob, nodes), len(nodes)))
    for p in nodes:
        print("%s | compatible=%s | reg=%s | interrupts=%s | status=%s"
              % (p, short(nodes, p, "compatible"), short(nodes, p, "reg"),
                 short(nodes, p, "interrupts"), short(nodes, p, "status")))


def matches(path, props, patterns):
    hay = (path + " " + fmt(props.get("compatible", b""))).lower()
    return any(pat.lower() in hay for pat in patterns)


def cmd_detail(dtb, patterns):
    blob = open(dtb, "rb").read()
    nodes = parse(blob)
    lab = label(dtb, blob, nodes)
    n = 0
    for p, props in nodes.items():
        if not matches(p, props, patterns):
            continue
        n += 1
        print("== %s %s" % (lab, p))
        for k, v in props.items():
            print("   %s = %s" % (k, fmt(v)))
    print("# %d matching nodes for %s" % (n, ",".join(patterns)))


def cmd_diff(a, b):
    na, nb = parse(open(a, "rb").read()), parse(open(b, "rb").read())
    for p in sorted(set(na) | set(nb)):
        if p not in na or p not in nb:
            print("%s only in %s" % (p, a if p in na else b))
            continue
        for k in sorted(set(na[p]) | set(nb[p])):
            if k == "phandle" or k == "linux,phandle":
                continue
            va, vb = na[p].get(k), nb[p].get(k)
            if va != vb:
                print("%s %s: %s | %s" % (p, k, fmt(va) if va is not None else "-",
                                         fmt(vb) if vb is not None else "-"))


def main(argv):
    if len(argv) >= 3 and argv[1] == "table":
        cmd_table(argv[2])
    elif len(argv) >= 3 and argv[1] == "detail":
        cmd_detail(argv[2], argv[3].split(",") if len(argv) > 3 else DRIVER_PATTERNS)
    elif len(argv) == 4 and argv[1] == "diff":
        cmd_diff(argv[2], argv[3])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
