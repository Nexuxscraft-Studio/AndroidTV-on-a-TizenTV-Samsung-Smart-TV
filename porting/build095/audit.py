"""Audit the pinned Build 094 CI evidence without unpacking or executing it."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "build070/tools"))
from dt_nodes import parse, fmt

RUN = 43584172324
ARTIFACT = 14109975921
COMMIT = "51751a4dea3daf838816f1c505f580e5cc0e3b88"
ARCHIVE_SHA256 = "1a64265ddff78f617faea951e3543417900deedcfc0b7a9bbec3f6eae1be2744"
MODULES = {
    "sdp_display.ko": "DRM_SDP",
    "panfrost.ko": "DRM_PANFROST",
    "sdp_hdmi.ko": "DRM_SDP_HDMI",
    "sdp_mac.ko": "SDP_MAC",
    "sdp_micom_irb.ko": "SDP_MICOM_IRB",
    "sdp_micom_irs.ko": "SDP_MICOM_IRS",
    "sdp_nikel_cpu_clk.ko": None,
    "sdp_nikel_cpufreq.ko": None,
    "sdp_nikel_thermal.ko": None,
}
BOARDS = ("sdp-nikel-q60t-1g5.dtb", "sdp-nikel-q60t-2g.dtb")
DTBS = (*BOARDS, "cpu-disabled.dtb", "display-disabled.dtb")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_modules(files):
    config = set(files["kernel.config"].decode().splitlines())
    logs = {name: files[name].decode() for name in ("kernel.log", "cpu.log")}
    headers = re.split(r"(?m)^([^\s]+)\nELF Header:\n", files["elf.txt"].decode())
    names = headers[1::2]
    require(not headers[0] and len(names) == 10 and set(names) == {"vmlinux", *MODULES},
            "Unexpected ELF evidence inventory")
    require(all(re.search(r"(?m)^\s*MODPOST\s+(?:\S+/)?Module\.symvers\s*$", log)
                for log in logs.values()), "Missing kernel or external modpost")
    for name, header in zip(names, headers[2::2]):
        fields = dict(re.findall(r"(?m)^\s*(Class|Data|Type|Machine|Flags):[ \t]+(.+)$", header))
        expected_type = "EXEC" if name == "vmlinux" else "REL"
        require(fields["Class"] == "ELF32" and fields["Machine"] == "ARM"
                and fields["Data"].endswith("little endian")
                and fields["Type"].split()[0] == expected_type
                and int(fields["Flags"], 16) >> 24 == 5,
                f"{name}: wrong architecture, byte order, type or EABI")
        if name == "vmlinux":
            continue
        symbol = MODULES[name]
        log = logs["kernel.log" if symbol else "cpu.log"]
        require(re.search(rf"(?m)^\s*LD \[M\][ \t]+\S*/{re.escape(name)}[ \t]*$", log),
                f"{name}: missing link record")
        if symbol:
            require(f"CONFIG_{symbol}=m" in config, f"{name}: incorrect Kconfig")


def verify_dt(files):
    checksums = {name: digest(files[name]) for name in DTBS}
    supplied = files["dtb.sha256"].decode().splitlines()
    require(sorted(supplied) == sorted(f"{sha}  {name}" for name, sha in checksums.items()),
            "DTB checksum inventory does not match")
    with TemporaryDirectory() as temp:
        names = ("display-disabled.dtb", "cpu-disabled.dtb", *BOARDS)
        paths = [Path(temp) / name for name in names]
        for path in paths:
            path.write_bytes(files[path.name])
        subprocess.run([sys.executable, str(HERE.parent / "build094/check-dt.py"), *map(str, paths)],
                       check=True, stdout=sys.stderr)

    boards = {}
    for name in BOARDS:
        nodes = parse(files[name])
        chosen = nodes["/chosen"]
        uart = nodes["/aliases"]["serial0"].rstrip(b"\0").decode()
        require(chosen["stdout-path"] == b"serial0:115200n8\0"
                and nodes[uart]["compatible"] == b"samsung,sdp-uart2\0"
                and nodes[uart]["status"] == b"okay\0", f"{name}: UART contract changed")
        require(nodes["/psci"]["method"] == b"smc\0", f"{name}: PSCI contract changed")
        for path in ("/regulator-usb-vbus", "/soc@0/clock-controller@f50000/gpu-power-domain"):
            require(nodes[path]["status"] == b"disabled\0", f"{name}: {path} is enabled")
        boards[name] = {
            "compatible": fmt(nodes["/"]["compatible"]),
            "memory_reg": fmt(nodes["/memory@40000000"]["reg"]),
            "stdout_path": fmt(chosen["stdout-path"]),
            "bootargs": fmt(chosen["bootargs"]),
            "psci_method": "smc",
            "uart_path": uart,
        }
    return boards


def audit(archive):
    require(digest(archive.read_bytes()) == ARCHIVE_SHA256, "Build 094 archive SHA-256 mismatch")
    with ZipFile(archive) as zipped:
        names = zipped.namelist()
        expected = {*DTBS, "kernel.config", "kernel.log", "cpu.log", "elf.txt",
                    "dtb.sha256", "dt-status.txt"}
        require(len(names) == len(expected) and set(names) == expected, "Unexpected archive inventory")
        files = {name: zipped.read(name) for name in sorted(names)}

    verify_modules(files)
    return {
        "build094": {"run_id": RUN, "artifact_id": ARTIFACT, "commit": COMMIT,
                     "archive_sha256": ARCHIVE_SHA256},
        "sha256": {name: digest(data) for name, data in files.items()},
        "modules": {name: {"kconfig": symbol, "evidence": "ELF report and link log"}
                    for name, symbol in MODULES.items()},
        "boards": verify_dt(files),
        "retail_boot": "blocked",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--print-manifest", action="store_true")
    args = parser.parse_args()
    try:
        report = audit(args.archive)
        if args.print_manifest:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            require(report == json.loads((HERE / "manifest.json").read_text()),
                    "Build 095 manifest differs from verified evidence")
            print("Verified nine ARM32 module reports, four DTBs and the evidence manifest.")
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Build 095 audit failed: {error}\n")


if __name__ == "__main__":
    main()
