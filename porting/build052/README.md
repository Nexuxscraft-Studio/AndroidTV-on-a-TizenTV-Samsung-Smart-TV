# Build 052 – Samsung DRM / GEM auf Linux 6.6 vorbereiten

**Status: COMPILER_CONTRACT_ONLY. Kein Hardware-Port, nicht flashbar.**

Build 051 hat nach dem fehlenden `drm_device.h` laut externem
Build-Protokoll die AArch64-Objektdatei `panel-sdp.o` erzeugt. Das
nachfolgende `modpost` scheiterte wegen fehlender `Module.symvers` und
unaufgelöster DRM-/Kernel-Symbole. **Damit ist nur die C-Übersetzung des
Panels belegt**, nicht das fertige oder lauffähige Modul.

Build 051 bleibt unverändert. Build 052 enthält in `contract/` einen
separaten, bewusst nicht ladbaren Linux-6.6-Kompilierungstest für:

- `struct drm_driver` mit `DRIVER_GEM`, `.gem_create_object` und GEM-FOPS;
- `struct drm_gem_object_funcs.free` statt `drm_driver.gem_free_object`;
- `drm_gem_object_init()` / `drm_gem_object_release()`;
- `drm_dev_alloc()` → `drm_dev_register()` → `drm_dev_unregister()` →
  `drm_dev_put()` (nur compilergeprüfte, **nie ausgeführte** Skizze).

Der Code bindet an keine Device-Tree-`compatible`-Zeichenkette, führt
keine Samsung-Hardwarebefehle aus und liefert beim Laden `-ENODEV`.
Das ist **nicht** der Samsung-Treiber und stellt keine GPU- oder
Displayfunktion bereit. Insbesondere wird weder `sdp_drm_drv.c` noch
`sdp_drm_gem.c` in diesem Test kompiliert.

## Auf dem Linux-6.6-Testserver kompilieren

Nur den neuen Ordner `porting/build052/contract/` in ein **neues**
Arbeitsverzeichnis übertragen. Im neuen Contract-Ordner ausführen:

```bash
make -C /opt/samsung-atv-lab/linux-6.6.162 \
  O=/opt/samsung-atv-lab/build051-arm64-obj \
  ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  M="$PWD" nover_sdp_linux66_contract.o

file nover_sdp_linux66_contract.o
aarch64-linux-gnu-readelf -h nover_sdp_linux66_contract.o \
  | grep -E 'Class:|Machine:'
```

Das einzelne `.o`-Ziel vermeidet den `modpost`-Schritt, für den uns
derzeit die vollständigen Kernel-Symbole fehlen. **Nicht** `insmod`,
`modprobe` oder Hardwaretests auf dem Fernseher ausführen.

## Was der Samsung-Quellcode für den echten Port noch benötigt

| Originalquelle | Hindernis | Nächster Arbeitsschritt |
| --- | --- | --- |
| `sdp_drm_drv.c` | `drm_platform_init()` / `drm_put_dev()` | Probe-/Remove-Lebenszyklus neu aufbauen; Fehlerpfade belegen |
| `sdp_drm_drv.c` | `.load` / `.unload` in 6.6 noch vorhanden, aber veraltet | Initialisierung vor Registrierung, Cleanup nach Unregister |
| `sdp_drm_drv.c` | entfernte Treiberfelder wie `.gem_free_object`, `.gem_vm_ops`, `.gem_prime_vmap` | GEM-Callbacks objektbezogen migrieren, keine bloße Umbenennung |
| `sdp_drm_gem.c` | Zugriffe auf GEM-Referenzzähler und `reservation_object` | Referenz-/Reservierungssemantik gegen Linux 6.6 prüfen |
| Samsung CMA-Fork | `drm_gem_cma_*` und zusätzliche `slot_index`-/`paddr`-Felder | Samsung-Speicherlayout und moderne `drm_gem_dma_*`-API vergleichen |
| proprietäre Samsung-Header | `drm_tztv.h`, SDP-/GPU-/DP-Interfaces | Abhängigkeiten inventarisieren und für ARM64 auflösen |
| Display-Ausgänge | echte Connector-, Encoder-, Panel- und TCON-Daten fehlen | Kein Hardware-Binding ohne verifizierte Werte |

Dieser Vertrag beweist ausschließlich, ob die gewählten Linux-6.6-API-
Signaturen und Typen im AArch64-Kernelbau übersetzbar sind. Einen späteren
kompletten Modul-Link einschließlich `Module.symvers` und eine echte
Hardwarevalidierung brauchen wir weiterhin.

Referenzen: [Linux 6.6 DRM Internals](https://www.kernel.org/doc/html/v6.6/gpu/drm-internals.html),
[Linux 6.6 DRM Memory Management](https://www.kernel.org/doc/html/v6.6/gpu/drm-mm.html).
