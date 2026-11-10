# Build 053 – erste tatsächliche Samsung-DRM/GEM-Quellcodeportierung

**Status: PARTIAL_SOURCE_MIGRATION, NOT_COMPILED, NOT_LOADABLE, NOT_FLASHABLE.**

Eingangsdaten sind das SHA-256-fixierte Samsung-Originalarchiv
`tztv-media-nike.tgz` aus `20_DTV_NikeL.zip`.
Der neue Generator `q60t_build053_samsung_drm_stage1.py` verändert
die Originalarchive nie, sondern erzeugt zwei alternative Unified Diffs.

## Welcher Patch?

- **`patches/0001-original-sdp-drm-gem-linux66-partial.patch`** gilt
  für eine frische, unveränderte Extraktion von `tztv-media-nike.tgz`.
  Er enthält die bereits geprüften Build-050-Sicherheitskorrekturen
  für `sdp_drm_drv.c` zusätzlich.
- **`patches/0002-after-build050-stage1-sdp-drm-gem-linux66-partial.patch`**
  gilt ausschließlich, wenn der DRM-Teil des Build-050-Stage-1-Patches
  bereits angewendet wurde. In beiden Fällen muss `sdp_drm_gem.c` noch
  das unveränderte Samsung-Original sein.

**Genau einen** dieser beiden Patches auf eine separate
**Build-053-Arbeitskopie** anwenden. Build 051 und Build 052 bleiben
unverändert. Patches nicht kombinieren.

## Was wirklich am Samsung-Quellcode verändert wurde

| Datei | Änderung | Einschränkung |
| --- | --- | --- |
| `sdp_drm_drv.c` | `drm_platform_init()` / `drm_put_dev()` durch `drm_dev_alloc()`, `drm_dev_register()`, `drm_dev_unregister()`, `drm_dev_put()` ersetzt | Probe-/Remove-Abfolge muss nach vollständiger Initialisierung weiter geprüft werden |
| `sdp_drm_drv.c` | `.load` und `.unload` als Callbacks entfernt, interne Funktionen derzeit explizit in Probe/Remove aufgerufen | Fehlerpfade und abhängige Initialisierung noch nicht final |
| `sdp_drm_drv.c` | Unter Linux 6.6 nicht mehr vorhandene `drm_driver`-GEM-Felder entfernt und `DRIVER_PRIME`-Flag gestrichen | GEM-Callbacks sind **noch nicht** nach `drm_gem_object_funcs` überführt; kein funktionierender DRM-Treiber |
| `sdp_drm_gem.c` | `drm_gem_object_reference/unreference` → `drm_gem_object_get/put` | Call-Site-Semantik und Synchronisation später weiter prüfen |
| `sdp_drm_gem.c` | Dreiparametriger `drm_gem_object_lookup()` → `(file, handle)` | Veraltete zusätzliche `dev->struct_mutex`-Verwendung noch zu auditieren |
| `sdp_drm_gem.c` | Refcount-Debugzugriffe → `kref_read()`, GEM-Core-Teardown statt direktem `fput()` | Noch keine vollständige GEM-/DMA-Migration |

### Zwei harte Sicherheitsgrenzen

1. Der reale Compatible-String `samsung,sdp-drm` wurde im
   Testquelltext zu `nover,compile-only-sdp-drm` geändert.
2. Der Samsung-Modulinitialisierer bricht **vor** jedem Aufruf
   von `gfxp_init()`, `sdp_dp_init()` oder anderer Hardwareinitialisierung
   mit `-ENODEV` ab. Das Modul soll nicht geladen werden.

## Bewusst nicht gelöst

Dieser Patch ist eine **erste Migration wirklicher Samsung-Codezeilen**,
kein abgeschlossener Build. Bekannte Blocker sind insbesondere:

- `sdp_drm_drv.h` und `sdp_drm_gem.h` verwenden weiter `drmP.h`
  und andere alte Kernel-/Vendor-Header.
- Alte `reservation_object`-, Fence-, CMA- und DMABUF-Operationen sind
  nicht mit `dma_resv`, `dma_fence` und den DRM-DMA-Helfern abgeglichen.
- Private Samsung-Felder (`slot_index`, `paddr`) verhindern ein
  blindes Ersetzen des CMA-Objekts durch die generische Linux-6.6-Struktur.
- Die Mode-Config, CRTC/Plane-/Connector- und Debugfs-Callbacks sind
  noch nicht vollständig geprüft.
- `drm_gem_object_funcs.free` ist noch nicht in alle Samsung-GEM-
  Objektlebenszyklen eingebaut – diese Lücke blockiert jede Nutzung.
- Kein Test auf echter Hardware, kein erfolgreiches Linux-6.6-Objekt
  für `sdp_drm_drv.c` oder `sdp_drm_gem.c`, kein Module-Link.

## Patch auf einer neuen Kopie prüfen

Beispiel für ein **frisch extrahiertes** `tztv-media-nike`-Quellverzeichnis
unter `/opt/samsung-atv-lab/build053-stage1-test01`:

```bash
cd /opt/samsung-atv-lab/build053-stage1-test01
patch --dry-run --batch -p1 -i /pfad/0001-original-sdp-drm-gem-linux66-partial.patch
patch --batch -p1 -i /pfad/0001-original-sdp-drm-gem-linux66-partial.patch
```

Die `patch`-Befehle setzen voraus, dass der Ordner bereits
`tztv-media-nike/sdp_drm_nike/` enthält. Nicht auf die
Build-051-Quelle oder ein produktives Firmwareabbild anwenden.

## Erster Linux-6.6-Compilertest

Um das alte Samsung-Makefile mit ARM32-Flags und Linux-4.1-Pfaden zu
umgehen, liegt unter `test-kbuild/Kbuild` ein **diagnostisches** Kbuild,
das ausschließlich die beiden echten Samsung-C-Dateien ansteuert.
Die Datei nur in die neue `sdp_drm_nike`-Arbeitskopie übernehmen.

Der erste Test sollte **nur die `.o`-Datei** anfordern, nicht `.ko`:

```bash
cd /opt/samsung-atv-lab/build053-stage1-test01/tztv-media-nike/sdp_drm_nike
make -C /opt/samsung-atv-lab/linux-6.6.162 \
  O=/opt/samsung-atv-lab/build053-arm64-obj \
  ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  M="$PWD" sdp_drm_drv.o
```

`build053-arm64-obj` muss zuvor separat mit passender ARM64-`.config`
und `modules_prepare` vorbereitet werden (wie bei Build 052).
Für `sdp_drm_gem.o` kann derselbe Compileraufruf mit diesem anderen
Ziel wiederholt werden. **Es werden noch Compilerfehler erwartet.**
Insbesondere Proprietär-Header und alte Speicher-APIs sind noch offen.

Erster Erfolg bedeutet: reale Samsung-C-Datei im ARM64-
Linux-6.6-Kbuild wird übersetzt. Das ist weder ein vollständiger
Treiber noch eine Aussage zu Bootloader, Display oder Mali-GPU.

## Reproduzierbarkeit

```bash
python3 q60t_build053_samsung_drm_stage1.py \
  --media-tgz /pfad/tztv-media-nike.tgz --base original \
  --output /pfad/zu/einem/neuen.patch

python3 -m unittest tests.test_build053_samsung_drm_stage1 -v
```

Beide Eingangsdateien werden einzeln per SHA-256 validiert; vorhandene
Patchdateien werden nicht überschrieben. Kein Befehl schreibt auf den TV.

Referenz: [Linux 6.6 DRM Internals](https://www.kernel.org/doc/html/v6.6/gpu/drm-internals.html),
[Linux 6.6 DRM Memory Management](https://www.kernel.org/doc/html/v6.6/gpu/drm-mm.html).
