# Build 055 — Mali-G51 / Panfrost Offline-Referenz

**Ziel:** Linux 6.6 Panfrost als bevorzugte Open-Source-GPU-Lösung prüfen und
Samsung-GPU-Quellen ausschließlich als Hardware-Referenz verwenden.

**Status:** statische Quellcodeanalyse; **kein GPU-Treiber gebaut, geladen oder
am Fernseher getestet**. Der Samsung Q60T wurde nicht angesprochen.

## Linux 6.6 und Mesa

- Linux-6.6 `drivers/gpu/drm/panfrost/panfrost_gpu.c`: `GPU_MODEL(g51, 0x7000)`.
- Linux-6.6 `drivers/gpu/drm/panfrost/panfrost_drv.c`: DT-Match `arm,mali-bifrost`.
- Linux-6.6 `Documentation/devicetree/bindings/gpu/arm,mali-bifrost.yaml`:
  u.a. GPU-Registerbereich, Job/MMU/GPU-Interrupts, Clocks und gegebenenfalls
  Resets, Regulator und Power-Domains erforderlich.
- [Mesa Panfrost](https://docs.mesa3d.org/drivers/panfrost.html): Mali-G51
  gehört zu den unterstützten Bifrost-GPUs.

**GPU-Arbeitshypothese:** Mali-G51 Bifrost r11p0 (vom Nutzer aus einem Exploit
abgeleitet). Eine ausgelesene `GPU_ID` genau dieses Fernsehers liegt noch nicht
vor. Ältere Annahmen zu Mali-G31 sind nicht als Hardwarebeleg anzusehen.

## Samsung-Referenz

Der original veröffentlichte Samsung-OSS-Quellcode befindet sich im
SHA-256-geprüften `tztv-media-nike.tgz`. Relevante Dateien unter
`sdp_gpu_nike/drivers/gpu/arm/midgard/`:

| Originaldatei | Verwendung |
|---|---|
| `mali_kbase_core_linux.c` | Legacy-Kbase-Probe und OF-Matches `arm,mali-midgard` / `arm,malit6xx` |
| `mali_kbase_mem_linux.c` | Legacy-Speicherverwaltung/DMA-BUF als Architekturhinweis |
| `platform/sdp/mali_kbase_platform_sdp.c` | Samsung-spezifische Clocks, Resets, Power-Handling und DVFS |
| `platform/sdp/mali_kbase_config_platform.h` | Getrennte Nike.M-/Nike.L-Clock-/Reset-Registerbelegungen |

Ein paar **Nike.L-Kontrollregister** aus der Samsung-Quelle:

| Funktion | Alt-Quellcodewert |
|---|---|
| GPU Clock Mask | `0x00f5088c` |
| GPU Bus Reset | `0x00f507f8` |
| GPU Core Reset | `0x00f507f8` |
| GPU Idle Request | `0x00f50a10` |
| GPU Idle Status | `0x00f50a14` |

Diese Adressen sind **keine** nachgewiesene GPU-MMIO-Basis und **keine**
Freigabe für Registerzugriffe. Die tatsächliche TV-Boardvariante ist zu
verifizieren. Panfrost nutzt nicht automatisch die alten Samsung-Kbase-APIs:
Clock/Reset/Power-Integration gehört in geeignete Linux-6.6-Plattformtreiber.

## Reproduzieren (Debian, ausschließlich offline)

Vom Repository-Stammverzeichnis:

```bash
python3 q60t_build055_gpu_panfrost_evidence.py \
  --media-tgz .build050_vendor/srcarchives/tztv-media-nike.tgz \
  --output /tmp/build055-panfrost-reference.json
```

Das Ausgabefile darf noch nicht existieren; der Audit überschreibt nichts.
Ohne unverändertes Samsung-Archiv verweigert er die Analyse.

Falls die **echte** `sdp_gpu.ko` später aus einer bereits vorliegenden Firmware
verfügbar ist (derzeit nicht im Repository), nur die Datei offline inspizieren:

```bash
bash porting/build055/inspect-sdp-gpu-ko.sh /pfad/zur/sdp_gpu.ko
```

Das zeigt SHA-256, ARM32/ARM64, Modulversion und Abhängigkeiten. Weder das
Python- noch das Shell-Skript lädt Kernelmodule. Die Ausgabe beweist für sich
genommen **nicht**, dass die Mali-G51 im TV sitzt.

## Offene Blocker

1. Nachgewiesene tatsächliche GPU-ID bzw. Hardware-Evidence der Q60T-Variante.
2. GPU-MMIO-Basis/-Größe, Job/MMU/GPU-Interrupts und validierter Device Tree.
3. Nachweis der SoC-spezifischen Clock-/Reset-/Power-/Regulator-Kopplung.
4. IOMMU, DMA-Adressraum, coherency, Thermal- und Devfreq-Anbindung.
5. Abhängigkeiten von Firmware/Trusted World, die Panfrost blockieren könnten.

**Kein Test am realen TV und kein Flashen** ist Teil dieses Builds.
