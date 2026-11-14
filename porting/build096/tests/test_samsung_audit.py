"""Host tests for the Build 096 Samsung audit, using synthetic DTBs and configs."""

import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import samsung_audit as sa  # noqa: E402


def fdt(tree):
    """Serialize {name: {prop: bytes | dict(child)}} into a DTB (version 17)."""
    structure, strings, offsets = bytearray(), bytearray(), {}

    def name_offset(name):
        if name not in offsets:
            offsets[name] = len(strings)
            strings.extend(name.encode() + b"\0")
        return offsets[name]

    def node(name, body):
        structure.extend(struct.pack(">I", 1) + name.encode() + b"\0")
        structure.extend(b"\0" * (-len(structure) % 4))
        for key, value in body.items():
            if not isinstance(value, dict):
                structure.extend(struct.pack(">III", 3, len(value), name_offset(key)) + value)
                structure.extend(b"\0" * (-len(structure) % 4))
        for key, value in body.items():
            if isinstance(value, dict):
                node(key, value)
        structure.extend(struct.pack(">I", 2))

    node("", tree)
    structure.extend(struct.pack(">I", 9))
    off_rsv = 40
    off_struct = off_rsv + 16
    off_strings = off_struct + len(structure)
    total = off_strings + len(strings)
    header = struct.pack(">10I", 0xD00DFEED, total, off_struct, off_strings, off_rsv, 17, 16, 0,
                         len(strings), len(structure))
    return header + b"\0" * 16 + bytes(structure) + bytes(strings)


def s(*values):
    return b"".join(v.encode() + b"\0" for v in values)


def cells(*values):
    return struct.pack(">%dI" % len(values), *values)


def board(model="samsung,q60t-nikel-2g"):
    soc = {
        "compatible": s("simple-bus"),
        "interrupt-controller@431000": {"compatible": s("arm,gic-400"), "reg": cells(0x431000, 0x1000, 0x432000, 0x1000)},
        "clock-controller@f50000": {"compatible": s("samsung,sdp1804-clock"), "reg": cells(0xf50000, 0x3000),
                                    "clocks": cells(1),
                                    "gpu-power-domain": {"status": s("disabled")}},
        "serial@190a00": {"compatible": s("samsung,sdp-uart2"), "reg": cells(0x190a00, 0x40), "status": s("okay")},
    }
    for i, compatible in enumerate(sa.GUARDED):
        soc[f"node@{i:x}"] = {"compatible": s(compatible), "status": s("disabled")}
    tree = {
        "compatible": s(model, "samsung,dtv", "samsung,sdp-nikel"),
        "model": s("Samsung Q60T TV (Nike-L, 2G profile)"),
        "aliases": {"serial0": s("/soc@0/serial@190a00")},
        "chosen": {"bootargs": s("earlycon keep_bootcon loglevel=8"), "stdout-path": s("serial0:115200n8")},
        "cpus": {f"cpu@{i}": {"compatible": s("arm,cortex-a57"), "enable-method": s("psci")} for i in range(4)},
        "psci": {"compatible": s("arm,psci-0.2"), "method": s("smc")},
        "timer": {"compatible": s("arm,armv8-timer", "arm,armv7-timer"), "clock-frequency": cells(24000000),
                  "interrupts": cells(*[1, 13, 0xf08] * 4)},
        "clock-24000000": {"compatible": s("fixed-clock"), "clock-frequency": cells(24000000), "phandle": cells(1)},
        "memory@40000000": {"reg": cells(0, 0x40000000, 0, 0x14000000, 0, 0xa2000000, 0, 0x3dc00000)},
        "soc@0": soc,
    }
    return tree


CONFIG = "\n".join(["CONFIG_ARM=y", "CONFIG_NR_CPUS=4", "CONFIG_CC_VERSION_TEXT=\"clang 18\""]
                   + [f"CONFIG_{x}=y" for x in sa.CONFIG_BUILTIN]
                   + [f"CONFIG_{x}=m" for x in sa.CONFIG_MODULE]) + "\n"


class DtTests(unittest.TestCase):
    def audit(self, tree, compatibles=frozenset(sa.GUARDED) | {"samsung,sdp-uart2"}):
        audit = sa.Audit()
        result = sa.audit_board_dtb(audit, "board.dtb", fdt(tree), compatibles)
        return audit, result

    def test_clean_board(self):
        audit, result = self.audit(board())
        self.assertEqual(audit.errors, [])
        self.assertEqual(result["cpu"]["count"], 4)
        self.assertEqual(result["ram"]["total_mib"], 320 + 988)
        self.assertEqual(result["clock_controller"]["parent_hz"], 24000000)
        self.assertEqual(result["uart"]["status"], "okay")
        self.assertTrue(any("no clocks" in f for f in audit.findings))

    def test_enabled_experimental_node_is_an_error(self):
        tree = board()
        tree["soc@0"]["node@0"]["status"] = s("okay")
        audit, _ = self.audit(tree)
        self.assertTrue(any("must stay disabled" in e for e in audit.errors))

    def test_enabled_gpu_power_domain_is_an_error(self):
        tree = board()
        tree["soc@0"]["clock-controller@f50000"]["gpu-power-domain"]["status"] = s("okay")
        audit, _ = self.audit(tree)
        self.assertTrue(any("gpu-power-domain" in e for e in audit.errors))

    def test_psci_and_console_contract(self):
        tree = board()
        tree["psci"]["method"] = s("hvc")
        tree["chosen"]["stdout-path"] = s("serial1:115200n8")
        audit, _ = self.audit(tree)
        self.assertTrue(any("PSCI" in e for e in audit.errors))
        self.assertTrue(any("console" in e for e in audit.errors))

    def test_opp_before_validation_is_an_error(self):
        tree = board()
        tree["opp-table"] = {"compatible": s("operating-points-v2")}
        audit, _ = self.audit(tree)
        self.assertTrue(any("OPP" in e for e in audit.errors))

    def test_driver_mismatch_is_a_finding(self):
        audit, result = self.audit(board(), compatibles=frozenset(sa.GUARDED) - {"samsung,sdp-drm"})
        self.assertEqual(audit.errors, [])
        self.assertTrue(result["guarded_blocks"]["/soc@0/node@0"]["driver_matches"] is False)

    def test_manifest_comparison(self):
        audit, result = self.audit(board())
        manifest = {"boards": {"board.dtb": {
            "compatible": '"samsung,q60t-nikel-2g", "samsung,dtv", "samsung,sdp-nikel"',
            "memory_reg": result["ram"]["memory_reg"], "stdout_path": '"serial0:115200n8"',
            "bootargs": '"earlycon keep_bootcon loglevel=8"', "uart_path": "/soc@0/serial@190a00",
            "psci_method": "smc"}}, "sha256": {"board.dtb": result["sha256"]}}
        audit = sa.Audit()
        cmp = sa.compare_manifest(audit, {"board.dtb": result}, manifest)
        self.assertEqual(audit.errors, [])
        self.assertTrue(cmp["board.dtb"]["bit_identical_to_build094"])
        broken = copy.deepcopy(manifest)
        broken["boards"]["board.dtb"]["memory_reg"] = "<0x0>"
        broken["sha256"]["board.dtb"] = "0" * 64
        audit = sa.Audit()
        sa.compare_manifest(audit, {"board.dtb": result}, broken)
        self.assertTrue(any("memory_reg" in e for e in audit.errors))
        self.assertTrue(any("bit-identical" in f for f in audit.findings))

    def test_fixture_must_stay_disabled(self):
        tree = {"ref": {"compatible": s("nover,nikel-thermal-offline"), "status": s("okay")}}
        audit = sa.Audit()
        sa.audit_fixture(audit, "cpu.dtb", fdt(tree), ["nover,nikel-thermal-offline"])
        self.assertTrue(audit.errors)


class ConfigTests(unittest.TestCase):
    def test_expected_config(self):
        audit = sa.Audit()
        result = sa.audit_config(audit, CONFIG, CONFIG.replace("clang 18", "clang 17"))
        self.assertEqual(audit.errors, [])
        self.assertTrue(result["arm32"])
        self.assertTrue(result["matches_build094"])

    def test_missing_module_symbol(self):
        audit = sa.Audit()
        sa.audit_config(audit, CONFIG.replace("CONFIG_SDP_MAC=m", "CONFIG_SDP_MAC=y"))
        self.assertTrue(any("SDP_MAC" in e for e in audit.errors))

    def test_arm64_rejected(self):
        audit = sa.Audit()
        sa.audit_config(audit, CONFIG + "CONFIG_ARM64=y\n")
        self.assertTrue(any("ARM32" in e for e in audit.errors))

    def test_semantic_config_drift_vs_build094(self):
        audit = sa.Audit()
        result = sa.audit_config(audit, CONFIG, CONFIG + "CONFIG_EXTRA=y\n")
        self.assertFalse(result["matches_build094"])
        self.assertEqual(result["diff_vs_build094"]["only_build094"], ["CONFIG_EXTRA=y"])


class ModuleTests(unittest.TestCase):
    def test_probe_profile(self):
        gated = """static int p(struct platform_device *pdev) { if (!x) return -EOPNOTSUPP;
                   base = devm_platform_ioremap_resource(pdev, 0); return 0; }
                   static struct platform_driver d = { .probe = p };"""
        open_probe = """static int q(struct platform_device *pdev) {
                   base = devm_platform_ioremap_resource(pdev, 0); writel(1, base); return 0; }
                   static struct platform_driver d = { .probe = q };"""
        self.assertTrue(sa.probe_profile([gated])["rejects_before_mmio"])
        profile = sa.probe_profile([open_probe])
        self.assertFalse(profile["rejects_before_mmio"])
        self.assertEqual(profile["register_writes_in_driver"], 1)

    def test_module_levels_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp)
            d = tree / "drivers/net/ethernet/sdp"
            d.mkdir(parents=True)
            (d / "Makefile").write_text("obj-$(CONFIG_SDP_MAC) += sdp_mac.o\n")
            (d / "Kconfig").write_text("config SDP_MAC\n\ttristate \"x\"\n")
            (d / "sdp_mac.c").write_text('{ .compatible = "samsung,sdp-mac" },')
            audit = sa.Audit()
            report = sa.audit_modules(audit, tree, {"SDP_MAC": "m"}, None, {}, {})
            mac = report["sdp_mac.ko"]
            self.assertTrue(mac["source"]["present"])
            self.assertEqual(mac["ko_file"], [])
            self.assertEqual(mac["build_evidence"], "not supplied")
            self.assertFalse(mac["hardware_tested"])
            # the other in-tree modules are missing in this synthetic tree
            self.assertTrue(any("sdp_hdmi.ko" in e for e in audit.errors))

    def test_find_ko(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "sub").mkdir()
            (Path(tmp) / "sub/panfrost.ko").write_bytes(b"\x7fELF")
            (Path(tmp) / "other.ko").write_bytes(b"x")
            hits = sa.find_ko([Path(tmp)])
            self.assertEqual(list(hits), ["panfrost.ko"])

    def test_build094_evidence_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            elf, log = [], []
            for module, (symbol, _d, _c) in sa.MODULES.items():
                elf.append(f"{module}\nELF Header:\n  Class:                             ELF32\n"
                           f"  Type:                              REL (Relocatable file)\n"
                           f"  Machine:                           ARM\n")
                log.append(f"  LD [M]  drivers/x/{module}")
            (d / "elf.txt").write_text("".join(elf))
            (d / "kernel.log").write_text("\n".join(log) + "\n")
            manifest = {"sha256": {name: __import__("hashlib").sha256((d / name).read_bytes()).hexdigest()
                                   for name in ("elf.txt", "kernel.log")}}
            audit = sa.Audit()
            result = sa.parse_build094(audit, d, manifest)
            self.assertEqual(audit.errors, [])
            self.assertEqual(result["panfrost.ko"]["elf"], "ELF32 ARM REL")
            self.assertTrue(result["sdp_nikel_thermal.ko"]["link_record"])

    def test_repository_cpu_modules(self):
        audit = sa.Audit()
        report = sa.audit_modules(audit, Path("/nonexistent"), {}, None, {}, {})
        for module in ("sdp_nikel_cpu_clk.ko", "sdp_nikel_cpufreq.ko", "sdp_nikel_thermal.ko"):
            self.assertTrue(report[module]["source"]["present"], module)
            self.assertTrue(report[module]["probe"]["rejects_before_mmio"], module)


class ManifestTests(unittest.TestCase):
    def test_build095_manifest_lists_the_nine_modules(self):
        manifest = json.loads((sa.REPO / "porting/build095/manifest.json").read_text())
        self.assertEqual(set(manifest["modules"]), set(sa.MODULES))
        self.assertEqual(manifest["retail_boot"], "blocked")


if __name__ == "__main__":
    unittest.main()
