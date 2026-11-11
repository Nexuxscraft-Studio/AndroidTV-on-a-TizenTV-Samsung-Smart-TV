# Display-Portierung – `sdp-drm` nach Linux 6.6 (ARM32)

**Read-only Portierungsplan. Kein Gerätezugriff, kein Flash.** Kritischer Pfad:
Ohne KMS kein Panfrost-Bild (siehe `GPU_INTEGRATION.md`).

## Ausgangslage

- DT: `samsung,sdp-drm` + Panel `samsung,sdp1202-panel`; Timing-Blöcke
  `samsung,tztv-tcon*`, `samsung,sdp-frc-*`; Quelle Nike-L (`sdp_drm_nike`).
- Build 058 hat `sdp_drm_util` (User-Copy/IO-Helfer) und `sdp_drm_fence`
  (`struct fence` → `struct dma_fence`) nach 6.6 migriert (compile-only).
- Build 063 ergänzt ein **minimales DRM/KMS-Skelett** (`sdp_drm.c`): DRM-Device,
  ein Fixed-Mode-Connector, eine `drm_simple_display_pipe`, fbdev-Emulation.
  **Kein** reales Modeset/Plane/VSync – alles TODO.

## 4.1 → 6.6 API-Migration (Kernpunkte)

| 4.1.10 (Vendor) | 6.6 (Ziel) |
| --- | --- |
| `struct fence` | `struct dma_fence` (Build 058 erledigt) |
| eigene fbdev-Pfade | `drm_fbdev_dma_setup()` |
| legacy `drm_*` CRTC | atomic KMS (`drm_atomic_helper_*`) |
| `drm_gem_cma_*` | `drm_gem_dma_*` (Umbenennung) |
| eigene IOCTLs | möglichst Standard-KMS; vendor-IOCTLs separat prüfen |
| ad-hoc Plane | `drm_simple_display_pipe` oder volle CRTC/plane/encoder |

## Bring-up-Schritte (auf dem echten Buildhost)

1. **Compile-Gate** (Build 063 CI): `sdp_drm.o` baut W=1 -Werror für ARM32.
2. **MMIO/IRQ verifizieren:** echte reg-Base/Size und Display-IRQ aus dem
   Nike-L-DTB übernehmen (Platzhalter in `dts/sdp-nikel-display-disabled.dts`).
3. **Clock/Reset/Power:** Display teilt sich MMIO-Regionen mit dem
   sdp1804-Clock-Controller – **ein** koordinierter Owner nötig (nicht zwei
   MMIO-Provider). Erst Clock/Reset/Panel-Power, dann Modeset.
4. **Panel-Timing:** echtes `sdp1202`-Timing statt des 1080p60-Platzhalters;
   Panel-Init-Sequenz und Backlight (`tztv-tcon`/`frc`).
5. **Modeset/Plane/VSync:** `pipe_enable/disable/update` mit Controller-
   Programmierung füllen; vblank/IRQ anbinden.
6. **Integration:** `drm_hwcomposer` + Panfrost/`kmsro` (siehe GPU-Doku).

## Grenzen

- Register-Ownership unverifiziert; Überlappung mit sdp1804-Clock.
- Kein Panel-Timing bestätigt; Platzhaltermodus ist willkürlich.
- Skelett erzeugt **kein** Bild. `BoardConfig.mk`-`$(error)`-Sperre bleibt.
