# Build 058 — run003 preparation / evidence ledger (2026-11-10)

Target: Samsung Q60T GQ50Q60TGUXZG; Linux 6.6.162 ARM32, offline only.

## Verified from repository source, not recompiled here

- `sdp_nikel_cpufreq.c` already implements `verify(struct cpufreq_policy_data *)`.
- `cpufreq_driver.name = "sdp-nikel-off"` is 13 printable characters, 14 bytes with NUL; below `CPUFREQ_NAME_LEN=16`.
- CPUFreq probe remains fail-closed (`-EOPNOTSUPP`), no OPPs or voltage writes.
- Existing runner builds external `.o` targets before any module link; `modules_prepare` alone does not provide an adequate `Module.symvers`.
- Optional full-kernel path is now `vmlinux modules`; it attempts external module linking only with a nonempty generated `Module.symvers`. Unresolved symbols must remain failures. No `KBUILD_MODPOST_WARN`.
- A deterministic staged-only transformation replaces the optional `trace_early_message(msg)` call with `pr_debug("%s", msg)` in `sdp_drm_drv.c` and removes its `trace/early.h` include. The tool refuses unexpected input and emits a unified patch into run output. No original Samsung archive is modified.

## Build evidence

Previous user-supplied run002 results (not reproduced in this environment):
- ARM ELF objects: Panfrost, `sdp_nikel_gpu_clkrst`, `sdp_nikel_cpu_clk`, `sdp_drm_util`, `sdp_drm_fence`.
- Missing/failed: CPUFreq, Thermal, original Samsung DRM Core/GEM; `modpost` unresolved kernel exports from a prepare-only kernel.

**run003: NOT EXECUTED.** The paths under `/opt/samsung-atv-lab`, Samsung proprietary tar archive and cross compiler are not available in this agent workspace. No new ARM32 success is asserted.

## Run003 (Debian lab; new output only)

```bash
python3 porting/build058/integration/test-early-tracing.py -v
CROSS_COMPILE=arm-linux-gnueabihf- JOBS=2 BUILD058_FULL_KERNEL=1 \
  bash porting/build058/integration/run-arm32-compile-only.sh \
  /opt/samsung-atv-lab/linux-6.6.162 \
  /opt/samsung-atv-lab/samsung/kernel/tztv-media-nike.tgz \
  /opt/samsung-atv-lab/build058-integration-run003
```

The archive must match the pinned SHA256; if this path contains a different archive, the script aborts. Do not rename a different archive to bypass pinning. Inspect `RESULTS.tsv`, `logs/*.log`, `inputs.txt`, and `samsung-drm-early-tracing.patch`. `BUILD058_FULL_KERNEL=0` may be selected for object-only testing, with module link explicitly skipped.

## Samsung ABI blockers and remaining investigation

- `drm/drm_tztv.h` is absent from available pinned source archives. Its exact original contents, integer values, command indices, struct sizes, field offsets and compat32 layout remain **unknown**.
- Determine the exact required declarations using a compiler diagnostic pass **after** finding an authentic header. Do not ascribe every `DRM_SDP_*` identifier found in the source to this header: some may already live in other Samsung includes.
- Review genuine interface definitions used by `sdp_drm_drv.c`, `sdp_drm_gem.c`, `sdp_drm_crtc.c`, `sdp_drm_capture_drv.c`, `sdp_drm_debugfs.c`, `sdp_drm_out_connector.c`, `sdp_drm_out_encoder.c`, and `sdp_drm_tzdev.c`.
- **GEM/CMA remains unported**: compare Linux 4.1 `drm_gem_cma_helper.h` with Linux 6.6 `drm_gem_dma_helper.h` including alloc/free object lifetime, mmap/vmap, DMA-BUF map/attach, PRIME import/export, dumb buffer callbacks and Samsung memory flags. Those have hardware/ABI implications and cannot be blindly swapped.
- `vd_kernel-interfaces`, vendor display interfaces, HDMI/plane/scanout and security-zone dependencies remain blockers. No synthetic enum, ioctl or struct has been added.

## Safety

No TV access, module loading, device-tree enablement, MMIO, firmware flash or hardware verification. A successful compile or module link would **not** establish a safe boot image.
