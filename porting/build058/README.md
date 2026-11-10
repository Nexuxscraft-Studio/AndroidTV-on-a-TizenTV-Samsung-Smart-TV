# Build 058 — Linux 6.6 Samsung Nike-L GPU Clock/Reset Prototype

> **Integration update:** the separate
> [`integration/`](integration/README.md) component now includes a reproducible
> Linux **6.6.162 ARM32** Panfrost compile target, two Samsung-derived DRM
> C source migrations (`sdp_drm_util.c` and `sdp_drm_fence.c`), diagnostic
> vendor DRM builds, and compilation of the disabled GPU/CPU/thermal
> prototypes. These tools are compile-only, not proof of a working GPU or TV.
> The CPU-specific design remains under [`cpu/`](cpu/README.md).

**Status: `PROTOTYPE_FAIL_CLOSED_OFFLINE`.**

Build 058 takes Build 057's SHA256-pinned Samsung GPU power-control evidence
and sketches an ARM32 Linux 6.6 Common Clock Framework (CCF) and Reset
Controller API module. **It is not usable on the television**: the module's
`probe()` unconditionally returns `-EOPNOTSUPP` before mapping any MMIO,
and the provided DT reference has `status = "disabled"`.

## Files

- `kernel/sdp_nikel_gpu_clkrst.c`: compile-only provider implementation,
  masked read-modify-write of four known GPU control registers, clock gate,
  separate BUSIF/CORE reset IDs, guarded idle polling and an explicit bind
  blocker. The code is not enabled for production.
- `kernel/Makefile`: external module build contract.
- `sdp-nikel-gpu-clkrst-disabled.dts`: standalone syntactic reference node,
  **not** Samsung's board DT and **not** a bootable artifact.
- `build-arm32-offline.sh`: build command for an existing, configured Linux 6.6
  ARM32 tree on the Debian development server; never loads the `.ko`.
- `../../q60t_build058_nikel_clkrst_contract.py`: offline source/DT cross-check.

## Samsung register mapping (offset from `0x00f50000`)

| Function | Absolute address | Offset | Mask | Samsung value |
|---|---|---|---|---|
| GPU clock gate | `0x00f5088c` | `0x088c` | `BIT(12)` | 1=on |
| BUSIF reset | `0x00f507f8` | `0x07f8` | `BIT(24)` | 1=deassert |
| CORE reset | `0x00f507f8` | `0x07f8` | `BIT(28)` | 1=deassert |
| Idle request | `0x00f50a10` | `0x0a10` | `BIT(0)` | 1=request |
| Idle acknowledge | `0x00f50a14` | `0x0a14` | `BIT(0)` | 1=idle |

The prototype preserves the Samsung sequence when enabling or disabling the
clock. Unlike original Samsung code it tests the idle bit with `&`, not `&&`,
and limits polling to 2000 microseconds. **That timeout is merely a safe
analysis bound, NOT a hardware-validated timing specification.**
On timeout the prototype leaves the physical clock on, which can differ from
CCF's logical state because `.disable` has no return value. Thus this
design is *not ready for activation even after removing the probe block*.

The shared reset register is updated under a spinlock with per-bit masks.
The reset control IDs are BUSIF=0 and CORE=1. No input clock parent or clock
rate is fabricated: the provider is intentionally incomplete.

## Offline check

From the project root, with the pinned vendor source and the extracted,
SHA256-verified firmware references from Build 056:

```bash
python3 q60t_build058_nikel_clkrst_contract.py \
  --media-tgz .build050_vendor/srcarchives/tztv-media-nike.tgz \
  --dtb /path/to/dtb.bin \
  --gpu-ko /path/to/sdp_gpu.ko \
  --drm-ko /path/to/sdp_drm.ko \
  --output /tmp/build058-clock-reset-audit.json

python3 -m unittest tests.test_build058_nikel_clkrst -v
```

To **compile only** against an already-prepared ARM32 Linux 6.6 kernel:

```bash
bash porting/build058/build-arm32-offline.sh /path/to/configured/linux-6.6
```

This current workspace has no `arm-linux-gnueabihf-gcc` and no prepared
Linux-6.6 kernel build tree, so a genuine ARM32 module compile **has not
been run here**. Static guard tests must not be confused with a kernel compile.

## Unresolved before any hardware-enabling proposal

1. Real `samsung,sdp1804-clock`/CCF clock parent, frequency and provider
   ownership. The prototype mapping overlaps the original controller region.
2. Validated reset sequencing relative to Panfrost runtime PM; its separate
   reset API may conflict with combining clock and reset operations.
3. Actual idle timing and failure handling consistent with CCF state.
4. Regulator, OPP, power domains, and actual Samsung GPU voltage controls.
5. Verified interrupt trigger type (JOB 0x72 / MMU 0x71 / GPU 0x70), phandles,
   full Nike-L DT, and the rest of the TV display pipeline.

**No real TV access, no `insmod`, no `modprobe`, no flash, no DT enablement.**
