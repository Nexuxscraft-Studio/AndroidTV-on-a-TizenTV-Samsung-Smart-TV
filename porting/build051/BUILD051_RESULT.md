# Build 051 – Samsung SDP Panel: ARM64/Linux 6.6 Referenzartefakt

Erfasst am **10. November 2026** anhand der vom Benutzer bereitgestellten
Ausgaben des separaten Debian-Testservers. Das Kernelmodul selbst wurde
in diesem Repository **nicht** hochgeladen und sein Inhalt wurde hier
**nicht unabhängig verifiziert**.

## Artefakt und SHA-256

- **Datei:** `panel-sdp.ko`
- **Pfad auf dem Testserver:**
  `/opt/samsung-atv-lab/build051-stage1-test01/linux-4.1.10/drivers/gpu/drm/panel/panel-sdp.ko`
- **SHA-256 (Benutzerausgabe):**
  `2d6545958a20852da29f7657efe57a7e576c6b8e574919e706ec18870d1581ae`
- **Kernel-Vermagic:** `6.6.162 SMP preempt mod_unload aarch64`
- **Modulname:** `panel_sdp`
- **Modulbeschreibung:** `Samsung SDP SoCs DRM panel driver`
- **Modullizenz:** `GPL v2`
- **Gemeldete Modulabhängigkeiten:** `depends=` (leer)
- **Device-Tree-Alias:** `nover,compile-only-sdp-panel` (bewusst kein echtes Samsung-Binding)

## Beobachtete Belege

1. `file panel-sdp.o`: ELF64, AArch64, relocatable.
2. `aarch64-linux-gnu-readelf -h panel-sdp.o`: `Class: ELF64`, `Machine: AArch64`.
3. Kbuild meldete `LD [M] .../panel-sdp.ko` nach dem erfolgreichen
   Build der ursprünglichen Samsung-Panelquelle mit Linux-6.6-Anpassungen.
4. `aarch64-linux-gnu-readelf -p .modinfo panel-sdp.ko` bestätigte
   Modulmetadaten, `vermagic` und den sicheren Compile-only-DT-Alias.
5. `sha256sum panel-sdp.ko` wurde vom Benutzer ausgeführt; der Digest
   steht oben.

## Einordnung und Sicherheitsgrenzen

- **Bestätigt:** AArch64-Übersetzung, Modul-Link und vorhandenes `.ko`.
- **Nicht bestätigt:** Laden des Moduls, symbolische Laufzeitauflösung,
  TCON/Backlight, tatsächliche Panel-Hardware, Bildausgabe oder Android.
- `depends=` leer bedeutet nicht, dass alle zur Ladezeit erforderlichen
  Kernel-Symbole oder Versions-/Konfigurationsvoraussetzungen erfüllt sind.
- Der DT-Alias ist absichtlich von Samsungs realem Compatible-String
  verschieden; das Modul ist **compile-only**, kein flashbarer Treiber.
- Der ARM64-Test beweist nicht, dass das konkrete Q60T-Board einen
  AArch64-Kernel starten kann. Der originale Samsung-Referenz-Kernel
  wurde separat als ARM32 identifiziert.

**Build 051 bleibt eingefroren.** Build 052 wird unabhängig vom
`build051-stage1-test01`-Quellbaum weiterentwickelt.

## Später erneut prüfen

```bash
sha256sum /opt/samsung-atv-lab/build051-stage1-test01/linux-4.1.10/drivers/gpu/drm/panel/panel-sdp.ko
```

Der ausgegebene Hash muss exakt mit dem oben dokumentierten Wert
übereinstimmen. Keine Installations-, Lade- oder Flashaktion ist
Bestandteil dieses Verifikationsschritts.
