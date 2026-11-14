# Build 087 – Samsung Nike-L DRM hardware preparation

Ziel: Q60T GQ50Q60TGUXZG, ARM32, Linux **6.6.162**. Nur Softwarevorbereitung;
kein nachgewiesener Displaybetrieb. **Ein erfolgreicher Compiler-Test beweist
keine Funktion auf dem echten Fernseher.** Kein Boot, Firmwarezugriff oder Flash.

## Ausgangspunkt und Integration

Repository und sämtliche Remote-Branches wurden vor der Implementierung geprüft.
`main` stand bei `cb36b83` (Build 017); die aktuelle zusammenhängende
Display-/GPU-Portierung liegt auf `codex/graphics`, Stand
`02c90838d353b30d5dd1515b9946d41f18f364a6`. Der Arbeitsbranch
`feature/build087-drm-hardware-layer` basiert darauf. Der Draft-PR richtet sich
gegen `codex/graphics`, damit er ausschließlich Build 087 enthält. Dieser
Basisbranch gehört zum noch offenen PR #14; dessen Änderungen bleiben erhalten.

- Build 058/053: bisherige Fence-/GEM-Portierung bleibt unverändert.
- Build 063: dessen KMS-Skelett dient als Grundlage; historische Dateien bleiben
  unverändert, insbesondere wird sein alter DT-Platzhalter nicht weiterverwendet.
- Build 059: neuer kumulativer Patch `0026` nach `0001..0025`; `kernel/build.sh`
  nimmt ihn automatisch auf. Er **ersetzt bewusst den bisherigen experimentellen
  Display-Schreibpfad** durch das gesperrte Build-087-Skelett. Clock-, GPU-,
  Panel- und sonstige Treiber werden nicht geändert. Frühere Patches bleiben
  unverändert und in der Historie; sie dürfen nicht allein als Build 087 gelten.
- `kernel/` enthält dieselben Quellen separat für gezielte Compile-Prüfungen.
  CI vergleicht sie mit dem Ergebnis der kumulativen Patchserie.
- Neuer projektlokaler Compatible `samsung,nikel-drm-hw-preparation`: die alte
  siebenbankige `samsung,sdp-drm`-DT-Beschreibung wird nicht stillschweigend als
  neuer dreibankiger Ressourcenvertrag interpretiert. Alte deaktivierte
  Board-Nodes werden nicht aktiviert oder automatisch umgeschrieben.

## Registervertrag

Alle Offsets sind **Byteoffsets**, keine 32-Bit-Registerindizes.

| Bank | Basis | benannte DT-Ressource |
| --- | --- | --- |
| OSDP | `0x005d0000` | `osdp` |
| GP | `0x005d4000` | `gp` |
| Mixer | `0x005d8000` | `mixer` |

| Register | Bank | Offset |
| --- | --- | --- |
| Plane Enable | GP | `0x00` |
| Source Size | GP | `0x10` |
| Destination Size | GP | `0x14` |
| Source Offset | GP | `0x18` |
| Framebuffer A1 | GP | `0x30` |
| Register Update | GP | `0x54` |
| IRQ Clear | Mixer | `0x08` |
| IRQ Mask | Mixer | `0x0c` |

Die Registerpositionen sind der Aufgabenvertrag. Bestehende Samsung-Quellbelege
im Repository: Build-059-Patch `0015` referenziert `sdp_logo_nike/nikem/sdp_logo.c`
und `sdp_logo_gfx.c`; Patch `0023` außerdem
`sdp_drm_nike/gfx/nikel/sdp_mixer.c` und `sdp_hw_plane.c`. Die bekannten Offsets
entsprechen dort `REG(0/4/5/6/12)` und Mixer `REG(2/3)`.
Das originale `tztv-media-nike.tgz` wurde anschließend vom bereits im Repository
benannten Quellserver heruntergeladen und gegen den bekannten SHA-256
`40c2a25eba331b8b04d8d81baf76061493f15f228a74893c7f825f7a1da724b6`
geprüft. Im **Nike-L**-Verzeichnis bestätigt `sdp_gfx_reg_addr.h` die GP-Offsets
in Zeilen 249, 260, 263, 266, 273, 283–284 und die Mixer-Offsets in 490/493.
Auch Update-Masken (`0x03`/`0x10`, Zeilen 394–395) und ein A1-High-Register
sind dort beschrieben; sie werden bewusst nicht als Schreibzugriffe übernommen.
`sdp_gfx.c:464–466` bestätigt Größenpacking und `h_offset = src_w / 4`,
`sdp_gp.c:97–104` dessen Nutzung. `sdp_mixer.c:190–198` liest/schreibt das
Clear-Register; die sichere IRQ-Bitbehandlung bleibt vor Hardwarebetrieb zu prüfen.
Dateihashes und Quellbelege stehen in
[results/vendor-source-evidence.json](results/vendor-source-evidence.json).
Der originale **Kernel**-4.1.10-Baum wurde nicht zusätzlich heruntergeladen;
Quellbefunde ersetzen keine Hardwarevalidierung. Die Update-/Latch-Sequenz
bleibt unimplementiert.

Je Bank werden die bisherigen `0x4000`-Fenster verwendet. Der Mapper prüft alle
Namen, übersetzten Ressourcenbasen und Größen vor der ersten Reservierung;
anschließend verwendet er `devm_platform_ioremap_resource_byname()`. Die
Ressourcen sind getrennt und überlappen sich nicht. Die Fixture beschreibt einen
identisch abgebildeten SoC-Adressraum, keinen bootfähigen Board-DT.

## Sicherheitszustand und vorbereitete APIs

`sdp_hw_access_allowed()` liefert fest `false`, ohne DT- oder Modulparameter.
Probe liefert `-EOPNOTSUPP` **vor** DMA-Setup, MMIO-Mapping, DRM-Registrierung und
IRQ-Anmeldung. Zusätzlich erzwingen DT-Fixture und Binding `status = "disabled"`.
Auch ein versehentlich auf `okay` gesetzter Node überwindet die Codesperre nicht.

Der neue Treibercode enthält keine MMIO-Lese-/Schreiboperationen, keine
IRQ-Anforderung und keinen Aufruf, der ein VBlank vortäuscht. Die Enable/Update/
Disable-Callbacks programmieren nichts. `enable_vblank` liefert `-EOPNOTSUPP`,
`disable_vblank` tut nichts. Ein späterer IRQ-Handler muss erst nach CRTC- und
`drm_vblank_init()`-Initialisierung registriert werden, die eigene IRQ-Quelle
prüfen, korrekt quittieren und ausschließlich bestätigte VBlanks melden.

Die Simple-Display-Pipe ruft in `.check` die reine Framebuffer-Vorbereitung auf:
linear, eine Plane, XRGB8888/ARGB8888, dicht gepackte 32-Bit-Pixel, ohne Crop,
Rotation, Skalierung oder Interlace. Auflösung und Zielgröße müssen übereinstimmen.
Diese Einschränkungen sind ein konservativer Softwarevertrag, keine bestätigten
Hardwarefähigkeiten. Das 1920×1080-Connector-Skelett ist kein verifiziertes
Panel-Timing.

DMA wird als `dma_addr_t` gehalten; Berechnungen erfolgen mit geprüftem `u64`.
GEM-Objektgröße, FB-Offset, gesamter Scanoutbereich und natürliche Pixelausrichtung
werden geprüft. Erst nach Prüfung auf `U32_MAX` erfolgt die Umwandlung in
`dma_addr_t`. Keine CPU-physische Adresse, kein `virt_to_phys`, kein Abschneiden
hoher Bits. Der vorbereitete Probe-Pfad setzt eine 32-Bit-DMA-Maske.
Ergebnis ist nur `struct sdp_scanout`, **kein Register-Schreibplan**. Formatbits,
Stride-Encoding, DMA-BUF-Synchronisation und Cachepflege werden nicht geraten.

## Reproduzieren

Benötigt: ARM32-GCC/binutils, make, flex, bison, m4, bc, OpenSSL-/ELF-Header.
Auf einen frischen Linux-6.6.162-Baum alle Build-059-Patches numerisch anwenden.
Nicht auf einen bereits gepatchten Baum erneut anwenden.

```sh
for p in porting/build059/kernel/patches/*.patch; do
    patch -d "$KSRC" -p1 --batch --forward < "$p"
done
make -C "$KSRC" O="$KOUT" ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- multi_v7_defconfig
"$KSRC/scripts/config" --file "$KOUT/.config" -e COMPILE_TEST -e DRM -e DRM_SDP -e DRM_KMS_HELPER -e DRM_GEM_DMA_HELPER
make -C "$KSRC" O="$KOUT" ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- olddefconfig prepare modules_prepare
make -C "$KSRC" O="$KOUT" ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- W=1 KCFLAGS=-Werror drivers/gpu/drm/sdp/
porting/build087/compile-arm32.sh "$KSRC" "$KOUT"
```

Bei versioniertem Compiler kann zusätzlich `CC=arm-linux-gnueabihf-gcc-14`
übergeben werden. Die externe Prüfung erzeugt ein zusammengesetztes
`sdp_display.o`, **kein ladefertiges `.ko` und kein vollständiges Kernelimage**.
Der Workflow `build087-drm-hardware.yml` wiederholt Patchanwendung, Quellenabgleich,
beide Compile-Pfade und DT-/Schema-Prüfung. Auf Self-hosted verwendet die CI
vorhandenes LLVM bzw. die LineageOS-Prebuilts wie Build 070; das Compile-Skript
unterstützt dazu `TOOLCHAIN=llvm`. Die unten dokumentierte lokale Prüfung
verwendete GCC.

## Ergebnis am 14.11.2026

- Kernel: offizielles `linux-6.6.162.tar.xz`, SHA-256
  `4aa89f3652fc131e5d39990f3bcd4b9e131028af3f315dbe83f3a8557dc06f06`.
- GCC: Debian `arm-linux-gnueabihf-gcc-14` 14.2.0-19; binutils 2.44.
- Vollständige Build-059-Serie einschließlich `0026`: ohne Patchfehler angewendet.
- In-tree: beide C-Dateien mit `W=1 KCFLAGS=-Werror`, Archiv erfolgreich.
- Extern: beide C-Dateien mit denselben Flags, `sdp_display.o` erfolgreich gelinkt.
- Objekte: ELF 32-bit LSB relocatable, ARM, EABI5.
- DT: DTC erfolgreich; `dt-doc-validate` am installierten Binding-Pfad und
  `dt-validate` auf Fixture-DTB ohne Meldung erfolgreich.
- Checkpatch (`--strict`) für beide C-Dateien und Header: 0 Fehler/Warnungen/Checks.
- Bestehende Tests: Build 059 (17) und Build 063 (5) erfolgreich. Veraltete
  Patchserienprüfung (erwartete 22 trotz bereits 24 Patches) auf die vollständige
  nummerierte Serie bis 0026 aktualisiert.
- Shellsyntax und Quellenabgleich gegen angewendeten Patch erfolgreich.
- Compilerabhängigkeiten zunächst fehlend (`m4`, `bc`); lokal extrahierte Pakete
  verwendet. Versionierten GCC-Aufruf im Compile-Skript berücksichtigt.
  Danach keine Treiber-Compilerfehler. Keine Systeminstallation erforderlich.
- Vorerst kein vollständiger Kernel-Link/Modpost, kein Boot, keine IRQ-/VBlank-,
  DMA-BUF-/Panfrost- oder Panel-Laufzeitprüfung. CI-Workflow lokal vorbereitet;
  die ersten GitHub-hosted Jobs wurden vor Ausführung wegen einer
  Zahlungs-/Ausgabenlimit-Sperre abgewiesen. Auf Nutzerwunsch laufen Build 087
  und die für diesen PR betroffenen Build-059-/Build-067-/Offline-Workflows
  jetzt mit `[self-hosted, Linux, X64]`, wie die vorhandenen Builds 068–070.
  Runner-Inventarabfrage war mit der Integration nicht erlaubt (HTTP 403);
  der Runner übernahm Build 087 und bestand die Portierungstests. Die zunächst
  übernommene sudo-Paketinstallation scheiterte mangels Passwortfreigabe und wurde
  durch Nutzung der vorhandenen LLVM-/LineageOS-Buildwerkzeuge ersetzt. Es werden
  keine Systempakete installiert; dtschema wird in einer lokalen venv eingerichtet.
  Fehlende native Python-Header für pylibfdt werden bei Bedarf per `apt-get download`
  und `dpkg-deb -x` ausschließlich ins Job-Tempverzeichnis extrahiert.
  Ein erfolgreicher Self-hosted-Compile-Lauf wird damit noch nicht behauptet.

Compilerprotokolle: [in-tree](results/arm32-in-tree.txt),
[extern](results/arm32-external.txt).

## Offene Hardwarefragen vor jeder Freigabe

1. Originalquellbefunde mit der konkreten Nike-L-Hardware abgleichen; `0x54`-Update-Bits,
   Reihenfolge, Barrieren und Latch-Zeitpunkt; Source-Offset ist nicht automatisch
   eine Pixel-Crop-Adresse (alter Logo-Pfad verwendet `width >> 2`).
2. Enable-/Format-/Blend-Bits, Byte-/Kanalreihenfolge, Größen-Encoding,
   Stride-Einheit, maximale Abmessungen und reale DMA-Ausrichtung bestätigen.
3. Busadresse versus CPU-/DMA-Adresse, mögliche Adressübersetzung/IOMMU,
   High-Address-Register, CMA und zusammenhängende DMA-BUF-Imports bestätigen.
4. Mixer-IRQ-Quelle, Leitung, Trigger/Polarität, Statusbits, W1C-/Clear-Semantik,
   Maskenpolarität und Verhalten bei geteilten IRQs verifizieren. Alte IRQ-Werte
   werden nicht ungeprüft übernommen.
5. Clock-/Reset-/Power-Sequenz, MMIO-Ownership mit SDP1804 und QE/GA/POST/TMG
   klären; frühere vermutete Überschneidungen nicht durch doppelte Mappings lösen.
6. Native Panel-Timings, TCON/FRC, Panel-/Backlight-Initialisierung und sichere
   Übergabe vom Firmware-Bootlogo belegen; 1080p→UHD-Skalierung ist nicht portiert.
7. Atomic-Latch, Flip-Event-Zeitpunkt, VBlank an/aus, Suspend/Resume und Fehlerpfade
   erst mit bestätigtem IRQ-/Registervertrag implementieren und testen.
8. Echte Q60T-Funktion bleibt unbewiesen. Jede spätere Hardwarefreigabe benötigt
   einen eigenen überprüfbaren Code-/DT-Schritt; Build 087 bietet keinen Schalter.
