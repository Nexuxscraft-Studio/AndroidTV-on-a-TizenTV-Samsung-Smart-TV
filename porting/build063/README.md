# Build 063 – Treiber-Bring-up-Framework (Linux 6.6.162 ARM32)

**Status: compile-only Scaffolds, CI-gegated. NICHT gebootet, kein Flash, kein
Gerätezugriff.** Fortsetzung von Build 056–059. Die `BoardConfig.mk`-`$(error)`-
Sperre bleibt.

Build 063 legt ein zusammenhängendes **Treiber-Bring-up-Framework** für die vier
P0-Subsysteme an und lässt die kompilierbaren Teile **auf GitHub Actions**
cross-kompilieren (W=1 -Werror für ARM32) – kein lokaler Buildhost nötig.

## Subsysteme

| Subsystem | Art | Artefakte |
| --- | --- | --- |
| **Display** (`sdp-drm`) | eigenes 6.6-DRM/KMS-**Skelett** | `kernel/display/sdp_drm.c` (+Kconfig/Makefile), `dts/…display…`, `configs/nikel-display.config`, `docs/DISPLAY_PORT.md` |
| **GPU** (Mali-G51) | **Panfrost** (Upstream) | `configs/nikel-gpu.config`, `dts/…gpu-panfrost…`, `docs/GPU_INTEGRATION.md` |
| **CPU-DVFS/Thermal** | **cpufreq-dt** (Upstream) | `configs/nikel-cpu.config`, `dts/…cpu-dvfs…`, `docs/CPU_THERMAL_SOC_PORT.md` |
| **Core-SoC** | Build-059-Knoten aktivieren | `configs/nikel-soc-extra.config`, `docs/CPU_THERMAL_SOC_PORT.md` |

Leitlinie: **Upstream-Treiber bevorzugen** (Panfrost, cpufreq-dt), eigenen
C-Treiber nur wo nötig (Display). Das hält das Compile-Gate fokussiert und
nutzt gepflegten Mainline-Code.

## Compile-Gate (GitHub Actions)

`.github/workflows/build063-driver-compile.yml`:
1. Unit-Tests + Coverage-Matrix (`driver_coverage.py`).
2. Linux 6.6.162 klonen (gepinnter Commit), `build.sh` ausführen:
   - `sdp_drm.o` mit **W=1 -Werror** für ARM32 bauen,
   - alle Build-063-DTS mit **dtc** prüfen.

Lokal reproduzierbar:
```bash
python3 -m unittest discover -s porting/build063/tests -v
python3 porting/build063/driver_coverage.py
bash porting/build063/build.sh /pfad/zu/linux-6.6.162 arm /pfad/zu/out
```

## Kritischer Pfad

`sdp-drm` (Display-KMS) → `kmsro` → Panfrost → gbm_gralloc → SurfaceFlinger, und
parallel `drm_hwcomposer`. **Ohne KMS kein Bild.** Siehe `docs/GPU_INTEGRATION.md`.

## Grenzen

Alle DT-Knoten `disabled`; reg/IRQ/Clock/Reset/Panel-Timing/OPP/TMU sind
unverifizierte Platzhalter. Ein grünes CI beweist **Compile-Barkeit**, nicht
Funktion oder Boot.
