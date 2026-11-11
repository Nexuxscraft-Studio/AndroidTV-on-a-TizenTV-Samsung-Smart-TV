# Build 062 – LineageOS-ARM32-Baubarkeit & Treiberprüfung

Planungs-/Verifikationsanalyse (read-only, keine Hardware, kein Flash).
Vollständiger Bericht: `../../BUILD062_REPORT.md`.
Maschinenlesbare Treiber-Matrix: `../../reports/lineage_arm32_driver_matrix_build062.json`.

## Kernaussagen

- **LOS 22.2 baut 32-Bit-ARM-Android-TV** – produktiv belegt durch `sabrina`
  (Chromecast with Google TV, Android:arm, Mali-G31).
- **Unser Ziel:** durchgängig 32-Bit – `TARGET_ARCH=arm` + 32-Bit-Binder auf dem
  **Build-059-Linux-6.6.162-ARM32**-Kernel (nicht 4.1.10-Stock).
- **6.6.162 löst** die 4.1.10-Lücken (Binder-ABI, SELinux, dma-buf-heaps)
  strukturell.
- **GPU Mali-G51 ist Panfrost-fähig** (GLES 3.1); offenes Bifrost-Gralloc (Apache).
  Kritischer Pfad ist der **Display-KMS-Treiber** (`samsung,sdp-drm`), an dem
  Panfrost hängt.
- **Korrektur zu Build 060:** AOSP hat das 32-Bit-ARM-TV-**Emulator**-Target
  (`aosp_tv_arm`) entfernt; `sdk_tv_arm` in LOS 22.2 ist **unbestätigt** und am
  Lineage-Manifest zu prüfen. Fallback: Geräte-Target/GSI unter QEMU (wie
  Build 018–022).

## Reihenfolge

1. 32-Bit-Userspace im Emulator/QEMU beweisen (ohne Samsung-Treiber).
2. 6.6.162-ARM32-Kernel am Gerät (Bootchain/Signatur = separater Gate, Build 061).
3. Display-KMS + Panfrost + Gralloc → erstes Bild.
4. Input/Audio/Video → 5. Netzwerk/DRM.

Die `BoardConfig.mk`-`$(error)`-Sperre und alle Boot-Gates bleiben.
