# Samsung Nike-L → Linux 6.6: konkrete Quellcode-Migrationsmatrix

**Build 050, zweite Phase.** Quelle: unveränderte, SHA-256-fixierte
`linux-4.1.10-tizen5.5.tgz` und `tztv-media-nike.tgz` aus dem Originalpaket
`20_DTV_NikeL.zip`. Zielgerät: Samsung Q60T `GQ50Q60TGUXZG`.

**Ergebnis:** Der Linux-6.6-Vergleich erkennt **27** reale Altcode-Merkmale,
davon **17 kritisch**. Eine Erkennung ist **kein** gelöster Port und
auch kein Beleg für funktionierende Hardware. Der maschinenlesbare Bericht
liegt unter `reports/hardware_build050_linux66_port_gaps.json`.

## Eindeutiger API-Abgleich

| Samsung Linux 4.1.10 | Linux 6.6 (`torvalds/linux`, Tag `v6.6`) | Maßnahme |
| --- | --- | --- |
| `drm_platform_init()` innerhalb `sdp_drm_platform_probe()` | DRM-Device in `probe()` erzeugen, Treiber initialisieren, dann `drm_dev_register()` | Device-Erzeugung, Fehlerpfade und Entfernen strukturell umarbeiten |
| `drm_driver.load` / `.unload` | In 6.6 **noch vorhanden, aber deprecated** | Logik in Probe und ausdrückliche Reverse-Order-Cleanup-Pfade verschieben |
| `drm_driver.gem_free_object` / `.gem_vm_ops` | Nicht mehr Felder von `struct drm_driver` | GEM-Objektlebenszyklus auf `struct drm_gem_object_funcs` umstellen |
| `.gem_prime_export`, `.gem_prime_get_sg_table`, `.gem_prime_vmap`, `.gem_prime_vunmap`, `.gem_prime_mmap` | Nicht mehr als diese Felder von `struct drm_driver` verfügbar | DMA-BUF/PRIME-Export und GEM-Mappings mitsamt Signaturen neu anbinden |
| `.set_busid`, `.debugfs_cleanup`, `.dumb_destroy`, `.gem_open_object` | Alte `drm_driver`-Felder fehlen | Core-/GEM-Lifecycle und Debugfs-Registrierung modernisieren |
| `drm_fbdev_cma_restore_mode()` in `lastclose` | Alte CMA-FBDEV-Hilfe nicht der aktuelle Weg | FBDEV-Helfer/Emulation mit aktuellem KMS abgleichen |
| `drm_panel_init(&panel->base)` | `drm_panel_init(panel, dev, funcs, connector_type)` | Aufruf und Verantwortlichkeiten ändern |
| `ret = drm_panel_add(...)` | `drm_panel_add()` gibt `void` zurück | Rückgabe-/Fehlerlogik überarbeiten |
| `get_modes(struct drm_panel *panel)` | `get_modes(panel, connector)` | Connector aus Argument nehmen; `panel->connector` und `panel->drm` gibt es nicht |
| `struct drm_display_mode.vrefresh` | Das Feld fehlt; `drm_mode_vrefresh()` berechnet die Rate | Feldinitializer und Zugriffe entfernen |

**Basis für den Vergleich:** öffentliche Kernel-6.6-Header
[`include/drm/drm_drv.h`](https://github.com/torvalds/linux/blob/v6.6/include/drm/drm_drv.h),
[`include/drm/drm_panel.h`](https://github.com/torvalds/linux/blob/v6.6/include/drm/drm_panel.h)
und [`include/drm/drm_modes.h`](https://github.com/torvalds/linux/blob/v6.6/include/drm/drm_modes.h).
Die exakten Git-Blob-Hashes stehen im JSON-Bericht.

## Panel-Daten sind ausdrücklich *nicht* nutzbar

Im Samsung-Quelltext `drivers/gpu/drm/panel/panel-sdp.c` steht wörtlich
`this panel-sdp.c contains dummy info`. Der Dummy hat:

- `hdisplay=1920`, `vdisplay=1080`, `vrefresh=60`
- `htotal=1920`, `vtotal=1080` – **keine Blanking-Intervalle**
- `clock=150660` kHz – rechnerisch ca. **72,656 Hz** statt der
  eingetragenen 60 Hz, wenn die Totalwerte zur Berechnung benutzt werden

Damit ist nicht einmal das interne Dummy-Timing konsistent. **Wir
übernehmen daraus weder Panel-Frequenzen noch Auflösungen, Power-Sequencing,
Spannungen oder TCON-Register in einen möglichen Hardware-Port.**
Die Displayidentität und die verlässlichen Timingdaten müssen zuerst am
konkreten Board bzw. in verifizierten Panel-Konfigurationsdaten nachgewiesen werden.

## ARM64-Sonderfall im Samsung-Makefile

Die Original-Makefiles `sdp_drm_nike/Makefile` und `sdp_gpu_nike/Makefile`
haben unter `PRO=YES` und `ARM64=YES` einen Zweig mit
`ARCH=arm64` und `aarch64-tizen-linux-gnueabi-`. Gleichzeitig enthalten
die DRM-Include-Flags Pfade zu `arch/arm/mach-sdp/include`.

Die Option beweist lediglich: Samsung sah für bestimmte Produkte einen
ARM64-Modulbuild vor. Sie beweist **nicht**, dass die Nike-L-Quellen
ohne weitere Änderungen für ARM64 gebaut wurden oder der Q60T-Bootloader
einen AArch64-Kernel starten darf. Der echte Samsung-Referenz-`uImage`
ist nach wie vor ARM32.

## Durchführung: Reihenfolge und Stop-Gates

1. **Nur Host-Umgebung:** sauberen Linux-6.6-Quellbaum mit passendem
   ARM64-Compiler als unabhängige Build-Umgebung bereitstellen. Kein
   Vendor-Modul auf dem Host laden.
2. **DRM-Kern zuerst:** `sdp_drm_drv.c` vom Legacy-Registrierungs- und
   GEM-Lebenszyklus auf 6.6 migrieren. Kernel-Syntax-/Kbuild-Test nur
   mit anwendungsfreien Testkonfigurationen und ohne echten Hardwarezugriff.
3. **Display-Anbindung:** echte Encoder-/Connector-Erzeugung,
   TCON/FRC/Clock/Reset/IRQ/DMA-Abhängigkeiten inventarisieren.
   Ohne gültige Displaydaten **keine** Aktivierung von Panel/Backlight.
4. **GPU-Kopplung:** Mali-Midgard-Hardware-ID, verfügbare Userspace-DDK-
   Schnittstelle und DMA-/IOMMU-Pfade nachweisen. Eine erfolgreiche
   DRM-Kompilierung genügt noch nicht für Android Hardware Composer.
5. **ARM64-Hardwarevertrag:** tatsächlichen Bootloader-Einsprung,
   AArch64-EL, PSCI/SMP, GIC, Timer und Nike-L-Device-Tree klären.
6. **Recovery unabhängig testen:** Erst mit nachweisbar unabhängigem
   Recovery auf einer passenden Ersatzplatine einen volatilen Start prüfen.
   **Kein Flash auf den produktiv genutzten Q60T.**

## Offline reproduzieren

```bash
python3 q60t_build050_linux66_port_gaps.py \
  --kernel-tgz /pfad/linux-4.1.10-tizen5.5.tgz \
  --media-tgz /pfad/tztv-media-nike.tgz \
  --output /pfad/zum/neuen-portabilitaetsbericht.json

python3 -m unittest tests/test_build050_linux66_port_gaps.py -v
```

Das Werkzeug liest nur vier explizit erlaubte Dateien aus zwei
SHA-256-fixierten Original-Tarballs, prüft konkrete Token/Zeilennummern
und verweigert das Überschreiben bestehender Berichte. Auch bei
vollständig positiven Erkennungen bleibt `safe_to_flash: false`.
