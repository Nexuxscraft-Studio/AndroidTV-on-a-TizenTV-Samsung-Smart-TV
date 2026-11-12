# Treiber-Gesamtplan – Samsung Q60T / Nike-L → LineageOS 22.2 ARM32

**Read-only Gesamtplan über alle Subsysteme. Kein Gerätezugriff, kein Flash.**
Konsolidiert Build 056–064. Zielkernel: **Linux 6.6.162 ARM32** (Build 059),
Userspace: **LineageOS 22.2 (Android 15), `TARGET_ARCH=arm`** (Build 062).

## Grundprinzipien

1. **Upstream vor Eigenbau.** Panfrost (GPU), `cpufreq-dt` (DVFS), `thermal-of`,
   `dw_mmc-exynos` (eMMC), V4L2-m2m (Video), ASoC (Audio), `rc-core` (IR) sind
   Mainline. Nur wo es keinen Upstream-Treiber gibt (Display `sdp-drm`), wird
   ein eigener 6.6-Treiber geschrieben.
2. **6.6 statt 4.1.10.** Der neue Kernel bringt Binder/SELinux/dma-buf-heaps
   upstream → die 4.1.10-Lücken (Build 012–017) entfallen.
3. **Alles `disabled`, bis am Gerät verifiziert.** reg/IRQ/Clock/Reset/Regulator/
   Timing sind Platzhalter. Die `BoardConfig.mk`-`$(error)`-Sperre bleibt.

## Kritischer Pfad (erstes Bild)

```
Core-SoC-Boot (UART ok -> eMMC)             [P0, Build 059/063]
        |
   sdp-drm KMS  --kmsro-->  Panfrost  --> gbm_gralloc --> SurfaceFlinger
        |                                        ^
        +---------------> drm_hwcomposer --------+          [P0, Build 063]
```
**Ohne `sdp-drm`-KMS kein Panfrost-Bild.** Die Display-Vendor-Logik (Modeset)
ist der eigentliche Engpass und braucht die Nike-L-Vendor-Quellen.

## Subsystem-Matrix

Build 070: Alle Kconfig-Symbole der Tabelle stecken in
`porting/build059/kernel/configs/nikel-drivers.config` (Profil `android`);
DT-Knoten erst mit Werten aus der Firmware-`dtb.bin`. Details: `porting/build070/README.md`.

| Subsystem | Prio | Zielreiber | Samsung-Quelle (GPL) | Status (Build) |
| --- | --- | --- | --- | --- |
| Core-SoC (UART/Clk/GPIO) | P0 | eigen (6.6) | `board-nike-dt.c`, `sdp_uart` | 059: gebaut |
| eMMC | P0 | `dw_mmc-exynos` | `samsung,sdp-mmc` | 063: config/enable |
| **Display** | **P0** | **eigen `sdp-drm`** | `sdp_drm_nike` | **070 codex/graphics: 0015 + 0023 Scanout-/VBlank-Kandidat, lokal ARM32-GCC kompiliert; DT disabled, ABGR/Timings UNBELEGT, kein Gerätetest** |
| GPU | P0 | Panfrost (Upstream) | — (DT: mali) | 070 codex/graphics: disabled DT + genpd, ARM32-GCC compile; Parent/Rate/Supply UNBELEGT; Runner ausstehend |
| CPU-DVFS/Thermal | P0 | `cpufreq-dt`/`thermal-of` | — | 063: config/DT/plan; 070: im gemeinsamen Kernel |
| Video-Decode (MFC) | P1 | V4L2-m2m | `sdp_codec_nike` | 064: config/DT/plan |
| Audio | P1 | ASoC | `sdp_alsa_nike` | 064: config/DT/plan |
| HDMI | P1 | drm-bridge/eigen | `samsung,sdp-hdmi` | 064: DT/plan |
| HDMI-CEC | P1 | `cec`-core | `sdp-mc-cecif` (disabled) | 064: DT/plan; **070: Patch 0014 portiert, kompiliert** |
| IR-Fernbedienung | P1 | `rc-core` | Micom (`tztv-micom` rc-wt61p807) | 064: DT/plan; **070: Patch 0013 (Mailbox+Micom+RC) portiert, kompiliert** |
| USB (HID/Storage) | P2 | EHCI/OHCI | `sdp-usben` | 063: config/enable |
| Ethernet | P2 | eigen/generic | `samsung,sdp-mac` | 064: config/DT/plan |
| WLAN/BT | P2 | chipsatzabhängig | unklar | offen |
| DRM/Widevine | P2 | — | keine HW-DRM-HAL | nicht garantiert |

## 4.1.10 → 6.6 – wiederkehrende Migrationen

- `struct fence` → `struct dma_fence` (Display: Build 058 erledigt).
- `drm_gem_cma_*` → `drm_gem_dma_*`; eigene fbdev → `drm_fbdev_dma_setup()`.
- Legacy-DRM-CRTC → Atomic-KMS (`drm_atomic_helper_*`).
- ION → dma-buf-heaps (Grafik-Buffer).
- V4L2: alte vendor-ioctls → `v4l2_m2m`-Framework + `media-controller`.
- Clock/Reset: ad-hoc-Register → `clk`/`reset`-Controller (Build 059
  `clk-sdp1804`; GPU/Display/CPU teilen MMIO → EIN koordinierter Owner).
- Platform-Treiber: `.remove` gibt in 6.6 noch `int` zurück.

## Android-HAL-Zuordnung (Userspace)

| HW | Android-HAL (offen) |
| --- | --- |
| Display | `drm_hwcomposer` (AIDL composer3) |
| GPU | Mesa Panfrost (`libEGL/GLESv2_mesa`) + `gbm_gralloc` |
| Video | Codec2 / `c2.android.*` + V4L2-Backend |
| Audio | `audio.primary` ASoC-basiert / tinyalsa |
| Input/IR | evdev + Android keylayout |
| CEC | `android.hardware.tv.cec` (nach Kernel-CEC) |

## Reihenfolge (Bring-up)

1. **Boot:** Core-SoC (UART steht) → eMMC → minimaler 6.6-ARM32-Boot am Gerät
   (Bootchain/Signatur = separater Gate, Build 061). *Zuerst Emulator/QEMU.*
2. **Bild:** `sdp-drm`-Modeset (Vendor-Logik) → Panfrost/kmsro → gralloc → HWC.
3. **Bedienung:** IR/Input, Audio-HAL.
4. **Medien:** MFC/V4L2 → Codec2.
5. **Netz/Komfort:** Ethernet, USB, WLAN/BT; DRM nicht garantiert.

## Grenzen

Kein Subsystem ist am Gerät verifiziert. Grüne CI-Läufe beweisen
**Compile-Barkeit/DTS-Syntax**, nicht Funktion oder Boot. Die eigentliche
Hardware-Logik (Display-Modeset, OPP-Werte, TMU, Codec-Buffer) erfordert die
Nike-L-Vendor-Quellen und das reale Gerät.
