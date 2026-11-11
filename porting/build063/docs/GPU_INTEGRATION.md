# GPU-Integration – Mali-G51 (Bifrost) unter LineageOS 22.2 ARM32

**Read-only Portierungsplan. Kein Gerätezugriff, kein Flash.** Die reale GPU-ID
muss am Gerät bestätigt werden: DT nennt generisch `arm,mali-midgard`,
unabhängige Q60T-Forschung berichtet **Mali-G51 / Bifrost r11p0**.

## Strategie: offener Stack (Panfrost + Mesa), nicht Tizen-`libmali.so`

Die Tizen-`libmali.so` ist ein TrustZone-/Tizen-Userspace-Blob und **kein**
Android-GLES/EGL-HAL. Der realistische Weg ist der **offene Panfrost-Stack**:

- **Kernel:** `CONFIG_DRM_PANFROST=m` (Upstream, kein eigener Treiber nötig).
  Panfrost unterstützt Bifrost G31/G51/G52/G76 mit **GLES 3.1 / GL 3.1**.
- **Userspace (Mesa):** Gallium-Treiber `panfrost`, plus `kmsro`, weil Mali
  keinen Display-Controller hat – `kmsro` bindet an den KMS-Treiber (unser
  `sdp-drm`, Build 063). Vulkan/OpenCL: nicht verfügbar (für Android-TV-GLES
  nicht erforderlich).
- **Gralloc:** zwei Optionen –
  1. **`gbm_gralloc` / `gralloc.gbm`** (offen, über Mesa GBM) – passt zum
     Panfrost+kmsro-Weg.
  2. ARMs **Apache-lizenziertes Bifrost-Android-Gralloc-Modul**
     (`developer.arm.com/downloads/-/mali-drivers/android-gralloc-module`),
     falls GBM-Gralloc am TV Probleme macht.
- **HWC:** **`drm_hwcomposer`** (offener AIDL-Hardware-Composer, Android 13+),
  setzt auf unserem `sdp-drm`-KMS auf.

## Abhängigkeitskette (kritisch)

```
sdp-drm (KMS, Build 063)  ->  kmsro  ->  Panfrost (GLES)  ->  gbm_gralloc
            |                                   |
            +---------> drm_hwcomposer  <-------+---> SurfaceFlinger
```

**Ohne funktionierenden `sdp-drm`-KMS-Treiber kein Panfrost-Bild.** Der
Display-KMS (Build 063 Skelett + Vendor-Portierung) ist der echte Engpass.

## LineageOS-Device-Tree-Integration (device/samsung/nikel)

Nach bestätigtem KMS + Panfrost in das Gerät einhängen (Platzhalter, erst nach
Compile/Boot-Nachweis setzen):

```makefile
# BoardConfig.mk (erst nach Nachweis; $(error)-Sperre bleibt bis dahin)
TARGET_USES_DRM_HWCOMPOSER := true
# device.mk
PRODUCT_PACKAGES += \
    android.hardware.graphics.composer3-service.drm \
    libGLES_mesa \
    gralloc.gbm \
    hwcomposer.drm
PRODUCT_PACKAGES += \
    libEGL_mesa libGLESv1_CM_mesa libGLESv2_mesa
# Mesa über external/mesa3d (AOSP) mit -Dgallium-drivers=panfrost,kmsro
```

Relevante Properties: `ro.hardware.gralloc=gbm`, `ro.hardware.egl=mesa`,
`ro.hardware.hwcomposer=drm`, `debug.sf.nobootanimation`/`vsync`-Tuning.

## Offene Verifikationen

- Reale GPU-ID (Midgard vs. Bifrost, exaktes Modell) am Gerät.
- Panfrost benötigt die **GPU-Clock/Reset** (Build-058-`gpu-clkrst`) + Power-
  Domain + `mali-supply` – alle noch unverifiziert.
- `operating-points-v2` für GPU-Devfreq (optional, später).
- GLES-Konformität am realen Panel erst nach KMS-Bringup messbar.

## Quellen
- `docs.mesa3d.org/drivers/panfrost.html` (Bifrost G31/G51/G52/G76, GLES 3.1).
- `developer.arm.com/downloads/-/mali-drivers/android-gralloc-module` (Apache).
- Projektintern: `porting/build056/panfrost-sdp-nikel-disabled.dts`,
  `porting/build058/.../sdp_nikel_gpu_clkrst.c`, `BUILD062_REPORT.md`.
