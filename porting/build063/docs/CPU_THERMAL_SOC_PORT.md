# CPU-DVFS, Thermal und Core-SoC – Portierungsplan (Linux 6.6 ARM32)

**Read-only Plan. Kein Gerätezugriff, kein Flash.** Anschluss an Build 058
(CPU-Clock/DVFS/Thermal-Prototyp) und Build 059 (Core-SoC-Patches).

## CPU-DVFS: `cpufreq-dt` statt eigenem Treiber

Build 058 lieferte `sdp_nikel_cpufreq.c` als Prototyp. Der **sauberere Zielweg**
ist der Upstream-`cpufreq-dt`: DVFS wird als DT `operating-points-v2` + CPU-Clock
+ `cpu-supply` ausgedrückt, kein eigener C-Treiber nötig.

- Config: `CONFIG_CPUFREQ_DT=y`, `CONFIG_PM_OPP=y`, Governoren (`schedutil`…).
- DT: `cpu_opp_table` (Platzhalter-OPPs, `status="disabled"`), je CPU
  `operating-points-v2 = <&cpu_opp_table>`, `clocks`, `cpu-supply`.
- **Offen:** reale OPP-Frequenzen/Spannungen, CPU-Clock-Provider (sdp1804),
  Regulator. Bis dahin `disabled`.

## Thermal: DT `thermal-zones` + TMU-Sensor

- Config: `CONFIG_THERMAL_OF=y`, `CONFIG_CPU_THERMAL=y`, `GOV_STEP_WISE`.
- DT: `thermal-zones/cpu-thermal` mit Trips (Platzhalter 85 °C passive / 105 °C
  critical) + cooling-maps (später, nach OPP).
- **TMU-Sensor:** Nike-L-TMU weicht von `exynos-tmu` ab; Build 058 hat einen
  Prototyp. Sensor-Treiber + `#thermal-sensor-cells` sind noch zu verifizieren.

## Core-SoC: Build-059-Knoten aktivieren

Build 059 bringt `sdp_uart`, `clk-sdp1804` (nur lesend), `gpio-sdp`, plus
eMMC-/USB-/GPIO-Knoten, die im Referenz-DT `disabled` sind.

- **eMMC (`dw_mmc-exynos`) – P0:** nötig für Partitionsinventar und Datenzugriff
  eines realen Boot-Targets. `CONFIG_MMC_DW_EXYNOS=y`; DT-Knoten auf `okay` erst
  mit verifizierten Clocks/Regulatoren/Bus-Width.
- **USB EHCI/OHCI:** HID-Fernbedienungen, Storage; `CONFIG_USB_EHCI/OHCI_HCD=y`;
  VBUS-Regler (GPIO 86, Build-059-Patch 0009) prüfen.
- **Clock `clk-sdp1804`:** bisher nur lesend; für GPU/Display/CPU müssen
  Gate/Reset-Pfade koordiniert werden (ein Owner, keine doppelten MMIO-Provider).

## Reihenfolge

1. Core-SoC-Boot (UART-Konsole steht, eMMC als nächstes) – Build 059/063-Config.
2. CPU-Clock/Regulator → OPP → `cpufreq-dt` aktivieren.
3. TMU-Sensor → thermal-zones → cooling-maps.

Alles `disabled`/compile-only, bis am Gerät verifiziert. Sperre bleibt.
