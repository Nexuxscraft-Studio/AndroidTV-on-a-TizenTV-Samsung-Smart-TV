#!/usr/bin/env python3
"""Build 058: verify a fail-closed Linux 6.6 GPU CCF/reset skeleton offline."""

import argparse
import json
import os
from pathlib import Path
import re
import sys

from q60t_build057_gpu_power_dependencies import inspect as audit_build057


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "porting/build058/kernel/sdp_nikel_gpu_clkrst.c"
KBUILD = ROOT / "porting/build058/kernel/Makefile"
DTS = ROOT / "porting/build058/sdp-nikel-gpu-clkrst-disabled.dts"

REGISTERS = {
    "GPU_CLK_MASK": ("SDP_NIKEL_GPU_CLOCK_OFFSET", "SDP_NIKEL_GPU_CLOCK_GATE"),
    "GPU_BUSIF_SW_RESET": ("SDP_NIKEL_GPU_RESET_OFFSET", "SDP_NIKEL_GPU_BUS_RESET"),
    "GPU_CORE_SW_RESET": ("SDP_NIKEL_GPU_RESET_OFFSET", "SDP_NIKEL_GPU_CORE_RESET"),
    "GPU_POWER_REQ_IDLE": ("SDP_NIKEL_GPU_IDLE_REQ_OFFSET", "SDP_NIKEL_GPU_IDLE_BIT"),
    "GPU_POWER_IDLE": ("SDP_NIKEL_GPU_IDLE_ACK_OFFSET", "SDP_NIKEL_GPU_IDLE_BIT"),
}


def require(yes, why):
    if not yes:
        raise ValueError(why)


def definition(code, name):
    match = re.search(r"^#define\s+" + re.escape(name) +
                      r"\s+(0x[0-9A-Fa-f]+|[0-9]+|BIT\([0-9]+\))\s*$", code, re.M)
    require(match, "Missing/changed kernel register definition: " + name)
    value = match.group(1)
    return (1 << int(value[4:-1])) if value.startswith("BIT(") else int(value, 0)


def function_body(code, start, next_start):
    begin = code.find(start)
    require(begin >= 0, "Missing provider function: " + start)
    finish = code.find(next_start, begin + len(start))
    require(finish > begin, "Provider function end marker not found: " + start)
    return code[begin:finish]


def parse_writes(code):
    pattern = re.compile(
        r"nikel_gpu_update_bits\(ctl,\s*(SDP_NIKEL_GPU_\w+_OFFSET),\s*"
        r"(SDP_NIKEL_GPU_\w+),\s*(true|false)\s*\)", re.S
    )
    return [(offset, mask, value == "true") for offset, mask, value in pattern.findall(code)]


def verify_provider(code, dts):
    require(definition(code, "SDP_NIKEL_BUILD058_HARDWARE_DISABLED") == 1,
            "Build 058 hardware guard must be hard-disabled")
    probe = function_body(code, "static int nikel_gpu_clkrst_probe(",
                          "static const struct of_device_id nikel_gpu_clkrst_of_match")
    marker = "#if SDP_NIKEL_BUILD058_HARDWARE_DISABLED"
    require(marker in probe, "Missing compile-time probe stop")
    stop = probe.index(marker)
    map_position = probe.index("devm_platform_ioremap_resource")
    require(stop < map_position and "return dev_err_probe" in probe[stop:map_position],
            "Provider could access MMIO without a hard probe stop")
    require("-EOPNOTSUPP" in probe[stop:map_position], "Wrong probe refusal code")

    require("status = \"disabled\";" in dts, "Reference DT is not disabled")
    require("nover,sdp-nikel-gpu-clkrst-experimental" in dts,
            "DT compatible does not match prototype")
    require("{ .compatible = \"nover,sdp-nikel-gpu-clkrst-experimental\" }" in code,
            "Kernel compatible does not match reference DT")
    require("#clock-cells = <1>;" in dts and "#reset-cells = <1>;" in dts,
            "Reference provider specifier cells changed")
    require("reg = <0x00f50000 0x3000>;" in dts,
            "Reference controller base/size changed")

    require("spin_lock_irqsave(&ctl->lock" in code and
            "value |= mask" in code and "value &= ~mask" in code and
            "spin_unlock_irqrestore(&ctl->lock" in code,
            "Shared reset register lacks serialized masked RMW")

    enabled = function_body(code, "static int nikel_gpu_clock_enable(",
                            "static void nikel_gpu_clock_disable(")
    disabled = function_body(code, "static void nikel_gpu_clock_disable(",
                             "static int nikel_gpu_clock_is_enabled(")
    expected_on = [
        ("SDP_NIKEL_GPU_CLOCK_OFFSET", "SDP_NIKEL_GPU_CLOCK_GATE", True),
        ("SDP_NIKEL_GPU_RESET_OFFSET", "SDP_NIKEL_GPU_BUS_RESET", True),
        ("SDP_NIKEL_GPU_RESET_OFFSET", "SDP_NIKEL_GPU_CORE_RESET", True),
        ("SDP_NIKEL_GPU_IDLE_REQ_OFFSET", "SDP_NIKEL_GPU_IDLE_BIT", False),
    ]
    expected_off = [
        ("SDP_NIKEL_GPU_IDLE_REQ_OFFSET", "SDP_NIKEL_GPU_IDLE_BIT", True),
        # The second write occurs only on timeout and rolls back idle request.
        ("SDP_NIKEL_GPU_IDLE_REQ_OFFSET", "SDP_NIKEL_GPU_IDLE_BIT", False),
        ("SDP_NIKEL_GPU_RESET_OFFSET", "SDP_NIKEL_GPU_BUS_RESET", False),
        ("SDP_NIKEL_GPU_RESET_OFFSET", "SDP_NIKEL_GPU_CORE_RESET", False),
        ("SDP_NIKEL_GPU_CLOCK_OFFSET", "SDP_NIKEL_GPU_CLOCK_GATE", False),
    ]
    require(parse_writes(enabled) == expected_on,
            "On-sequence does not match Samsung's original write ordering")
    require(parse_writes(disabled) == expected_off,
            "Off-sequence or its timeout rollback changed")
    require("readl_poll_timeout_atomic" in disabled and
            "value & SDP_NIKEL_GPU_IDLE_BIT" in disabled and
            "SDP_NIKEL_GPU_IDLE_TIMEOUT_US" in disabled and
            "if (ret)" in disabled and
            disabled.index("if (ret)") < disabled.index("SDP_NIKEL_GPU_BUS_RESET"),
            "Idle acknowledgment must be masked and bounded before reset")
    require(definition(code, "SDP_NIKEL_GPU_IDLE_TIMEOUT_US") == 2000,
            "Unreviewed timeout change")
    require("devm_clk_hw_register" in probe and
            "devm_reset_controller_register" in probe and
            "devm_of_clk_add_hw_provider" in probe,
            "Expected Linux 6.6 clock/reset provider APIs missing")
    require("devm_platform_ioremap_resource" in probe, "Missing future MMIO mapping")
    require(".num_parents = 0" in probe,
            "Build058 must not guess an unverified clock parent")
    return {"on": expected_on, "off_with_rollback": expected_off}


def inspect(media_tgz, dtb, gpu_ko, drm_ko):
    original = audit_build057(media_tgz, dtb, gpu_ko, drm_ko)
    code = SOURCE.read_text(encoding="utf-8")
    dts = DTS.read_text(encoding="utf-8")
    kbuild = KBUILD.read_text(encoding="utf-8")
    require("obj-m += sdp_nikel_gpu_clkrst.o" in kbuild,
            "External Linux 6.6 module build recipe missing")
    sequences = verify_provider(code, dts)
    base = int(original["clock_controller"]["base"], 16)
    original_regs = original["nike_l_gpu_control_registers"]
    result_regs = {}
    for name, (offset_key, bit_key) in REGISTERS.items():
        expected_address = int(original_regs["SDP_REG_" + name], 16)
        offset = definition(code, offset_key)
        mask = definition(code, bit_key)
        require(base + offset == expected_address,
                "Linux 6.6 draft address differs from original Samsung " + name)
        source_entries = original["power_sequence"]["on"] + original["power_sequence"]["off"]
        references = [item for item in source_entries if item["control"] == name]
        require(references and all(int(item["mask"], 16) == mask for item in references),
                "Linux 6.6 draft bit mask differs from Samsung " + name)
        result_regs[name] = {"offset": "0x%04x" % offset,
                             "address": "0x%08x" % expected_address,
                             "mask": "0x%08x" % mask}

    require(definition(code, "SDP_NIKEL_GPU_RESET_BUS_ID") == 0 and
            definition(code, "SDP_NIKEL_GPU_RESET_CORE_ID") == 1 and
            definition(code, "SDP_NIKEL_GPU_RESET_COUNT") == 2,
            "Reset-line numbering changed")
    return {
        "build": "058",
        "status": "PROTOTYPE_FAIL_CLOSED_OFFLINE",
        "derived_from_build057": original["status"],
        "original_samsung_archive_sha256": original["samsung_original_source_archive_sha256"],
        "original_firmware_entries_sha256": original["firmware_entries_sha256"],
        "registers_original_source_crosschecked": result_regs,
        "register_write_sequences_checked": {"on": len(sequences["on"]),
                                             "off_including_rollback": len(sequences["off_with_rollback"])},
        "reset_ids": {"BUSIF": 0, "CORE": 1},
        "linux66_interfaces_in_prototype": ["clk_ops", "devm_clk_hw_register",
                                             "reset_control_ops", "devm_reset_controller_register",
                                             "devm_of_clk_add_hw_provider"],
        "critical_gaps": ["Unverified clock parent/rate", "Unverified power supply/OPP",
                          "Unverified interrupt trigger", "Potential CCF enable state mismatch on idle timeout",
                          "Shared system clock controller ownership unresolved",
                          "Full Nike-L board DT absent"],
        "hard_probe_block": True,
        "dts_status_disabled": True,
        "arm32_kernel_module_compilation_performed": False,
        "hardware_access_performed": False,
        "safe_to_load_or_flash": False,
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
            json.dump(result, stream, indent=2)
            stream.write("\n")
        print(result["status"] + "; hardware_access=false")
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print("Build 058 contract refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
