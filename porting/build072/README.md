# Build 072 – Q60T RAM-Boot feasibility (offline, read-only)

**Target:** Samsung GQ50Q60TGUXZG, Nike-L, ARM32, firmware T-NKLDEUC 2743.0.
**Date of review:** 2026-11-12.
**Scope:** Assess whether an existing Tizen session can hand off to our own
Linux 6.6.162 image **without** writing to TV storage. No TV connection,
boot action, module loading, firmware modification or signing bypass here.

## Short answer

A mini-kernel does **not** need Panfrost, DRM, HDMI, audio, network or Android.
The diagnostic ARM32 kernel and embedded initramfs already exist in Build 059;
Build 067 demonstrated its initramfs startup under generic QEMU ARM32.
This does **not** establish a Samsung-hardware boot.

The Samsung GPL file named `Nike.M-Tizen_release_defconfig` is reported in
[Build 059](../build059/README.md) with `# CONFIG_KEXEC is not set`.
If the **actual running kernel** on our specific TV also has KEXEC disabled,
a normal Linux `kexec` handoff from stock Tizen is unavailable.

**Evidence caveat:** A released defconfig is *not* proof of the effective
configuration of the retail TV with firmware 2743.0. Until an authenticated
runtime config or equivalent evidence is available, state is **UNVERIFIED**,
not a positive or negative live-device finding.

Samsung's official Smart TV Developer Mode provides an app development
and debugging path, **not** a documented root shell, bootloader console, or
arbitrary kernel execution mechanism. SDB connectivity is not proof of
privileges required for `kexec_load`.

## Ranked entry routes

| Route | Current finding | What would be needed |
| --- | --- | --- |
| Stock Tizen `kexec` | Reference defconfig disables it; runtime unknown | Actual kernel configuration, privileges/security constraints, tested shutdown/handoff |
| Samsung bootloader loading a kernel from RAM | Not demonstrated | Identified loader, authenticated allowed image, safe reversible invocation |
| Service/developer mode | No kernel handoff proven | Vendor-supported nonpersistent kernel launch, not just app debugging |
| Generic U-Boot/UEFI/GRUB | Not established | Verified executable loader on exact hardware; uImage header alone is insufficient |
| QEMU ARM32 `virt` | **Demonstrated as emulation**, not a TV boot | Continue CI experiments independently of TV |

The original firmware has a legacy `uImage` wrapper, but the wrapper's format
does not prove an installed U-Boot implementation. `sign.bin`, `seret.bin`
and TrustZone artifacts do not establish the acceptance rules for our images.

A load/entry value such as `0x80008000` in the *reference* uImage must
**never** be copied as a safe RAM address for the retail set. Build 059
already notes that it does not match the static DT memory banks. A runtime
memory map and actual handoff contract would be needed.

## Offline audit of reference evidence

The Python tool only reads **local files already obtained separately**.
It does not connect to SDB, load kernel modules, run `kexec`, edit firmware,
or contact the TV.

From the repository root:

```bash
python3 porting/build072/ramboot_audit.py
python3 -m unittest discover -s porting/build072/tests -v
```

Optionally compare existing local artifacts:

```bash
python3 porting/build072/ramboot_audit.py \
  --stock-defconfig /local/path/Nike.M-Tizen_release_defconfig \
  --runtime-config /local/path/saved-real-tv-config.gz \
  --output /tmp/q60t-build072-ramboot.json
```

The runtime input can be a previously saved plain-text kernel `.config`
or `/proc/config.gz` snapshot (gzip is supported). **Do not label a Samsung
source-tree defconfig as a live runtime config.** It is acceptable for the
runtime input to be unavailable: the result will explicitly remain
`NOT_VERIFIED_ON_TV`. Raw logs and identifying data are deliberately excluded
from the report. Output creation refuses overwrites.

The report's boot decision is **always blocked**: `CONFIG_KEXEC=y` would
establish only one prerequisite, not that a handoff is safe or executable.
The eight recovery gates from [boot-evidence.json](../boot-evidence.json)
remain independent, with manual review even if every gate later passes.

## Existing minimal kernel (do not reimplement it)

Build 059 already supports `arm tiny` with `DIAG_INITRAMFS=1` and produces
an ARM32 kernel, matching Nike-L DTBs, and the embedded
`q60t-diag-init`. To rebuild **only on a development host** using a clean
Linux 6.6.162 tree and a separate output directory:

```bash
DIAG_INITRAMFS=1 bash porting/build059/kernel/build.sh \
  /path/to/clean-linux-6.6.162 arm tiny /path/to/q60t-kernel-out
```

The build script patches its specified kernel source tree; use a dedicated
checkout. The resulting files are **build artifacts, not bootable/authorized
Samsung firmware packages**. For the already existing QEMU boot regression,
use [Build 067](../build067/README.md).

## What needs to happen before *any* TV boot attempt

1. Identify the exact 50-inch board/RAM revision and confirm firmware/SoC.
2. Obtain trustworthy **read-only** evidence of the running kernel config
   and boot arguments, if the device explicitly permits access. Do not
   elevate access or modify the running TV just to collect this.
3. Identify the first and second boot stages by passive logs or reliable
   vendor evidence. Do not infer loader identity from the `uImage` magic.
4. Independently confirm the start contract: entry mode, DTB pointer,
   physical RAM layout, reserved regions, interrupt/timer/PSCI state and
   UART for diagnostics.
5. Demonstrate a nonpersistent, authenticated boot entry and **proven
   recovery/rollback on spare equivalent hardware** before proceeding.
6. Keep Samsung flash partitions, boot variables and bootloader untouched.

## Sources / scope boundaries

- [Build 059: kernel and original KEXEC baseline](../build059/README.md)
- [Build 067: generic QEMU boot](../build067/README.md)
- [Build 071: passive bootloader investigation](../build071/README.md)
- [Build 061: bootchain inventory](../../reports/bootchain_forensics_build061.json)
- [Samsung Developer – TV Device](https://developer.samsung.com/smarttv/develop/getting-started/using-sdk/tv-device.html)
- [Linux KEXEC config index](https://cateee.net/lkddb/web-lkddb/KEXEC.html)

**Status:** We can prepare and compile the diagnostic image offline today.
On the retail Samsung TV, a **safe RAM boot is not yet demonstrated**.
