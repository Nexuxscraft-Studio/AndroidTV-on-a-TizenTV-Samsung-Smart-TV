# Build 050 – Erste Linux-6.6-Quellcodefixes (Stage 1)

Die Datei [`patches/0001-nike-linux66-stage1-compile-only.patch`](patches/0001-nike-linux66-stage1-compile-only.patch)
ist ein **realer, deterministisch generierter Unified-Diff** gegen zwei
unveränderte Dateien aus dem verifizierten Samsung-OSS-Archiv.

| Fix | Effekt | Absichtlich offen |
| --- | --- | --- |
| Panel-6.6-API | Entfernt das verschwundene `drmP.h`, passt `get_modes`/`drm_panel_init`/`drm_panel_add` an, entfernt `drm_panel_detach` und altes `vrefresh`-Feld | Reales Panel-Timing, Connector-Typ, Backlight-Sequenzierung, Kernelkompilierung |
| Panel-Sicherheitsgrenze | Ersetzt `samsung,sdp1202-panel` durch `nover,compile-only-sdp-panel` | **Keine** Bindung an den echten Samsung-DTB, kein Bild auf dem Gerät |
| DRM ohne Connector | Gibt `-ENXIO` zurück, wenn keine Encoder/Connectoren vorhanden sind | Vollständige Encoder-/FRC-/TCON-Registrierung und Fehlerpfade |
| Veralteter fbdev-Aufruf | Entfernt einen möglicherweise problematischen `lastclose`-Pfad mit `drm_fbdev_cma_restore_mode(priv->fbdev)` | Moderne fbdev-Emulation, DRM/GEM-Gesamtportierung |

## Sicherheitsgrenzen

- **Kein** Linux-6.6-Treiber ist erfolgreich kompiliert worden.
- Der Haupt-DRM-Treiber enthält weiterhin zahlreiche inkompatible APIs,
  darunter `drm_platform_init`, `gem_free_object`, `gem_vm_ops`.
- Der Panel-Treiber ist ausdrücklich **compile-only**: Die neue
  `compatible`-Kennung entspricht **nicht** der echten Samsung-Kennung.
- Aus den Dummy-Paneltimings (1920×1080) werden **keine** Register-
  oder Backlight-Einstellungen für den Q60T abgeleitet.
- **Nicht auf dem Fernseher flashen oder Hardwaremodule laden.**

## Patch reproduzieren

Das Skript kontrolliert erst beide Original-TGZ-SHA-256 und danach
die konkreten Quell-Dateihashes. Es verweigert mehrdeutige/verschobene
Quellstellen und Überschreiben. Erzeugt wird ausschließlich eine
neue Textpatchdatei.

```bash
python3 q60t_build050_stage1_source_fixes.py \
  --kernel-tgz /pfad/linux-4.1.10-tizen5.5.tgz \
  --media-tgz /pfad/tztv-media-nike.tgz \
  --output /pfad/zu/neuer-stage1.patch

python3 -m unittest tests/test_build050_stage1_source_fixes.py -v
```

Auf einem **separaten, schreibbaren Quelltestverzeichnis**, das nur
Kopien der beiden Originaldateien unter ihren Archivpfaden enthält,
ist der reine Patch-Kontexttest möglich:

```bash
patch --dry-run --batch -p1 \
  -i /absoluter/pfad/0001-nike-linux66-stage1-compile-only.patch
```

Den Befehl aus dem **Wurzelverzeichnis der Quellkopie** starten, damit
`-p1` die Präfixe `a/` und `b/` entfernt. Dieser Trockenlauf wurde
bereits erfolgreich gegen die verifizierten Originaldateien getestet.

## Nächster Gate: tatsächliche Kbuild-Compilation

Ein Linux-6.6-Quellbaum, passender AArch64-Compiler und die exakten
`Kconfig`-/Include-Abhängigkeiten müssen vor dem ersten echten
Kompilationstest vorbereitet werden. Erst danach können wir neu
auftauchende Compilerfehler einzeln beheben. Panel-Stromversorgung,
Registerzugriffe und Kernel-Boot bleiben ausdrücklich gesperrt.
