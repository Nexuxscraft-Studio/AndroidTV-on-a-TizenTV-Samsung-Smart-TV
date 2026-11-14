#!/usr/bin/env python3
"""Build 096: boot the minimal ARM32 kernel on QEMU "virt" and judge the result.

Usage:
  qemu_boot_test.py run --zimage Z --initrd I --out DIR [--timeout S]
  qemu_boot_test.py analyze SERIAL_LOG [--qemu-rc N] [--timed-out]

`run` starts qemu-system-arm without a display (-nographic, -nodefaults),
writes the guest's serial console (ttyAMA0) to DIR/serial.log, watches it
while the guest runs and stops QEMU early on a kernel panic. It writes
DIR/boot-report.json and exits 0 only for a verified boot:

  * the kernel announced Linux 6.6.162 and the QEMU virt machine model,
  * the kernel started /init from the initramfs,
  * /init printed BUILD096_ARM32_QEMU_BOOT_OK on a line of its own, after
    the kernel's "Run /init" message,
  * no panic, oops or init failure was logged,
  * the guest powered itself off and QEMU exited with status 0.

QEMU emulates generic virtual hardware only. A pass says nothing about the
Samsung Q60T, its Nike-L SoC or its boot chain.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time

MARKER = "BUILD096_ARM32_QEMU_BOOT_OK"
INIT_FAIL = "BUILD096_ARM32_QEMU_INIT_FAIL"
EXPECTED_RELEASE = "6.6.162"

# Result classes and their process exit codes.
EXIT = {
    "PASS": 0,
    "KERNEL_PANIC": 10,
    "INIT_FAILURE": 11,
    "BOOT_HANG": 12,
    "NO_SERIAL_OUTPUT": 13,
    "POWEROFF_HANG": 14,
    "QEMU_ERROR": 15,
    "MARKER_INVALID": 16,
}

# Kernel messages that end a boot attempt. Checked in this order.
INIT_FAILURE_PATTERNS = (
    re.compile(r"Failed to execute /init \(error -?\d+\)"),
    re.compile(r"No working init found"),
    re.compile(r"Attempted to kill init"),
    re.compile(r"Requested init /init failed"),
    re.compile(re.escape(INIT_FAIL) + r".*"),
)
PANIC_PATTERNS = (
    re.compile(r"Kernel panic - not syncing:.*"),
    re.compile(r"Internal error: Oops.*"),
    re.compile(r"Unable to handle kernel .*"),
    re.compile(r"BUG: .*"),
)

# Boot milestones recorded as evidence (informational unless listed in REQUIRED).
MILESTONES = {
    "kernel_banner": re.compile(r"Linux version (\S+)"),
    "machine_model": re.compile(r"(?:Machine model|OF: fdt: Machine model): (.+)"),
    "cpu": re.compile(r"CPU: (ARMv7 Processor .+)"),
    "psci": re.compile(r"psci: (PSCIv[\d.]+ detected in firmware)"),
    "irq": re.compile(r"(NR_IRQS: .+)"),
    "arch_timer": re.compile(r"arch_timer: (cp15 timer.+)"),
    "smp": re.compile(r"SMP: (Total of \d+ processors activated.*)"),
    "uart": re.compile(r"(\S+: ttyAMA0 at MMIO .+)"),
    "initramfs": re.compile(r"(Trying to unpack rootfs image as initramfs.*|Unpacking initramfs.*)"),
    "run_init": re.compile(r"Run (/init) as init process"),
    "poweroff": re.compile(r"reboot: (Power down|System halted)"),
}
REQUIRED = ("kernel_banner", "machine_model", "run_init")


def analyze(text, qemu_rc=None, timed_out=False):
    """Classify a serial log. Pure function; used by `run` and the unit tests."""
    lines = text.replace("\r", "").splitlines()
    report = {"result": None, "reasons": [], "milestones": {}, "marker_line": None,
              "qemu_exit_code": qemu_rc, "timed_out": timed_out,
              "serial_lines": len(lines)}

    for name, pattern in MILESTONES.items():
        for number, line in enumerate(lines, 1):
            match = pattern.search(line)
            if match:
                report["milestones"][name] = {"line": number, "text": match.group(1).strip()}
                break

    marker_lines = [n for n, line in enumerate(lines, 1) if line.strip() == MARKER
                    or re.fullmatch(r"\[\s*\d+\.\d+\]\s*" + MARKER, line.strip())]
    loose_marker = any(MARKER in line for line in lines)
    if marker_lines:
        report["marker_line"] = marker_lines[0]

    def finish(result, reason):
        report["result"] = result
        report["reasons"].append(reason)
        report["exit_code"] = EXIT[result]
        return report

    for pattern in INIT_FAILURE_PATTERNS:
        for line in lines:
            match = pattern.search(line)
            if match:
                return finish("INIT_FAILURE", match.group(0).strip())
    for pattern in PANIC_PATTERNS:
        for line in lines:
            match = pattern.search(line)
            if match:
                return finish("KERNEL_PANIC", match.group(0).strip())

    if not any(line.strip() for line in lines):
        if qemu_rc not in (None, 0) and not timed_out:
            return finish("QEMU_ERROR", f"QEMU exited with status {qemu_rc} before any serial output")
        return finish("NO_SERIAL_OUTPUT", "the guest wrote nothing to ttyAMA0")

    if not marker_lines:
        if loose_marker:
            return finish("MARKER_INVALID", f"{MARKER} appeared, but not on a line of its own")
        if timed_out:
            last = report["milestones"]
            stage = max(last, key=lambda k: last[k]["line"]) if last else "first serial line"
            return finish("BOOT_HANG", f"timeout without {MARKER}; last milestone: {stage}")
        if qemu_rc not in (None, 0):
            return finish("QEMU_ERROR", f"QEMU exited with status {qemu_rc} without {MARKER}")
        return finish("BOOT_HANG", f"guest stopped without printing {MARKER}")

    missing = [name for name in REQUIRED if name not in report["milestones"]]
    if missing:
        return finish("MARKER_INVALID", "marker seen but kernel milestones missing: " + ", ".join(missing))
    banner = report["milestones"]["kernel_banner"]["text"]
    if not banner.startswith(EXPECTED_RELEASE):
        return finish("MARKER_INVALID", f"kernel banner reports {banner}, expected {EXPECTED_RELEASE}")
    model = report["milestones"]["machine_model"]["text"]
    if "linux,dummy-virt" not in model and "virt" not in model.lower():
        return finish("MARKER_INVALID", f"machine model {model!r} is not QEMU virt")
    if "samsung" in model.lower() or "nike" in model.lower():
        return finish("MARKER_INVALID", f"unexpected Samsung machine model {model!r}")
    if report["marker_line"] < report["milestones"]["run_init"]["line"]:
        return finish("MARKER_INVALID", "marker appeared before the kernel ran /init")

    if timed_out:
        return finish("POWEROFF_HANG", f"{MARKER} seen, but the guest did not power off in time")
    if qemu_rc != 0:
        return finish("QEMU_ERROR", f"{MARKER} seen, but QEMU exited with status {qemu_rc}")
    return finish("PASS", f"/init printed {MARKER} at serial line {report['marker_line']} "
                          "and the guest powered off")


def qemu_command(qemu, zimage, initrd, serial_log, smp, memory):
    # Generic QEMU virt board and its own generated DT. No -dtb, no Samsung
    # addresses: the kernel finds the PL011 through QEMU's device tree.
    return [qemu, "-M", "virt", "-cpu", "cortex-a15", "-smp", str(smp), "-m", str(memory),
            "-nographic", "-nodefaults", "-no-reboot", "-monitor", "none",
            "-serial", f"file:{serial_log}",
            "-kernel", str(zimage), "-initrd", str(initrd),
            "-append", "console=ttyAMA0 earlycon panic=-1 rdinit=/init loglevel=8"]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    serial_log = out / "serial.log"
    stderr_log = out / "qemu-stderr.log"
    serial_log.write_bytes(b"")
    qemu = shutil.which(args.qemu) or args.qemu
    if not shutil.which(qemu):
        report = {"result": "QEMU_ERROR", "reasons": [f"{args.qemu} not found on PATH"],
                  "exit_code": EXIT["QEMU_ERROR"]}
        (out / "boot-report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"build096: {report['reasons'][0]}", file=sys.stderr)
        return report["exit_code"]

    version = subprocess.run([qemu, "--version"], capture_output=True, text=True).stdout.splitlines()
    command = qemu_command(qemu, args.zimage, args.initrd, serial_log, args.smp, args.memory)
    (out / "qemu-command.txt").write_text(shlex.join(command) + "\n")
    print("build096: " + shlex.join(command))

    start = time.monotonic()
    timed_out = early_stop = False
    with open(stderr_log, "wb") as stderr:
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stderr, stderr=stderr)
        while proc.poll() is None:
            time.sleep(0.25)
            text = serial_log.read_text(errors="replace")
            if any(p.search(text) for p in (*PANIC_PATTERNS, *INIT_FAILURE_PATTERNS)):
                time.sleep(1.0)       # let the panic backtrace reach the log
                early_stop = True
                break
            if time.monotonic() - start > args.timeout:
                timed_out = True
                break
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    elapsed = round(time.monotonic() - start, 2)

    text = serial_log.read_text(errors="replace")
    report = analyze(text, qemu_rc=None if early_stop else proc.returncode, timed_out=timed_out)
    report.update({
        "elapsed_seconds": elapsed,
        "timeout_seconds": args.timeout,
        "stopped_early_on_failure": early_stop,
        "qemu_version": version[0] if version else None,
        "qemu_command": command,
        "inputs": {"zImage": sha256(args.zimage), "initramfs.cpio.gz": sha256(args.initrd)},
        "serial_log_sha256": sha256(serial_log),
        "scope": "QEMU virt (generic virtual ARM hardware); not Samsung Q60T hardware",
    })
    (out / "boot-report.json").write_text(json.dumps(report, indent=2) + "\n")

    print("---- serial console (ttyAMA0) ----")
    print(text.rstrip())
    print("----------------------------------")
    if stderr_log.stat().st_size:
        print("---- qemu stderr ----")
        print(stderr_log.read_text(errors="replace").rstrip())
    print(f"build096: result {report['result']}: {'; '.join(report['reasons'])} ({elapsed}s)")
    return report["exit_code"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--zimage", required=True)
    r.add_argument("--initrd", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--timeout", type=float, default=120.0)
    r.add_argument("--qemu", default="qemu-system-arm")
    r.add_argument("--smp", type=int, default=2)
    r.add_argument("--memory", type=int, default=256)
    a = sub.add_parser("analyze")
    a.add_argument("serial_log")
    a.add_argument("--qemu-rc", type=int)
    a.add_argument("--timed-out", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "run":
        return run(args)
    report = analyze(Path(args.serial_log).read_text(errors="replace"), args.qemu_rc, args.timed_out)
    print(json.dumps(report, indent=2))
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
