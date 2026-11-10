# Build 058 – Linux-6.6.162-API-Review

Stand: 10.11.2026. Grundlage: Branch `claude/build058-arm32-compile-gate`
(enthält alle Build-058-Feature-Branches und Build 057).

## Referenz und Werkzeuge

- Kernel: `gregkh/linux`, Tag `v6.6.162`, Commit
  `5139929c698c273e07cb0635732f6a918a7b8e78` (identisch mit CI-Pin).
- `multi_v7_defconfig` + `MODULES`, `DRM`, `DRM_PANFROST=m`, `modules_prepare`.
- GCC `arm-linux-gnueabihf-` und LLVM/clang (`LLVM=1`), jeweils `ARCH=arm`.
- `dtc` mit Standardprüfungen.

## Ergebnis

| Prüfung | Ergebnis |
| --- | --- |
| `run-arm32-compile-only.sh --no-vendor-drm`, GCC | alle Pflichtobjekte PASS, `REPO_OBJECTS_COMPILED` |
| dasselbe mit LLVM | alle Pflichtobjekte PASS |
| alle 8 Repo-Kernelquellen (Build 052, 054, 058) mit `W=1`, GCC + LLVM | keine Fehler/Warnungen (nach den Fixes unten) |
| externe Symbole der Objekte gegen `EXPORT_SYMBOL*` in 6.6.162 | alle exportiert (außer modpost-eigenem `__this_module`) |
| DTS-Fixtures Build 056/058 | übersetzbar; Build 056: bekannte, dokumentierte Warnung `Missing interrupt-parent` |
| Host-Tests `python3 -m unittest discover -s tests` | 307 Tests OK (13 übersprungen) |

`modpost`/`.ko`-Link wurde nicht ausgeführt (braucht `BUILD058_FULL_KERNEL=1`
bzw. `Module.symvers`); die Symbolprüfung oben ersetzt das nur näherungsweise.

## Behobene 6.6-API-Fehlanpassungen

1. **`build052/contract`: `.gem_create_object` falsch verwendet.** Der Hook
   ist in 6.6 nur der Allokator der GEM-shmem-/DMA-Helper; diese wenden
   `container_of()` auf ihren eigenen, größeren Objekttyp an und rufen danach
   selbst `drm_gem_object_init()` auf. Der Contract-Konstruktor initialisierte
   selbst und allozierte nur `struct drm_gem_object` → Doppel-Init und
   Speicherüberlauf, sobald ein Helper ihn nutzt. Der Konstruktor bleibt als
   treibereigene Funktion erhalten, ist aber nicht mehr als Hook eingehängt.
2. **`cpu/kernel/sdp_nikel_cpufreq.c`: `.remove` → `.remove_new`.** In 6.6
   ist das `int`-zurückgebende `platform_driver.remove` veraltet
   (`include/linux/platform_device.h`: „drivers should implement
   .remove_new()“).

## Geprüft, ohne Änderungsbedarf

- `cpufreq_driver.verify(struct cpufreq_policy_data *)`, `CPUFREQ_NAME_LEN`.
- Thermal: `get_temp(struct thermal_zone_device *, int *)`,
  `thermal_zone_device_priv()`, `devm_thermal_of_zone_register()`.
- CCF/Reset: `devm_clk_hw_register()`, `devm_of_clk_add_hw_provider()`,
  `devm_reset_controller_register()`, `readl_poll_timeout_atomic()` im
  atomaren `clk_ops.disable`.
- DMA-Fence: `dma_fence_init()`, `dma_fence_ops`, `dma_fence_context_alloc()`.
- Build 050 Panel-Patch: `drm_panel_init(…, connector_type)`, `void
  drm_panel_add()`, `get_modes(panel, connector)`, `drm_mode_vrefresh()`.

## Offen (nicht ohne Samsung-Quellen lösbar)

Die Vendor-DRM-Patches Build 053/054 sind bewusst partiell. Gegen 6.6.162
bleiben u. a. `.preclose`, `.get_vblank_counter = drm_vblank_count`,
`.enable_vblank`/`.disable_vblank` (nur unter `CONFIG_DRM_LEGACY`),
`drm_gem_cma_*` (6.6: `drm_gem_dma_*`) und `<linux/reservation.h>`
(6.6: `<linux/dma-resv.h>`) stehen. Das ist in
`integration/DRM_GEM_LINUX66_MAP.md` bereits erfasst. Eine Korrektur der
Patches braucht das gepinnte `tztv-media-nike.tgz`, damit die Hunks
überhaupt geprüft werden können; der Blocker `drm/drm_tztv.h` bleibt davon
unberührt.

Es gibt im Repository keine `Android.bp`. Die `.mk`-Dateien unter
`porting/device/samsung/nikel/` sind syntaktisch in Ordnung, und
`BoardConfig.mk` blockiert jeden ROM-Build absichtlich mit `$(error …)`.
