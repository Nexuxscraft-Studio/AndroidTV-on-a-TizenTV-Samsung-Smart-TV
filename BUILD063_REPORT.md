# Build 063 – Treiber-Bring-up-Framework (Linux 6.6.162 ARM32)

**Zielgerät:** Samsung `GQ50Q60TGUXZG`, Nike-L. **Branch:**
`claude/build063-driver-bringup` (aus Build 062). **Status:** compile-only
Scaffolds, auf GitHub Actions cross-kompiliert (W=1 -Werror, ARM32). **Kein**
Gerätezugriff, **kein** Boot, **kein** Flash. Fortsetzung von Build 056–059.

Build 062 hat die ARM32-Baubarkeit und die Treiberlage bewertet. Build 063 setzt
das in ein **zusammenhängendes Treiber-Bring-up-Framework** um: Skelette,
Device-Tree-Fixtures, Kconfig-Fragmente, Integrationspläne und ein
**CI-Compile-Gate** für die vier P0-Subsysteme.

## Leitentscheidung: Upstream vor Eigenbau

Wo Mainline den SoC-Treiber schon kann, wird er genutzt statt neu geschrieben:
- **GPU:** Panfrost (Upstream) – Mali-G51/Bifrost, GLES 3.1. Kein eigener Treiber.
- **CPU-DVFS/Thermal:** `cpufreq-dt` + DT-OPP/thermal-zones (Upstream). Kein
  eigener Treiber (Build 058 hatte einen Prototyp; DT-Weg ist sauberer).
- **Display:** eigenes 6.6-DRM/KMS-**Skelett** nötig (kein Upstream-sdp-drm).
- **Core-SoC:** Build-059-Treiber (`sdp_uart`/`clk-sdp1804`/`gpio-sdp`) plus
  Aktivierung der bisher `disabled`-Knoten (eMMC/USB).

Das hält das Compile-Gate fokussiert (nur das Display-`.o`) und nutzt gepflegten
Mainline-Code für den Rest.

## 1. Display (`sdp-drm`) – kritischer Pfad

`porting/build063/kernel/display/sdp_drm.c`: minimales 6.6-DRM/KMS-Skelett
(Platform-Treiber, DRM-Device via `devm_drm_dev_alloc`, `drmm_mode_config_init`,
ein Fixed-Mode-Connector, `drm_simple_display_pipe`, `drm_fbdev_dma_setup`).
Baut auf Build 058 (`sdp_drm_util`/`sdp_drm_fence`, `fence`→`dma_fence`) auf.
**Alle Hardware-Schritte (Modeset, Plane, VSync, Panel-Init) sind TODO** und aus
den Nike-L-Vendor-Quellen zu füllen. Plan: `docs/DISPLAY_PORT.md` (inkl.
4.1→6.6-API-Mapping). Die Register-Region überlappt den sdp1804-Clock-Controller
→ ein koordinierter Owner nötig.

## 2. GPU (Mali-G51) – offener Panfrost-Stack

`configs/nikel-gpu.config` (`CONFIG_DRM_PANFROST=m` + Helfer),
`dts/…gpu-panfrost…` (Bifrost-Knoten, `disabled`, Clock/Reset auf Build-058-
`gpu-clkrst` verweisend). Userspace-Integration in `docs/GPU_INTEGRATION.md`:
Mesa/Panfrost + `kmsro` (bindet an `sdp-drm`), **gbm_gralloc** oder ARMs
Apache-Bifrost-Gralloc, **drm_hwcomposer** (AIDL-HWC). Abhängigkeitskette:
`sdp-drm → kmsro → Panfrost → gralloc → SurfaceFlinger`. **Ohne KMS kein Bild.**
Die Tizen-`libmali.so` ist bewusst nicht der Weg (kein Android-HAL).

## 3. CPU-DVFS/Thermal – `cpufreq-dt`

`configs/nikel-cpu.config` (`CPUFREQ_DT`, `PM_OPP`, Governoren, `THERMAL_OF`,
`CPU_THERMAL`), `dts/…cpu-dvfs…` (`operating-points-v2` + `thermal-zones`,
Platzhalter, `disabled`). OPP-Werte/Spannungen, CPU-Clock/Regulator und
TMU-Sensor (Build-058-Prototyp) sind offen.

## 4. Core-SoC

`configs/nikel-soc-extra.config` aktiviert die Build-059-Knoten für Compile-/
Boot-Vorbereitung: eMMC (`dw_mmc-exynos`, **P0** für Partitionen/Daten), USB
EHCI/OHCI, Ethernet-Platzhalter. DT-Knoten erst mit verifizierten
Clocks/Regulatoren auf `okay`.

## CI-Compile-Gate (GitHub Actions)

`.github/workflows/build063-driver-compile.yml` (gespiegelt an build059):
- `host-tests`: Unit-Tests + `driver_coverage.py`.
- `compile`: Linux 6.6.162 (gepinnt) klonen, `build.sh` → `sdp_drm.o` **W=1
  -Werror** (ARM32) + **dtc** über alle Build-063-DTS.

Ein grüner Lauf beweist **Compile-Barkeit** des Display-Skeletts und
DTS-Syntax – **nicht** Funktion oder Boot.

## Verifikation lokal

`driver_coverage.py` → Matrix (alle vier Subsysteme `SCAFFOLD_PRESENT`);
Report `reports/driver_coverage_build063.json`. **9** (build061) + **5**
(build063) synthetische Tests. Release-Audit-Allowlist um die neuen
`.c/.dts/.sh/.config/Kconfig/Makefile`-Pfade erweitert.

## Grenzen / offen

- Alle DT-Knoten `disabled`; reg/IRQ/Clock/Reset/Panel-Timing/OPP/TMU sind
  unverifizierte Platzhalter.
- Reale GPU-ID, Display-MMIO/IRQ, CPU-OPPs und TMU am Gerät zu bestätigen.
- Sperre und Boot-Gates bleiben. Nächster Schritt: CI grün bekommen, dann
  Display-Vendor-Logik füllen (Modeset) – der Engpass für das erste Bild.
