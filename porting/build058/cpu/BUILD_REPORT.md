# Samsung Q60T — Build 058 CPU/DVFS/Thermal report

Target Linux: **6.6.162**; development target: **Samsung Nike-L / Cortex-A57
in original Tizen 2743.0 DTB**, original Linux 4.1.10 source.

## Delivered

1. Offline audit `q60t_build058_cpu_dvfs_thermal_audit.py` parses pinned
   Samsung source and both known firmware FDT variants and emits
   `reports/build058-nikel-cpu-dvfs-thermal.json`.
2. CPU clock read-only CCF API prototype `kernel/sdp_nikel_cpu_clk.c`, with
   explicit unsupported `clk_ops.set_rate` and hard-failed `probe`.
3. Dedicated modern `.target_index` CPUFreq API prototype
   `kernel/sdp_nikel_cpufreq.c`, without OPPs or usable transitions and with
   hard-failed `probe`. `cpufreq-dt` is the preferred future route **only**
   after valid CCF and OPP/regulator bindings exist.
4. Thermal API prototype `kernel/sdp_nikel_thermal.c` (millidegrees C,
   `devm_thermal_of_zone_register`, no sensor initialization or cooling),
   hard-failed in `probe`.
5. An inert, standalone DT reference with **three disabled nodes**,
   no OPP, no cooling map and no active CPU regulator.
6. Pure host-side C model that refuses unsafe non-L0/non-L0 transitions
   and flags the 100/125 MHz L4 mismatch.
7. ARM32 external-module build command for a **prepared Linux 6.6.162**
   kernel tree, with a strict version/toolchain check.

## Tests executed in current artifact workspace

| Check | Result |
|---|---|
| Vendor Linux 4.1.10 archive SHA256 + source markers | PASS |
| Both pinned original Nike-L FDT variants (4 Cortex-A57, PSCI/SMC, TMU, clock) | PASS |
| Samsung ASV table dimensions, units, and L4 inconsistency | PASS |
| Linux-6.6 API drafts: disabled DT + fail-closed probe checks | PASS |
| Portable C model compiled with host GCC (`-Wall -Wextra -Werror -pedantic`) | PASS |
| CPU-specific Python test suite | 5/5 PASS |
| ARM32 module build against Linux 6.6.162 | **NOT RUN** – no configured kernel tree / ARM cross-compiler here |
| ARM64 module compatibility | NOT RUN |
| TV/GPU/CPU hardware tests | NOT RUN; intentionally prohibited |

The shell script's existence is **not** evidence that the ARM32 kernel C files
successfully compile. Run the command on the actual Debian build server with
the cross-toolchain to collect real compiler errors and iterate.

## Findings that block activating CPUFreq or thermal

| Risk / uncertainty | Evidence | Required next action |
|---|---|---|
| Nike-M source vs Nike-L hardware | Nike-L clock init commented in Samsung `clk-sdp.c`; firmware uses `samsung,sdp1804-clock` | Verify actual clock ownership and parent |
| L4 mismatch | Table=100 MHz, legacy `/8` divider=125 MHz | Confirm using real readback, update table only with evidence |
| L0 not constant | Rewritten from current clock at Nike init | Do not hardcode 1.7 GHz OPP |
| Reduced-state transitions | Old `sdp_nike_set_clkdiv()` does nothing L1–L4 → L1–L4 | Design validated state machine with voltage rollback |
| ASV voltage table | Five groups, 870000–1020000 microvolts | Verify bin source and actual CPU regulator |
| PLL-K missing from calculation | Register declared but omitted by `get_speed` | Validate PLL formula and fractional mode |
| Firmware TMU calibration | 8-bit raw sample + chip-ID fuse; old code filters 20°C jumps | Validate Nike-L fuse and initialization |
| Thermal policy | Legacy TMU notifier directly caps CPU and hotplugs CPUs | Integrate OPP-aware CPUFreq cooling after calibration |
| Boot environment | Original ARM32, four ARMv8 CPU nodes, PSCI SMC | ARM64 boot remains unproven |
| Device Tree | Only isolated and intentionally disabled CPU/TMU reference | Build verified complete Nike-L board DT |

## Implementation notes

- **No automatic migration** of old `sdp-cpufreq.c` API and `CPU_PW` voltage
  control is attempted: `cpufreq_frequency_table_target` and the old custom
  notifier do not provide an adequate modern safety contract.
- No `operating-points-v2` or `cooling-maps` are supplied because their values
  cannot be validated from current evidence.
- The standalone reference's clock MMIO overlaps the existing
  `samsung,sdp1804-clock` region; **never instantiate both**.
- The old Samsung `sdp_thermal.c` temperature output is in °C; the Linux 6.6
  Thermal API expects milli-°C. Calibration and sensor initialization are
  separate unresolved issues.
- Previous GPU/DRM sources are preserved; no original vendor source was edited.

## Next on the Debian server

```bash
# From the repository root after checking out the CPU feature branch:
bash porting/build058/cpu/run-host-tests.sh
python3 -m unittest tests.test_build058_cpu_dvfs_thermal -v
bash porting/build058/cpu/build-arm32-offline.sh /path/to/prepared/linux-6.6.162
```

Do **not** install or load any of the experimental `.ko` modules or use
the disabled DTS as a TV boot DTB. These are developer-only artifacts.
