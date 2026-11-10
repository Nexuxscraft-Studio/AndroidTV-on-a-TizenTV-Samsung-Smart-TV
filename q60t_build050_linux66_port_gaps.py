#!/usr/bin/env python3
"""Analyze hash-pinned Samsung Nike source against selected Linux 6.6 DRM APIs.

This is a *source-level migration inventory*, not a driver conversion or
compilation. It never builds, loads, flashes, or executes vendor code.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tarfile

from q60t_build050_vendor_code_audit import MAX_MEMBER, MEMBERS, SOURCE_SHA, sha256_file


LINUX66_REFERENCE = {
    "repository": "torvalds/linux",
    "tag": "v6.6",
    "drm_driver_header": "include/drm/drm_drv.h",
    "drm_driver_header_git_blob_sha": "9813fa759b75d4dd39350a6eb687fbf455a64aed",
    "panel_header": "include/drm/drm_panel.h",
    "panel_header_git_blob_sha": "10015891b056f816c7a992a2052b36fd26943c5b",
    "modes_header": "include/drm/drm_modes.h",
    "modes_header_git_blob_sha": "c613f0abe9dceca89ae399b796feb3f2e222e6f2",
}

SOURCE_MAP = {
    "drm": ("media", "drm_display"),
    "panel": ("kernel", "panel_legacy"),
    "drm_makefile": ("media", "drm_makefile"),
    "gpu_makefile": ("media", "gpu_makefile"),
}

MAKEFILES = {
    "drm_makefile": "tztv-media-nike/sdp_drm_nike/Makefile",
    "gpu_makefile": "tztv-media-nike/sdp_gpu_nike/Makefile",
}

# Rule markers are deliberately *literal* and tied to observed legacy code.
# These findings do not assert that a one-line substitution would be sufficient.
RULES = [
    ("legacy_drm_bus_init", "drm", "drm_platform_init(", "critical",
     "Move full device initialization into platform probe before drm_dev_register()."),
    ("legacy_drm_load", "drm", ".load", "high",
     "Move initialization out of deprecated drm_driver.load into probe."),
    ("legacy_drm_unload", "drm", ".unload", "high",
     "Use explicit reverse-order teardown and drm_dev_unregister()/drm_dev_put()."),
    ("removed_gem_free_object_driver_field", "drm", ".gem_free_object", "critical",
     "Rework GEM lifetime through drm_gem_object_funcs.free; validate ownership."),
    ("removed_gem_vm_ops_driver_field", "drm", ".gem_vm_ops", "critical",
     "Review per-object VM mappings and drm_gem_object_funcs instead."),
    ("removed_set_busid_driver_field", "drm", ".set_busid", "high",
     "Drop obsolete drm_driver.set_busid; use DRM core registration."),
    ("removed_debugfs_cleanup_driver_field", "drm", ".debugfs_cleanup", "high",
     "Rework debugfs cleanup with current DRM-managed lifetimes."),
    ("removed_dumb_destroy_driver_field", "drm", ".dumb_destroy", "high",
     "Handle GEM lifetime via current GEM core and object functions."),
    ("removed_gem_open_object_driver_field", "drm", ".gem_open_object", "high",
     "Use drm_gem_object_funcs.open for per-handle callbacks."),
    ("removed_gem_prime_export_driver_field", "drm", ".gem_prime_export", "critical",
     "Review GEM DMA-BUF export through per-object funcs and dma_buf APIs."),
    ("removed_gem_prime_get_sg_table_driver_field", "drm", ".gem_prime_get_sg_table", "critical",
     "Move scatter/gather export to current drm_gem_object_funcs."),
    ("removed_gem_prime_vmap_driver_field", "drm", ".gem_prime_vmap", "critical",
     "Review drm_gem_object_funcs.vmap and iosys_map semantics."),
    ("removed_gem_prime_vunmap_driver_field", "drm", ".gem_prime_vunmap", "critical",
     "Review drm_gem_object_funcs.vunmap and matching memory ownership."),
    ("removed_gem_prime_mmap_driver_field", "drm", ".gem_prime_mmap", "critical",
     "Review current GEM mmap and DMA-BUF callback interfaces."),
    ("legacy_fbdev_restore", "drm", "drm_fbdev_cma_restore_mode", "high",
     "Review 6.6 fbdev emulation and lastclose lifecycle."),
    ("unchecked_missing_connectors", "drm", "no encoders/connectors found", "critical",
     "Do not consider a registered DRM device display-ready without a validated connector."),
    ("unchecked_dma_address_width", "drm", "coherent_dma_mask = DMA_BIT_MASK(64)", "high",
     "Validate real DMA address width and use DMA mask APIs; do not assume 64 bits."),
    ("old_panel_init_signature", "panel", "drm_panel_init(&panel->base);", "critical",
     "Linux 6.6 drm_panel_init takes panel, device, funcs, connector type."),
    ("old_panel_add_return_value", "panel", "ret = drm_panel_add(&panel->base);", "critical",
     "Linux 6.6 drm_panel_add returns void; revise probe error paths."),
    ("old_panel_get_modes_signature", "panel", "sdp_panel_get_modes(struct drm_panel *panel)", "critical",
     "Linux 6.6 get_modes receives (panel, connector); update mode allocation."),
    ("old_panel_embedded_connector", "panel", "p->base.connector", "critical",
     "Linux 6.6 drm_panel no longer owns a connector field."),
    ("old_panel_embedded_drm_device", "panel", "p->base.drm", "critical",
     "Use the supplied DRM connector's device instead of panel.drm."),
    ("dummy_panel_data", "panel", "contains dummy info", "critical",
     "These are dummy 1080p timings, not proof of actual Q60T panel wiring/timings."),
    ("removed_display_mode_vrefresh_field", "panel", ".vrefresh = 60", "critical",
     "Linux 6.6 drm_display_mode no longer has .vrefresh; use drm_mode_vrefresh()."),
    ("drm_arm64_conditional_build", "drm_makefile", "ifeq ($(ARM64),YES)", "info",
     "ARM64 switch exists but this is neither a 6.6 compile test nor boot evidence."),
    ("gpu_arm64_conditional_build", "gpu_makefile", "ifeq ($(ARM64),YES)", "info",
     "GPU module has an ARM64 switch, but its older DDK and includes require porting."),
    ("drm_arm32_include_dependency", "drm_makefile", "arch/arm/mach-sdp/include/", "critical",
     "Remove/replace ARM32 mach-sdp private header dependencies for arm64."),
]


def source_locations(contents, token):
    return [number for number, line in enumerate(contents.splitlines(), 1) if token in line][:20]


def analyze(contents):
    missing = []
    checks = []
    for rule_id, source, literal, severity, work in RULES:
        lines = source_locations(contents[source], literal)
        checks.append({"id": rule_id, "source": source, "original_line_numbers": lines,
                       "detected": bool(lines), "severity": severity,
                       "required_work": work})
        if not lines:
            missing.append(rule_id)
    if missing:
        raise ValueError("Source markers absent; refuse stale migration report: " + ", ".join(missing))

    panel = contents["panel"]
    def raw_number(key):
        match = re.search(r"^\s*\." + re.escape(key) + r"\s*=\s*(\d+),?", panel, re.M)
        if not match:
            raise ValueError("Missing original panel field: " + key)
        return int(match.group(1))

    dummy = {name: raw_number(name) for name in
             ("clock", "hdisplay", "htotal", "vdisplay", "vtotal", "vrefresh")}
    mode_clock_hz = dummy["clock"] * 1000
    total_pixels = dummy["htotal"] * dummy["vtotal"]
    dummy["frequency_from_clock_and_totals_hz"] = round(mode_clock_hz / total_pixels, 3)
    dummy["timing_has_no_horizontal_or_vertical_blanking"] = (
        dummy["hdisplay"] == dummy["htotal"] or dummy["vdisplay"] == dummy["vtotal"]
    )
    dummy["is_usable_q60t_panel_timing"] = False

    return {"type": "q60t_build050_linux66_source_porting_gaps", "build": "050",
            "status": "SOURCE_API_MIGRATION_REQUIRED", "linux_6_6_reference": LINUX66_REFERENCE,
            "checks": checks, "blocking_check_count": sum(c["severity"] == "critical" for c in checks),
            "dummy_panel_mode": dummy, "arm64_compile_test_passed": False,
            "linux_6_6_driver_compiled": False, "target_gpu_id_verified": False,
            "target_panel_verified": False, "safe_to_flash": False,
            "notes": [
                "drm_driver.load/unload still exist in v6.6 but are deprecated; do not call them removed.",
                "gem_free_object and gem_vm_ops are absent from Linux v6.6 drm_driver.",
                "drm_panel_init is four-argument and drm_panel_add returns void in Linux v6.6.",
                "Linux v6.6 drm_display_mode has no .vrefresh member; the dummy 1080p mode is unusable.",
                "Samsung source ARM64 build flags do not demonstrate a verified ARM64 bootloader.",
                "No hardware registers, clocks, panel voltages or DTB should be guessed.",
            ]}


def read_original_text(archive_path, member_path):
    with tarfile.open(archive_path, "r:gz") as archive:
        member = archive.getmember(member_path)
        if not member.isfile() or member.size > MAX_MEMBER:
            raise ValueError("Source member non-regular or too large: " + member_path)
        source = archive.extractfile(member)
        if source is None:
            raise ValueError("Unreadable member: " + member_path)
        body = source.read(MAX_MEMBER + 1)
        if len(body) != member.size:
            raise ValueError("Truncated/oversized source member: " + member_path)
        return body.decode("utf-8", errors="replace"), hashlib.sha256(body).hexdigest()


def inspect_archives(kernel_tgz, media_tgz):
    paths = {"kernel": Path(kernel_tgz), "media": Path(media_tgz)}
    archives = {}
    for name, path in paths.items():
        digest = sha256_file(path)
        if digest != SOURCE_SHA[name]:
            raise ValueError(name + " original TGZ SHA-256 mismatch")
        archives[name] = {"sha256": digest, "filename": path.name}
    sources = {}
    hashes = {}
    for label, (family, key) in SOURCE_MAP.items():
        member = MAKEFILES[key] if key in MAKEFILES else MEMBERS[family][key]
        content, digest = read_original_text(paths[family], member)
        sources[label] = content
        hashes[label] = {"sha256": digest, "member": member, "archive_family": family}
    result = analyze(sources)
    result["vendor_source_archives"] = archives
    result["vendor_source_members"] = hashes
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-tgz", required=True)
    parser.add_argument("--media-tgz", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        report = inspect_archives(args.kernel_tgz, args.media_tgz)
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
        print(json.dumps({"status": report["status"], "rules": len(report["checks"]),
                          "critical": report["blocking_check_count"], "safe_to_flash": False}))
        return 0
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        print("Build 050 Linux 6.6 gap check refused: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
