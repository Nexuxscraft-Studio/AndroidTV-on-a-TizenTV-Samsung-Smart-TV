#!/usr/bin/env python3
"""Build 096: static audit of the Samsung Q60T / Nike-L Linux 6.6.162 ARM32 integration.

This audit is separate from the QEMU boot test. It reads files only: the
patched kernel tree, the Nike-L kernel configuration produced in this run,
the Q60T DTBs compiled in this run, the pinned Build 094 evidence and the
Build 095 manifest. It never loads a module, touches hardware or flashes
anything.

Every module and hardware block is reported on four separate levels, which
must not be confused:

  source      driver source, Kconfig and Makefile entries exist in the tree
  build       a build record exists (Build 094 ELF report and link log)
  file        a .ko file is actually present in the searched directories
  hardware    tested on a real Q60T  (always "no": nothing was run on the TV)

Usage:
  samsung_audit.py --kernel-tree T --config C --dtb A.dtb --dtb B.dtb \
      [--cpu-fixture F.dtb] [--display-fixture F.dtb] [--build094 DIR] \
      [--ko-search DIR ...] --out DIR

Exit status 1 means a safety or consistency contract is broken (an
experimental node enabled, a required symbol missing, Build 094/095 evidence
contradicted). Open hardware questions are reported as findings, not errors.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "porting/build070/tools"))
from dt_nodes import fmt, parse  # noqa: E402

BUILD094_RUN = 43584172324
BUILD094_ARTIFACT = 14109975921
BOARDS = ("sdp-nikel-q60t-1g5.dtb", "sdp-nikel-q60t-2g.dtb")

# name: (Kconfig symbol or None for external Kbuild, source dir, DT compatible)
MODULES = {
    "sdp_display.ko": ("DRM_SDP", "drivers/gpu/drm/sdp", "samsung,nikel-drm-hw-preparation"),
    "sdp_hdmi.ko": ("DRM_SDP_HDMI", "drivers/gpu/drm/sdp-hdmi", "samsung,sdp-hdmi"),
    "panfrost.ko": ("DRM_PANFROST", "drivers/gpu/drm/panfrost", "arm,mali-bifrost"),
    "sdp_mac.ko": ("SDP_MAC", "drivers/net/ethernet/sdp", "samsung,sdp-mac"),
    "sdp_micom_irb.ko": ("SDP_MICOM_IRB", "drivers/misc/sdp-micom", "samsung,sdp-mc-irb"),
    "sdp_micom_irs.ko": ("SDP_MICOM_IRS", "drivers/misc/sdp-micom", "samsung,sdp-mc-irs"),
    "sdp_nikel_cpu_clk.ko": (None, "porting/build058/cpu/kernel", "nover,nikel-cpu-clock-offline"),
    "sdp_nikel_cpufreq.ko": (None, "porting/build058/cpu/kernel", "nover,nikel-cpufreq-offline"),
    "sdp_nikel_thermal.ko": (None, "porting/build058/cpu/kernel", "nover,nikel-thermal-offline"),
}

# Expected Nike-L ARM32 configuration (Build 094 build-arm.sh contract).
CONFIG_BUILTIN = (
    "ARCH_SDP", "ARM_LPAE", "ARM_PSCI", "SMP", "ARM_GIC", "ARM_ARCH_TIMER",
    "SERIAL_SDP", "SERIAL_SDP_CONSOLE", "SERIAL_EARLYCON", "COMMON_CLK_SDP1804",
    "GPIO_SDP", "SDP1804_GPU_POWER", "PM_GENERIC_DOMAINS", "SDP_MSGBOX", "SDP_MICOM",
    "IR_SDP_MICOM", "CEC_SDP_CECIF", "CPU_FREQ", "CPUFREQ_DT", "THERMAL", "THERMAL_OF",
    "DRM_SIMPLEDRM", "MODULES",
)
CONFIG_MODULE = ("DRM_SDP", "DRM_SDP_HDMI", "DRM_PANFROST", "SDP_MAC", "SDP_MICOM_IRB", "SDP_MICOM_IRS")
# Lines that only reflect the host toolchain and may differ between runners.
TOOLCHAIN_LINE = re.compile(
    r"^(# Linux/arm .* Kernel Configuration|# Automatically generated file; DO NOT EDIT\."
    r"|CONFIG_(CC_VERSION_TEXT|CLANG_VERSION|LLD_VERSION|AS_VERSION|LD_VERSION|GCC_VERSION"
    r"|RUSTC_VERSION|RUSTC_LLVM_VERSION|PAHOLE_VERSION|CC_HAS_[A-Z0-9_]+|AS_HAS_[A-Z0-9_]+"
    r"|TOOLS_SUPPORT_[A-Z0-9_]+|LD_CAN_[A-Z0-9_]+|LLD_[A-Z0-9_]+)=.*)$")

# Board-DT nodes that must stay disabled until hardware evidence exists
# (same list as porting/build094/check-dt.py).
GUARDED = (
    "samsung,sdp-drm", "arm,mali-bifrost", "samsung,sdp-messagebox", "samsung,tztv-micom",
    "samsung,sdp-mc-cecif", "samsung,sdp-mac", "samsung,sdp-hdmi", "samsung,sdp-mc-irb",
    "samsung,sdp-mc-irs", "samsung,sdp1804-dw-mshc", "samsung,sdp-ehci", "samsung,sdp-ohci",
)


class Audit:
    def __init__(self):
        self.errors = []
        self.findings = []

    def error(self, message):
        self.errors.append(message)

    def finding(self, message):
        self.findings.append(message)


# --------------------------------------------------------------------------- config
def parse_config(text):
    values = {}
    for line in text.splitlines():
        m = re.match(r"CONFIG_(\w+)=(.*)", line)
        n = re.match(r"# CONFIG_(\w+) is not set", line)
        if m:
            values[m.group(1)] = m.group(2)
        elif n:
            values[n.group(1)] = "n"
    return values


def normalized_config(text):
    return [line for line in text.splitlines() if line and not TOOLCHAIN_LINE.match(line)]


def audit_config(audit, text, build094_text=None):
    values = parse_config(text)
    result = {"builtin": {}, "module": {}, "nr_cpus": values.get("NR_CPUS")}
    for sym in CONFIG_BUILTIN:
        result["builtin"][sym] = values.get(sym, "n")
        if values.get(sym) != "y":
            audit.error(f"config: CONFIG_{sym} is {values.get(sym, 'n')}, expected y")
    for sym in CONFIG_MODULE:
        result["module"][sym] = values.get(sym, "n")
        if values.get(sym) != "m":
            audit.error(f"config: CONFIG_{sym} is {values.get(sym, 'n')}, expected m")
    if values.get("ARM") != "y" or values.get("ARM64") == "y":
        audit.error("config: not an ARM32 configuration")
    result["arm32"] = values.get("ARM") == "y" and values.get("ARM64") != "y"
    if build094_text is not None:
        ours, theirs = normalized_config(text), normalized_config(build094_text)
        removed = sorted(set(theirs) - set(ours))
        added = sorted(set(ours) - set(theirs))
        result["matches_build094"] = not removed and not added
        result["diff_vs_build094"] = {"only_build094": removed, "only_build096": added}
        if removed or added:
            audit.error(f"config: differs from Build 094 kernel.config ({len(removed)} lines only "
                        f"in Build 094, {len(added)} only in Build 096, toolchain lines ignored)")
    return result


# ------------------------------------------------------------------------------- DT
def u32s(data):
    return list(struct.unpack(">%dI" % (len(data) // 4), data)) if data else []


def strings(data):
    return [s.decode() for s in data.rstrip(b"\0").split(b"\0")] if data else []


def status(props):
    return props["status"].rstrip(b"\0").decode() if "status" in props else "okay"


def by_compatible(nodes, compatible):
    return [(p, props) for p, props in nodes.items() if compatible in strings(props.get("compatible", b""))]


def phandles(nodes):
    return {u32s(props["phandle"])[0]: path for path, props in nodes.items() if "phandle" in props}


def audit_board_dtb(audit, name, blob, driver_compatibles):
    nodes = parse(blob)
    handles = phandles(nodes)
    root = nodes["/"]
    out = {"sha256": hashlib.sha256(blob).hexdigest(), "model": fmt(root.get("model", b"")),
           "compatible": strings(root.get("compatible", b""))}

    # CPU and RAM
    cpus = [(p, props) for p, props in nodes.items() if re.fullmatch(r"/cpus/cpu@\d+", p)]
    out["cpu"] = {"count": len(cpus),
                  "compatible": sorted({fmt(props.get("compatible", b"")) for _, props in cpus}),
                  "enable_method": sorted({fmt(props.get("enable-method", b"")) for _, props in cpus})}
    if len(cpus) != 4 or any(props.get("enable-method") != b"psci\0" for _, props in cpus):
        audit.error(f"{name}: expected four CPUs with enable-method psci")
    mem = nodes.get("/memory@40000000", {})
    cells = u32s(mem.get("reg", b""))
    banks = [((cells[i] << 32) | cells[i + 1], (cells[i + 2] << 32) | cells[i + 3])
             for i in range(0, len(cells) - 3, 4)]
    out["ram"] = {"banks": [{"base": hex(b), "size": hex(s)} for b, s in banks],
                  "total_mib": round(sum(s for _, s in banks) / 2**20, 2),
                  "memory_reg": fmt(mem.get("reg", b""))}
    if not banks or banks[0][0] != 0x40000000:
        audit.error(f"{name}: memory does not start at 0x40000000")
    if "/reserved-memory" not in nodes:
        audit.finding(f"{name}: no /reserved-memory node; the gaps between the {len(banks)} banks "
                      "(secure world, video, GPU buffers) are only implied by the bank layout")

    # PSCI, GIC, timer
    psci = nodes.get("/psci", {})
    out["psci"] = {"compatible": strings(psci.get("compatible", b"")), "method": fmt(psci.get("method", b""))}
    if psci.get("method") != b"smc\0":
        audit.error(f"{name}: PSCI method is not smc")
    gics = by_compatible(nodes, "arm,gic-400")
    out["gic"] = [{"path": p, "reg": fmt(props.get("reg", b"")), "status": status(props),
                   "driver_matches": "arm,gic-400" in driver_compatibles} for p, props in gics]
    if len(gics) != 1 or status(gics[0][1]) != "okay":
        audit.error(f"{name}: expected one enabled arm,gic-400")
    timers = by_compatible(nodes, "arm,armv7-timer")
    out["timer"] = [{"path": p, "compatible": strings(props.get("compatible", b"")),
                     "clock_frequency": u32s(props.get("clock-frequency", b""))[:1],
                     "ppis": len(u32s(props.get("interrupts", b""))) // 3} for p, props in timers]
    if len(timers) != 1:
        audit.error(f"{name}: expected one arm,armv7-timer node usable by an ARM32 kernel")

    # UART and console
    chosen = nodes.get("/chosen", {})
    uart_path = nodes.get("/aliases", {}).get("serial0", b"").rstrip(b"\0").decode()
    uart = nodes.get(uart_path, {})
    out["uart"] = {"serial0": uart_path, "compatible": strings(uart.get("compatible", b"")),
                   "status": status(uart) if uart else "missing", "reg": fmt(uart.get("reg", b"")),
                   "clocks": fmt(uart["clocks"]) if "clocks" in uart else None,
                   "stdout_path": fmt(chosen.get("stdout-path", b"")),
                   "bootargs": fmt(chosen.get("bootargs", b"")),
                   "driver_matches": "samsung,sdp-uart2" in driver_compatibles}
    if out["uart"]["status"] != "okay" or chosen.get("stdout-path") != b"serial0:115200n8\0":
        audit.error(f"{name}: serial0 console contract changed")
    if "clocks" not in uart:
        audit.finding(f"{name}: {uart_path} has no clocks; sdp_uart derives the rate from the "
                      "boot loader divisor (unverified on hardware)")

    # Clock controller
    clocks = by_compatible(nodes, "samsung,sdp1804-clock")
    clock = {}
    if clocks:
        cpath, cprops = clocks[0]
        parent = handles.get(u32s(cprops.get("clocks", b""))[:1][0]) if cprops.get("clocks") else None
        rate = u32s(nodes.get(parent, {}).get("clock-frequency", b""))[:1] if parent else []
        clock = {"path": cpath, "reg": fmt(cprops.get("reg", b"")), "status": status(cprops),
                 "parent": parent, "parent_hz": rate[0] if rate else None}
    out["clock_controller"] = clock
    if not clock or clock.get("parent_hz") != 24000000:
        audit.error(f"{name}: samsung,sdp1804-clock must reference the 24 MHz fixed clock")

    # Experimental blocks: must stay disabled
    blocks = {}
    for compatible in GUARDED:
        for path, props in by_compatible(nodes, compatible):
            node_compatibles = strings(props.get("compatible", b""))
            blocks[path] = {"compatible": compatible, "status": status(props),
                            "reg": fmt(props.get("reg", b"")),
                            "clocks": "clocks" in props,
                            "driver_matches": any(c in driver_compatibles for c in node_compatibles)}
            if status(props) != "disabled":
                audit.error(f"{name}: {path} ({compatible}) is {status(props)}, must stay disabled")
    out["guarded_blocks"] = blocks
    for path, props in nodes.items():
        if "samsung,enable-experimental-kms" in props:
            audit.error(f"{name}: {path} opts into experimental KMS")
        if path.endswith("/gpu-power-domain") and status(props) != "disabled":
            audit.error(f"{name}: {path} must stay disabled")
    missing = sorted(set(GUARDED) - {b["compatible"] for b in blocks.values()})
    if missing:
        audit.error(f"{name}: guarded nodes missing: {missing}")
    for path, block in blocks.items():
        if not block["driver_matches"]:
            audit.finding(f"{name}: {path} uses {block['compatible']}, which no driver in the "
                          "audited tree matches")

    # CPUFreq / thermal: nothing may be wired in the board DT yet
    opp = [p for p, props in nodes.items() if "operating-points-v2" in strings(props.get("compatible", b""))]
    zones = [p for p in nodes if p.startswith("/thermal-zones")]
    out["cpufreq_thermal"] = {"opp_tables": opp, "thermal_zones": zones,
                              "cpu_supply": any("cpu-supply" in props for _, props in cpus)}
    if opp or zones:
        audit.error(f"{name}: OPP table or thermal zones present before hardware validation")
    return out


def audit_fixture(audit, name, blob, compatibles):
    nodes = parse(blob)
    seen = {}
    for compatible in compatibles:
        for path, props in by_compatible(nodes, compatible):
            seen[compatible] = {"path": path, "status": status(props)}
            if status(props) != "disabled":
                audit.error(f"{name}: {path} must stay disabled")
    for compatible in set(compatibles) - set(seen):
        audit.error(f"{name}: missing {compatible}")
    return {"sha256": hashlib.sha256(blob).hexdigest(), "nodes": seen}


def compare_manifest(audit, boards, manifest):
    result = {}
    for name, board in boards.items():
        expected = manifest["boards"].get(name, {})
        semantic = {
            "compatible": ", ".join(f'"{c}"' for c in board["compatible"]) == expected.get("compatible"),
            "memory_reg": board["ram"]["memory_reg"] == expected.get("memory_reg"),
            "stdout_path": board["uart"]["stdout_path"] == expected.get("stdout_path"),
            "bootargs": board["uart"]["bootargs"] == expected.get("bootargs"),
            "uart_path": board["uart"]["serial0"] == expected.get("uart_path"),
            "psci_method": board["psci"]["method"].strip('"') == expected.get("psci_method"),
        }
        identical = board["sha256"] == manifest["sha256"].get(name)
        result[name] = {"semantic_match": semantic, "bit_identical_to_build094": identical}
        for key, ok in semantic.items():
            if not ok:
                audit.error(f"{name}: {key} contradicts the Build 095 manifest")
        if not identical:
            audit.finding(f"{name}: DTB is not bit-identical to Build 094 "
                          f"({board['sha256'][:12]} vs {manifest['sha256'].get(name, '?')[:12]})")
    return result


# -------------------------------------------------------------------------- modules
def function_body(source, name):
    m = re.search(r"\b" + re.escape(name) + r"\s*\([^;{]*\)\s*\{", source)
    if not m:
        return ""
    depth, i = 1, m.end()
    while i < len(source) and depth:
        depth += {"{": 1, "}": -1}.get(source[i], 0)
        i += 1
    return source[m.end():i]


def probe_profile(sources):
    """Describe what the probe function does before it can touch hardware."""
    text = "\n".join(sources)
    probes = re.findall(r"\.probe\s*=\s*(\w+)", text)
    body = "".join(function_body(text, p) for p in probes)
    gate = min([body.find(t) for t in ("-EOPNOTSUPP", "sdp_hw_access_allowed") if t in body] or [-1])
    remap = min([body.find(t) for t in ("ioremap", "devm_platform_ioremap") if t in body] or [-1])
    return {
        "probe": probes[0] if probes else None,
        "rejects_before_mmio": gate >= 0 and (remap < 0 or gate < remap),
        "maps_mmio_in_probe": remap >= 0,
        "register_writes_in_driver": len(re.findall(r"\bwrite[lbwq](?:_relaxed)?\s*\(", text)),
    }


def audit_modules(audit, tree, config_values, build094, ko_hits, board_compatibles):
    report = {}
    for module, (symbol, directory, compatible) in MODULES.items():
        stem = module[:-3]
        base = (REPO if directory.startswith("porting/") else tree) / directory
        makefile = (base / "Makefile").read_text() if (base / "Makefile").is_file() else ""
        composite = re.search(rf"^{stem}-(?:y|objs)\s*:?=\s*(.+)$", makefile, re.M)
        names = [o[:-2] + ".c" for o in composite.group(1).split()] if composite else [stem + ".c"]
        if module == "panfrost.ko":
            names = [p.name for p in base.glob("panfrost_*.c")] if base.is_dir() else []
        files = sorted(base / n for n in names if (base / n).is_file())
        kconfig = (base / "Kconfig").read_text() if (base / "Kconfig").is_file() else ""
        if symbol:
            in_make = bool(re.search(rf"obj-\$\(CONFIG_{symbol}\)\s*\+=\s*{stem}\.o", makefile))
            in_kconfig = bool(re.search(rf"^config {symbol}\b", kconfig, re.M))
        else:
            in_make, in_kconfig = bool(re.search(rf"obj-m\s*\+=\s*{stem}\.o", makefile)), None
        sources = [p.read_text(errors="replace") for p in files]
        matches = any(f'"{compatible}"' in s for s in sources)
        source_ok = bool(files) and in_make and in_kconfig is not False and matches
        entry = {
            "kconfig_symbol": symbol,
            "source": {"present": source_ok, "dir": directory, "files": [p.name for p in files],
                       "makefile_entry": in_make, "kconfig_entry": in_kconfig,
                       "of_compatible": compatible, "of_match_in_source": matches},
            "config_value": config_values.get(symbol, "n") if symbol else "external Kbuild",
            "probe": probe_profile(sources) if module != "panfrost.ko" else {"probe": "upstream panfrost_probe"},
            "dt_node": board_compatibles.get(compatible, "no node in board DT"),
            "build_evidence": build094.get(module) if build094 else "not supplied",
            "ko_file": ko_hits.get(module, []),
            "hardware_tested": False,
        }
        if not source_ok:
            audit.error(f"{module}: source integration incomplete in the audited tree")
        if symbol and config_values.get(symbol) != "m":
            audit.error(f"{module}: CONFIG_{symbol} is not m")
        report[module] = entry
    return report


def parse_build094(audit, directory, manifest):
    directory = Path(directory)
    result = {}
    for name, digest in manifest["sha256"].items():
        path = directory / name
        if not path.is_file():
            audit.error(f"Build 094 evidence: {name} missing")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            audit.error(f"Build 094 evidence: {name} does not match the Build 095 manifest")
    elf = (directory / "elf.txt").read_text() if (directory / "elf.txt").is_file() else ""
    logs = "\n".join((directory / n).read_text() for n in ("kernel.log", "cpu.log") if (directory / n).is_file())
    chunks = re.split(r"(?m)^([^\s]+)\nELF Header:\n", elf)
    headers = dict(zip(chunks[1::2], chunks[2::2]))
    for module in MODULES:
        header = headers.get(module, "")
        fields = dict(re.findall(r"(?m)^\s*(Class|Machine|Type):[ \t]+(.+)$", header))
        linked = bool(re.search(rf"(?m)^\s*LD \[M\][ \t]+\S*/{re.escape(module)}[ \t]*$", logs))
        result[module] = {"run": BUILD094_RUN, "artifact": BUILD094_ARTIFACT,
                          "elf": f"{fields.get('Class')} {fields.get('Machine')} {fields.get('Type', '').split(' ')[0]}"
                          if fields else None,
                          "link_record": linked}
        if fields.get("Class") != "ELF32" or fields.get("Machine") != "ARM" or not linked:
            audit.error(f"Build 094 evidence: {module} lacks an ARM32 ELF report or link record")
    return result


def find_ko(directories):
    hits = {}
    for directory in directories:
        for root, _dirs, files in os.walk(directory):
            for name in files:
                if name in MODULES:
                    path = Path(root) / name
                    hits.setdefault(name, []).append(
                        {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return hits


def tree_compatibles(tree):
    found = set()
    for path in list((tree / "drivers").rglob("*.c")) + list((REPO / "porting/build058/cpu/kernel").glob("*.c")):
        if path.name.endswith(".orig"):
            continue
        text = path.read_text(errors="replace")
        if ".compatible" in text:
            found.update(re.findall(r'\.compatible\s*=\s*"([^"]+)"', text))
        if "_DECLARE(" in text:
            found.update(re.findall(r'_DECLARE\(\s*\w+\s*,\s*"([^"]+)"', text))
    return found


# --------------------------------------------------------------------------- report
def markdown(report):
    out = ["# Build 096 – Samsung Nike-L Hardware-Audit (statisch)", "",
           "Nur Dateiprüfung. Kein Modul geladen, nichts auf dem Q60T ausgeführt, nichts geflasht.", "",
           f"Ergebnis: **{'OK' if not report['errors'] else 'FEHLER'}** – "
           f"{len(report['errors'])} Vertragsverletzungen, {len(report['findings'])} offene Befunde.", ""]
    cfg = report.get("config", {})
    if cfg:
        out += ["## Kernelkonfiguration", "",
                f"ARM32: {cfg.get('arm32')}, NR_CPUS={cfg.get('nr_cpus')}, "
                f"identisch zu Build 094 (ohne Toolchain-Zeilen): {cfg.get('matches_build094', 'nicht verglichen')}", ""]
    for name, board in report.get("boards", {}).items():
        man = report.get("manifest_comparison", {}).get(name, {})
        out += [f"## {name}", "",
                f"- Modell: {board['model']}",
                f"- CPUs: {board['cpu']['count']} × {', '.join(board['cpu']['compatible'])}, "
                f"enable-method {', '.join(board['cpu']['enable_method'])}",
                f"- RAM: {len(board['ram']['banks'])} Bänke ab 0x40000000, {board['ram']['total_mib']} MiB",
                f"- PSCI: {', '.join(board['psci']['compatible'])} über {board['psci']['method']}",
                f"- GIC: {', '.join(g['path'] + ' ' + g['reg'] for g in board['gic'])}",
                f"- Timer: {', '.join(', '.join(t['compatible']) for t in board['timer'])}, "
                f"clock-frequency {board['timer'][0]['clock_frequency'] if board['timer'] else '-'}",
                f"- UART: {board['uart']['serial0']} ({', '.join(board['uart']['compatible'])}) "
                f"status {board['uart']['status']}, stdout-path {board['uart']['stdout_path']}",
                f"- Clock-Controller: {board['clock_controller'].get('path')} ← "
                f"{board['clock_controller'].get('parent')} ({board['clock_controller'].get('parent_hz')} Hz)",
                f"- OPP-Tabellen/Thermal-Zonen im Board-DT: {len(board['cpufreq_thermal']['opp_tables'])}/"
                f"{len(board['cpufreq_thermal']['thermal_zones'])}",
                f"- SHA-256: `{board['sha256']}` – bitidentisch zu Build 094: "
                f"{man.get('bit_identical_to_build094', 'nicht verglichen')}", "",
                "| Knoten | compatible | status | Treiber-Match | clocks |", "| --- | --- | --- | --- | --- |"]
        for path, block in board["guarded_blocks"].items():
            out.append(f"| `{path}` | {block['compatible']} | {block['status']} | "
                       f"{'ja' if block['driver_matches'] else 'nein'} | {'ja' if block['clocks'] else 'nein'} |")
        out.append("")
    out += ["## Kernelmodule", "",
            "| Modul | Quelle integriert | Config | Build-Nachweis (Build 094) | .ko vorhanden | Probe vor MMIO abgelehnt | DT-Knoten | Hardware getestet |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for module, m in report.get("modules", {}).items():
        ev = m["build_evidence"]
        ev_text = (f"{ev['elf']}, LD [M] {'ja' if ev['link_record'] else 'nein'}"
                   if isinstance(ev, dict) else ev)
        ko = f"ja ({len(m['ko_file'])})" if m["ko_file"] else "nein"
        gate = m["probe"].get("rejects_before_mmio")
        gate_text = "–" if gate is None else ("ja" if gate else "nein")
        out.append(f"| {module} | {'ja' if m['source']['present'] else 'NEIN'} | {m['config_value']} | "
                   f"{ev_text} | {ko} | {gate_text} | {m['dt_node']} | nein |")
    out += ["", "## Vertragsverletzungen", ""] + ([f"- {e}" for e in report["errors"]] or ["- keine"])
    out += ["", "## Offene Befunde (keine Fehler, aber vor Hardwaretests zu klären)", ""]
    out += [f"- {f}" for f in report["findings"]] or ["- keine"]
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kernel-tree", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dtb", type=Path, action="append", default=[])
    parser.add_argument("--cpu-fixture", type=Path)
    parser.add_argument("--display-fixture", type=Path)
    parser.add_argument("--build094", type=Path, help="extracted, verified Build 094 evidence directory")
    parser.add_argument("--manifest", type=Path, default=REPO / "porting/build095/manifest.json")
    parser.add_argument("--ko-search", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    audit = Audit()
    manifest = json.loads(args.manifest.read_text())
    config_text = args.config.read_text()
    build094_config = None
    if args.build094 and (args.build094 / "kernel.config").is_file():
        build094_config = (args.build094 / "kernel.config").read_text()
    report = {"scope": "static Samsung Nike-L audit; no hardware access, no module load",
              "hardware_validated": False, "retail_boot": manifest.get("retail_boot", "blocked")}
    report["config"] = audit_config(audit, config_text, build094_config)
    compatibles = tree_compatibles(args.kernel_tree)

    report["boards"] = {}
    board_nodes = {}
    for dtb in args.dtb:
        blob = dtb.read_bytes()
        report["boards"][dtb.name] = audit_board_dtb(audit, dtb.name, blob, compatibles)
        for path, props in parse(blob).items():
            for c in strings(props.get("compatible", b"")):
                board_nodes.setdefault(c, f"{path} ({status(props)})")
    if sorted(report["boards"]) != sorted(BOARDS):
        audit.error(f"expected DTBs {list(BOARDS)}, got {sorted(report['boards'])}")
    report["manifest_comparison"] = compare_manifest(audit, report["boards"], manifest)
    fixtures = {}
    if args.cpu_fixture:
        fixtures["cpu"] = audit_fixture(audit, args.cpu_fixture.name, args.cpu_fixture.read_bytes(),
                                        [MODULES[m][2] for m in MODULES if MODULES[m][0] is None])
        for c, n in fixtures["cpu"]["nodes"].items():
            board_nodes.setdefault(c, f"fixture {n['path']} ({n['status']})")
    if args.display_fixture:
        fixtures["display"] = audit_fixture(audit, args.display_fixture.name,
                                            args.display_fixture.read_bytes(),
                                            ["samsung,nikel-drm-hw-preparation"])
        for c, n in fixtures["display"]["nodes"].items():
            board_nodes.setdefault(c, f"fixture {n['path']} ({n['status']})")
    report["fixtures"] = fixtures

    build094 = parse_build094(audit, args.build094, manifest) if args.build094 else None
    ko_hits = find_ko(args.ko_search)
    report["modules"] = audit_modules(audit, args.kernel_tree, parse_config(config_text),
                                      build094, ko_hits, board_nodes)
    if not ko_hits:
        audit.finding("no .ko file of the nine modules is present in the searched directories; "
                      "Build 096 does not rebuild them and Build 094 archived ELF reports and logs only")
    if "samsung,sdp-drm" not in compatibles:
        audit.finding("board DT display node samsung,sdp-drm has no matching driver: sdp_display.ko "
                      "binds only the samsung,nikel-drm-hw-preparation fixture and its hardware "
                      "interlock always rejects probe")
    for module in ("sdp_hdmi.ko", "sdp_mac.ko", "sdp_micom_irb.ko", "sdp_micom_irs.ko"):
        probe = report["modules"][module]["probe"]
        if probe.get("maps_mmio_in_probe") and not probe.get("rejects_before_mmio"):
            audit.finding(f"{module}: probe maps MMIO without a software gate; only the disabled "
                          "DT node keeps it from binding")
    audit.finding("hardware: no module, DTB or kernel of this audit has been started on a Samsung Q60T")

    report["errors"], report["findings"] = audit.errors, audit.findings
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "samsung-audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (args.out / "samsung-audit.md").write_text(markdown(report))
    print(markdown(report))
    return 1 if audit.errors else 0


if __name__ == "__main__":
    sys.exit(main())
