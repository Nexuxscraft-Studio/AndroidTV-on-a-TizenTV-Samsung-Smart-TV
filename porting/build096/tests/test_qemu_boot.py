"""Host tests for the Build 096 QEMU harness. They never start a real QEMU."""

import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import textwrap
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import qemu_boot_test as harness  # noqa: E402

MARKER = harness.MARKER

GOOD = textwrap.dedent(f"""\
    [    0.000000] Booting Linux on physical CPU 0x0
    [    0.000000] Linux version 6.6.162 (build096@qemu-virt) (clang version 18) #1 SMP Thu Jan  1 00:00:00 UTC 2026
    [    0.000000] CPU: ARMv7 Processor [414fc0f0] revision 0 (ARMv7), cr=30c5387d
    [    0.000000] OF: fdt: Machine model: linux,dummy-virt
    [    0.000000] psci: PSCIv0.2 detected in firmware.
    [    0.000000] arch_timer: cp15 timer(s) running at 62.50MHz (virt).
    [    0.050000] SMP: Total of 2 processors activated (125.00 BogoMIPS).
    [    0.080000] Trying to unpack rootfs image as initramfs...
    [    0.090000] 9000000.pl011: ttyAMA0 at MMIO 0x9000000 (irq = 17, base_baud = 0) is a PL011 rev1
    [    0.120000] Run /init as init process
    build096-init: started
    build096-init: kernel release 6.6.162
    build096-init: cpu ARMv7 (32-bit)
    build096-init: dt compatible linux,dummy-virt
    {MARKER}
    build096-init: requesting power off
    [    0.200000] reboot: Power down
    """)


class AnalyzeTests(unittest.TestCase):
    def test_pass(self):
        report = harness.analyze(GOOD, qemu_rc=0)
        self.assertEqual(report["result"], "PASS", report["reasons"])
        self.assertEqual(report["exit_code"], 0)
        for name in ("psci", "arch_timer", "smp", "uart", "poweroff", "cpu"):
            self.assertIn(name, report["milestones"])

    def test_kernel_panic(self):
        log = GOOD.split("[    0.120000]")[0] + \
            "[    0.110000] Kernel panic - not syncing: VFS: Unable to mount root fs\n"
        report = harness.analyze(log, qemu_rc=0)
        self.assertEqual(report["result"], "KERNEL_PANIC")
        self.assertNotEqual(report["exit_code"], 0)

    def test_oops(self):
        log = GOOD.replace("[    0.120000] Run /init", "[    0.11] Unable to handle kernel NULL pointer dereference\n[    0.120000] Run /init")
        self.assertEqual(harness.analyze(log, qemu_rc=0)["result"], "KERNEL_PANIC")

    def test_init_exec_failure(self):
        log = GOOD.split("build096-init")[0] + textwrap.dedent("""\
            [    0.121000] Failed to execute /init (error -8)
            [    0.122000] Kernel panic - not syncing: No working init found.
            """)
        report = harness.analyze(log, qemu_rc=0)
        self.assertEqual(report["result"], "INIT_FAILURE")
        self.assertIn("error -8", report["reasons"][0])

    def test_init_self_check_failure(self):
        log = GOOD.replace(MARKER, "BUILD096_ARM32_QEMU_INIT_FAIL: device tree is not linux,dummy-virt")
        self.assertEqual(harness.analyze(log, qemu_rc=0)["result"], "INIT_FAILURE")

    def test_init_killed(self):
        log = GOOD.replace(MARKER, "[    0.3] Kernel panic - not syncing: Attempted to kill init! exitcode=0x0000000b")
        self.assertEqual(harness.analyze(log, qemu_rc=0)["result"], "INIT_FAILURE")

    def test_hang_before_init(self):
        log = GOOD.split("[    0.080000]")[0]
        report = harness.analyze(log, qemu_rc=None, timed_out=True)
        self.assertEqual(report["result"], "BOOT_HANG")
        self.assertIn("smp", report["reasons"][0])

    def test_no_serial_output(self):
        self.assertEqual(harness.analyze("", timed_out=True)["result"], "NO_SERIAL_OUTPUT")

    def test_qemu_failed_to_start(self):
        self.assertEqual(harness.analyze("", qemu_rc=1)["result"], "QEMU_ERROR")

    def test_poweroff_hang(self):
        log = GOOD.replace("[    0.200000] reboot: Power down\n", "")
        self.assertEqual(harness.analyze(log, timed_out=True)["result"], "POWEROFF_HANG")

    def test_marker_must_be_own_line(self):
        log = GOOD.replace(f"{MARKER}\n", f"echo {MARKER}\n")
        self.assertEqual(harness.analyze(log, qemu_rc=0)["result"], "MARKER_INVALID")

    def test_marker_before_init(self):
        log = GOOD.replace(f"{MARKER}\n", "").replace("[    0.080000]", f"{MARKER}\n[    0.080000]")
        self.assertEqual(harness.analyze(log, qemu_rc=0)["result"], "MARKER_INVALID")

    def test_wrong_kernel_version(self):
        log = GOOD.replace("Linux version 6.6.162", "Linux version 6.1.0")
        self.assertEqual(harness.analyze(log, qemu_rc=0)["result"], "MARKER_INVALID")

    def test_samsung_model_rejected(self):
        log = GOOD.replace("linux,dummy-virt\n", "Samsung Q60T Nike-L\n", 1)
        self.assertEqual(harness.analyze(log, qemu_rc=0)["result"], "MARKER_INVALID")

    def test_marker_without_kernel_milestones(self):
        self.assertEqual(harness.analyze(f"{MARKER}\n", qemu_rc=0)["result"], "MARKER_INVALID")


class CommandTests(unittest.TestCase):
    def test_virtual_board_only(self):
        cmd = harness.qemu_command("qemu-system-arm", "zImage", "initrd", "serial.log", 2, 256)
        joined = " ".join(cmd)
        self.assertIn("-M virt", joined)
        self.assertIn("-cpu cortex-a15", joined)
        self.assertIn("-nographic", cmd)
        self.assertIn("-nodefaults", cmd)
        self.assertIn("-no-reboot", cmd)
        self.assertIn("console=ttyAMA0", joined)
        self.assertNotIn("-dtb", cmd)
        self.assertNotIn("sdp", joined.lower())
        self.assertNotIn("samsung", joined.lower())


FAKE_QEMU = """#!{python}
import sys, time
args = sys.argv[1:]
if args == ["--version"]:
    print("QEMU emulator version 0.0 (fake)"); sys.exit(0)
serial = args[args.index("-serial") + 1].split(":", 1)[1]
mode = {mode!r}
log = open(serial, "w")
log.write(open({good!r}).read() if mode != "panic" else "Linux version 6.6.162\\nKernel panic - not syncing: test\\n")
log.flush()
if mode in ("hang", "panic"):
    time.sleep(60)
"""


class RunTests(unittest.TestCase):
    def fake(self, mode):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        good = root / "good.log"
        good.write_text(GOOD.replace("[    0.200000] reboot: Power down\n", "") if mode == "hang" else GOOD)
        qemu = root / "qemu-system-arm"
        qemu.write_text(FAKE_QEMU.format(python=sys.executable, mode=mode, good=str(good)))
        qemu.chmod(qemu.stat().st_mode | stat.S_IEXEC)
        (root / "zImage").write_bytes(b"z")
        (root / "initrd").write_bytes(b"i")
        return root, qemu

    def tearDown(self):
        self.tmp.cleanup()

    def invoke(self, mode, timeout="20"):
        root, qemu = self.fake(mode)
        rc = harness.main(["run", "--qemu", str(qemu), "--zimage", str(root / "zImage"),
                           "--initrd", str(root / "initrd"), "--out", str(root / "out"),
                           "--timeout", timeout])
        return rc, json.loads((root / "out/boot-report.json").read_text())

    def test_run_pass(self):
        rc, report = self.invoke("pass")
        self.assertEqual((rc, report["result"]), (0, "PASS"))
        self.assertIn("not Samsung", report["scope"])

    def test_run_timeout(self):
        rc, report = self.invoke("hang", timeout="2")
        self.assertEqual(report["result"], "POWEROFF_HANG")
        self.assertTrue(report["timed_out"])
        self.assertNotEqual(rc, 0)

    def test_run_panic_stops_early(self):
        rc, report = self.invoke("panic", timeout="30")
        self.assertEqual(report["result"], "KERNEL_PANIC")
        self.assertTrue(report["stopped_early_on_failure"])
        self.assertLess(report["elapsed_seconds"], 15)
        self.assertNotEqual(rc, 0)

    def test_missing_qemu(self):
        root, _ = self.fake("pass")
        rc = harness.main(["run", "--qemu", str(root / "missing"), "--zimage", str(root / "zImage"),
                           "--initrd", str(root / "initrd"), "--out", str(root / "out")])
        self.assertEqual(rc, harness.EXIT["QEMU_ERROR"])


class SourceTests(unittest.TestCase):
    def test_init_never_contains_marker_literal(self):
        source = (HERE.parent / "init.c").read_text()
        self.assertNotIn(MARKER, source)
        self.assertIn("LINUX_REBOOT_CMD_POWER_OFF", source)

    def test_config_has_no_samsung_symbols(self):
        config = (HERE.parent / "qemu-virt-arm32.config").read_text()
        for symbol in ("ARCH_SDP", "SERIAL_SDP", "SDP1804", "DRM_SDP"):
            self.assertNotIn(symbol, config)
        for symbol in ("CONFIG_ARCH_VIRT=y", "CONFIG_SERIAL_AMBA_PL011_CONSOLE=y",
                       "CONFIG_BLK_DEV_INITRD=y", "CONFIG_ARM_PSCI=y"):
            self.assertIn(symbol, config)


if __name__ == "__main__":
    unittest.main()
