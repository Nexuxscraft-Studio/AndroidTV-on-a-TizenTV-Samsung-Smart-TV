# Build 094 — Samsung Nike-L on Linux 6.6.162 ARM32

The base is Build 093 at `e5b8200` ([successful Debian run](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/actions/runs/43582450885)).
Build 094 is a compile/link and offline validation target. Hardware validation
is out of scope for every row.

## Integration matrix

Build and modpost columns describe the CI gates. The linked Actions run
provides their actual results. Built-ins link into vmlinux, while modules
must be present and pass modpost against the same kernel.

| Component | Present | Patched | Required config | Built | Modpost | DT | Hosttest | Hardware validated |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SDP DRM, GP/OSDP/Mixer preparation | SDP KMS and inert register planning | 0012 → 0015 → 0020 → 0023–26 → 088 → 089 → 091 → 093 | DRM_SDP=m | sdp_display.ko | module | board and binding fixture disabled | pattern and DMA-span tests | No |
| HDMI transmitter | probe skeleton | 0018 | DRM_SDP_HDMI=m | sdp_hdmi.ko | module | disabled | — | No |
| SimpleDRM | upstream and Build 066 reference | upstream | DRM_SIMPLEDRM=y | vmlinux | built-in | handoff reference only | — | No |
| Panfrost | upstream Mali Bifrost | 0021 supplies DT | DRM_PANFROST=m | panfrost.ko | module | disabled | — | No |
| GPU clock/reset/genpd | production candidate under SDP1804 clock driver | 0022 after 0021 and 0004 | SDP1804_GPU_POWER=y | vmlinux | built-in | provider child disabled | callback sequencing and rollback model | No |
| CPU clock / cpufreq / thermal | Build 058 branch, three probe-blocked sources | external Kbuild against shared tree | CPUFREQ_DT=y, THERMAL_OF=y | three .ko | external modules | standalone disabled reference | CPU transition model | No |
| ALSA / ASoC | upstream framework; Samsung audio is vendor research | — | SND_SOC=y | vmlinux framework | built-in | no Nike-L audio binding | — | No |
| UART / SDP platform / clocks / GPIO | native ports | 0001–05, 0008–09 | ARCH_SDP, SERIAL_SDP, COMMON_CLK_SDP1804, GPIO_SDP=y | vmlinux | built-in | existing baseline board DT | porting tests | No |
| eMMC / USB / VBUS | upstream MMC, EHCI/OHCI and regulator | 0006–09 describe devices | MMC_DW_EXYNOS and USB platform drivers=y | vmlinux | built-in | storage and USB controllers disabled | — | No |
| Micom message box / IR remote | existing platform ports | 0013 | SDP_MSGBOX, SDP_MICOM, IR_SDP_MICOM=y | vmlinux | built-in | disabled | porting tests | No |
| HDMI CEC | Micom interface | 0014 after 0013 | CEC_SDP_CECIF=y | vmlinux | built-in | disabled | porting tests | No |
| IRB / IRS | skeletons plus separate GPL variants | 0019 skeletons | SDP_MICOM_IRB/IRS=m | two .ko | module | disabled | — | No |
| Ethernet | SDP MAC probe skeleton | 0017 | SDP_MAC=m | sdp_mac.ko | module | disabled | — | No |
| Video decode / panel / backlight | framework or research in 064/065/070 | — | media framework | framework only | — | no integrated driver binding | — | No |

## Patch order and conflicts

- [Full patch-path inventory](PATCHES.md). The Build 059 series uses filename
  ordering from the Build 093 baseline. It includes shared BPF and DRM ioctl
  changes (0010 and 0011). Build 091's two patches apply in numerical order.
- Builds 050, 053 and 054 are earlier DRM/GEM experiments. Build 053 offers
  alternative bases for the same partial port and 054 extends that line.
  The shared tree uses the separate SDP KMS implementation in 0012/0015.
  Build 058 helper extraction and Build 063 KMS out-of-tree source are
  alternatives to that implementation. Build 059 first display probe is
  an earlier standalone experiment. Build 087 is already in patch 0026.
- Builds 056–057 document Panfrost resources and sequencing. Build 058's
  standalone GPU clock/reset provider overlaps the SDP1804/genpd implementation
  in 0022. Only the latter owns the integration path. The CPU clock fixture
  likewise overlaps the live SDP1804 clock window. It stays a separate fixture.
  CPU OPP voltages, transition sequencing and TMU calibration are unresolved.
- Build 070 branch tip `681d6de` contains two additional GPL ports. Their
  0021/0022 prefixes collide with unrelated GPU patches; they apply on top of
  0019 in their own line. The IRB port has a weak message-box callback stub
  and unresolved callback integration. IRS exposes a cdev ioctl that resets
  a raw hard-coded MMIO address in the shared Micom CMU. Build 094 retains
  the skeletons pending a validated resource and reset ownership model.
- The older Binder/dtc patches and Build 069 SurfaceFlinger patches address
  separate kernel/userspace baselines. They are outside the Nike-L driver stack.
- Build 064/065/066 peripheral, GPL and framebuffer artifacts include reference
  DT/config and vendor inventory. The ALSA framework alone does not provide a
  Nike-L audio machine/codec/DMA port.

CI succeeds when the pinned archive and patch order validate, host and
checkpatch gates pass, the shared kernel and required modules link, the
required ELF headers identify ARM32, and both Q60T DTBs plus the display
fixture pass their checks. The runner only compiles and performs offline tests.
