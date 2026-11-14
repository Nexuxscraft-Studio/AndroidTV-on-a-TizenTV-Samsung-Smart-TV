# Build 095 — Safe Boot & Hardware Readiness

Retail boot readiness remains **blocked**. The input is the successful
[Build 094 run](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/actions/runs/43584172324)
on Linux 6.6.162 ARM32. Download its build094-evidence ZIP and run:

    python3 porting/build095/audit.py /path/to/build094-evidence.zip
    python3 -m unittest discover -s porting/build095/tests -v

The audit checks the pinned GitHub ZIP digest, compares ten member digests
to [the manifest](manifest.json), verifies four DTB checksums and repeats
Build 094's disabled-node checks. CI requires an unexpired artifact and
Actions read access. After expiration, a new successful run needs reviewed
provenance and an updated manifest.

All nine recorded module headers show relocatable little-endian ELF32 ARM
EABI5. Six in-tree modules have matching Kconfig entries and link records
after kernel modpost. Three external CPU modules have link records after
external modpost. The archive holds reports and logs. Binary vermagic,
module dependency closure and load behavior remain unverified.

## Device Tree and handoff

- The 1.5G and 2G profiles describe four and three RAM banks respectively,
  starting at 0x40000000. Confirm the real profile and live reserved ranges
  before any placement decision. Gaps may contain secure and video buffers.
- Both trees describe four Cortex-A57 CPUs, PSCI 0.2 over SMC, a GIC-400
  and an architected timer. Actual ARM32 entry state, PSCI and interrupt
  and timer state still need confirmation.
- The SDP1804 clock provider references the 24 MHz fixed clock. Serial0
  points to the enabled SDP UART and requests 115200n8 with earlycon.
  Loader fixups, UART clock and pinmux remain unverified.
- DRM, GPU and its power domain, HDMI, Ethernet, MICOM, CEC, IRB/IRS,
  eMMC, USB controllers and USB VBUS remain disabled in both board DTBs.
  The standalone CPU fixture leaves CPU clock, cpufreq and thermal
  experiments disabled.

## Diagnostic configuration draft

Apply [diagnostic.config](diagnostic.config) in a future offline experiment
with the existing [Build 059 tiny profile](../build059/README.md) and
embedded diagnostic init. The draft requests a single CPU, serial output,
a RAM-only init and no module loader or optional I/O subsystems. Verify
effective Kconfig after olddefconfig before compiling and use an emulated
regression check for the diagnostic init. CI for this change checks files
on a GitHub-hosted runner and produces no deployment image.

[Build 072 research](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/blob/feature/build072-ramboot-preflight/porting/build072/README.md)
records that the reference defconfig disables KEXEC and retail SDB reports
disabled interactive shell and root. Runtime KEXEC support, an authenticated
nonpersistent entry, the ARM32 handoff contract and proven recovery on
equivalent hardware remain open. Stock uImage metadata alone cannot
establish the loader identity or usable entry addresses.
