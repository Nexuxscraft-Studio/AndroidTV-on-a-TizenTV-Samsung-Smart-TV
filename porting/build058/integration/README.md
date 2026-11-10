# Build 058 — Hardware integration / compile-only gate

**Branch:** `feature/build058-hardware-integration`  
**Kernel:** Linux **6.6.162**, **ARCH=arm (ARM32)**  
**Status:** reproducible compile gate; **no Q60T hardware test**.

The earlier Build 057 GPU/DRM analyses and Build 058 clock/reset, CPUFreq,
CPU-clock and thermal prototypes are unchanged. This integration block
provides one compile-only entry point for the three crucial areas:

1. **Real upstream Panfrost**, compiled from the *target kernel's own*
   `drivers/gpu/drm/panfrost/` sources. `CONFIG_DRM_PANFROST=m` is verified
   after `olddefconfig`; the generated composite `panfrost.o` must be ARM32.
2. **Samsung DRM**, including real ports of the original `sdp_drm_util.c`
   and `sdp_drm_fence.c` translation units to modern kernel interfaces and
   a separate diagnostic build
   of original `sdp_drm_drv.c` and `sdp_drm_gem.c`, with existing Build 053/054
   migration patches applied to an *isolated extracted copy*.
3. **Build 058 CPU/GPU providers**, compiled from the existing disabled
   clock/reset, CPUFreq and thermal C files, without enabling any DT node.

## Run on the Debian test server

Prerequisites: complete **Linux 6.6.162 source tree**, GCC ARM32
`arm-linux-gnueabi-gcc` and its `readelf`, host kernel build dependencies,
`make`, `patch`, `tar` and the original unchanged `tztv-media-nike.tgz`.
The runner performs an independent `multi_v7_defconfig` in a **new** output
directory; it does not change the target kernel source or existing build
objects. It refuses a non-6.6.162 kernel, the wrong vendor archive SHA-256,
missing ARM32 compiler, or an already-existing output path.

```bash
# Run from the checked-out repository root; choose a NEW output directory.
chmod +x porting/build058/integration/run-arm32-compile-only.sh
bash porting/build058/integration/run-arm32-compile-only.sh \
  /opt/samsung-atv-lab/linux-6.6.162 \
  /opt/samsung-atv-lab/samsung/build018-qemu-004/tztv-media-nike.tgz \
  /opt/samsung-atv-lab/build058-integration-run001
```

If the archive is stored elsewhere, substitute that actual path. The
archive's pinned SHA-256 is
`40c2a25eba331b8b04d8d81baf76061493f15f228a74893c7f825f7a1da724b6`.
The runner creates `RESULTS.tsv`, `inputs.txt`, individual logs and staged
work copies under the output directory. Do not equate a `PASS` on the ported
utility object with success for the complete Samsung DRM stack.

If the server has `arm-linux-gnueabihf-gcc` instead, invoke with
`CROSS_COMPILE=arm-linux-gnueabihf-`. Set `JOBS=2` on a small VM to avoid OOM.

## Why the two DRM build paths?

- `integration/drm/sdp_drm_util.c` and `.h` are an annotated, GPL-2.0-only
  derivative of **Samsung's 2013** `tztv-media-nike/sdp_drm_nike/sdp_drm_util.c`
  and `.h` (Linux 4.1.10).
  It replaces removed `drmP.h` dependency, unsafe indefinite user-copy
  retries, ARM-only inline CLZ, and legacy wait logic. An unverified high-bit
  mask convention is **rejected**, not silently emulated.
- `integration/drm/sdp_drm_fence.c` and `.h` directly migrate Samsung's
  original `struct fence` API to `struct dma_fence`, and use a kref to retain
  the timeline context until outstanding fences are released. No real GPU
  signaling/IRQ path exists yet; these objects must remain unused on the TV.
- The original large `sdp_drm_drv.c`/`sdp_drm_gem.c` contain non-upstream
  `vd_kernel-interfaces`, old DRM core/GEM/CMA, and Samsung-specific display
  APIs. The runner attempts compilation after **existing** Build 053/054
  patches and keeps errors verbatim, but does not invent replacement structs
  or declare these drivers working. They can remain blocked on missing
  proprietary headers or additional API changes.

## Report interpretation

| Stage | What PASS proves | What it does not prove |
|---|---|---|
| `panfrost_elf` | Built actual ARM32 Panfrost composite object | GPU clocks, reset, MMU IRQ, power |
| `sdp_drm_util_elf`, `sdp_drm_fence_elf` | Compiled real Samsung-derived utilities and DMA fences | Samsung scanout, HDMI, framebuffer or fence signaling |
| `sdp_drm_drv_elf`, `sdp_drm_gem_elf` | Individual Samsung patched objects, *if* they build | Complete DRM driver or module link |
| `sdp_nikel_*.o` | Compiled fail-closed prototype object | Clock/voltage/temperature on Q60T |

`modules` may report missing `Module.symvers` and fail at modpost even if
individual `.o` objects exist: the report intentionally checks both. A
prepared upstream kernel (including its symbol table) will provide stronger
module-link evidence later.

Panfrost Linux 6.6 Kconfig depends on `DRM`, ARM/ARM64 or `COMPILE_TEST`,
MMU and `!GENERIC_ATOMIC64`, and selects devfreq/GEM helpers. If the module
option is disabled after `olddefconfig`, the runner **stops** rather than
claiming the GPU was compiled.

Sources:

- Samsung original vendor source, `20_DTV_NikeL.zip`, GPLv2, SHA-256 pinned.
- [Panfrost Kconfig, Linux v6.6](https://github.com/torvalds/linux/blob/v6.6/drivers/gpu/drm/panfrost/Kconfig).
- [Panfrost Makefile, Linux v6.6](https://github.com/torvalds/linux/blob/v6.6/drivers/gpu/drm/panfrost/Makefile).
- [Linux kbuild documentation](https://docs.kernel.org/6.6/kbuild/modules.html).

No `insmod`, `modprobe`, firmware flash, DT enablement, TV MMIO, or TV
access. Successful compilation is **not** proven hardware functionality.
