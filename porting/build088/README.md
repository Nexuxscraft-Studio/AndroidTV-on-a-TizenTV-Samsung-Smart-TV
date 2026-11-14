# Build 088 – Nike-L Display und DMA-Testbild

Basis: `feature/build087-drm-hardware-layer` bei `3de20b0208c5d052d5bd5eda20c8b5304d5c4812`.
Die eingecheckten Build-087-Protokolle zeigen `CC` für beide ARM32-Dateien,
`AR` für den In-tree-Treiber und `LD` für das externe Objekt. Build 087
hat damit einen dokumentierten Objektbuild. Der Build-088-Workflow wiederholt
den ARM32-Compile vor Anwendung des neuen Patches.

Build 088 wird als zusätzlicher Patch nach der Build-059-Serie bis 0026
angewendet. Der DRM-Probe bleibt vor Clock-Lookup, DMA-Allokation und Mapping
unbedingt gesperrt. Die vorbereitete CCF-Anbindung verlangt alle sechs
Firmware-Takte. Der DMA-Puffer verwendet kohärenten, geräteverwalteten Speicher,
eine 32-Bit-DMA-Maske und eine zusätzliche Prüfung des gesamten Adressbereichs.
Er enthält 1920×1080 XRGB8888-Pixel (7680 Bytes Pitch, 8.294.400 Bytes):
acht senkrechte Farbbalken und einen grauen Ein-Pixel-Rand. Die Pixel werden
als Little-Endian-Wörter mit null im X-Byte geschrieben. Der Puffer wird
keinem Scanout-Register übergeben.

## Quellen und zulässige Zugriffe

Die drei Originaldateien stammen vom [Quellserver des Projekts](https://testpaymenter.noverhost.de/sehrwichtig/).
Die Archive wurden lokal heruntergeladen und mit den im Repository
dokumentierten SHA-256-Werten abgeglichen.

| Quelle | SHA-256 |
| --- | --- |
| `inner/linux-4.1.10-tizen5.5.tgz` | `31a92f0d20248abbe2976bd2da1ab95dde4fed3e010ddcdc1c07494c4fd867b0` |
| `inner/tztv-media-nike.tgz` | `40c2a25eba331b8b04d8d81baf76061493f15f228a74893c7f825f7a1da724b6` |
| `dtb.bin` | `9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2` |

Beide FDTs (Bundle-Offsets `0x0` und `0x15000`) deklarieren den
SDP1804-Controller bei `0xf50000` mit `0x3000` Bytes. Die drei Display-Bänke
haben je `0x4000` Bytes. OSDP `0x5d0000` referenziert
`osdp_clk_c/vo` (Phandles `0x3a/0x3b`), GP `0x5d4000`
`gp_clk_c/vo` (`0x3c/0x3d`) und Mixer `0x5d8000`
`gfxp_clk_c/vo` (`0x3e/0x3f`). Die Phandles zeigen auf
Zero-cell-Kindknoten des Controllers. Die Zuordnung zu Registerbits fehlt.
Der Firmware-DT enthält an diesen Display-Knoten keine Reset- oder
Power-Domain-Spezifizierer. Bootlogo und Cursor beanspruchen teils dieselben
Fenster. Bootlogo referenziert außerdem `ga2d_clk`. Das Dummy-Panel nennt
1920×1080 aktive Pixel bei Pixelclock null.

- **Clock/Reset.** `drivers/clk/clk-sdp.c:888–911` enthält die sechs Namen mit
  `ga2d_f_clk` als Parent für **SDP1406**. Die von
  `sdp1804_clk_init()` (2522–2540) verwendete Tabelle `sdp1804_gate[]`
  (1547–1570) enthält diese Gates nicht. Für SDP1804 bleiben Gate-Bits,
  Parent-Takt, Polarität, Reset- und Power-Reihenfolge offen. Der Patch
  registriert keine Gate-Provider und ruft kein CCF-Enable auf.
- **GP.** Nike-L `sdp_gfx_reg_addr.h:249–284,385,394–395` belegt
  Byteoffsets für Plane (`0x00`), Größen (`0x10/0x14`), Offset
  (`0x18`), Adresse (`0x30` plus High-Feld) und Update (`0x54`).
  `sdp_gfx.c:464–466` packt Breite und Höhe und berechnet
  `src_w / 4`. `sdp_gp.c:97–104,162–165` verwendet diese Werte.
  DMA-Busübersetzung, zulässige Ausrichtung, Formatbits und Latch-Reihenfolge
  für den Port bleiben offen.
- **OSDP.** Nike-L `sdp_osdp.c:45,79–80` verwendet vier Bytes pro
  Registerindex und programmiert Skalierkoeffizienten bei `0x200` und
  `0x240`. Die Firmware nennt IRQ `<0 0x2f 0>`. Für ein
  1080p-Testbild ist weder ein OSDP-Programmierbedarf noch ein vollständiges
  Panel-Timing belegt.
- **Mixer.** Nike-L `sdp_gfx_reg_addr.h:490,493` benennt IRQ Clear
  `0x08` und Mask `0x0c`. `sdp_mixer.c:108–146,190–198` enthält
  Maskierung und Quittierung. Geteilte Zuständigkeit mit Cursor und Bootlogo,
  IRQ-Bitbelegung und sichere Quittierung bleiben offen.

Der Build-088-Zugriffsvertrag für diese Registerfenster ist leer. Die
DT-Fixture bleibt deaktiviert und enthält keine simulierten Provider. Das
Binding beschreibt die sechs Clock-Namen für eine spätere verdrahtete Fixture.
Es wurden kein Modul geladen, kein Fernseher angesprochen und keine Firmware
geflasht.

## Prüfungen

[Build-088-Workflow](../../.github/workflows/build088-display.yml)
startet bei Pushes auf `feature/build088-*` und verwendet ausschließlich
`[self-hosted, debian]`. Er enthält alle Kommandos für Patch-Anwendung,
ARM32-Compile mit `W=1 KCFLAGS=-Werror`, vollständiges Kbuild-Modpost
mit echtem `Module.symvers`, Checkpatch und DT-Prüfungen. Das Schema
wird an der deaktivierten Fixture geprüft. Beide Board-DTBs werden kompiliert.

Lokal verifiziert wurden der Kernel-Tarball-Hash, die Samsung-Archiv-Hashes,
beide Firmware-DTs und Checkpatch des geänderten Treibers (0 Fehler,
0 Warnungen, 0 Checks). Der ARM32- und Modpost-Nachweis für Build 088
wird am Workflow-Lauf gemessen.
