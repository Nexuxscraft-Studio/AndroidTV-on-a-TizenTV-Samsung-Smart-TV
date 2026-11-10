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
It returns a nonzero exit status if any required ARM object is absent, even
when the partial results and logs are useful. A full PASS for the original
large Samsung DRM files is **not yet established**.

If the server has `arm-linux-gnueabihf-gcc` instead, invoke with
`CROSS_COMPILE=arm-linux-gnueabihf-`. Set `JOBS=2` on a small VM to avoid OOM.

### Toolchain and scope options (added after run002)

| Option | Values | Meaning |
|---|---|---|
| `BUILD058_TOOLCHAIN` | `gcc` (default), `llvm` | `gcc` uses `${CROSS_COMPILE}gcc`/`readelf` (reference for the Debian lab). `llvm` passes `LLVM=1` (clang, ld.lld, llvm-readelf) as an independent second compiler. A caller's `LLVM`/`LLVM_IAS` environment is never inherited: Kbuild treats any non-empty `LLVM`, even `LLVM=0`, as enabled. |
| 2nd argument `--no-vendor-drm` | instead of the `.tgz` path | Builds only repository-owned sources and Panfrost. Records `original_drm_extract = SKIPPED_NO_VENDOR_ARCHIVE` and `integration_scope = REPO_OBJECTS_ONLY`; exits 0 only if those objects exist. It is **never** a Samsung DRM result. |

`inputs.txt` now records `TOOLCHAIN`, the exact compiler version line and
`VENDOR_DRM`. Object checks require **ELF32 and Machine ARM**. Preflight also
requires `flex`, `bison` and `bc` (needed by Kbuild).

GitHub CI (`.github/workflows/build058-arm32-compile.yml`) runs the
`--no-vendor-drm` mode with GCC (`arm-linux-gnueabihf-`) and LLVM against Linux
6.6.162, pinned to commit `5139929c698c273e07cb0635732f6a918a7b8e78`
(`gregkh/linux`, tag `v6.6.162`). A manual `workflow_dispatch` can add the full
kernel/modpost build.

Further analysis in this directory:

- [`DRM_GEM_LINUX66_MAP.md`](DRM_GEM_LINUX66_MAP.md): which Samsung GEM/PRIME
  callbacks Build 053 dropped, which `drm_driver` fields are
  `CONFIG_DRM_LEGACY`-only in 6.6.162, and Samsung's own extended CMA helper.
- [`PANFROST_CLKRST_LINUX66.md`](PANFROST_CLKRST_LINUX66.md): Panfrost 6.6.162
  clock/reset/IRQ requirements and the sequencing conflict with the prototype.
- `inventory-sdp-drm-abi.py`: read-only inventory of the pinned Samsung archive
  that separates identifiers defined somewhere in the archive from the
  candidates for the missing `drm/drm_tztv.h`.

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

**Build 058 ARM32 correction (after the first Debian run):** A successful
`.o` compile is **not** a successful `.ko` link. The runner now compiles each
external object directly with the Linux 6.6 kbuild single-target syntax
`make ... M=<staged-path> <name>.o` and checks ELF class/machine separately.
The default run performs no `modpost`; `RESULTS.tsv` reports
`<component>_modpost = SKIPPED_OBJECT_ONLY` and explicitly records whether
`kernel-obj/Module.symvers` exists. A missing symbol table after
`modules_prepare` is **expected** and is not reported as a C compilation
failure.

For a **full kernel build and module-link attempt**, use a *new* output
directory with the optional flag (needs much more RAM, disk and time):

```bash
BUILD058_FULL_KERNEL=1 JOBS=2 bash \
  porting/build058/integration/run-arm32-compile-only.sh \
  /opt/samsung-atv-lab/linux-6.6.162 \
  /opt/samsung-atv-lab/samsung/build018-qemu-004/tztv-media-nike.tgz \
  /opt/samsung-atv-lab/build058-integration-fullkernel001
```

This attempts a `vmlinux` build for the same configured source tree and
links staged modules only if the resulting `Module.symvers` exists. Kernel
or modpost failures get their **own** status/log; per-object `.o` results
remain separate. This does not boot or install anything.

### Vendor DRM headers

The exact `trace/early.h` was recovered from the original Samsung
`linux-4.1.10/include/trace/early.h` (copyright Roman Pen, 2014). A
license-attributed copy is under `drm/legacy-include/trace/early.h` and is
passed through `ccflags-y` **only** in the extracted diagnostic DRM build.
No Linux 6.6 system header is overwritten.

`drm/drm_tztv.h` does **not** occur in either pinned Samsung Linux
4.1.10 or `tztv-media-nike` source archive. It defines part of the vendor
DRM ioctl ABI (`DRM_SDP_*` commands, request structures, etc.). The runner
records `samsung_drm_tztv_header = BLOCKED_MISSING_ABI`, tries original
Core/GEM source compilation for evidence, and keeps the actual compiler
errors. It does **not** fabricate ABI definitions. Full source compilation
requires the genuine `vd_kernel-interfaces` headers and further API porting.

Panfrost Linux 6.6 Kconfig depends on `DRM`, ARM/ARM64 or `COMPILE_TEST`,
MMU and `!GENERIC_ATOMIC64`, and selects devfreq/GEM helpers. If the module
option is disabled after `olddefconfig`, the runner **stops** rather than
claiming the GPU was compiled.

Sources:

- Samsung original vendor source, `20_DTV_NikeL.zip`, GPLv2, SHA-256 pinned.
- [Panfrost Kconfig, Linux v6.6](https://github.com/torvalds/linux/blob/v6.6/drivers/gpu/drm/panfrost/Kconfig).
- [Panfrost Makefile, Linux v6.6](https://github.com/torvalds/linux/blob/v6.6/drivers/gpu/drm/panfrost/Makefile).
- [Linux kbuild documentation](https://docs.kernel.org/6.6/kbuild/modules.html).
- [Linux 6.6 cpufreq.h (`verify` signature, 16-byte name)](https://github.com/torvalds/linux/blob/v6.6/include/linux/cpufreq.h).

No `insmod`, `modprobe`, firmware flash, DT enablement, TV MMIO, or TV
access. Successful compilation is **not** proven hardware functionality.
