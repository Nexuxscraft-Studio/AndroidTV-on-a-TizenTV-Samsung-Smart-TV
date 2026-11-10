#!/usr/bin/env python3
"""Source-pinned Nike-L CPU/DVFS/TMU audit for Linux 6.6.162 (offline only)."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tarfile

from q60t_build056_panfrost_dt_evidence import get_pinned_file, parse_fdt_at, words, strings


ROOT = Path(__file__).resolve().parent
TREE = ROOT / "porting/build058/cpu"
KERNEL = TREE / "kernel"
DTS = TREE / "nikel-cpu-thermal-disabled.dts"
ORIGINAL_KERNEL_SHA256 = "31a92f0d20248abbe2976bd2da1ab95dde4fed3e010ddcdc1c07494c4fd867b0"
SOURCE_PATHS = {
    "nike": "drivers/cpufreq/sdp-nike-cpufreq.c",
    "wrapper": "drivers/cpufreq/sdp-cpufreq.c",
    "thermal": "drivers/soc/sdp/sdp_thermal.c",
    "thermal_header": "include/soc/sdp/sdp_thermal.h",
    "clock": "drivers/clk/clk-sdp.c",
    "board": "arch/arm/mach-sdp/board-nike-dt.c",
    "hwclock": "arch/arm/mach-sdp/sdp_hwclock.c",
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def load_originals(tgz):
    archive = Path(tgz)
    require(archive.is_file() and not archive.is_symlink(), "Samsung original archive missing")
    h = hashlib.sha256()
    with archive.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    require(h.hexdigest() == ORIGINAL_KERNEL_SHA256,
            "Samsung original kernel SHA256 differs from pinned source")

    wanted = {"linux-4.1.10/" + val: key for key, val in SOURCE_PATHS.items()}
    result = {}
    # Stream through the large tarball once rather than seeking and inflating repeatedly.
    with tarfile.open(archive, mode="r|gz") as tar:
        for member in tar:
            key = wanted.get(member.name)
            if key is not None:
                require(member.isfile() and member.size < 2 * 1024 * 1024,
                        "Unexpected Samsung source member type/size")
                src = tar.extractfile(member)
                require(src is not None, "Original Samsung source member cannot be extracted")
                result[key] = src.read().decode("utf-8", "replace")
    require(set(result) == set(SOURCE_PATHS), "Not all seven Samsung source files were present")
    return result


def parse_legacy_cpu(source):
    require("NIKE-M/L CPU frequency scaling support" in source, "Unexpected Nike CPU driver")
    levels = [(int(index), int(freq)) for index, freq in re.findall(
        r"\{\s*0,\s*L([0-4]),\s*([0-9]+)\s*\*\s*1000\s*\}", source)]
    require(levels == [(0, 1700), (1, 1000), (2, 500), (3, 250), (4, 100)],
            "Samsung original CPU frequency table changed")

    table = re.search(r"static const unsigned int sdp_nike_asv_voltage.*?=\s*\{(.*?)\n\};",
                      source, re.S)
    require(table, "ASV voltage table missing")
    voltages = []
    for row in re.findall(r"\{\s*([0-9,\s]+)\}", table.group(1)):
        vals = [int(value.strip()) for value in row.split(",") if value.strip()]
        if vals:
            voltages.append(vals)
    require(len(voltages) == 5 and all(len(row) == 5 for row in voltages),
            "Original ASV voltage table is not 5 by 5")
    require(min(min(row) for row in voltages) == 870000 and
            max(max(row) for row in voltages) == 1020000,
            "Original ASV voltage endpoints changed")

    required = ("sdp_nike_get_speed", "sdp_nike_set_clkdiv",
                "REG_SDP_NIKE_CLKBASE 0x00f50000", "REG_SDP_NIKE_PMUBASE 0x00400000",
                "g_clkbase + 0x001c", "g_clkbase + 0x0020",
                "g_pmubase + 0x0008", "ARM_DVFS_CLK_FREQ 1000000000",
                "else if (old_index == L0 && new_index > L0)",
                "else if (old_index > L0 && new_index == L0)",
                "no tempclk for this case", "regulator/consumer.h")
    for marker in required:
        require(marker in source, "Expected Samsung CPUFreq marker absent: " + marker)

    return {
        "nominal_table_khz": [freq * 1000 for _, freq in levels],
        "divided_1ghz_levels_khz": [None, 1000000, 500000, 250000, 125000],
        "l0_adjusted_from_measured_clock": "sdp_nike_freq_table[L0].frequency = freq/1000" in source,
        "l4_table_divider_mismatch": 100000 != 125000,
        "asv_microvolts": voltages,
        "non_l0_to_non_l0_direct_switch_unimplemented": True,
        "pll_pms_address": "0x00f5001c",
        "pll_k_address_defined_but_not_used_by_get_speed": "0x00f50020",
        "pmu_dvfs_ctrl_address": "0x00400008",
    }


def parse_legacy_thermal(sources):
    thermal = sources["thermal"]
    header = sources["thermal_header"]
    wrapper = sources["wrapper"]
    for marker in ("#define TSC_DEGREE_25\t\t46", "sdp_tmu_notifier_call_chain",
                   "cpu_limit_1st_throttle", "cpu_limit_2nd_throttle",
                   "cpu_limit_3rd_throttle", "readl((void*)(info->chipid_base + 0x10))",
                   "curr_temp = curr_temp + diff_val", "TMU_MAX_TEMP_DIFF\t(20)",
                   "sdpxxxx_enable_tmu", "sdpxxxx_get_temp"):
        require(marker in (header if marker.startswith("#define TSC") else thermal),
                "Samsung thermal formula/calibration marker missing: " + marker)
    for marker in ("cpufreq_frequency_table_target", "cpufreq_frequency_table_verify",
                   "cpufreq_freq_transition_begin", "regulator_set_voltage",
                   'regulator_get_optional(NULL, "CPU_PW")',
                   "cpufreq_register_driver", "sdp_cpufreq_tmu_notifier",
                   "param->cpu_limit_freq[0] / 1000"):
        require(marker in wrapper, "Samsung CPUFreq wrapper marker missing: " + marker)
    require("freqs.new > freqs.old" in wrapper and "freqs.new < freqs.old" in wrapper,
            "Original voltage sequencing not present")
    return {
        "fuse_zero_fallback": 46,
        "calibration_celsius_model": "raw + 25 - fused_value_or_46",
        "original_temperature_sanity_delta_c": 20,
        "thermal_limits_confirmed_khz": True,
        "legacy_apis_to_replace": ["cpufreq_frequency_table_target",
                                   "cpufreq_frequency_table_verify",
                                   "custom_sdp_tmu_notifier", "direct_cpu_hotplug",
                                   "global_regulator_get_optional_CPU_PW",
                                   "direct_ioremap", "sdp_nike_set_clkdiv"],
    }


def inspect_firmware(dtb):
    blob = get_pinned_file(dtb, "dtb")
    variants = []
    for off, label in ((0, "nikel-2G"), (86016, "nikel-1.5G")):
        nodes = parse_fdt_at(blob, off)
        for i in range(4):
            cpu = nodes.get(f"/cpus/cpu@{i}", {})
            require("arm,cortex-a57" in strings(cpu.get("compatible", b"")) and
                    "arm,armv8" in strings(cpu.get("compatible", b"")) and
                    strings(cpu.get("enable-method", b"")) == ["psci"],
                    "Expected four Nike-L Cortex-A57/PSCI CPU nodes")
        psci = nodes.get("/psci", {})
        require(strings(psci.get("compatible", b"")) == ["arm,psci-0.2"] and
                strings(psci.get("method", b"")) == ["smc"],
                "Firmware PSCI 0.2 SMC contract unexpected")
        tm = nodes.get("/soc/thermal", {})
        require(strings(tm.get("compatible", b"")) == ["samsung,sdp-thermal"] and
                words(tm.get("reg", b"")) == [0x00f520c0, 0x30, 0x00180000, 0x30] and
                strings(tm.get("reg-names", b"")) == ["tmu", "chipid"],
                "Original Samsung Nike-L thermal register layout differs")
        limits = [words(tm.get(f"cpu_limit_{n}_throttle", b"")) for n in
                  ("1st", "2nd", "3rd")]
        require(limits == [[1000000], [700000], [100000]],
                "Samsung firmware CPU throttle frequency limits changed")
        clock = nodes.get("/soc/clock-controller@00F50000", {})
        require(strings(clock.get("compatible", b"")) == ["samsung,sdp1804-clock"] and
                words(clock.get("reg", b"")) == [0x00f50000, 0x3000],
                "Unexpected original Nike-L firmware clock controller")
        variants.append({"name": label, "cpu_count": 4, "cores": "cortex-a57",
                         "psci": "psci-0.2/smc", "thermal_base": "0x00f520c0",
                         "chipid_base": "0x00180000",
                         "cpu_throttle_limits_khz": [x[0] for x in limits],
                         "original_clock_compatible": "samsung,sdp1804-clock"})
    return variants


def verify_drafts():
    draft = DTS.read_text(encoding="utf-8")
    require(draft.count('status = "disabled";') == 3,
            "All CPUFreq, Clock and TMU references must be disabled")
    for blocked in ("operating-points-v2 =", "cpu-supply =", "operating-points =",
                    'status = "okay";'):
        require(blocked not in draft, "Unsafe active CPU/OPP DTS marker: " + blocked)
    for marker in ("0x00f50000 0x1000", "0x00400000 0x1000",
                   "0x00f520c0 0x30", "0x00180000 0x30"):
        require(marker in draft, "Missing disabled DTS source address: " + marker)

    files = {p.name: p.read_text(encoding="utf-8") for p in KERNEL.glob("*.c")}
    require(set(files) == {"sdp_nikel_cpu_clk.c", "sdp_nikel_cpufreq.c",
                           "sdp_nikel_thermal.c"}, "Incomplete Build058 CPU kernel prototypes")
    for name, text in files.items():
        require("#define NIKEL_CPU_BUILD058_OFFLINE_ONLY 1" in text,
                "Fail-closed provider macro missing: " + name)
        marker = "#if NIKEL_CPU_BUILD058_OFFLINE_ONLY"
        start = text.find(marker)
        require(start >= 0, "Missing compile-time probe refusal: " + name)
        end = text.find("#endif", start)
        require(end > start and "return dev_err_probe" in text[start:end] and
                "-EOPNOTSUPP" in text[start:end],
                "Provider must refuse before accessing Samsung hardware: " + name)
        risky_calls = [call for call in ("devm_platform_ioremap_resource(",
                                       "cpufreq_register_driver(",
                                       "devm_thermal_of_zone_register(") if call in text]
        require(risky_calls and all(text.index(call) > end for call in risky_calls),
                "Hardware initialization or driver register precedes probe guard: " + name)
    require(".target_index = nikel_cpu_target_index" in files["sdp_nikel_cpufreq.c"] and
            "return -EOPNOTSUPP" in files["sdp_nikel_cpufreq.c"],
            "Unsafe CPUFreq target activated")
    require(".set_rate = nikel_cpu_set_rate" in files["sdp_nikel_cpu_clk.c"] and
            "return -EOPNOTSUPP" in files["sdp_nikel_cpu_clk.c"],
            "Unvalidated CPU clock frequency writes enabled")
    require("devm_thermal_of_zone_register" in files["sdp_nikel_thermal.c"] and
            "* 1000" in files["sdp_nikel_thermal.c"],
            "Modern thermal device / millidegree temperature contract missing")
    makefile = (KERNEL / "Makefile").read_text(encoding="utf-8")
    require(all(f"obj-m += {p.removesuffix('.c')}.o" in makefile for p in files),
            "Build 058 kernel module targets missing")


def inspect(kernel_tgz, dtb):
    sources = load_originals(kernel_tgz)
    legacy_cpu = parse_legacy_cpu(sources["nike"])
    legacy_thermal = parse_legacy_thermal(sources)
    clock = sources["clock"]
    require('CLK_OF_DECLARE(sdp_1804_clk, "samsung,sdp1804-clock"' in clock,
            "Clock provider original compatible missing")
    require(re.search(r'^//\s*CLK_OF_DECLARE\(sdp_nikel_clk', clock, re.M),
            "Expected Nike-L clock registration no longer commented")
    require("sdp_nike_dt_compat" in sources["board"], "Legacy board implementation missing")
    variants = inspect_firmware(dtb)
    verify_drafts()
    return {
        "build": "058",
        "focus": "CPU_DVFS_THERMAL",
        "target_kernel": "6.6.162",
        "status": "CPU_DVFS_THERMAL_AUDITED_OFFLINE_PROTOTYPES_BLOCKED",
        "original_samsung_kernel_source_sha256": ORIGINAL_KERNEL_SHA256,
        "original_files_examined": SOURCE_PATHS,
        "original_firmware_dtb_sha256": "9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2",
        "firmware_variants": variants,
        "nike_cpu_source": legacy_cpu,
        "nike_thermal_source": legacy_thermal,
        "driver_option": {
            "cpufreq_dt": "BLOCKED: no validated provider set_rate, OPPs or CPU regulator",
            "dedicated_sdp_cpufreq": "API prototype exists but refuses all transitions",
        },
        "clock_variant_mismatch": "Nike-L source CLK_OF_DECLARE commented; firmware uses samsung,sdp1804-clock",
        "api_prototypes": ["Linux 6.6 clk_ops", "Linux 6.6 cpufreq_driver.target_index",
                           "Linux 6.6 devm_thermal_of_zone_register"],
        "model_host_test": "run-host-tests.sh (compile and execute separately)",
        "arm32_kernel_build": "not_run_no_prepared_toolchain_in_artifact_workspace",
        "arm64_kernel_build": "not_run",
        "kernel_drivers_probe_blocked": True,
        "device_tree_references_disabled": True,
        "hardware_access_performed": False,
        "safe_to_load_or_flash": False,
        "open_questions": [
            "Nike-M frequency/voltage tables may differ on Nike-L silicon",
            "L4 100 MHz table disagrees with 125 MHz DVFS divider",
            "L0 real frequency depends on real boot-time clock",
            "Unimplemented direct transitions between non-L0 states",
            "Unverified real PLL-K and CCF parent/clock provider ownership",
            "Unverified CPU_PW regulator / five-bin ASV calibration",
            "Thermal efuse, sensor init and trip calibration not validated",
            "ARM64 boot of Samsung chain unverified; original kernel is ARM32",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-kernel", required=True)
    parser.add_argument("--dtb", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect(args.original_kernel, args.dtb)
        with os.fdopen(os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600),
                       "w", encoding="utf-8") as target:
            json.dump(result, target, ensure_ascii=False, indent=2)
            target.write("\n")
        print(result["status"] + "; hardware_access=false")
        return 0
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        print("Build 058 CPU audit refused: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
