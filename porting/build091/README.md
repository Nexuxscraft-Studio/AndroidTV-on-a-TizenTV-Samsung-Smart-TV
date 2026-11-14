# Build 091 – Nike-L-Display-Clocks und Reset-Handles

Basis ist Build 089 bei `a1cda7a`. Für Linux 6.6.162 zuerst Build 059
bis Patch 0026, danach Build 088, Build 089 und diese beiden Patches in
numerischer Reihenfolge anwenden. `main` bei `cb36b83` enthält die
Display-Serie nicht. In den erreichbaren Branches, Tags und der
Commit-Historie waren keine eigenständigen Builds 086 oder 090 zu finden.

## Quellenstand

- Build 085 (`origin/research/build-085-clock-controller`, `60d7327`)
  ordnet die dort dokumentierten SDP1804-Beispiele Muse-L ES zu.
  Insbesondere ist `0xf5088c` als Q60T-Display-Gate unbelegt.
- [Build 087](../build087/README.md) trennt und validiert die drei
  Display-Fenster. Die Probe-Sperre liegt vor der Ressourceninitialisierung.
- [Build 088](../build088/README.md) und [Build 089](../build089/README.md)
  gleichen die Firmware-DTBs ab. OSDP verwendet `osdp_clk_c` und
  `osdp_clk_vo`, GP verwendet `gp_clk_c` und `gp_clk_vo`, der Mixer
  verwendet `gfxp_clk_c` und `gfxp_clk_vo`. Die sechs Namen sind
  in der SDP1406-Tabelle zu finden und fehlen in der SDP1804-Gate-Tabelle.
  Beide Firmware-DTBs lassen Reset- und Power-Domain-Spezifizierer für
  diese Verbraucher offen.

## Integration

`DRM_SDP` bleibt standardmäßig deaktiviert und setzt Common Clock
Framework und Reset Controller voraus. Hinter der unbedingten
Probe-Sperre speichert der DRM-Gerätezustand die sechs per CCF
angeforderten Clock-Handles. Die Reset-API bereitet optional eine
verwaltete exklusive Gruppe für künftig belegte Reset-Spezifizierer vor.
Die fehlende Gruppe ist zulässig. Provider-Fehler und Probe-Deferral
werden weitergereicht. Devres gibt erworbene Handles beim Abbruch frei.
Der Binding-Patch dokumentiert den Reset-Befund. Er definiert keine
neuen Reset-Spezifizierer.

Der DT-Knoten bleibt deaktiviert. Der Code schaltet keine Clocks,
setzt keine Raten und löst keine Reset-Operationen aus. Der geerbte
1080p-Testpuffer und sein RAM-Registerplan verbleiben hinter der Sperre.
Es erfolgen weder Hardwareaktivierung noch MMIO-Zugriffe am TV.

## Offene Nachweise

Vor einer Hardwarefreigabe fehlen für Nike-L die Parent- und Gate-Zuordnung
mit Polaritäten, Reset-IDs und Sequenz, Power-Abhängigkeiten, DMA-
Busübersetzung und Hardwareausrichtung, Formatbits, Routing, Latch- und
IRQ-Semantik, echte Panel-Timings und ein Weg zur Wiederherstellung der
OEM-Bildausgabe.

Der [Workflow](../../.github/workflows/build091-display.yml) testet
auf dem Debian-Runner den standardmäßigen Kconfig-Zustand, den
Build-089-Hosttest, Checkpatch, den ARM32-Treiber mit `W=1 KCFLAGS=-Werror`,
vmlinux und Modul-Modpost, beide Board-DTBs und das Schema der Fixture.

## CI-Ergebnisse

Der [Build-091-Lauf bei `2963874`](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/actions/runs/43577182835)
bestand Checkpatch, den Framebuffer-Hosttest, die Prüfung des
standardmäßig deaktivierten Treibers, den ARM32-Build mit Modpost und
ELF32/ARM-Prüfung, beide Q60T-DTBs und die Schema-Prüfung.
Die [Offline-Prüfungen](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/actions/runs/43577182762)
für denselben Commit waren erfolgreich.

Der erste Lauf bei `8502bed` stoppte bei Checkpatch. Aus dem
Projekt-Checkout heraus behandelte Checkpatch die getrackte Patchdatei
als Quelltext. Seit `2963874` erfolgt die Patch-Prüfung aus dem
separaten Kernel-Verzeichnis.
