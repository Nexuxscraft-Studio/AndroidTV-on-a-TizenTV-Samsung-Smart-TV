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

**run003 on the Debian lab: NOT EXECUTED.** The Samsung archive and the lab
paths are not available to the agent.

**New since this ledger was written (2026-11-10, evening; outside the Debian lab):**
the repository-owned sources were compiled for real against Linux 6.6.162
(`gregkh/linux` `v6.6.162`, commit `5139929c698c273e07cb0635732f6a918a7b8e78`),
`multi_v7_defconfig` + `DRM_PANFROST=m`, **without** the Samsung archive:

| Evidence | Toolchain | Where | Result |
|---|---|---|---|
| 7 repo objects + `panfrost.o` (`--no-vendor-drm`) | `arm-linux-gnueabihf-gcc` 13.3.0 | GitHub CI run 42885294253 | ELF32/ARM, PASS |
| same | clang 18.1.3 (`LLVM=1`) | GitHub CI run 42885294253 and agent workspace | ELF32/ARM, PASS; `W=1` clean |
| full `vmlinux` + 856 in-tree modules | clang 18.1.3 | agent workspace | PASS (23m44s, `-j2`) |
| `modpost` of the 6 repo modules against that `Module.symvers` | clang 18.1.3 | agent workspace | 6 × `.ko`, no modpost warnings |

The four symbols reported unresolved in run002 (`__platform_driver_register`,
`dev_err_probe`, `arm_copy_from_user`, `kmalloc_trace`) are present as
vmlinux exports in the full build's `Module.symvers`. This supports the
diagnosis that run002's modpost failure came from a `modules_prepare`-only
tree. **GCC module linking is still unverified** and is what run003 with
`BUILD058_FULL_KERNEL=1` will show. No result here concerns Samsung DRM
Core/GEM or any hardware.

## Run003 (Debian lab; new output only)

```bash
cd /opt/sdpt-build002/samsung-driver-porting-toolkit
git fetch origin
git checkout -B claude/build058-arm32-compile-gate origin/claude/build058-arm32-compile-gate
python3 -m unittest discover -s tests -q
python3 porting/build058/integration/test-early-tracing.py -v

# Same kernel sources as CI? Expected: b6e9982c1f8dd98496e494a4e8cbc2f35cdb383488d63f9cc041a227591b1286
(cd /opt/samsung-atv-lab/linux-6.6.162 && LC_ALL=C bash -c 'sha256sum Makefile include/linux/cpufreq.h include/linux/thermal.h include/linux/clk-provider.h include/linux/reset-controller.h include/drm/drm_drv.h include/drm/drm_gem.h include/drm/drm_gem_dma_helper.h include/linux/dma-fence.h drivers/gpu/drm/panfrost/*.c drivers/gpu/drm/panfrost/Kconfig drivers/gpu/drm/panfrost/Makefile | sha256sum')

# a) objects only (minutes)
CROSS_COMPILE=arm-linux-gnueabihf- JOBS=2 \
  bash porting/build058/integration/run-arm32-compile-only.sh \
  /opt/samsung-atv-lab/linux-6.6.162 \
  /opt/samsung-atv-lab/samsung/kernel/tztv-media-nike.tgz \
  /opt/samsung-atv-lab/build058-integration-run003

# b) full kernel + modpost (about 25 min on 2 cores in the agent workspace; more on a small VM)
CROSS_COMPILE=arm-linux-gnueabihf- JOBS=2 BUILD058_FULL_KERNEL=1 \
  bash porting/build058/integration/run-arm32-compile-only.sh \
  /opt/samsung-atv-lab/linux-6.6.162 \
  /opt/samsung-atv-lab/samsung/kernel/tztv-media-nike.tgz \
  /opt/samsung-atv-lab/build058-integration-run003-full

# c) read-only Samsung ABI inventory (no extraction)
python3 -I porting/build058/integration/inventory-sdp-drm-abi.py \
  /opt/samsung-atv-lab/samsung/kernel/tztv-media-nike.tgz \
  /opt/samsung-atv-lab/build058-sdp-drm-abi-inventory.json
```

With the Samsung archive, runs a) and b) are **expected to exit 1** as long
as `sdp_drm_drv_elf`/`sdp_drm_gem_elf` are blocked (`drm/drm_tztv.h`). The
useful evidence is in `RESULTS.tsv` and the per-step logs, especially
`logs/samsung_drm_drv_gem_arm32_sdp_drm_drv_compile.log` (first real compiler
error) and the `*_modpost` lines of run b).

The fingerprint only covers the files that the Build 058 objects and
Panfrost depend on most directly. A different value means the Debian tree is
not byte-identical to the CI tree in those files, not necessarily that it is
broken. In that case report it; do not "fix" the tree.

The archive must match the pinned SHA256; if this path contains a different archive, the script aborts. Do not rename a different archive to bypass pinning. Inspect `RESULTS.tsv`, `logs/*.log`, `inputs.txt`, and `samsung-drm-early-tracing.patch`. `BUILD058_FULL_KERNEL=0` may be selected for object-only testing, with module link explicitly skipped.

## Samsung ABI blockers and remaining investigation

- `drm/drm_tztv.h` is absent from available pinned source archives. Its exact original contents, integer values, command indices, struct sizes, field offsets and compat32 layout remain **unknown**.
- Determine the exact required declarations using a compiler diagnostic pass **after** finding an authentic header. Do not ascribe every `DRM_SDP_*` identifier found in the source to this header: some may already live in other Samsung includes.
- Review genuine interface definitions used by `sdp_drm_drv.c`, `sdp_drm_gem.c`, `sdp_drm_crtc.c`, `sdp_drm_capture_drv.c`, `sdp_drm_debugfs.c`, `sdp_drm_out_connector.c`, `sdp_drm_out_encoder.c`, and `sdp_drm_tzdev.c`.
- **GEM/CMA remains unported**: compare Linux 4.1 `drm_gem_cma_helper.h` with Linux 6.6 `drm_gem_dma_helper.h` including alloc/free object lifetime, mmap/vmap, DMA-BUF map/attach, PRIME import/export, dumb buffer callbacks and Samsung memory flags. Those have hardware/ABI implications and cannot be blindly swapped.
- `vd_kernel-interfaces`, vendor display interfaces, HDMI/plane/scanout and security-zone dependencies remain blockers. No synthetic enum, ioctl or struct has been added.

## Safety

No TV access, module loading, device-tree enablement, MMIO, firmware flash or hardware verification. A successful compile or module link would **not** establish a safe boot image.
