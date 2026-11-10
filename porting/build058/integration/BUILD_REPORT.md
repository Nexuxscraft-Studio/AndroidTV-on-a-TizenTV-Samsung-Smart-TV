# Build 058 — Integrationsbericht (initial)

## Delivered

- Integration branch based on `feature/build058-cpu-dvfs-thermal-linux66162`
  (itself based on existing GPU Build 058 / Build 057 work).
- Real upstream Panfrost ARM32 compile target for exact Linux 6.6.162.
- Samsung DRM staged build: isolated application of Build 053 then Build 054
  patches to the pinned original `tztv-media-nike.tgz`.
- Two genuine Samsung-derived C files modernized to Linux 6.6:
  `sdp_drm_util.c` (bounded copy/wait/mask behavior) and `sdp_drm_fence.c`
  (modern `dma_fence` and reference-counted context ownership).
- CPU clock, CPUFreq, thermal, and GPU clock/reset source compilation invoked
  from copies of the already disabled Build 058 prototypes.
- Strict input checks, per-phase logs, ELF architecture checks, no destructive
  cleanup or writes to original vendor archives/kernel source.

## Evidence collected in this development environment

| Check | Result |
|---|---|
| New source files staged | Yes |
| Pinned original Samsung media archive | Present and SHA-256 matched |
| Upstream Panfrost v6.6 Kconfig/Makefile | Consulted directly |
| Shell script syntax/static regression | See local test output |
| ARM32 GCC cross-compiler installed here | **No** |
| Linux 6.6.162 full prepared kernel here | **No** |
| **Actual Panfrost ARM32 kernel compile** | **NOT RUN** (requires Debian server) |
| **Actual Samsung DRM C object compile** | **NOT RUN** (requires Debian server) |
| **Actual CPU/thermal ARM32 kernel compile** | **NOT RUN** (requires Debian server) |

The runner is designed to produce machine-verifiable `RESULTS.tsv` and
individual compile logs. **Do not replace these `NOT RUN` statuses with PASS
until actual ARM ELF objects and compiler logs exist.**

## Technical blockers to resolve after the Debian run

1. **Panfrost:** Kconfig dependencies; GPU clock/reset/PM domains and IRQ
   triggering still unverified. Compiling `panfrost.o` does not enable a
   functional Mali-G51.
2. **Samsung DRM:** original large `sdp_drm_drv.c` and `sdp_drm_gem.c` still
   need modern DRM core, GEM object, DMA fence, CMA, platform interfaces;
   proprietary `vd_kernel-interfaces` headers may be absent. Report exact
   first failing header/API from the server logs, not speculative fixes.
3. **CPU DVFS:** non-L0-to-non-L0 transition and 100/125 MHz L4 mismatch,
   ASV binning and regulator/clock ownership unresolved. No active OPPs.
4. **Thermal:** original formula and limits reconstructed but no Nike-L
   calibration validation or live cooling linkage.
5. **Boot/Display:** complete Nike-L DT and Samsung ARM64 boot capability
   remain unknown. ARM32 compilation alone cannot establish either.

## Safety

The script is a **compilation tool only**. Output always goes into a new
directory, original GPL sources remain unchanged, and it never loads a
module, writes firmware, enables a DT node or accesses the television.
