# Build 089 – Vorbereitung des ersten 1080p-Framebuffer-Tests

Basis ist Build 088 bei 247aea2 mit dem nachfolgenden Dokumentationscommit f60e453.
Die Patch-Reihenfolge ist Build 059 bis 0026, Build 088, dann Build 089.

Build 088 enthält bereits Clock-Lookup und kohärente DMA-Allokation hinter
der unbedingten Probe-Sperre. Build 089 übernimmt die Allokation und nutzt
die Testbildfunktion aus dem Hosttest und aus dem Treiber. Der Puffer enthält
1920 × 1080 XRGB8888-Pixel mit 7680 Bytes pro Zeile, acht vertikalen
Farbbalken und einem grauen Ein-Pixel-Rand. Der Treiber schreibt jedes Wort
in Little Endian. Der Plan prüft die 4-Byte-Ausrichtung und die inklusive
Endadresse des gesamten 8.294.400-Byte-Bereichs vor der Verengung auf 32 Bit.
Die Ausrichtung ist derzeit eine Softwareanforderung.

## Quellenprüfung

Die drei Originaldateien wurden erneut gegen die SHA-256-Werte im
[Build-088-Bericht](../build088/README.md) geprüft. Beide FDTs bei 0x0 und
0x15000 referenzieren dieselben sechs Zero-cell-Kindknoten des Controllers
samsung,sdp1804-clock bei 0xf50000.

| Fenster | Adressbereich | Clock-Namen und Phandles |
| --- | --- | --- |
| OSDP | 0x5d0000–0x5d3fff | osdp_clk_c/vo (0x3a/0x3b) |
| GP | 0x5d4000–0x5d7fff | gp_clk_c/vo (0x3c/0x3d) |
| Mixer | 0x5d8000–0x5dbfff | gfxp_clk_c/vo (0x3e/0x3f) |

Im Originalkernel enthält drivers/clk/clk-sdp.c:888–911 die Namen in
der SDP1406-Tabelle. sdp1804_clk_init() wählt dagegen sdp1804_gate[]
(1547–1570), in der alle sechs fehlen. Parent, Gate-Bit, Polarität und
Reset-/Power-Sequenz sind für SDP1804 offen. Die DTs enthalten an den
drei Verbrauchern keine Reset- oder Power-Domain-Spezifizierer.

Im Nike-L-Archiv belegt sdp_gfx_reg_addr.h die bankrelativen Byteoffsets.
sdp_gfx.c:462–466, sdp_gp.c:97–104 und sdp_osdp.c:94–102 belegen
die Packung Breite << 16 | Höhe sowie die Quelloffset-Einheit src_w / 4.

| Bank | Werte im RAM-Plan |
| --- | --- |
| GP | 0x10 und 0x14 jeweils 0x07800438, 0x18 mit 480 |
| OSDP | dieselben Geometriewerte als Referenz für unskalierten Betrieb |
| Mixer | Haupt-Aktivgröße 0x20 mit 0x07800438, siehe sdp_mixer.c:1025–1038 |

Die GP-A1-Register liegen bei 0x30 und 0x34. Die DMA-Adresse wird
separat gespeichert, bis die Busübersetzung geklärt ist. OSDP-
Skalierkoeffizienten ab 0x200 und 0x240, der GP-Latch bei 0x54 sowie
Mixer-IRQ-Clear und Mask bei 0x08 und 0x0c bleiben außerhalb des Plans.
Der deaktivierte DT-Knoten und die unbedingte Probe-Sperre verhindern
Hardwarezugriffe. Es gab keine Flash-Aktion.

## Reale Bildausgabe auf dem GQ50Q60TGUXZG

Vor einem Hardwaretest Clock-/Reset-/Power-Abhängigkeiten und die
DMA-Adressübersetzung samt Hardwareausrichtung anhand belastbarer Quellen
oder vorhandener, autorisiert erfasster Hersteller-Traces klären. GP-
Formatbits, Routing, Latch-Reihenfolge und die Übernahme der mit Bootlogo
und Cursor geteilten Fenster verifizieren. Der Dummy-Panel-Knoten enthält
eine Pixelclock von null. Die tatsächlichen Panel-/V-by-One-Timings und
ein Verfahren zur Wiederherstellung der OEM-Bildausgabe sind offen.

Der Build-089-Workflow startet bei Pushes auf feature/build089-* auf
[self-hosted, debian]. Er prüft die produktive Pixel- und Planlogik
per Hosttest, kompiliert den ARM32-Treiber mit W=1 KCFLAGS=-Werror,
baut vmlinux und Module mit echtem Module.symvers, führt Checkpatch
im Strict-Modus aus und baut beide Board-DTBs. Die deaktivierte
Fixture wird mit dtschema 2026.9 geprüft.

## CI-Ergebnisse

Der [Build-089-Push-Lauf](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/actions/runs/43574978657)
war bei Commit de18365 auf dem Runner debian erfolgreich. Linux 6.6.162
mit Android Clang 19.0.1 erzeugte ein ARM-ELF32-Modul und ein echtes
Module.symvers. Für alle vier C-/Header-Dateien meldete Checkpatch null
Fehler, Warnungen und Checks. Der Hosttest prüfte alle 2.073.600 Pixel,
alle sieben Geometrieeinträge und mehrere DMA-Grenzfälle. Beide Board-DTBs
und die Schema-Prüfung der deaktivierten Fixture waren erfolgreich.

Der [separate Offline-Lauf](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/actions/runs/43574978695)
war für denselben Commit erfolgreich. Beim ersten Push fehlten drei
Hosttest-Pfade in der exakten Allowlist des Release-Audits. Der Folgecommit
ergänzt nur diese drei Pfade.
