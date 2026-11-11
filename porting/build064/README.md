# Build 064 – P1/P2-Peripherie-Scaffolds + Treiber-Gesamtplan

**Read-only. Kein Gerätezugriff, kein Flash.** Ergänzt das Build-063-P0-Framework
um die P1/P2-Subsysteme (Audio, Video/MFC, HDMI/CEC, IR, Netzwerk) als
Config/DT/Plan und liefert den **Treiber-Gesamtplan** (`docs/DRIVER_MASTER_PLAN.md`).

- `configs/nikel-peripherals.config` – ASoC/V4L2/CEC/rc-core/Netz (Compile-Coverage).
- `dts/sdp-nikel-peripherals-disabled.dts` – MFC-Knoten (Base 0xa40000 aus HAL-Matrix)
  + Audio/HDMI/CEC/IR/Ethernet, alle `disabled`, Platzhalter.
- `docs/DRIVER_MASTER_PLAN.md` – alle Subsysteme sequenziert, Samsung-Quelldatei-
  Mapping, 4.1→6.6-Migrationen, Android-HAL-Zuordnung, kritischer Pfad.
- Maschinenlesbar: `../../reports/driver_subsystem_matrix_build064.json`.

CI (`build064-dts-check.yml`) prüft die DTS mit `dtc`. Kein neuer C-Treiber →
kein Kernel-Compile nötig. Sperre und Boot-Gates bleiben.
