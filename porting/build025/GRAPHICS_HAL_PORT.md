# Samsung Nike-L: GPU-/Display-Port und Android-14-HAL-Vertrag

**Entwicklungszweig:** Build 025, ausschließlich statische Quelle und
55-Zoll-Referenzfirmware `T-NKLDEUC 2743.0`. Die tatsächliche
50-Zoll-Hardware, GPU-ID und der ARM64-Bootweg sind ungeprüft.

## 1. Zwei grundsätzlich verschiedene Grafikpfade

**A – Samsung-Kbase beibehalten:**

- Im vorhandenen Samsung-Quellarchiv verweist `arm,mali-midgard`
  auf `sdp_gpu_nike/drivers/gpu/arm/midgard/mali_kbase_core_linux.c`.
- Zunächst GPU-ID und Kbase-Version **aus den echten Firmwaremodulen**
  unabhängig feststellen. Ein DT-String allein identifiziert nicht
  zuverlässig die genaue Mali-Generation.
- Ein 4.1.10-Kbase-Treiber ist nicht unverändert für Linux 6.6 geeignet:
  DMA/IOMMU, Clock/Power, Linux-Synchronisierung und die Export-ABI
  können abweichen. Auch eine Tizen-`libmali.so` ist nicht automatisch
  eine Android-EGL-Library mit passender ABI.
- Vor dem Android-HAL muss das Legacy-GPU-/Userspace-Paar auf einem
  *passenden Testgerät* mit funktionierender Bufferübergabe belegt sein.

**B – Linux-DRM/Panfrost:**

- Mesa/Panfrost kann für geeignete Midgard-/Bifrost-GPUs ein offener
  Kandidat sein, erfordert aber einen kompatiblen Kernel-DRM-Treiber.
- Panfrost rendert 3D; es ersetzt **nicht** Samsungs Displaycontroller,
  Frame-Rate-Converter (FRC), TCON und Panel-Timing.
- DRM/KMS, DMA-BUF, Render-Node, GPU-Energiesparzustände und
  dazu passende Mesa-EGL-/GLES-Bibliotheken müssen zusammen getestet
  werden. Die Verwendung von `kmsro` allein garantiert keinen Scanout.

Die Wege dürfen nicht anhand eines generischen `arm,mali-midgard`-Strings
vermischt werden. Welche Variante überhaupt sinnvoll ist, hängt von
der echten GPU-Kennung und der Android-/Linux-ABI ab.

## 2. Samsung-Displaypfad (gemeinsame Pflicht für beide Wege)

Im Build-011-Quellvergleich wurden wörtliche Bezüge zu folgenden
Samsung-Geräten und Modulen gefunden:

| Funktion | Firmware-DT | Bisheriger Quellhinweis | Offener Test |
| --- | --- | --- | --- |
| GPU | `arm,mali-midgard` | `sdp_gpu_nike` | GPUID, Kernel- und Userspace-ABI |
| Displaycontroller | `samsung,sdp-drm` | `sdp_drm_nike/sdp_drm_drv.c` | DRM-Connector/CRTC/Plane/Framebuffer |
| Panel | `samsung,sdp1202-panel` | `drivers/gpu/drm/panel/panel-sdp.c` | Mode, Timing, Backlight |
| Framekonvertierung | `samsung,sdp-frc-l` | `sdp_frc_nike/.../sdp_frc_drv.c` | FRC-/TCON-Initialisierung und Synchronisierung |
| HDMI | `samsung,sdp-hdmi` | `sdp_hdmi_nike/sdp_hdmi_main.c` | Eingangsschaltung, Takt und Hotplug |
| Video | `samsung,sdp-mfc` | `sdp_codec_nike` | V4L2/Codec2, Ausgabepuffer |

Diese Referenzen sind **nicht** automatisch Linux-6.6-Module.
Insbesondere hängt die Panel-Ausgabe bei einem Fernsehgerät von
mehreren Samsung-spezifischen Display-Bausteinen ab; eine funktionierende
Mali-GPU würde alleine noch keinen Android-Frame sichtbar machen.

## 3. Android-14-HAL-Vertrag

Hier beschreiben wir die *benötigten Implementierungen* – es werden
bewusst **keine** erfundenen `manifest.xml`-Dienstdeklarationen erzeugt.

1. **Buffer Allokation/Mapping:** Pixel-Formate, Stride, Usage-Flags,
   Cache-Kohärenz, DMA-BUF-FD-Import/Export sowie geschützte Speicherpfade
   nachweislich mit GPU und Displaycontroller abgleichen.
2. **Synchronisierung:** Acquire-/Release-/Present-Fences über GPU,
   SurfaceFlinger und Scanout korrekt halten; keine stillen Ausnahmen
   im Nutzerraum oder global deaktivierten SELinux-Regeln.
3. **Composer:** für Android 14 eine vom Target unterstützte
   `android.hardware.graphics.composer3`-AIDL-HAL untersuchen,
   einschließlich Displaykonfiguration, VSync, Layer-Komposition,
   `validateDisplay`/`presentDisplay` und Screen-Blanking.
4. **GLES/EGL:** Renderpfad und Bufferlayout mit dem gewählten
   GPU-Kerneltreiber testen. GLES-Unterstützung sagt nichts über DRM-/HDCP
   oder Samsung-spezifische HDMI-Eingänge aus.
5. **Vendor-/SELinux-Vertrag:** erst nach realen Treiber-Device-Nodes
   die korrekten `ueventd`-Rechte, `file_contexts`, Service-Domains und
   VINTF-Manifeste implementieren und mit Android-Testtools prüfen.

Ein gültiges XML-Gerätemanifest oder ein gebautes `libmali.so` ersetzt
**keinen** Laufzeittest der HAL-Dienste auf echter Hardware.

## 4. Read-only Quelle-ABI-Inventur in Build 025

Der neue Prüfer `q60t_build025_graphics_pipeline.py` kombiniert die
beiden vorhandenen Reports und macht folgende Unterschiede explizit:

- `present_in_both_reference_profiles`: die Komponente wird in beiden
  firmwareseitigen DTB-Varianten erwähnt, **nicht** im echten TV bestätigt.
- `disabled_in_reference`: eine Komponente ist in den gewählten
  Referenzprofilen deaktiviert. Das gilt bisher für HDMI-CEC.
- `legacy_api_symbol_observations`: bei optionalem Samsung-Media-Quellbaum
  nur **wortwörtliche Nennungen** alter Linux-APIs wie ION, DMA-BUF,
  DRM/KMS, IRQ, Runtime-PM, IOMMU und Sync-Fence.
- `android_display_stages`: vom Render-Treiber über Scanout, Buffer und
  Composer bis zum sichtbaren SurfaceFlinger-Bild: **alle ungeprüft**.

Es werden nur im Build-011-Bericht nachgewiesene Quellpfade gelesen,
keine Binärdaten hochgeladen und keine fremden Buildskripte gestartet.

Beispiel, aus dem Repository-Wurzelverzeichnis:

```bash
python3 q60t_build025_graphics_pipeline.py \
  --hardware-report reports/hardware_2743.0_build004_final.json \
  --legacy-source-report reports/source_compat_build011.json \
  --output /opt/samsung-atv-lab/build025-graphics-pipeline.json
```

Wenn der separate lokale Samsung-`media-source`-Ordner verfügbar ist,
kommt optional `--vendor-source /pfad/zu/media-source` dazu.

## 5. Konkrete Prüf-Reihenfolge – sobald das Labor bereit ist

1. **Exaktes Board:** anhand einer regulären, lesenden Live-Quelle
   50-Zoll-RAM-Profil, CPU und Mali-GPU-ID bestätigen; keine vertraulichen
   Geräteinformationen veröffentlichen.
2. **Boot-/Device Tree:** CPU-/PSCI-/Clock-/Displayknoten zu einem
   geeigneten Kernel zuordnen; unveränderter 4.1.10-Source ist
   vorerst nur Referenz. Kein TV-Flash.
3. **GPU:** erst im isolierten Labor funktionierendes Render-Device,
   Speicherallokation, DMA-BUF und Fence-Synchronisierung prüfen.
4. **Display:** DRM/KMS und Panel-/TCON-/FRC-Pfad validieren.
5. **Android:** erst dann Gralloc, EGL/GLES und Composer3 integrieren,
   danach Audio, Codec2 und Input/CEC.
6. **Sicherheit:** ohne unabhängigen, getesteten Recovery-/Rollbackweg
   kein persistenter Bootversuch auf dem Produktiv-TV.

Die Ergebnisse aus QEMU `virt` zählen niemals als Beweis für Samsung-
GPU-, HDMI-, TCON- oder Recovery-Funktion.

### Referenzen

- [AOSP – Grafikarchitektur](https://source.android.com/docs/core/graphics/architecture)
- [AOSP – Hardware Composer](https://source.android.com/docs/core/graphics/implement-hwc)
- [AOSP – AIDL Composer3](https://source.android.com/docs/core/graphics/aidl-hwc)
- [AOSP – Synchronisation](https://source.android.com/docs/core/graphics/sync)
- [Mesa – Panfrost](https://docs.mesa3d.org/drivers/panfrost.html)
