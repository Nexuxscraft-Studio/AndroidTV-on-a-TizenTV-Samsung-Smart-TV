# Build 093 – DRM Integration Audit für den Samsung Q60T

## Basis und Quellen

Der lokale Checkout stand auf `feature/build089-framebuffer-plan`. Basis
für `feature/build093-drm-integration-audit` ist der geprüfte Remote-Head
`feature/build091-display-clkrst` bei `3fa985a7e7107fc0cc05b593c2cd264b313f1115`.
`main` stand bei `cb36b83300d46989167e90a7ec14a89f4d2e5226` ohne diese
Display-Patchserie. Ein Build-092-Branch war unter den Remote-Heads
nicht vorhanden. Für den OEM-Abgleich dienten die drei Textanhänge zu
Build 092, Schritte 18–20, im Chat „Proxmox Testlabor fortsetzen“.
Sie enthalten Auszüge aus dem Samsung-Code. Der zentrale Aufrufer der
OEM-Modeset-Callbacks und die vollständige Kaltstartfolge sind darin
noch offen.

Maßgeblich ist der angewandte Stand auf Linux 6.6.162. In numerischer
Reihenfolge Build 059 (0001 bis 0026), Build 088, Build 089, Build 091
und Build 093 anwenden. Patch 0015 enthält den historischen
Bootlogo-basierten MMIO- und Mixer-VSync-Entwurf. Patch 0026 ersetzt ihn
durch die inerte KMS- und Hardwarevorbereitung. Die separat abgelegten
Build-063- und Build-087-Dateien sind historische Stände.

## Implementierung und Abgleich mit Build 092

| Bereich | Effektiver Linux-6.6-Stand | OEM-Befund und verbleibende Lücke |
| --- | --- | --- |
| DRM/KMS | Einfache Display-Pipe, GEM-DMA, fbdev-Vorbereitung, 1920 × 1080 als Softwaregrenze. Enable/Disable/Update ohne Hardwareimplementierung. Probe liefert vor Ressourcenbezug `-EOPNOTSUPP`. | `sdp_drm_module_init()` registriert GP, Mixer, OSDP, QE, Cursor, Panel und DP Main über deren Callback-Tabellen. Die Registrierung belegt keine Aufruf- oder Hardwaresequenz. Der erste Scanout braucht einen verifizierten GP-Pfad bis zum Panel. |
| DT | Die beiden Q60T-Boards enthalten über das gemeinsame DTSI den deaktivierten Legacy-Knoten `samsung,sdp-drm` mit sieben Bereichen und den SPI-Angaben 47/102. Der aktuelle Treiber matcht `samsung,nikel-drm-hw-preparation`. Dieser Knoten existiert in der separat kompilierten deaktivierten Fixture. Deren benannte OSDP-, GP- und Mixer-Fenster beginnen bei `0x005d0000`, `0x005d4000` und `0x005d8000` und sind je `0x4000` Byte groß. | OEM-Probe mappt die Blöcke separat. Drei Fenster sind im aktuellen Treiber modelliert. Eine validierte Board-Anbindung mit Clock-, IRQ- und Panel-Beschreibung fehlt. |
| Clock, Reset und PM | Sechs CCF-Handles (`osdp_clk_c/vo`, `gp_clk_c/vo`, `gfxp_clk_c/vo`) und optionale exklusive Reset-Gruppe werden hinter der Sperre vorbereitet. Fixture ohne Provider-Referenzen. Keine Clock-Schaltung, Reset-Operation oder Display-PM-Sequenz. | OEM-`sdp_runtime_pm_init_and_get()` übernimmt einen bereits aktiven Zustand ohne Resume. Mixer-Clock-Selektoren unterscheiden sich je nach Pfad, etwa `0x80002110`, `0x80001101` und `0x80000110`. Für SDP1804 fehlen belegte Parent-/Gate-Zuordnung, Polaritäten sowie die Reset- und Power-Reihenfolge. |
| IRQ | Kein IRQ-Request. VBlank-Enable liefert `-EOPNOTSUPP`. Mixer-Register für Clear und Mask sind nur Konstanten. | OEM-OSDP-Probe fordert einen Shared IRQ mit `osdp_irq_handler` an. Der alte Mixer-VSync-Pfad aus 0015 belegt damit weder die Zuständigkeit für den ersten GP-Scanout noch Status, Maskierung und Ack auf dem Zielboard. |
| Framebuffer und Bootlogo | Linearer, unskalierter GEM-DMA-Scanout mit XRGB8888/ARGB8888, Objektgrenzenprüfung und 32-Bit-DMA-Grenze. Separater kohärenter 1080p-XRGB8888-Farbbalkenpuffer mit 7680 Byte Pitch und sieben Geometrieeinträgen im RAM. Weder Testpuffer noch GEM-Puffer sind mit einem Hardware-Flip verbunden. | OEM-GP, Mixer und OSDP berücksichtigen unter `SDP_LOGO` vorhandene Registerzustände. Hardwareausrichtung, DMA-Busübersetzung, Formatbits, Routing, Latch sowie Bootlogo-Übernahme und Wiederherstellung bleiben offen. |

## Priorität für den ersten Bildausgabetest

1. **P0 – Startzustand und Ausgang**. OEM-Modeset-Aufrufer, Bootlogo-Übergabe
   und Wiederherstellung belegen. SDP1804-Clock-/Reset-/Power-Abhängigkeiten
   und die tatsächliche Panel-/V-by-One-Konfiguration zuordnen.
2. **P0 – GP-Scanout**. DMA-Busadresse, Ausrichtung, Format, Mixer-Routing und
   Latch-Reihenfolge belegen. Die Geometrie im RAM beschreibt nur den
   unskalierten Fall.
3. **P1 – Board-Binding und VBlank**. Mit den geklärten Abhängigkeiten den
   Legacy-DT-Knoten ablösen und IRQ-Leitung, Trigger, Statusquelle, Maskierung
   und Ack für den gewählten Scanout verifizieren. Erst dann IRQ und
   Flip-Completion integrieren.

## Änderung und Tests

Build 093 nutzt dieselbe DMA-Bereichsprüfung für GEM-Scanout und
Testbild. Die Prüfung lehnt leere, falsch ausgerichtete oder über
32 Bit reichende Bereiche ab. Die GEM-Objektprüfung und die
bisherigen Fehlercodes beider Aufrufer bleiben erhalten. Der Hosttest
deckt insbesondere die inklusive Endadresse `0xffffffff`, den
Übertritt um ein Byte, Null-Länge und eine extrem große Länge ab.
Probe-Sperre und deaktivierte DT-Stände bleiben bestehen.

| Prüfung | Ergebnis |
| --- | --- |
| Build-091-CI bei `2963874` | Laut eingechecktem Bericht bestanden ARM32, Modpost, ELF32/ARM, beide DTBs, Fixture-Schema, Checkpatch und Hosttest. Der Jobs-Endpunkt lieferte beim Audit HTTP 404. |
| Patchserie | Linux-6.6.162-Tarball gegen den in Build 091 hinterlegten SHA-256 geprüft. Vollständige Serie bis Build 091 lokal angewandt, Build-093-Patch gegen den resultierenden Treiber geprüft. |
| Build-059- und Build-063-Tests | 17 + 5 bestanden mit Python im UTF-8-Modus. |
| C-Hosttests | Build-089-Pixel-/Geometrie-/Grenztest und Build-093-DMA-Grenztest bestanden mit Zig cc 0.15.2 und `-Wall -Wextra -Werror`. |
| Checkpatch | Strikt für den Build-093-Patch und die vier effektiven Treiberdateien bestanden. |
| Offline-Suite auf Windows | 307 Tests, davon 11 Fehlschläge, 3 Fehler und 13 übersprungen. Der unveränderte Build-091-Stand zeigt dieselben Fehlertests. |
| Build-093-ARM32, Modpost, DTBs und Schema | Im Debian-Workflow vorgesehen. Für Build 093 liegt noch kein CI-Ergebnis vor. |

- [Build-091-Dokumentation und CI-Links](../build091/README.md)
- [Build-093-Workflow](../../.github/workflows/build093-display.yml)
