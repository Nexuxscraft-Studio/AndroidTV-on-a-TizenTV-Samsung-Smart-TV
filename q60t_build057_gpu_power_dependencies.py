#!/usr/bin/env python3
"""Build 057: reconstruct Samsung Nike-L GPU clock/reset/idle sequences offline.

Reads SHA256-pinned Samsung source and firmware references. Never uses MMIO,
insmod/modprobe, or writes hardware configuration.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tarfile

from q60t_build050_linux66_port_gaps import read_original_text
from q60t_build055_gpu_panfrost_evidence import ROOT, MEMBERS, inspect as audit_source
from q60t_build056_panfrost_dt_evidence import inspect as audit_firmware


EXPECTED_CONTROL_SEQUENCE = {
    "off": [
        ("GPU_POWER_REQ_IDLE", 1),
        ("GPU_BUSIF_SW_RESET", 0),
        ("GPU_CORE_SW_RESET", 0),
        ("GPU_CLK_MASK", 0),
    ],
    "on": [
        ("GPU_CLK_MASK", 1),
        ("GPU_BUSIF_SW_RESET", 1),
        ("GPU_CORE_SW_RESET", 1),
        ("GPU_POWER_REQ_IDLE", 0),
    ],
}


def location(text, position):
    return text.count("\n", 0, position) + 1


def macro_value(header, symbol):
    """Select Nike-L's #else values for the GPU BIT/MASK macros."""
    definitions = re.findall(r"^\s*#define\s+" + re.escape(symbol) +
                             r"\s+(0x[0-9A-Fa-f]+|[0-9]+)\s*$", header, re.M)
    if not definitions:
        raise ValueError("Missing Samsung register bit/mask: " + symbol)
    # The first definition of these duplicate symbols is Nike.M; the last is Nike.L.
    return int(definitions[-1], 0)


def extract_power_sequences(platform, header, nikel_regs):
    start_token = "void kbase_platform_sdp_gpu_power_control(int state)"
    end_token = "EXPORT_SYMBOL(kbase_platform_sdp_gpu_power_control);"
    start = platform.find(start_token)
    end = platform.find(end_token, start)
    if start < 0 or end < 0:
        raise ValueError("Original Samsung power-control function missing")
    function = platform[start:end]
    off = function.find("if(state==0)")
    on = function.find("else if(state==1)")
    if off < 0 or on < off:
        raise ValueError("Samsung GPU power state branches have changed")

    pattern = re.compile(
        r"sdp_set_clkrst_mux\(\s*(SDP_REG_\w+)\s*,\s*(SDP_MASK_\w+)\s*,\s*"
        r"([01])\s*<<\s*(SDP_BIT_\w+)\s*\)"
    )
    sequences = {}
    for state, begin, finish in (("off", off, on), ("on", on, len(function))):
        segment = function[begin:finish]
        writes = []
        for match in pattern.finditer(segment):
            address_macro, mask_macro, value, bit_macro = match.groups()
            key = address_macro.removeprefix("SDP_REG_")
            if (mask_macro != "SDP_MASK_" + key or bit_macro != "SDP_BIT_" + key
                    or address_macro not in nikel_regs):
                raise ValueError("Unexpected Samsung clock/reset macro matching")
            bit = macro_value(header, bit_macro)
            mask = macro_value(header, mask_macro)
            if mask != 1 << bit:
                raise ValueError("Samsung register bit/mask do not match: " + key)
            writes.append({
                "control": key,
                "register": nikel_regs[address_macro],
                "mask": "0x%08x" % mask,
                "bit": bit,
                "written_bit_value": int(value),
                "original_source_line": location(platform, start + begin + match.start()),
            })
        if [(w["control"], w["written_bit_value"]) for w in writes] != EXPECTED_CONTROL_SEQUENCE[state]:
            raise ValueError("Samsung original GPU power sequence differs from pinned expectation")
        sequences[state] = writes

    polling_expression = "sdp_read_clkrst_mux(SDP_REG_GPU_POWER_IDLE))&&SDP_MASK_GPU_POWER_IDLE"
    off_text = function[off:on]
    if polling_expression not in off_text or "}while(idle!=1);" not in off_text:
        raise ValueError("Samsung original idle polling expression changed")
    # No timeout/condition escape exists in this exact original function.
    if re.search(r"\b(timeout|jiffies|ktime|udelay|msleep|cpu_relax)\b", off_text):
        raise ValueError("Samsung idle-polling behavior changed; review manually")
    poll_position = platform.find("sdp_read_clkrst_mux(SDP_REG_GPU_POWER_IDLE)", start)
    if poll_position < 0:
        raise ValueError("Samsung original GPU idle register read missing")
    poll = {
        "control": "GPU_POWER_IDLE",
        "register": nikel_regs["SDP_REG_GPU_POWER_IDLE"],
        "mask": "0x%08x" % macro_value(header, "SDP_MASK_GPU_POWER_IDLE"),
        "bit": macro_value(header, "SDP_BIT_GPU_POWER_IDLE"),
        "original_source_line": location(platform, poll_position),
        "operator_in_original": "&& (logical AND, not bitwise AND)",
        "has_timeout": False,
        "risk": "Unbounded busy-loop can hang; logical AND may mistake other nonzero bits for IDLE.",
    }
    sequences["off"].insert(1, {"action": "wait_until_idle", **poll})
    return sequences


def verify_original_call_order(core):
    expected = (
        ("suspend", "kbase_pm_suspend(kbdev);", "kbase_platform_sdp_gpu_power_control(0);"),
        ("resume", "kbase_platform_sdp_gpu_power_control(1);", "kbase_pm_resume(kbdev);"),
    )
    lifecycle = {}
    for state, before, after in expected:
        start = core.find(before)
        finish = core.find(after, start)
        if start < 0 or finish < start or finish - start > 750:
            raise ValueError("Samsung kbase core suspend/resume order changed: " + state)
        lifecycle[state] = [
            {"operation": before, "source_line": location(core, start)},
            {"operation": after, "source_line": location(core, finish)},
        ]
    for marker in ("regulator_get_optional", "clk_prepare_enable", "sdp_runtime_pm_init_and_get"):
        if marker not in core:
            raise ValueError("Missing Samsung original clock/PM marker: " + marker)
    return lifecycle


def inspect(media_archive, dtb, gpu_module, drm_module):
    samsung_source = audit_source(media_archive)
    firmware = audit_firmware(dtb, gpu_module, drm_module)
    power_path = ROOT + MEMBERS["platform"][0]
    register_path = ROOT + MEMBERS["registers"][0]
    core_path = ROOT + MEMBERS["probe"][0]
    platform, _ = read_original_text(media_archive, power_path)
    header, _ = read_original_text(media_archive, register_path)
    core, _ = read_original_text(media_archive, core_path)
    nikel = samsung_source["samsung_source"]["nike_l_registers"]
    sequences = extract_power_sequences(platform, header, nikel)
    lifecycle = verify_original_call_order(core)

    clock_base = int(firmware["variants"][0]["clock_controller"]["register_base"], 16)
    clock_size = firmware["variants"][0]["clock_controller"]["register_bytes"]
    if not all(clock_base <= int(value, 16) < clock_base + clock_size
               for value in nikel.values()):
        raise ValueError("Samsung GPU control register outside DT clock-controller region")
    if nikel["SDP_REG_GPU_BUSIF_SW_RESET"] != nikel["SDP_REG_GPU_CORE_SW_RESET"]:
        raise ValueError("Samsung combined BUS/CORE reset register changed")

    variants = firmware["variants"]
    if any(v["gpu"]["has_clocks_property"] or v["gpu"]["has_power_domains_property"]
           for v in variants):
        raise ValueError("Original DT GPU clock/power reference assumption changed")

    return {
        "build": "057",
        "status": "ORIGINAL_POWER_SEQUENCE_CROSSCHECKED_OFFLINE",
        "samsung_original_source_archive_sha256": samsung_source["samsung_source"]["archive_sha256"],
        "firmware_entries_sha256": firmware["verified_entry_sha256"],
        "firmware_variants_checked": [v["label"] for v in variants],
        "gpu_core_mmio_base_not_clock_controller": "0x00500000",
        "clock_controller": {"base": "0x%08x" % clock_base, "size": clock_size},
        "nike_l_gpu_control_registers": nikel,
        "power_control_original_source": power_path,
        "power_sequence": sequences,
        "kbase_core_original_source": core_path,
        "suspend_resume_relative_order": lifecycle,
        "other_samsung_dependencies": [
            "regulator_get_optional(mali) in kbase platform probe",
            "clk_prepare_enable in kbase platform probe; legacy code can continue without GPU clock",
            "sdp_runtime_pm_init_and_get custom Samsung runtime-PM helper",
            "GPU DVFS path switching contains udelay(20) and mux/prescaler writes",
        ],
        "linux_6_6_panfrost_interfaces_already_present": {
            "source": "torvalds/linux v6.6 drivers/gpu/drm/panfrost/panfrost_device.c",
            "gpu_clock": "devm_clk_get + clk_prepare_enable",
            "optional_bus_clock": "devm_clk_get_optional(bus)",
            "reset": "devm_reset_control_array_get_optional_exclusive",
            "power": "panfrost_pm_domain_init and regulator/OPP integration",
            "runtime_pm": "drivers/gpu/drm/panfrost/panfrost_drv.c pm_runtime_*",
        },
        "migration_gaps": [
            "Linux 6.6 common-clock provider for samsung,sdp1804-clock not implemented/validated",
            "Linux 6.6 reset-controller provider for shared 0x00f507f8 register bits not implemented",
            "Hardware IDLE handshake needs bounded polling and verified timeout strategy",
            "DT GPU node lacks clocks; provider phandles/IDs not verified",
            "No validated power-domain/regulator bindings or safe suspend/resume order for Panfrost",
            "GIC interrupt trigger flags are raw zero values; polarity not verified",
            "Whole Samsung Nike-L board DT not yet ported",
        ],
        "notes": [
            "The reset bits for BUSIF and CORE share a register but have different masks.",
            "No clocks, resets or MMIO must be driven directly from this report.",
            "Original logical && in idle poll and missing timeout are unsafe to transplant verbatim.",
            "The Linux 6.6 Panfrost consumers already exist; Samsung hardware providers remain missing.",
        ],
        "gpu_driver_built": False,
        "device_tree_binding_validated": False,
        "hardware_access_performed": False,
        "safe_to_flash": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-tgz", required=True)
    parser.add_argument("--dtb", required=True)
    parser.add_argument("--gpu-ko", required=True)
    parser.add_argument("--drm-ko", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect(args.media_tgz, args.dtb, args.gpu_ko, args.drm_ko)
        with os.fdopen(os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600),
                       "w", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        print(result["status"] + "; hardware_access=false")
        return 0
    except (ValueError, OSError, KeyError, tarfile.TarError) as exc:
        print("Build 057 power audit refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
