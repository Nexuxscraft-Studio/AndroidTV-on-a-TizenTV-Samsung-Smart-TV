# Build 058 — Samsung Nike-L CPU / DVFS / Thermal (Linux 6.6.162)

**Status: OFFLINE_PROTOTYPES_NO_HARDWARE.** This is a separate CPU development
component alongside the previously delivered Build-058 GPU prototype. The
GPU/DRM work from Build 057 and GPU Build 058 is unchanged.

## Source provenance / licenses

Samsung's Linux 4.1.10 source tarball (SHA256 in the JSON report) contains:

| Original file | Finding / purpose |
|---|---|
| `drivers/cpufreq/sdp-nike-cpufreq.c` | Nike-M/L DVFS step table, PLL/PMU, ASV groups, unsupported transitions |
| `drivers/cpufreq/sdp-cpufreq.c` | Legacy policy, custom thermal notifier, `CPU_PW` regulator handling |
| `drivers/soc/sdp/sdp_thermal.c` | TMU, efuse calibration, state machine, old hotplug/notifier |
| `include/soc/sdp/sdp_thermal.h` | `TSC_DEGREE_25=46`, thermal constants |
| `drivers/clk/clk-sdp.c` | Multiple Samsung clock variants; Nike-L registration is commented out |
| `arch/arm/mach-sdp/board-nike-dt.c` | Legacy board/SMP hooks; not proof of Nike-L PSCI boot compatibility |
| `arch/arm/mach-sdp/sdp_hwclock.c` | Minimal clock helper; not a complete modern clock provider |

Samsung credits (c) 2014 Samsung Electronics; `sdp-cpufreq.c` declares GPL
version 2 or later. Our new, separately written C prototypes and host model
declare **GPL-2.0-only**. Original Samsung files are read but not rewritten,
and proprietary Tizen binaries are not included in this source branch.

## Hardware-evidence boundary

The SHA256-pinned original firmware `dtb.bin` contains **two** variants,
`nikel-2G` and `nikel-1.5G`, each with four `arm,cortex-a57` CPU nodes,
`arm,armv8`, PSCI `enable-method="psci"`, and `/psci` using SMC. This does
**not** show that Samsung's bootloader will launch an ARM64 kernel; original
drivers/modules are ARM32.

Both variants contain `/soc/thermal` with `samsung,sdp-thermal`, TMU register
`0x00f520c0` size 0x30, chip-ID register `0x00180000` size 0x30, and thermal
CPU frequency limits `1000000 / 700000 / 100000` **kHz**. Confirmation of
the units comes from Samsung `sdp-cpufreq.c` printing these divided by 1000
as MHz, with the same values fed into the CPUFreq frequency table.

The firmware clock node uses **`samsung,sdp1804-clock`** with an MMIO range
starting `0x00f50000` (size `0x3000`), while the older source has a
**commented-out** `CLK_OF_DECLARE(sdp_nikel_clk, "samsung,sdp-nikel-clock", ...)`.
Do not assume Nike-M clock definitions apply to Nike-L.

## CPUFreq decision

**Preferred long-term:** Linux 6.6 `cpufreq-dt` + a real CCF provider +
board-confirmed OPP/regulator data. `cpufreq-dt` delegates transitions to
the OPP layer / `clk_set_rate`; there is currently NO validated Nike-L
`clk_set_rate` implementation or valid OPP voltage/frequency set.

**Safer development fallback:** an SDP-Nike-specific `cpufreq_driver` using
the 6.6 `.target_index` interface. An API skeleton is included, but `.init`,
`.verify` and `.target_index` refuse operations with `-EOPNOTSUPP`, and
`probe()` is hard-blocked before registration. This is deliberately NOT an
active cpufreq port.

The Samsung source table describes nominal frequencies L0=1700 MHz,
L1=1000 MHz, L2=500 MHz, L3=250 MHz, L4=100 MHz. However:

- L0 is dynamically replaced from the clock hardware at init time.
- The 1-GHz DVFS divider yields **L4=125 MHz**, not the table's 100 MHz.
- Original `sdp_nike_set_clkdiv` explicitly does nothing on non-L0 to
  non-L0 transitions; using L0 as an interim step could overclock a CPU
  before raising voltage. This is NOT automatically repaired.
- Five ASV bins contain values between **870000 and 1020000 microvolts**, but
  no verified Nike-L bin assignment or safe regulator control is available.
- The original wrapper raises voltage before increasing frequency, and lowers
  voltage after reducing frequency; that order cannot be safely reused until
  all clock transitions are correctly sequenced and errors are reportable.
- PLL `PMS` at `0x00f5001c` is decoded in `get_speed`. `PLL K` is defined at
  `0x00f50020` but is not included in that original speed calculation.

`kernel/sdp_nikel_cpu_clk.c` prototypes a **read-only** PLL/DVFS clock rate
decoder with `clk_ops` and an intentionally unsupported `.set_rate`.
`kernel/sdp_nikel_cpufreq.c` provides the CPUFreq 6.6 registration interface
without any active frequency/voltage table or transition.
All kernel modules fail closed in `probe()` **before any I/O resource mapping**.

## Thermal design

`kernel/sdp_nikel_thermal.c` uses the 6.6 thermal API
`devm_thermal_of_zone_register()` and a `.get_temp` callback. It documents
Samsung's legacy sensor formula (`raw + 25 - fuse`, with zero-fuse fallback
46), converts Celsius to **millidegrees Celsius**, but does NOT initialize
the actual TMU and is hard-blocked before probing hardware.

The Samsung-specific notifier/cpu_down/cpu_up throttling must be replaced by
a validated thermal zone, trip points, and CPUFreq cooling/OPP policy.
**No thermal-cooling map is activated** until sensor calibration and OPPs
are demonstrated on the exact Nike-L hardware variant.

## Compiling and testing

Run the hardware-independent C model now:

```bash
bash porting/build058/cpu/run-host-tests.sh
```

Run the Python source/firmware and safety checks from the repository root:

```bash
python3 -m unittest tests.test_build058_cpu_dvfs_thermal -v
```

Build all **three** fail-closed external kernel modules against a **prepared
Linux 6.6.162 ARM32** source/build tree on the Debian server:

```bash
bash porting/build058/cpu/build-arm32-offline.sh /path/to/linux-6.6.162
```

The build does NOT install/load modules and does NOT connect to the TV.
Our current artifact workspace has no prepared ARM32 kernel build tree and
no `arm-linux-gnueabihf-gcc`, so an actual ARM32 module build is currently
**NOT RUN**. The x86 host-model test is not an ARM32 compile substitute.

## Device Tree

`nikel-cpu-thermal-disabled.dts` is an isolated, syntactic, intentionally
disabled reference. It has NO usable OPP nodes, CPU regulator phandles,
cooling maps, thermal trips, or bootable CPU/PSCI tree. Its clock-register
range **overlaps** the existing `samsung,sdp1804-clock` controller and would
need ownership reconciliation before integration. Do not flash/use as an
actual TV DTB or overlay.

## Blockers before any active port

1. Identify real Nike-L CPU PLL/divider and its parent clock; reconcile Nike-M
   code with `samsung,sdp1804-clock` in the firmware.
2. Verify actual CPU frequency readback including L4, real PLL-K usage, and
   transition requirements for all 25 state pairs.
3. Resolve ASV bin and `CPU_PW` supply mapping and CPU regulator voltage
   limits, including rollback/error propagation.
4. Verify thermal efuse readout, sensor initialization, drift filtering and
   temperature thresholds; implement thermal cooling only afterwards.
5. Integrate genuine CPU/PSCI/thermal phandles in a complete Nike-L board DT.
6. Build against Linux 6.6.162 ARM32, then review compiler diagnostics;
   optionally compile the hardware-independent model on ARM64.
7. Preserve independent GPU, DRM, and video pipeline interfaces.

**Successful compilation will not demonstrate hardware safety/functionality.**
