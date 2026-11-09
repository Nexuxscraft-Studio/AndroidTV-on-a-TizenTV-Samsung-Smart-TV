# Hardware- und Android-HAL-Matrix – Nike-L / Firmware 2743.0

**Alle Hardwareangaben sind aus einer überprüften 55-Zoll-Referenzfirmware
abgeleitet. Sie sind keine Live-Messung am 50-Zoll-Zielgerät.**

| Bereich | Konkreter Firmware-Nachweis | Für Android TV fehlend | Priorität |
| --- | --- | --- | --- |
| CPU | 4 × `/cpus/cpu@0..3`, `arm,cortex-a57` | Passende 32-/64-Bit-ABI- und Kernelwahl | P0 |
| RAM/Boot-DTB | `nikel-2G` und `nikel-1.5G`, 130 geänderte Properties | Reale Variante und sichere RAM-Reservierungen | P0 |
| Grafik-GPU | `/soc/sdpgpu@00500000`, generische DT-Kennung `arm,mali-midgard`; Strings `/dev/mali0`, `libmali.so`; separate Q60T-Forschung berichtet Mali-G51/Bifrost r11p0 | GPU-ID und Treiberversion selbst verifizieren; passender Mali-Kerneltreiber + GLES/EGL + Gralloc | P0 |
| Display | `samsung,sdp-drm`, `samsung,sdp1202-panel` | Android SurfaceFlinger-Hardware-Composer, VSync, Moduswechsel | P0 |
| TV-Panel-/Timing | `samsung,tztv-tcon*`, `samsung,sdp-frc-*` | Panelinitialisierung und Backlight/Timing | P0 |
| Kernel | `uImage` ARM32 Linux 4.1.10, CRC geprüft | Reproduzierbarer GPL-Build, Android Binder/Security, Boot-Protokoll | P0 |
| Signaturen | UEP-Strings `SfdUepVerifyExecutableBinary`, `SfdUepVerifyFileSignature` | Reversibler Bootpfad und belastbarer Recovery-Nachweis | P0 |
| HDMI | `samsung,sdp-hdmi`, `samsung,tztv-hdmi-sw` | Eingangsverwaltung, Hotplug und HDMI-HDCP-Verhalten | P1 |
| HDMI CEC | `/soc/cecif`, `samsung,sdp-mc-cecif`; **`status = "disabled"` in beiden Referenz-DTBs** | Zuerst Aktivierungsmechanismus klären; danach Android CEC-HAL und Weitergabe | P1 |
| IR/Fernbedienung | `/soc/mcirb`, `samsung,sdp-mc-irb`; `/soc/mcirs`, `samsung,sdp-mc-irs`; **beide `status = "okay"`** | Prüfen, ob echte Input-Events kommen; Android Keylayout und Tastenbelegung | P1 |
| TV-Micom | `samsung,sdp-micom-ctrl`, `samsung,tztv-micom` | Einschaltzustände, Sleep/Wake, sichere Steuerprotokolle | P1 |
| Audio | `/sdp-audio`, `samsung,sdp-audio`; `/sdp-audio-spdif` | Android Audio-HAL und Lautstärke/Output-Pfade | P1 |
| Video-Dekoder | `/soc/sdp_mfc@0x00a40000`, `samsung,sdp-mfc` | MediaCodec/Codec2, V4L2/Buffer-Anbindung | P1 |
| Ethernet | `/soc/emac`, `samsung,sdp-mac` | Netzwerktreiber und Android-Netzwerkdienst | P2 |
| USB | EHCI/OHCI-Knoten und `samsung,sdp-usben` | Host-/HID-Integration | P2 |
| eMMC/Flash | `/soc/mmc`, `samsung,sdp-mmc`, SPI NOR | Partitionsinventar, readonly Datenzugang, keinerlei blindes Flashen | P0 |
| WLAN/Bluetooth | Im statischen DTB nicht eindeutig zugeordnet; Dateipfad-Hinweise vorhanden | Exakten Chipsatz und Firmware/Stack bestimmen | P2 |
| DRM/Streaming | Keine bestätigten Android-Hardware-DRM-/Widevine-HALs | Zertifizierung/Lizenzen, geschützte Wiedergabe | P2 |

## Bring-up-Abhängigkeiten

1. **P0: Korrektes Gerät, Kernel, RAM-Profil, sicherer Bootweg.** Ohne
   dies sind die folgenden Stufen nur hypothetisch.
2. **P0: Ein verifiziertes Bild auf dem Panel.** Dazu gehören GPU-Treiber,
   ein Android-kompatibler Buffer-Austausch und der Display-Composer.
3. **P1: Bedienbarkeit und Medien.** IR/CEC/Input, Audio-HAL, MFC-Codec.
4. **P2: Netzwerk, Komfort, Streaming-DRM.** DRM-Apps sind auch bei
   erfolgreichem Android-Boot nicht garantiert.

Für Android 13 und höher wird ein
[AIDL-Hardware-Composer](https://source.android.com/docs/core/graphics/aidl-hwc)
unterstützt; eine Tizen-`libmali.so` ist **kein** nachgewiesener
Android-Hardware-Composer.

**Quellennachweise:**

- `../reports/hardware_2743.0_build004_final.json`: geprüfte Device-Tree-Knoten,
  zwei Varianten, gesäuberte Props, expliziter `status` und `memory/reg`.
- `../reports/rootfs_strings_2743.0.json`: ausschließlich rohe Pfadstrings.
- `../reports/kernel_2743.0.json`: Kernelbanner und Security-Symbolnamen.
- Google:
  <https://source.android.com/docs/core/graphics/implement-hwc>
- GPU-Identitätsvergleich aus unabhängiger Q60T-Forschung:
  <https://github.com/sebastianspicker/tiz0wn/blob/main/docs/firmware-analysis.md>

Keine der hier genannten Klassen stellt automatisch einen realen,
einsatzbereiten oder lizenzrechtlich verteilbaren Treiber dar.
`status = "disabled"` im Referenz-DTB schließt eine spätere Aktivierung
durch Bootloader oder Software nicht aus; sie ist hier lediglich nicht belegt.

## Build-011-Abgleich mit tatsächlich vorliegenden Quellen

Der zusätzliche statische Nachweis in
[`../reports/source_compat_build011.json`](../reports/source_compat_build011.json)
enthält wörtliche C-/Header-Code-Referenzen für `arm,mali-midgard`
(`sdp_gpu_nike`), `samsung,sdp-drm` (`sdp_drm_nike`),
`samsung,sdp-mfc` (`sdp_codec_nike`), `samsung,sdp-mc-audio`
(`sdp_alsa_nike`) und `samsung,sdp-nikel` (Kernel-Boardcode).
Die HDMI-Umschaltkennung `samsung,tztv-hdmi-sw` fand sich nicht wörtlich
im gescannten Quelltext. Für Grafik/Video/Audio fehlen insbesondere
Android-kompatible Userspace-HALs und eine geprüfte Laufzeit-ABI.
