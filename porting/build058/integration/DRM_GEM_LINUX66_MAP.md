# Build 058 – Samsung DRM/GEM: Migrationskarte Linux 4.1.10 → 6.6.162

Stand: 10.11.2026. **Statische Analyse, kein Compile des Samsung-DRM-Cores.**

## Quellenlage

| Quelle | Verfügbar beim Erstellen | Verwendung |
|---|---|---|
| Linux 6.6.162 (`gregkh/linux`, Tag `v6.6.162`, Commit `5139929c698c273e07cb0635732f6a918a7b8e78`) | ja | `include/drm/drm_drv.h`, `drm_gem.h`, `drm_gem_dma_helper.h`, `drm_prime.h`, `drm_vblank.h` direkt gelesen |
| Kernel-Konfiguration `multi_v7_defconfig` + `DRM`/`DRM_PANFROST=m`, `olddefconfig` | ja (lokal erzeugt) | `CONFIG_DRM_LEGACY` ist **nicht** gesetzt |
| `tztv-media-nike.tgz` (Samsung) | **nein** | nur indirekt über den Kontext der Patches Build 053/054 |

Alle Aussagen über Samsung-Code stammen deshalb nur aus den Kontextzeilen von
`porting/build053/patches/0001-original-sdp-drm-gem-linux66-partial.patch`
und `porting/build054/patches/0003-after-build053-drm-headers-ioctl-flags.patch`.
Sie müssen am Originalarchiv auf dem Debian-Server bestätigt werden
(Befehle in `RUN003_PREPARATION.md`).

## 1. Callbacks, die Build 053 entfernt, aber nicht neu verdrahtet

Der Patch löscht diese Einträge aus `struct drm_driver`. Das ist für Linux 6.6
nötig, weil es die Felder dort nicht mehr gibt. Ihr Verhalten wird aber
**nirgends neu angebunden**. Der Kommentar im Patch („GEM VM functions must move to
per-object operations“) beschreibt nur die Aufgabe, erledigt sie aber nicht.

| Samsung 4.1.10 (`drm_driver`) | Samsung-Funktion | Ort in Linux 6.6.162 | Status |
|---|---|---|---|
| `.gem_free_object` | `sdp_drm_gem_free_object` | `drm_gem_object_funcs.free` | **verloren** |
| `.gem_vm_ops` (`.fault = sdp_drm_gem_vm_fault`) | eigener Fault-Handler | `drm_gem_object_funcs.vm_ops` bzw. `.mmap` | **verloren** |
| `.gem_open_object` | `sdp_drm_gem_open_object` | `drm_gem_object_funcs.open` | **verloren** |
| `.gem_prime_export` | `sdp_dmabuf_prime_export` | `drm_gem_object_funcs.export` | **verloren** |
| `.gem_prime_get_sg_table` | `sdp_drm_gem_prime_get_sg_table` | `drm_gem_object_funcs.get_sg_table` | **verloren** |
| `.gem_prime_vmap` / `.gem_prime_vunmap` | `sdp_drm_gem_prime_vmap/vunmap` | `drm_gem_object_funcs.vmap/vunmap` mit `struct iosys_map *` statt `void *` | **verloren**, Signatur geändert |
| `.gem_prime_mmap` | `sdp_drm_gem_prime_mmap` | `drm_gem_object_funcs.mmap` | **verloren** |

Belegt durch `sed -n '/struct drm_gem_object_funcs {/,/^};/p' include/drm/drm_gem.h`
in 6.6.162. Die Liste dort lautet: `free open close print_info export pin unpin
get_sg_table vmap vunmap mmap evict status`, dazu `vm_ops` als Zeiger.

**Folge:** Kompiliert der gepatchte Treiber später, wären Samsungs eigene
Speicherfreigabe, der Fault-basierte Mmap-Pfad und der eigene DMA-BUF-Export
stillgelegt. Die Objekte würden dann mit generischen Standardpfaden oder gar
nicht freigegeben. Ein grüner Compile wäre in diesem Zustand **keine** Portierung.

**Nächster echter Schritt:** In `sdp_drm_gem.c` eine
`static const struct drm_gem_object_funcs sdp_drm_gem_object_funcs` anlegen, die
genau diese Samsung-Funktionen enthält, und `obj->funcs` an **jeder** Stelle
setzen, an der Samsung ein GEM-Objekt erzeugt (normale, HW-Mem- und
Import-Pfade). Das erfordert den vollständigen Originalcode. Hier wird es nicht
blind ergänzt.

## 2. Felder, die in 6.6.162 nur unter `CONFIG_DRM_LEGACY` existieren

`include/drm/drm_drv.h`, ab Zeile 446: `#ifdef CONFIG_DRM_LEGACY` („Everything
below here is for legacy driver, never use!“). `CONFIG_DRM_LEGACY` ist in der
geprüften ARM32-Konfiguration **nicht gesetzt**. Build 053 behält aber:

| Feld im Samsung-`drm_driver` nach Build 053 | Erwartung beim Compile | 6.6-Zielort |
|---|---|---|
| `.preclose = sdp_drm_preclose` | Fehler: kein solches Member | `drm_driver.postclose` bzw. Aufräumen in `file_operations.release`; Semantik prüfen |
| `.get_vblank_counter = drm_vblank_count` | Fehler: kein Member; `drm_vblank_count()` ist in 6.6 nicht mehr deklariert oder exportiert | `drm_crtc_funcs.get_vblank_counter` (pro CRTC) |
| `.enable_vblank = sdp_drm_crtc_enable_vblank` | Fehler: kein Member | `drm_crtc_funcs.enable_vblank(struct drm_crtc *)` |
| `.disable_vblank = sdp_drm_crtc_disable_vblank` | Fehler: kein Member | `drm_crtc_funcs.disable_vblank(struct drm_crtc *)` |
| `DRIVER_HAVE_IRQ` in `driver_features` | kompiliert (`BIT(30)` existiert), aber nur Legacy-Bedeutung | entfernen; IRQ selbst per `devm_request_irq` |

Das ist eine **Vorhersage aus Headerlesung**. Erst der Compiler-Log aus run003
(`logs/samsung_drm_drv_gem_arm32_sdp_drm_drv_compile.log`) bestätigt oder
widerlegt sie. Wahrscheinlich bricht der Compile früher ab, an
`#include <drm/drm_tztv.h>`. Dann sind diese Fehler im Log noch gar nicht
sichtbar.

## 3. GEM/CMA → GEM/DMA

| Linux 4.1 (CMA) | Linux 6.6.162 (DMA) | Hinweis |
|---|---|---|
| `struct drm_gem_cma_object { base, paddr, sgt, vaddr }` | `struct drm_gem_dma_object { base, dma_addr, sgt, vaddr, map_noncoherent }` | upstream ohne Samsung-Zusatzfelder |
| `drm_gem_cma_dumb_create` | `drm_gem_dma_dumb_create` | Build 053 lässt den alten Namen stehen |
| `drm_gem_cma_dumb_map_offset` | entfällt; Standard `drm_gem_dumb_map_offset` | — |
| `drm_gem_cma_prime_import_sg_table` | `drm_gem_dma_prime_import_sg_table` | — |
| `drm_gem_cma_prime_vmap` (`void *`) | `drm_gem_dma_vmap(obj, struct iosys_map *)` | Signaturwechsel |
| `drm_fbdev_cma_*` | `drm_fbdev_dma_setup()` | Build 050 hat `lastclose` bereits entfernt |

**Wichtiger Befund:** `sdp_drm_gem.c` bindet `#include "drm_gem_cma_helper.h"`
mit **Anführungszeichen** ein und greift auf `cma_obj->num_slots` zu
(`item->slot_size = cma_obj->num_slots * obj->size`). Upstream gibt es dieses
Feld weder in 4.1 noch in 6.6. Samsung verwendet also eine **eigene, erweiterte
Kopie** des CMA-Helpers. Ein Ersetzen durch `drm_gem_dma_helper.h` per Suchen und
Ersetzen würde die Samsung-Slot-Verwaltung zerstören. Mögliche saubere Varianten,
erst nach Lesen der Samsung-Kopie:

1. Samsung-Objekt als Hülle: `struct sdp_drm_gem_object { struct drm_gem_dma_object dma; unsigned int num_slots; ... }`,
   Zugriff per `container_of`. Die Upstream-Helfer bleiben nutzbar.
2. Samsung-Helper (`drm_gem_cma_helper.c/.h` im `sdp_drm_nike`-Verzeichnis,
   falls vorhanden) als eigene Datei auf 6.6 portieren.

Welche Variante passt, hängt davon ab, ob Samsungs Kopie die Speicherallokation
selbst ändert (Slots, physische Zonen, Sicherheitsbereiche). Ohne den Quelltext
ist das **offen**.

## 4. `drm/drm_tztv.h` (unverändert Blocker)

Kein Fortschritt ohne echte Quelle. Es werden **keine** Werte erfunden. Zur
Eingrenzung ist auf dem Server zuerst zu klären, welche `DRM_SDP_*`- und
`DRM_DPINST_*`-Bezeichner **irgendwo im Archiv definiert** und welche nur
verwendet werden (Befehle in `RUN003_PREPARATION.md`). Nur die verbleibenden,
nirgends definierten Namen können aus dem fehlenden Header stammen.

## 5. DMA-BUF/Fence

`integration/drm/sdp_drm_fence.c` (Samsung `struct fence` → `struct dma_fence`)
kompiliert für ARM32 mit GCC (run002, gemeldet) und mit clang 18 gegen
6.6.162 (lokal, siehe `BUILD_REPORT.md`). Es fehlt weiterhin jeder echte
Signalisierungspfad (IRQ, Display-Flip). Wie sich die alte
`reservation_object`-API (4.1) auf `dma_resv` (6.6) abbildet, lässt sich erst am
Originalcode von `sdp_drm_gem.c` prüfen.
