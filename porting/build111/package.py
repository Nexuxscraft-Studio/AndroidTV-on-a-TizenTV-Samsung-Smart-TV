#!/usr/bin/env python3
"""Compile stock reservation data into the ARM32 DTS and check the offline bundle."""
import argparse
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "build110"))
import build110

STOCK = json.loads((HERE / "stock-reservations.json").read_text())
FIRMWARE_SHA256 = "cb717ed98daf9580eb5b84bccbad5adac82f75dd021ed028f1ee1bb6c4abde32"
KERNEL_SHA256 = "4aa89f3652fc131e5d39990f3bcd4b9e131028af3f315dbe83f3a8557dc06f06"
DTBS = build110.DTBS
PAYLOAD = ("zImage", "Image", *DTBS, "initramfs.cpio", "kernel.config")
INVENTORY = (*PAYLOAD, "manifest.json", "report.json", "SHA256SUMS")


def require(ok, message):
    build110.require(ok, message)


def prepare(source):
    boards = source / "arch/arm/boot/dts/sdp"
    for profile, evidence in STOCK.items():
        board = boards / f"sdp-nikel-q60t-{profile}.dts"
        original = board.read_text()
        require("arm64/samsung-sdp/" in original and "reserved-memory" not in original,
                f"Unexpected source for {board.name}")
        lines = [
            f"/* T-NKLDEUC 2743.0 dtb.bin+{evidence['offset']}; see stock-reservations.json. */",
            "/ {", "\tchosen {", '\t\tbootargs = "console=ttySDP0,115200n8";', "\t};",
            "\treserved-memory {", "\t\t#address-cells = <2>;", "\t\t#size-cells = <2>;", "\t\tranges;",
        ]
        for item in evidence["reservations"]:
            base, size = (int(item[key], 16) for key in ("base", "size"))
            lines.extend([
                f"\t\tstock@{base:x} {{",
                f"\t\t\treg = <0x{base >> 32:x} 0x{base & 0xffffffff:x} "
                f"0x{size >> 32:x} 0x{size & 0xffffffff:x}>;",
            ])
            if "no-map" in item["stock_flags"]:
                lines.append("\t\t\tno-map;")
            lines.append("\t\t};")
        lines.extend(["\t};", "};", ""])
        board.write_text(original + "\n" + "\n".join(lines))


def disjoint(ranges, label):
    ordered = sorted(ranges)
    require(all(a < b <= 1 << 64 for a, b in ordered), f"{label}: invalid interval")
    require(all(left[1] <= right[0] for left, right in zip(ordered, ordered[1:])),
            f"{label}: overlapping intervals")
    return ordered


def intersect(left, right):
    a, b = max(left[0], right[0]), min(left[1], right[1])
    return (a, b) if a < b else None


def free_intervals(banks, ranges):
    ordered = disjoint(ranges, "firmware reservations")
    free = []
    for first, last in banks:
        cursor = first
        for span in ordered:
            clipped = intersect((first, last), span)
            if clipped:
                a, b = clipped
                if cursor < a:
                    free.append((cursor, a))
                cursor = b
        if cursor < last:
            free.append((cursor, last))
    return free


def dt_report(blob, profile, sizes):
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / "board.dtb"
        path.write_bytes(blob)

        def fdt(*args):
            return subprocess.check_output(["fdtget", *args], text=True).split()

        def get(node, prop, kind="s"):
            return fdt("-t", kind, "-d", "-", str(path), node, prop)

        def children(node):
            return fdt("-l", str(path), node)

        def pairs(node):
            values = [int(value, 16) for value in get(node, "reg", "x")]
            require(values and len(values) % 4 == 0, f"{node}: reg cells")
            return [(hi << 32 | lo, (hi << 32 | lo) + (sh << 32 | sl))
                    for hi, lo, sh, sl in zip(*(iter(values),) * 4)]

        require(get("/", "compatible")[0] == f"samsung,q60t-nikel-{profile}", "board/profile")
        for node in ("/", "/reserved-memory"):
            require(get(node, "#address-cells", "x") == get(node, "#size-cells", "x") == ["2"],
                    f"{node}: cell widths")
        require(get("/reserved-memory", "ranges", "x") == [], "reserved-memory ranges")
        offset = struct.unpack_from(">I", blob, 16)[0]
        require(blob[offset:offset + 16] == bytes(16), "Unexpected FDT header reservations")
        memory = [f"/{name}" for name in children("/") if get(f"/{name}", "device_type") == ["memory"]]
        banks = disjoint([span for node in memory for span in pairs(node)], "RAM banks")
        require(len(banks) == (4 if profile == "1g5" else 3), "Unexpected RAM bank count")
        require(all(end <= 1 << 32 for _, end in banks), "RAM exceeds 32-bit address space")

        uart = "/soc@0/serial@190a00"
        require(get("/aliases", "serial0") == [uart]
                and get("/chosen", "stdout-path") == ["serial0:115200n8"]
                and get("/chosen", "bootargs") == ["console=ttySDP0,115200n8"]
                and get(uart, "compatible") == ["samsung,sdp-uart2"]
                and get(uart, "reg", "x") == ["190a00", "40"]
                and get(uart, "interrupts", "x") == ["0", "48", "4", "0", "49", "4"]
                and get(uart, "status") in (["-"], ["okay"]), "SDP UART binding")
        for name in children("/soc@0"):
            node = f"/soc@0/{name}"
            guarded = ("mmc@", "usb@", "gpu@", "display", "drm", "hdmi", "ehci@", "ohci@")
            if name.startswith(guarded) or set(get(node, "compatible")) & {
                    "samsung,sdp-drm", "samsung,sdp-hdmi"}:
                require(get(node, "status") == ["disabled"], f"{node}: expected disabled")

        evidence = STOCK[profile]
        declared = set(children("/reserved-memory"))
        expected = {f"stock@{int(row['base'], 16):x}" for row in evidence["reservations"]}
        require(declared == expected, "Stock reservation inventory")
        ranges = []
        rows = []
        for item in evidence["reservations"]:
            base, size = (int(item[key], 16) for key in ("base", "size"))
            span = (base, base + size)
            node = f"/reserved-memory/stock@{base:x}"
            flags = {"reg", "no-map"} if "no-map" in item["stock_flags"] else {"reg"}
            require(pairs(node) == [span] and set(fdt("-p", str(path), node)) == flags,
                    f"{node}: reservation properties")
            ranges.append(span)
            slices = [part for bank in banks if (part := intersect(bank, span))]
            rows.append(dict(item, in_ram_bytes=sum(b - a for a, b in slices)))
        free = free_intervals(banks, ranges)

        # Capacity sanity check only. A real placement needs the handoff's
        # actual addresses, decompressor relocation/workspace and running map.
        largest_gap = max((b - a for a, b in free), default=0)
        payload_total = sum(sizes.values()) + len(blob)
        require(largest_gap >= payload_total, f"{profile}: insufficient static capacity")
        return {"fdt_sha256": evidence["fdt_sha256"], "dtb_bin_offset": evidence["offset"],
                "ram_banks": [[hex(a), hex(b)] for a, b in banks], "reservations": rows,
                "free_intervals_static_only": [[hex(a), hex(b)] for a, b in free],
                "largest_static_gap_bytes": largest_gap, "payload_total_bytes": payload_total,
                "runtime_placement": "UNVERIFIED_NO_HANDOFF"}


def metadata(files):
    cfg = build110.config(files["zImage"])
    require(files["kernel.config"].decode().splitlines()[0] == "#",
            "Missing Kbuild .config header")
    require(cfg == dict(re.findall(r"^(CONFIG_\w+)=(.*)$", files["kernel.config"].decode(), re.M)),
            "Packaged config differs from the embedded config")
    for key in ("ARM", "CPU_V7", "ARM_LPAE", "ARCH_SDP", "ARM_GIC", "ARM_PSCI",
                "ARM_ARCH_TIMER", "SERIAL_SDP", "SERIAL_SDP_CONSOLE",
                "SERIAL_AMBA_PL011_CONSOLE", "BLK_DEV_INITRD", "BINFMT_ELF"):
        require(cfg.get(f"CONFIG_{key}") == "y", f"CONFIG_{key} must be built in")
    for key in ("DRM_SDP", "DRM_SDP_HDMI", "DRM_PANFROST"):
        require(cfg.get(f"CONFIG_{key}") == "m", f"CONFIG_{key} must remain modular")
    require(cfg.get("CONFIG_CMDLINE_FORCE") != "y" and cfg.get("CONFIG_INITRAMFS_SOURCE") == '""',
            "Bootargs or embedded initramfs configuration")
    require(files["initramfs.cpio"] == build110.cpio(), "BUILD110 initramfs mismatch")
    # The ARM gzip piggy payload is the raw Image built in the same tree.
    import zlib
    image = files["zImage"]
    raw = files["Image"]
    for match in re.finditer(b"\x1f\x8b\x08", image):
        try:
            decoder = zlib.decompressobj(31)
            candidate = decoder.decompress(image[match.start():], len(raw) + 1)
        except zlib.error:
            continue
        if decoder.eof and candidate == raw:
            break
    else:
        raise ValueError("zImage does not contain the supplied raw Image")
    sizes = {name: len(files[name]) for name in ("Image", "zImage", "initramfs.cpio")}
    report = {"build": 111, "linux_release": "6.6.162", "architecture": "ARM32",
              "hardware": "NO-GO", "linux_source_sha256": KERNEL_SHA256,
              "firmware_zip_sha256": FIRMWARE_SHA256,
              "sdp_uart": {"config": "y", "console_config": "y",
                           "sdp_earlycon_requested": False, "hardware_verified": False},
              "sizes_bytes": sizes,
              "profiles": {p: dt_report(files[name], p, sizes)
                           for p, name in zip(("1g5", "2g"), DTBS)}}
    manifest = {"mode": "OFFLINE-ONLY", "payloads": {
        name: {"bytes": len(files[name]), "sha256": build110.sha(files[name])} for name in PAYLOAD}}
    return {name: (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
            for name, value in (("manifest.json", manifest), ("report.json", report))}


def sums(files):
    return "".join(f"{build110.sha(data)}  {name}\n" for name, data in sorted(files.items())
                   if name != "SHA256SUMS").encode()


def package(out, archive):
    boot = out / "arch/arm/boot"
    files = {name: (boot / name).read_bytes() for name in ("zImage", "Image")}
    files.update({name: (boot / "dts/sdp" / name).read_bytes() for name in DTBS})
    files["kernel.config"] = (out / ".config").read_bytes()
    files["initramfs.cpio"] = build110.cpio()
    files.update(metadata(files))
    files["SHA256SUMS"] = sums(files)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as z:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    sidecar(archive).write_text(external_sum(archive))


def sidecar(archive):
    return archive.with_name(archive.name + ".sha256")


def external_sum(archive):
    return f"{build110.sha(archive.read_bytes())}  {archive.name}\n"


def verify(archive):
    require(sidecar(archive).read_text() == external_sum(archive), "ZIP SHA256 sidecar mismatch")
    with zipfile.ZipFile(archive) as z:
        require(sorted(z.namelist()) == sorted(INVENTORY)
                and sum(i.file_size for i in z.infolist()) <= 128 << 20, "ZIP inventory or size")
        files = {name: z.read(name) for name in INVENTORY}
    require(files["SHA256SUMS"] == sums(files), "Internal SHA256SUMS mismatch")
    for name, expected in metadata(files).items():
        require(files[name] == expected, f"{name} does not match payload")
    print("PASS BUILD111 offline archive, embedded Kconfig and Q60T DTB checks")
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("prepare").add_argument("source", type=Path)
    build = commands.add_parser("build")
    build.add_argument("out", type=Path)
    build.add_argument("archive", type=Path)
    for action in ("verify", "qemu"):
        commands.add_parser(action).add_argument("archive", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.source)
        return
    if args.action == "build":
        package(args.out, args.archive)
    files = verify(args.archive)
    if args.action == "qemu":
        build110.qemu({build110.KERNEL: files["zImage"], "initramfs.cpio": files["initramfs.cpio"]})


if __name__ == "__main__":
    main()
