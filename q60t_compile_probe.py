#!/usr/bin/env python3
"""Reproducible *host-only* ARM32 zImage compiler probe for Samsung Nike code.

Never runs Samsung BUILD.sh, signs artifacts, contacts a television or writes
to the supplied source tree. The result is not a firmware/LineageOS image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys

import q60t_android_kernel as android
import q60t_kernel_build as kernel
import q60t_kernel_stage as stage


PROJECT = Path(__file__).resolve().parent
PATCHES = (
    PROJECT / "porting/patches/0001-android-binder32-modern-abi.patch",
    PROJECT / "porting/patches/0002-legacy-dtc-yylloc-host-gcc.patch",
)
EXPECTED_DEFCONFIG_SHA256 = "54dab3e4d55462362d074e6ee11bac7be4d201cb0daa6b18de1454f162f06bc0"
EXPECTED_ANDROID_KCONFIG_SHA256 = "2e92b1dc5e3dc9f8822488cb4479891932eb419f9ce97d2a81167f361e74f795"
GENERATED_HEADER = (
    "/* HOST-ONLY TEST: not an authentic Samsung firmware build version. */\n"
    "/* Build 013 research; NEVER flash, deploy or sign this image. */\n"
    '#define DTV_KERNEL_VERSION "HOST_ONLY_TEST, release"\n'
    '#define DTV_LAST_PATCH "EXPERIMENTAL, Nike.M-Tizen, NO_FLASH"\n'
)
RESEARCH_SECURITY = {
    "SECURITY_SMACK": "y",
    "SECURITY_SFD": "y",
    "SECURITY_SELINUX": "n",
}
RESEARCH_FEATURES = {
    "ANDROID_BINDER_IPC": "y",
    "ANDROID_BINDER_IPC_32BIT": "n",
    "ASHMEM": "y",
    "MEMCG": "y",
    "ION": "y",
    "EXT4_FS": "y",
    "OVERLAY_FS": "y",
    "TUN": "y",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_directories(source: Path, workspace: Path) -> None:
    if not source.is_dir() or source.is_symlink():
        raise ValueError("Kernelquelle ist kein reguläres Verzeichnis")
    source_real = source.resolve()
    work_real = workspace.resolve()
    if source_real == work_real or source_real.is_relative_to(work_real) or work_real.is_relative_to(source_real):
        raise ValueError("Arbeitsverzeichnis darf Quelle nicht überlappen")
    if workspace.exists() or workspace.is_symlink():
        raise ValueError("Ausgabeverzeichnis existiert bereits – Abbruch ohne Überschreiben")
    if not workspace.parent.is_dir():
        raise ValueError("Übergeordnetes Arbeitsverzeichnis fehlt")
    if kernel.source_version(source) != "4.1.10":
        raise ValueError("Erwartet Samsung Linux 4.1.10")
    checks = (
        (source / "arch/arm/configs" / android.REFERENCE_PROFILE, EXPECTED_DEFCONFIG_SHA256),
        (source / "drivers/android/Kconfig", EXPECTED_ANDROID_KCONFIG_SHA256),
    )
    for path, digest in checks:
        if not path.is_file() or path.is_symlink() or file_sha256(path) != digest:
            raise ValueError(f"Unerwarteter Quellstand: {path.relative_to(source)}")


def check_source_symlinks(source: Path) -> int:
    """Preserve kernel-relative symlinks, reject escapes from the input tree."""
    root = source.resolve()
    checked = 0
    for base, dirs, files in os.walk(source, followlinks=False):
        for name in dirs + files:
            path = Path(base) / name
            if path.is_symlink():
                checked += 1
                if not path.resolve().is_relative_to(root):
                    raise ValueError(f"Symlink verlässt Quellbaum: {path.relative_to(source)}")
    return checked


def find_compiler(prefix: str) -> dict:
    compiler = shutil.which(prefix + "gcc")
    assembler = shutil.which(prefix + "as")
    if not compiler or not assembler:
        raise ValueError("ARM32-GCC/Assembler nicht gefunden (CROSS_COMPILE-Prefix)")
    machine = subprocess.run([compiler, "-dumpmachine"], check=True, capture_output=True, text=True, timeout=15).stdout.strip()
    if machine not in {"arm-linux-gnueabi", "armv7l-tizen-linux-gnueabi", "arm-linux-gnueabihf"}:
        raise ValueError(f"Kein erwarteter ARM32-Linux-Cross-Compiler: {machine}")
    version_line = subprocess.run([compiler, "--version"], check=True, capture_output=True, text=True, timeout=15).stdout.splitlines()[0]
    version_probe = subprocess.run([compiler, "-dumpfullversion"], capture_output=True,
                                   text=True, timeout=15)
    if version_probe.returncode:
        # GCC 6 predates -dumpfullversion.
        version_probe = subprocess.run([compiler, "-dumpversion"], check=True,
                                       capture_output=True, text=True, timeout=15)
    full_version = version_probe.stdout.strip()
    major_match = re.match(r"(\d+)", full_version)
    major = int(major_match.group(1)) if major_match else 0
    return {
        "compiler": compiler,
        "assembler": assembler,
        "machine": machine,
        "version": version_line,
        "major": major,
        "exact_samsung_vendor_compiler_verified": False,
    }


def diagnostics(log: Path, limit: int = 14) -> list[str]:
    if not log.exists():
        return []
    findings = []
    with log.open("r", errors="replace") as stream:
        for line in stream:
            text = line.strip()
            if ("fatal error:" in text or "error:" in text or
                    "Error " in text or "undefined reference" in text):
                if len(findings) < limit:
                    findings.append(text[:500])
    return findings


def run_logged(args: list[str], log: Path, timeout_seconds: int) -> dict:
    """No shell or vendor scripts; terminate make's process group on timeout."""
    with log.open("x", encoding="utf-8") as stream:
        process = subprocess.Popen(args, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        timed_out = False
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            exit_code = 124
    return {"exit_code": exit_code, "timed_out": timed_out,
            "log_sha256": file_sha256(log), "errors": diagnostics(log)}


def make_args(source: Path, output: Path, prefix: str, jobs: int, major: int,
              target: str) -> list[str]:
    args = ["make", "-C", str(source), "O=" + str(output), "ARCH=arm",
            "CROSS_COMPILE=" + prefix, "HOSTCC=gcc"]
    compat_flags = []
    if major >= 10:
        # Modern GCC diagnoses a 4.1-era attribute conflict as an error.
        # This is a *compiler diagnostic* override, not a security config change.
        compat_flags.append("-Wno-error=attributes")
    # The Samsung source contains this debug header but its default DVB-core
    # include paths do not find it. This affects search paths only.
    debug_headers = source / "kernel/t2ddebugd/include"
    if debug_headers.is_dir():
        compat_flags.append("-I" + str(debug_headers))
    if compat_flags:
        args.append("KCFLAGS=" + " ".join(compat_flags))
    args.extend([f"-j{jobs}", target])
    return args


def prepare_shadow(source: Path, workspace: Path) -> tuple[Path, Path]:
    shadow = workspace / "linux-4.1.10-shadow"
    shutil.copytree(source, shadow, symlinks=True)
    for patch in PATCHES:
        if not patch.is_file() or patch.is_symlink():
            raise ValueError(f"Fehlender Projektpatch: {patch.name}")
        # Samsung tar archives mark some files read-only: only shadow is writable.
        for relative in ({
            PATCHES[0].name: ("drivers/android/Kconfig",),
            PATCHES[1].name: ("scripts/dtc/dtc-lexer.l", "scripts/dtc/dtc-lexer.lex.c_shipped"),
        }[patch.name]):
            file = shadow / relative
            file.chmod(file.stat().st_mode | 0o200)
        check = subprocess.run(["patch", "--batch", "--forward", "--fuzz=0",
                                "-p1", "-d", str(shadow), "-i", str(patch)],
                               capture_output=True, text=True, timeout=30)
        if check.returncode:
            raise ValueError(f"Patch konnte nicht angewendet werden: {patch.name}: "
                             + check.stdout[-300:] + check.stderr[-300:])
    header = shadow / "include/linux/vdlp_version.h"
    if header.exists() or header.is_symlink():
        raise ValueError("Unerwarteter vdlp_version.h; nicht ersetzen")
    header.write_text(GENERATED_HEADER, encoding="utf-8")
    generated_fragment = workspace / "android-research.fragment"
    generated_fragment.write_text(android.fragment(android.compute_report(source)), encoding="utf-8")
    output = workspace / "output"
    stage.stage(source, generated_fragment, output)
    return shadow, output


def verify_config(output: Path) -> dict:
    resolved = android.read_config(output / ".config")["symbols"]
    checked = {name: resolved.get(name, "n") for name in (*RESEARCH_FEATURES, *RESEARCH_SECURITY)}
    expected = RESEARCH_FEATURES | RESEARCH_SECURITY
    differences = {name: {"expected": value, "actual": checked[name]}
                   for name, value in expected.items() if checked[name] != value}
    return {"sha256": file_sha256(output / ".config"),
            "verified": not differences, "checked": checked, "differences": differences}


def execute(source: Path, workspace: Path, prefix: str, jobs: int,
            timeout_seconds: int, preflight_only: bool = False) -> dict:
    validate_directories(source, workspace)
    # Kbuild interprets a relative O= differently after make -C. Normalize
    # *all* paths before invoking it, or it may build in an unintended tree.
    source = source.resolve()
    workspace = workspace.resolve()
    if "/" in prefix:
        prefix = str((Path.cwd() / prefix).resolve())
    link_count = check_source_symlinks(source)
    compiler = find_compiler(prefix)
    if not shutil.which("bc"):
        raise ValueError("Kernel-Build benötigt 'bc' (Host-Werkzeug)")
    report = {
        "type": "q60t_arm32_host_compile_probe",
        "build": "013", "target": "zImage", "kernel_version": "4.1.10",
        "source_reference": "Samsung 20_DTV_NikeL.zip (Nike-L package; Nike.M candidate config)",
        "source_matches_live_firmware_2743_0": False,
        "original_source_modified": False,
        "source_symlinks_checked": link_count,
        "vendor_build_script_executed": False,
        "synthetic_version_header": not preflight_only,
        "compiler": compiler,
        "host_only": True, "tv_accessed": False, "boot_or_flash_performed": False,
        "android_or_lineageos_boot_test_passed": False,
        "signed_or_flashable_image_produced": False,
        "disclaimer": "An ARM zImage is not a deployable Samsung TV firmware. "
                      "No boot signing, firmware-compatible defconfig, rollback, "
                      "Android HAL or runtime ABI has been established.",
        "status": "PRECHECK_PASS" if preflight_only else "RUNNING",
    }
    if preflight_only:
        return report
    workspace.mkdir(mode=0o700)
    result_path = workspace / "compile-report.json"
    try:
        shadow, output = prepare_shadow(source, workspace)
        kconfig_log = workspace / "kconfig.log"
        config_result = run_logged(
            make_args(shadow, output, prefix, 1, compiler["major"], "olddefconfig"),
            kconfig_log, timeout_seconds)
        report["kconfig"] = config_result
        if config_result["exit_code"]:
            report["status"] = "KCONFIG_FAILED"
            return report
        report["resolved_config"] = verify_config(output)
        if not report["resolved_config"]["verified"]:
            report["status"] = "KCONFIG_SECURITY_OR_FEATURE_MISMATCH"
            return report
        compile_log = workspace / "compile.log"
        compile_result = run_logged(
            make_args(shadow, output, prefix, jobs, compiler["major"], "zImage"),
            compile_log, timeout_seconds)
        report["compile"] = compile_result
        artifact = output / "arch/arm/boot/zImage"
        if compile_result["exit_code"] == 0 and artifact.is_file():
            report["artifact"] = {"path_within_workspace": "output/arch/arm/boot/zImage",
                                  "size_bytes": artifact.stat().st_size,
                                  "sha256": file_sha256(artifact),
                                  "safe_to_flash": False}
            report["status"] = "HOST_KERNEL_COMPILED_NOT_BOOTABLE_VALIDATED"
        else:
            report["status"] = "ARM32_COMPILE_FAILED"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        report["status"] = "PROBE_ERROR"
        report["error"] = str(exc)[:1000]
    finally:
        with result_path.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline ARM32-Linux-Kernelcompile, kein TV-Flash")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--cross-prefix", required=True,
                        help="z.B. /opt/linaro/bin/arm-linux-gnueabi-")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.jobs <= 32 or not 60 <= args.timeout <= 7200:
            raise ValueError("jobs 1..32 und timeout 60..7200 Sekunden erwartet")
        report = execute(args.source, args.workspace, args.cross_prefix,
                         args.jobs, args.timeout, args.preflight)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Build-013-Vorprüfung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"PRECHECK_PASS", "HOST_KERNEL_COMPILED_NOT_BOOTABLE_VALIDATED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
