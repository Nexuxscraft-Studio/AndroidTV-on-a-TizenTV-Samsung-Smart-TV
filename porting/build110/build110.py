#!/usr/bin/env python3
"""Build and verify the BUILD110 offline bundle; never connects to a TV."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zipfile
import zlib

HERE = Path(__file__).resolve().parent
SOURCE = "d5db24db1417d725b3948b908a8057db5f742b564f918e72f320660c5e95440d"
CI_SOURCE = "9a0e3731d668ce5e48fe4ff7183c4e747658e0978b6d359c65bdd5b036e1b1df"
MARKER = b"<5>BUILD110_INITRAMFS_OK pid1\n"
KERNEL = "zImage-modular"
DTBS = tuple(f"sdp-nikel-q60t-{p}.dtb" for p in ("1g5", "2g"))
FILES = (KERNEL, *DTBS, "initramfs.cpio", "report.json", "SHA256SUMS")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def init():
    # ARM EABI: write(1, marker+3, len-3); open("/dev/kmsg", O_WRONLY);
    # if opened, write(fd, marker, len); loop in pause(). No other device I/O.
    words = (
        0xe3a00001, 0xe28f103f, 0xe3a02000 + len(MARKER)-3, 0xe3a07004,
        0xef000000, 0xe28f0044, 0xe3a01001, 0xe3a07005, 0xef000000,
        0xe3500000, 0xba000003, 0xe28f1014, 0xe3a02000 + len(MARKER),
        0xe3a07004, 0xef000000, 0xe3a0701d, 0xef000000, 0xeafffffd,
    )
    # ADR immediates depend on ARM PC = instruction address + 8.
    words = list(words)
    words[1] = 0xe28f1000 | (72 + 3 - (4 + 8))
    words[5] = 0xe28f0000 | (72 + len(MARKER) - (20 + 8))
    words[11] = 0xe28f1000 | (72 - (44 + 8))
    code = struct.pack("<18I", *words) + MARKER + b"/dev/kmsg\0"
    ident = b"\x7fELF\x01\x01\x01" + bytes(9)
    base = 0x10000
    size = 84 + len(code)
    return (struct.pack("<16sHHIIIIIHHHHHH", ident, 2, 40, 1, base+84,
                        52, 0, 0x05000000, 52, 32, 1, 0, 0, 0)
            + struct.pack("<8I", 1, 0, base, base, size, size, 5, 4096) + code)


def cpio():
    out = bytearray()
    entries = [
        ("dev", 0o040755, b"", 0, 0),
        ("dev/console", 0o020600, b"", 5, 1),
        ("dev/kmsg", 0o020600, b"", 1, 11),
        ("init", 0o100755, init(), 0, 0),
        ("TRAILER!!!", 0, b"", 0, 0),
    ]
    for ino, (name, mode, data, major, minor) in enumerate(entries, 1):
        name = name.encode() + b"\0"
        fields = (ino, mode, 0, 0, 2 if mode == 0o040755 else 1,
                  0, len(data), 0, 0, major, minor, len(name), 0)
        for part in (b"070701" + "".join(f"{v:08x}" for v in fields).encode() + name, data):
            out.extend(part)
            out.extend(bytes(-len(out) % 4))
    return bytes(out)


def config(image):
    require(image[36:40] == b"\x18\x28\x6f\x01", "ARM zImage magic")
    for match in re.finditer(b"\x1f\x8b\x08", image):
        try:
            raw = zlib.decompressobj(31).decompress(image[match.start():], 64 << 20)
        except zlib.error:
            continue
        if b"IKCFG_ST" in raw and b"Linux version 6.6.162 " in raw:
            start = raw.index(b"IKCFG_ST") + 8
            end = raw.index(b"IKCFG_ED", start)
            cfg = gzip.decompress(raw[start:end]).decode()
            return dict(re.findall(r"^(CONFIG_\w+)=(.*)$", cfg, re.M))
    raise ValueError("Linux 6.6.162 embedded kernel config not found")


def board(blob, profile, directory):
    path = Path(directory) / profile
    path.write_bytes(blob)

    def fdt(*args):
        return subprocess.check_output(["fdtget", *args], text=True).split()

    def get(node, prop, kind="s", default=None):
        return fdt("-t", kind, "-d", "-" if default is None else default,
                   str(path), node, prop)

    def children(node):
        return fdt("-l", str(path), node)

    def disabled(node):
        return get(node, "status") == ["disabled"]

    root = get("/", "compatible")
    require(root[0] == f"samsung,q60t-nikel-{profile}", "board compatible")
    cpus = children("/cpus")
    require(len(cpus) == 4 and all(
        get("/cpus/"+n, "compatible") == ["arm,cortex-a57"]
        and get("/cpus/"+n, "enable-method") == ["psci"]
        and get("/cpus/"+n, "reg", "x") == [str(i)]
        and not disabled("/cpus/"+n) for i, n in enumerate(sorted(cpus))),
        "CPU topology or PSCI binding")
    require(get("/psci", "method") == ["smc"], "PSCI method")
    soc = "/soc@0"
    gic = soc + "/interrupt-controller@431000"
    require(get(gic, "compatible") == ["arm,gic-400"] and not disabled(gic)
            and "interrupt-controller" in fdt("-p", str(path), gic)
            and get("/", "interrupt-parent", "x") == get(gic, "phandle", "x")
            and get(gic, "#interrupt-cells", "x") == ["3"]
            and get(gic, "reg", "x") == ["431000", "1000", "432000", "1000"],
            "GIC binding")
    memory = [n for n in children("/") if n.startswith("memory@")]
    require(len(memory) == 1 and get("/", "#address-cells", "x") == ["2"]
            and get("/", "#size-cells", "x") == ["2"], "RAM node/cells")
    cells = [int(n, 16) for n in get("/"+memory[0], "reg", "x")]
    require(len(cells) == (16 if profile == "1g5" else 12), "RAM banks")
    banks = [(a, a+s) for hi, a, szhi, s in zip(*(iter(cells),)*4)
             if hi == szhi == 0 and s > 0 and a+s <= 2**32]
    require(len(banks)*4 == len(cells)
            and all(x[1] <= y[0] for x, y in zip(banks, banks[1:])), "RAM bounds")
    # These exact BUILD108 DTBs lack the stock reserved-memory node and map.
    off = struct.unpack_from(">I", blob, 16)[0]
    reserved = "reserved-memory" in children("/") or any(blob[off:off+16])
    uart = soc + "/serial@190a00"
    require(get("/chosen", "stdout-path") == ["serial0:115200n8"]
            and "earlycon" in get("/chosen", "bootargs")
            and get("/aliases", "serial0") == [uart]
            and get(uart, "compatible") == ["samsung,sdp-uart2"]
            and not disabled(uart), "stock-derived console binding")
    guarded = ("mmc@", "usb@", "gpu@", "display", "drm", "hdmi")
    for n in children(soc):
        node = soc + "/" + n
        compat = get(node, "compatible")
        if n.startswith(guarded) or set(compat) & {"samsung,sdp-drm", "samsung,sdp-hdmi"}:
            require(disabled(node), f"Guarded DT node enabled: {node}")
    return {"cpu_count": len(cpus), "gic": "arm,gic-400",
            "ram_banks_hex_start_end_exclusive": [[hex(a), hex(b)] for a, b in banks],
            "reservations_declared": reserved, "runtime_memory_map_verified": False,
            "stdout_path": "serial0:115200n8"}


def report(files):
    cfg = config(files[KERNEL])
    for key in ("ARM", "CPU_V7", "ARM_LPAE", "ARCH_SDP", "OF", "ARM_GIC",
                "ARM_PSCI", "ARM_ARCH_TIMER", "BLK_DEV_INITRD", "BINFMT_ELF",
                "PRINTK", "SERIAL_EARLYCON", "SERIAL_AMBA_PL011_CONSOLE"):
        require(cfg.get("CONFIG_"+key) == "y", "Missing built-in CONFIG_"+key)
    require(cfg.get("CONFIG_CMDLINE_FORCE") != "y", "Kernel overrides bootargs")
    require(cfg.get("CONFIG_DRM_SDP") == cfg.get("CONFIG_DRM_SDP_HDMI") == "m",
            "DRM interlock: driver not modular")
    with tempfile.TemporaryDirectory(prefix="build110-") as directory:
        dtbs = {p: board(files[name], p, directory)
                for p, name in zip(("1g5", "2g"), DTBS)}
    return {"build": 110, "mode": "OFFLINE-ONLY", "hardware": "NO-GO",
            "release": "6.6.162", "build109_sha256": SOURCE,
            "sdp_uart_kconfig": cfg.get("CONFIG_SERIAL_SDP"),
            "sdp_early_console_verified": False, "dtbs": dtbs}


def pinned_payload(path):
    digest = sha(path.read_bytes())
    require(digest in (SOURCE, CI_SOURCE), "Input differs from pinned BUILD109 or BUILD108 artifact")
    prefix = "payload/" if digest == SOURCE else ""
    with zipfile.ZipFile(path) as z:
        return {name: z.read(prefix + ("dtb/" if name in DTBS else "") + name)
                for name in (KERNEL, *DTBS)}


def package(source, output):
    files = pinned_payload(source)
    files["initramfs.cpio"] = cpio()
    files["report.json"] = (json.dumps(report(files), indent=2, sort_keys=True)+"\n").encode()
    files["SHA256SUMS"] = "".join(f"{sha(data)}  {name}\n"
                                  for name, data in sorted(files.items())).encode()
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_STORED) as z:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            z.writestr(entry, data)
    output.with_name(output.name+".sha256").write_text(
        f"{sha(output.read_bytes())}  {output.name}\n")


def verify(source, output):
    with zipfile.ZipFile(output) as z:
        require(sorted(z.namelist()) == sorted(FILES)
                and sum(i.file_size for i in z.infolist()) < 16 << 20, "ZIP inventory/size")
        files = {name: z.read(name) for name in FILES}
    for name, data in pinned_payload(source).items():
        require(files[name] == data, f"{name}: differs from pinned BUILD109")
    require(files["initramfs.cpio"] == cpio(), "initramfs differs from recipe")
    require(json.loads(files["report.json"]) == report(files), "report differs")
    sums = "".join(f"{sha(d)}  {n}\n" for n, d in sorted(files.items())
                   if n != "SHA256SUMS")
    require(files["SHA256SUMS"] == sums.encode(), "internal SHA256SUMS mismatch")
    print("PASS BUILD110 offline integrity and integration audit; hardware NO-GO")
    return files


def qemu(files):
    with tempfile.TemporaryDirectory(prefix="build110-qemu-") as directory:
        for name in (KERNEL, "initramfs.cpio"):
            (Path(directory)/name).write_bytes(files[name])
        cmd = ["qemu-system-arm", "-M", "virt,gic-version=2", "-cpu", "cortex-a15",
               "-m", "512M", "-smp", "1", "-display", "none", "-monitor", "none",
               "-serial", "stdio", "-nic", "none", "-no-reboot", "-kernel", KERNEL,
               "-initrd", "initramfs.cpio", "-append",
               "console=ttyAMA0 earlycon loglevel=8 rdinit=/init"]
        with tempfile.TemporaryFile() as log, subprocess.Popen(
                cmd, cwd=directory, stdout=log, stderr=subprocess.STDOUT) as proc:
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            log.seek(0)
            output = log.read().decode(errors="replace")
        for line in output.splitlines():
            if re.search("Linux version|dummy-virt|Run /init|BUILD110_|Kernel panic", line):
                print(line)
        require("Linux version 6.6.162 " in output
                and "Run /init as init process" in output
                and "BUILD110_INITRAMFS_OK pid1" in output
                and "Kernel panic" not in output, "QEMU guest failed:\n" + output[-4000:])
        print("PASS QEMU virt only; Samsung DTBs were not used")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify", "qemu"))
    parser.add_argument("build109", type=Path)
    parser.add_argument("build110", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        package(args.build109, args.build110)
    files = verify(args.build109, args.build110)
    if args.action == "qemu":
        qemu(files)


if __name__ == "__main__":
    main()
