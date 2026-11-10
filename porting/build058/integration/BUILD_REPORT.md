# Build 058 — Integrationsbericht (ARM32-Fix nach Testlauf)

## 2026-11-10 (Abend): Echter ARM32-Compile- und Link-Nachweis ohne Samsung-Archiv

Branch `claude/build058-arm32-compile-gate`, basiert auf
`feature/build058-hardware-integration` @ `fea14c5`.

### Kernelbasis

Linux **6.6.162** aus `gregkh/linux`, Tag `v6.6.162`, Commit
`5139929c698c273e07cb0635732f6a918a7b8e78`. Konfiguration wie im Runner:
`multi_v7_defconfig`, `MODULES=y`, `DRM=y`, `DRM_PANFROST=m`, `olddefconfig`.
`CONFIG_DRM_LEGACY` ist dabei **nicht** gesetzt.

### Ergebnisse

| Prüfung | Toolchain | Ort | Ergebnis |
|---|---|---|---|
| `defconfig`, `olddefconfig`, `modules_prepare` | GCC 13.3.0 `arm-linux-gnueabihf-` und clang 18.1.3 | GitHub CI, Run 42885294253 (Commit `ca7192a`) | PASS |
| `panfrost.o` (10 Quelldateien) | beide | CI und lokal | ELF32/ARM |
| `sdp_nikel_gpu_clkrst.o`, `sdp_nikel_cpu_clk.o` | beide | CI und lokal | ELF32/ARM |
| **`sdp_nikel_cpufreq.o`** (in run002 fehlgeschlagen) | beide | CI und lokal | **ELF32/ARM** |
| **`sdp_nikel_thermal.o`** (in run002 nicht erzeugt) | beide | CI und lokal | **ELF32/ARM** |
| `sdp_drm_util.o`, `sdp_drm_fence.o` | beide | CI und lokal | ELF32/ARM |
| dieselben 7 Objekte mit `W=1` | clang 18.1.3 | lokal | keine Warnung |
| vollständiger Kernel `vmlinux` + 856 Module | clang 18.1.3 | lokal | PASS, 23 min 44 s mit `-j2` |
| `modpost`/Link der 6 Repo-Module gegen diese `Module.symvers` | clang 18.1.3 | lokal | 6 × `.ko`, ELF32/ARM, vermagic `6.6.162 SMP mod_unload ARMv7 p2v8`, **keine** modpost-Warnung |
| Runner-Pfad `BUILD058_FULL_KERNEL=1 --no-vendor-drm` (erstmals ausgeführt) | clang 18.1.3 | lokal | `arm32_full_kernel_for_symvers` PASS, `kernel_module_symvers` PRESENT, 3 × `*_modpost` PASS ohne Warnung, Exit 0 |
| Samsung-DRM Core/GEM | — | — | **nicht versucht** (Archiv nicht vorhanden) |
| GCC-Modullink (`modpost`) | GCC | — | **nicht ausgeführt** |
| Boot, QEMU, Q60T | — | — | **nicht ausgeführt** |

Die in run002 ungelösten Symbole `__platform_driver_register`,
`dev_err_probe`, `arm_copy_from_user` und `kmalloc_trace` stehen in der
`Module.symvers` des Vollbuilds als vmlinux-Exports. Die run002-Diagnose
(„`modules_prepare` liefert keine Symboltabelle“) ist damit für clang
bestätigt. Für GCC bestätigt erst run003 b) auf dem Debian-Server.

### Geänderte Dateien

- `integration/run-arm32-compile-only.sh`: `BUILD058_TOOLCHAIN=gcc|llvm`,
  `--no-vendor-drm`, ELF32-und-ARM-Prüfung, Compiler-Version in `inputs.txt`,
  Vorabprüfung `flex`/`bison`/`bc`. `LLVM`/`LLVM_IAS` werden nie aus der
  Umgebung übernommen, weil Kbuild auch `LLVM=0` als „LLVM an“ wertet.
  `llvm-readelf` akzeptiert kein `--`; das hat der erste lokale Lauf korrekt
  als „blocked“ gemeldet, behoben ist es durch ausschließlich absolute
  Objektpfade.
- `.github/workflows/build058-arm32-compile.yml`: neuer CI-Compile-Gate
  (GCC + LLVM, Kernel per Commit gepinnt, Logs als Artefakt).
- `integration/inventory-sdp-drm-abi.py`: schreibgeschütztes Samsung-ABI-Inventar.
- `integration/DRM_GEM_LINUX66_MAP.md`, `integration/PANFROST_CLKRST_LINUX66.md`: Analyse.
- `tests/test_build058_hardware_integration.py`: 11 neue Tests (Runner-Guards
  mit Attrappen-Kernel, Inventar mit synthetischem Archiv, CI-Pinning).
- `tests/test_release_audit_sources.py`: ignoriert `__pycache__` wie
  `audit()` selbst. Vorher schlug `unittest discover` fehl, sobald
  `test-early-tracing.py` gelaufen war, also genau in der Reihenfolge aus
  `RUN003_PREPARATION.md`.

### Neue technische Befunde

1. **Samsung DRM (Phase C):** Build 053 entfernt Samsungs GEM/PRIME-Callbacks
   aus `drm_driver`, ohne sie in `drm_gem_object_funcs` neu anzubinden.
   `preclose` und die Vblank-Felder gibt es in 6.6.162 nur unter
   `CONFIG_DRM_LEGACY`. Samsung nutzt eine eigene, erweiterte
   `drm_gem_cma_helper.h` (`num_slots`). Details in `DRM_GEM_LINUX66_MAP.md`.
2. **GPU (Phase D):** Panfrost 6.6.162 setzt die Resets vor dem Abschalten
   des Takts und schaltet Takt/Reset nicht im Runtime-PM. Das widerspricht
   der Idle→Reset→Takt-aus-Sequenz im `.disable` des Prototyps. Details in
   `PANFROST_CLKRST_LINUX66.md`.

### Einordnung

Kompilieren und Linken beweisen **keine** Funktion. Alle Prototypen bleiben
fail-closed (`probe()` bricht vor jedem MMIO-Zugriff ab), kein DT-Knoten ist
aktiviert, nichts wurde geladen oder geflasht.

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
