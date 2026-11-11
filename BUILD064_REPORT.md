# Build 064 – Peripherie-Scaffolds und Treiber-Gesamtplan

**Branch:** `claude/build064-peripherals-masterplan` (aus Build 063).
**Status:** Read-only Config/DT/Plan. Kein Gerätezugriff, kein Boot, kein Flash.

Build 063 hat das P0-Treiber-Framework (Display/GPU/CPU/Core-SoC) CI-compile-
verifiziert. Build 064 vervollständigt die Treiberlandkarte um P1/P2 und liefert
den konsolidierten **Treiber-Gesamtplan** (`porting/build064/docs/DRIVER_MASTER_PLAN.md`).

## Inhalt

- **P1/P2-Subsysteme** als Compile-Coverage + DT-Fixtures (alle `disabled`):
  Audio (ASoC, `sdp_alsa_nike`), Video-Decode (V4L2-m2m, `sdp_codec_nike`,
  MFC-Base `0x00a40000`), HDMI + CEC (`sdp-mc-cecif`, stock disabled),
  IR (`rc-core`, `sdp-mc-irb/irs`, stock okay), Ethernet (`samsung,sdp-mac`).
- **Gesamtplan:** Subsystem-Matrix (Prio/Zielreiber/Samsung-Quelle/Status),
  4.1→6.6-Migrationsmuster, Android-HAL-Zuordnung, Bring-up-Reihenfolge,
  kritischer Pfad (Display-KMS → Panfrost → gralloc → SurfaceFlinger).
- Maschinenlesbar: `reports/driver_subsystem_matrix_build064.json`.

## CI

`.github/workflows/build064-dts-check.yml`: `dtc`-Prüfung der Build-064-DTS.
Kein neuer C-Treiber (alle P1/P2-Bindings sind Upstream-Subsysteme), daher kein
Kernel-Compile. Release-Audit PASS.

## Grenzen

Alle Knoten `disabled`; reg/IRQ/Clock sind unverifizierte Platzhalter (außer
MFC-Base). Die eigentliche SoC-Glue-Logik ist aus den Nike-L-Vendor-Quellen zu
portieren und am Gerät zu verifizieren. Sperre und Boot-Gates bleiben.
