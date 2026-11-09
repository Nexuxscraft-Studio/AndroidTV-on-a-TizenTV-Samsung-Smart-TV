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
import q60t_binder_lab as binder_lab
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
# An intentionally separate *host-only* configuration experiment. Keeping
# Samsung's SMACK/SFD code compiled is not a claim that both can enforce
# policy simultaneously, or that its vendor software works with SELinux.
SELINUX_LAB_SECURITY = {
    "SECURITY_SMACK": "y",
    "SECURITY_SFD": "y",
    "SECURITY_SELINUX": "y",
    "DEFAULT_SECURITY_SELINUX": "y",
    "DEFAULT_SECURITY_SMACK": "n",
    "DEFAULT_SECURITY": '"selinux"',
}
SELINUX_LAB_OVERLAY = {
    "SECURITY_SELINUX": "y",
    "DEFAULT_SECURITY_SELINUX": "y",
    "DEFAULT_SECURITY_SMACK": "n",
}
ANDROID_BOOTLAB_FEATURES = {
    "BLK_DEV_INITRD": "y",
    "IKCONFIG": "y",
    "IKCONFIG_PROC": "y",
}
ANDROID_BOOTLAB_OVERLAY = SELINUX_LAB_OVERLAY | ANDROID_BOOTLAB_FEATURES
# QEMU 'virt' is a distinct virtual board, not the Samsung SDP hardware.
# These settings are mandatory for the isolated ARMv7/Cortex-A15 experiment.
QEMU_VIRT_OVERLAY = {
    "ARCH_SDP": "n",
    "ARCH_SDP_NIKE": "n",
    # Samsung-only PM GPIO addresses and VDFS hardware headers do not exist on virt.
    "POWER_SAVING_MODE": "n",
    "ALWAYS_INSTANT_ON": "n",
    "VDFS4_FS": "n",
    # Samsung MMC hardware decompressor requires mach/hw_decompress.h,
    # which does not exist on QEMU virt (no Samsung MMC controller).
    "HW_DECOMPRESSOR": "n",
    "HW_DECOMP_BLK_MMC_SUBSYSTEM": "n",
    # QEMU virt provides no Samsung eMMC controller. A diskless initrd boot
    # must not link Samsung-specific MMC HS400 callbacks from the vendor tree.
    "MMC": "n",
    "SDP_MMC_RDQS_FIXUP": "n",
    "SDP_MMC_EXECUTE_HS400_RDQS_TUNING": "n",
    # Samsung emergency klog persists to /dev/mmcblk0, absent on QEMU virt;
    # regular printk, serial logging, and dmesg remain enabled.
    "EMRG_SAVE_KLOG": "n",
    # Samsung SFD securecontainer casts inode->i_security to Smack data;
    # that is unsafe when this host-only profile selects SELinux as LSM.
    "SECURITY_SFD": "n",
    "SECURITY_SFD_SECURECONTAINER": "n",
    "ARCH_MULTIPLATFORM": "y",
    "ARCH_MULTI_V7": "y",
    "ARCH_VIRT": "y",
    "ARM_PSCI": "y",
    "SERIAL_AMBA_PL011": "y",
    "SERIAL_AMBA_PL011_CONSOLE": "y",
    "DEVTMPFS": "y",
    "DEVTMPFS_MOUNT": "y",
    "VIRTIO": "y",
    "VIRTIO_MMIO": "y",
    # The first boot probe uses -nodefaults and no disks; vendor virtio_blk.c
    # is incompatible with the 4.1.10 virtio API in this source snapshot.
    "VIRTIO_BLK": "n",
    "RD_GZIP": "y",
    "TMPFS": "y",
}
# Build 020 is an opt-in derivative of Build 018. The Build-018 QEMU
# configuration and existing workspaces remain byte-for-byte untouched.
QEMU_ION_OVERLAY = {"ION_DUMMY": "y"}
QEMU_PROFILES = {"qemu-binder-lab", "qemu-ion-lab"}
PROFILES = {"tizen", "selinux-lab", "android-bootlab", "binder-lab"} | QEMU_PROFILES
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


def apply_research_overlay(output: Path, profile: str) -> None:
    """Opt-in change to *staged* .config only, never to vendor source."""
    if profile not in {"selinux-lab", "android-bootlab", "binder-lab"} | QEMU_PROFILES:
        raise ValueError("Für dieses Profil ist kein Overlay erlaubt")
    changes = (ANDROID_BOOTLAB_OVERLAY if profile in {"android-bootlab", "binder-lab"} | QEMU_PROFILES
               else SELINUX_LAB_OVERLAY)
    if profile in QEMU_PROFILES:
        changes = changes | QEMU_VIRT_OVERLAY
    if profile == "qemu-ion-lab":
        changes = changes | QEMU_ION_OVERLAY
    config_path = output / ".config"
    config_path.write_text(stage.shadow_config(
        config_path.read_text(encoding="utf-8"), changes),
        encoding="utf-8")
    manifest_path = output / "STAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "EXPERIMENTAL_PROFILE_STAGED_NOT_KCONFIG_VALIDATED"
    manifest["profile"] = profile
    manifest["vendor_security_untouched"] = False
    manifest["experimental_config_changes"] = changes
    if profile in QEMU_PROFILES:
        manifest["virtual_machine"] = "QEMU virt / ARMv7 Cortex-A15 (not Samsung Nike)"
        manifest["qemu_boot_or_binder_runtime_verified"] = False
    manifest["staged_config_sha256"] = file_sha256(config_path)
    if profile in QEMU_PROFILES:
        manifest["note"] = (
            "Host-only QEMU experiment: SELinux is default. Samsung SFD "
            "is disabled because its SecureContainer hook assumes Smack "
            "ownership of inode->i_security. This is not a Samsung TV "
            "security configuration. Never flash the image.")
        if profile == "qemu-ion-lab":
            manifest["note"] += " Build 020 enables ION_DUMMY in this QEMU shadow only."
    else:
        manifest["note"] = (
            "Host-only experiment: switch default kernel LSM to SELinux. "
            "Samsung SMACK/SFD remain compiled but Android runtime policy and "
            "device compatibility are unverified. Never deploy to a television.")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")


def apply_selinux_lab_overlay(output: Path) -> None:
    """Keep the explicit SELinux-only test helper for repeatable unit tests."""
    apply_research_overlay(output, "selinux-lab")


def validate_ion_dummy_source(shadow: Path) -> None:
    """Fail closed unless this *specific* vendor snapshot has a wired dummy.

    Never inject unreviewed upstream driver code into Samsung's source tree.
    Only the QEMU profile enables CONFIG_ION_DUMMY in the shadow .config.
    """
    ion_dir = shadow / "drivers/staging/android/ion"
    required = ("Kconfig", "Makefile", "ion_dummy_driver.c")
    for name in required:
        path = ion_dir / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"ION-Dummy fehlt im Samsung-Quellstand: {path}")
    kconfig = (ion_dir / "Kconfig").read_text(encoding="utf-8", errors="replace")
    makefile = (ion_dir / "Makefile").read_text(encoding="utf-8", errors="replace")
    driver = (ion_dir / "ion_dummy_driver.c").read_text(encoding="utf-8", errors="replace")
    if not re.search(r"(?m)^\s*config\s+ION_DUMMY\b", kconfig):
        raise ValueError("ION-Dummy-Kconfig-Symbol fehlt – kein stiller Fake-Treiber")
    if not re.search(r"CONFIG_ION_DUMMY\).*ion_dummy_driver\.o", makefile):
        raise ValueError("ION-Dummy nicht in Kernel-Makefile verdrahtet")
    if "ion_device_create" not in driver or "ion_device_add_heap" not in driver:
        raise ValueError("ION-Dummy-Treiber-API passt nicht zum erwarteten Kernel")
    # Build-020 guest uses the *legacy* 4.1 ION handle ABI, not the later
    # dma-buf-fd-only ABI. Refuse to run an ioctl with the wrong structure.
    candidates = (shadow / "drivers/staging/android/uapi/ion.h",
                  shadow / "drivers/staging/android/ion/ion.h",
                  shadow / "include/uapi/linux/ion.h")
    header_text = "\n".join(
        candidate.read_text(encoding="utf-8", errors="replace")
        for candidate in candidates if candidate.is_file() and not candidate.is_symlink()
    )
    if not all(token in header_text for token in (
            "struct ion_allocation_data", "heap_id_mask", "align",
            "ion_user_handle_t", "ION_IOC_ALLOC", "ION_IOC_FREE")):
        raise ValueError("ION-UAPI ist nicht das erwartete Legacy-Handle-ABI – kein ioctl-Test")


def prepare_shadow(source: Path, workspace: Path,
                   profile: str = "tizen") -> tuple[Path, Path, dict | None]:
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
    binder_metadata = (binder_lab.patch_shadow(shadow, workspace)
                       if profile in {"binder-lab"} | QEMU_PROFILES else None)
    if profile == "qemu-ion-lab":
        validate_ion_dummy_source(shadow)
    generated_fragment = workspace / "android-research.fragment"
    generated_fragment.write_text(android.fragment(android.compute_report(source)), encoding="utf-8")
    output = workspace / "output"
    stage.stage(source, generated_fragment, output)
    if profile in {"selinux-lab", "android-bootlab", "binder-lab"} | QEMU_PROFILES:
        apply_research_overlay(output, profile)
    return shadow, output, binder_metadata


def verify_config(output: Path, profile: str = "tizen") -> dict:
    resolved = android.read_config(output / ".config")["symbols"]
    security = (SELINUX_LAB_SECURITY if profile != "tizen"
                else RESEARCH_SECURITY)
    if profile in {"android-bootlab", "binder-lab"} | QEMU_PROFILES:
        security = security | ANDROID_BOOTLAB_FEATURES
    checked = {name: resolved.get(name, "n") for name in (*RESEARCH_FEATURES, *security)}
    expected = RESEARCH_FEATURES | security
    if profile in QEMU_PROFILES:
        expected = expected | QEMU_VIRT_OVERLAY
        checked.update({name: resolved.get(name, "n") for name in QEMU_VIRT_OVERLAY})
    if profile == "qemu-ion-lab":
        expected = expected | QEMU_ION_OVERLAY
        checked.update({name: resolved.get(name, "n") for name in QEMU_ION_OVERLAY})
    differences = {name: {"expected": value, "actual": checked[name]}
                   for name, value in expected.items() if checked[name] != value}
    return {"sha256": file_sha256(output / ".config"),
            "verified": not differences, "checked": checked, "differences": differences}


def execute(source: Path, workspace: Path, prefix: str, jobs: int,
            timeout_seconds: int, preflight_only: bool = False,
            profile: str = "tizen") -> dict:
    if profile not in PROFILES:
        raise ValueError("Unbekanntes experimentelles Kernelprofil")
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
        "build": "020" if profile == "qemu-ion-lab" else ("018" if profile == "qemu-binder-lab" else (
            "016" if profile == "binder-lab" else ("015" if profile != "tizen" else "013"))),
        "profile": profile, "target": "zImage", "kernel_version": "4.1.10",
        "source_reference": "Samsung 20_DTV_NikeL.zip (Nike-L package; Nike.M candidate config)",
        "source_matches_live_firmware_2743_0": False,
        "original_source_modified": False,
        "source_symlinks_checked": link_count,
        "vendor_build_script_executed": False,
        "vendor_security_config_unchanged": profile == "tizen",
        "default_lsm_changed_for_host_experiment": profile != "tizen",
        "synthetic_version_header": not preflight_only,
        "compiler": compiler,
        "host_only": True, "tv_accessed": False, "boot_or_flash_performed": False,
        "qemu_runtime_verified": False, "binder_runtime_verified": False,
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
        shadow, output, binder_metadata = prepare_shadow(source, workspace, profile)
        if binder_metadata is not None:
            report["binder_lab"] = binder_metadata
        kconfig_log = workspace / "kconfig.log"
        config_result = run_logged(
            make_args(shadow, output, prefix, 1, compiler["major"], "olddefconfig"),
            kconfig_log, timeout_seconds)
        report["kconfig"] = config_result
        if config_result["exit_code"]:
            report["status"] = "KCONFIG_FAILED"
            return report
        report["resolved_config"] = verify_config(output, profile)
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
    parser.add_argument("--profile", choices=sorted(PROFILES), default="tizen",
                        help="SELinux/Android boot feature labs: isolated host only; NOT for TV")
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.jobs <= 32 or not 60 <= args.timeout <= 7200:
            raise ValueError("jobs 1..32 und timeout 60..7200 Sekunden erwartet")
        report = execute(args.source, args.workspace, args.cross_prefix,
                         args.jobs, args.timeout, args.preflight, args.profile)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Build-013-Vorprüfung fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"PRECHECK_PASS", "HOST_KERNEL_COMPILED_NOT_BOOTABLE_VALIDATED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
