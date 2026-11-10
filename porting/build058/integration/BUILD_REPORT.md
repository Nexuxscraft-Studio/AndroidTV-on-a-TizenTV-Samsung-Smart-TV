# Build 058 — Integrationsbericht (ARM32-Fix nach Testlauf)

## 2026-11-10: Linux-6.6-ARM32-Fehlerkorrektur

Gemeldete **Debian-Testergebnisse** (noch nicht in diesem Workspace
unabhängig nachgebaut): Panfrost, GPU Clock/Reset, CPU Clock, DRM Utility
und DRM DMA-Fence erzeugten ARM32-Objekte. Die gemeldeten `modpost`-Fehler
werden nicht länger als Fehler der C-Objektkompilierung interpretiert.

Neue Korrekturen:

1. CPUFreq `verify` verwendet nun die Linux-6.6-Signatur
   `struct cpufreq_policy_data *`; die Treiberkennung `sdp-nikel-off`
   respektiert `CPUFREQ_NAME_LEN = 16` einschließlich Terminator.
2. Der ARM32-Runner führt pro `.c`-Datei einen **einzelnen** kbuild `.o`-Test
   aus und klassifiziert `modpost` separat; `BUILD058_FULL_KERNEL=1` führt
   auf Wunsch zuerst einen vollständigen `vmlinux`-Build aus, dessen
   `Module.symvers` für anschließende `.ko`-Tests benötigt wird.
3. `trace/early.h` aus dem veröffentlichten Linux-4.1.10-Archiv ist in
   einer diagnostischen Staging-Include-Directory enthalten. Die fehlende
   Datei `drm/drm_tztv.h` konnte in **keinem** der zwei originalen
   Samsung-Archive gefunden werden. Ihre echten DRM-UAPI-Definitionen
   dürfen nicht durch geratenen Code ersetzt werden.
4. Nike-L CPUFreq/DVFS und Thermal bleiben **fail-closed**. Kein OPP,
   keine Spannung, keine Clock-, Reset-, TMU- oder DRM-Initialisierung
   wird hier freigeschaltet.

Verifikation in diesem Workspace: Bash-Syntax, Regressionstests und
Release-Quelltext-Audit. **Ein erneuter ARM32-Compile-Lauf muss auf dem
Debian-Testserver durchgeführt werden; hier fehlen GCC ARM32 und der
komplette Linux-6.6.162-Baum.** `sdp_drm_drv.o` und `sdp_drm_gem.o` werden
bis zur echten Samsung-ABI und weiteren API-Portierung voraussichtlich
weiterhin scheitern. Der Report darf dafür keinen PASS vortäuschen.

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
