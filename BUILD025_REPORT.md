# Build 025 – Samsung Q60T: Hardware-/Kernel-/HAL-/Recovery-Portierbarkeit

**Zielgerät:** Samsung GQ50Q60TGUXZG, gemeldete Tizen-Firmware `T-NKLDEUC 2743.0`  
**Basis:** Ausschließlich die früher dokumentierte Samsung-**55-Zoll-Referenzfirmware** und Nike-L-Quellen. Kein Zugriff auf den 50-Zoll-Fernseher.  
**Entwicklungszweig:** `feature/build025-samsung-hardware-portability-audit`  
**Status:** Offline-Quell- und Firmwareauswertung. **Kein Samsung-ARM64-Boot, kein Android-HAL und kein Recoveryweg nachgewiesen.**

## 1. CPU, Board und Bootweg

- Beide bereits inventarisierten Referenz-DTBs aus `2743.0` haben die Kennung
  `samsung,sdp-nikel`, jeweils **vier** CPU-Knoten mit
  `arm,cortex-a57`/`arm,armv8`. Damit ist **ARMv8/AArch64 als
  SoC-Kandidat plausibel**. Das ist **keine** Beobachtung des tatsächlich
  verbauten 50-Zoll-Boards. Quelle: `reports/hardware_2743.0_build004_final.json`
  mit DTB-Bundle-SHA-256
  `9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2`.
- Die referenzierte Firmware bootet ein **ARM32-U-Boot-`uImage`** mit
  **Linux 4.1.10**. Gültige Header-/Payload-CRCs sind keine
  kryptografische Hersteller-Signaturprüfung. Quelle:
  `reports/decrypted_components.json` und `reports/kernel_2743.0.json`.
- Die beiden DTB-RAM-Profile `nikel-2g` und `nikel-1.5g` sind
  Firmware-Varianten. **Keines** wurde live am 50-Zoll-TV identifiziert.
- Die CPU-Implementierung allein beweist nicht, dass der aktuelle
  Bootloader den Kernel tatsächlich in **AArch64 EL1** startet oder
  dafür gültige PSCI-/SMC-Konventionen, GIC- und Memory-Maps übergibt.
  Ein isolierter Linux-6.6.162-ARM64-Start auf **QEMU `virt`** zeigt nur,
  dass der generische Kernel und das Test-Initramfs zusammenarbeiten.

**Entscheidung:** Die reale 50-Zoll-Hardware ist **nicht** bestätigt;
bootloaderabhängiger ARM64-Hardwaretest bleibt blockiert.

## 2. Kerneltreiber von Samsung nach Linux 6.6

Die **vorhandene** Code-/DTB-Gegenprüfung
`reports/source_compat_build011.json` nennt konkrete Samsung-Quellmodule.
Eine wörtliche `compatible`-Zeichenfolge beweist nur, dass Quellcode
darauf Bezug nimmt; sie beweist nicht, dass der Treiber gebaut, geladen
oder auf 6.6 portierbar ist.

| Teilbereich | Quellhinweis aus 4.1.10/Nike-L | Offene Linux-6.6-Arbeit |
| --- | --- | --- |
| Board/Boot | `arch/arm/mach-sdp/board-nike-dt.c` | ARM64-Startprotokoll, Clock, Reset, PSCI, Interrupts, MMU, IOMMU, `reserved-memory` |
| GPU | `sdp_gpu_nike/drivers/gpu/arm/midgard/mali_kbase_core_linux.c` (`arm,mali-midgard`) | GPU-ID und kbase-KABI; ggf. Panfrost-DRM, Energieverwaltung und EGL-/Mapper-Anbindung |
| Display/Scanout | `sdp_drm_nike/sdp_drm_drv.c`, `drivers/gpu/drm/panel/panel-sdp.c` | Modesetting, Panel-/TCON-/FRC-Sequenz, DMA-BUF, VSync, Display-Kompositor |
| HDMI | `sdp_hdmi_nike/sdp_hdmi_main.c` | HDMI-Eingänge, Timing und HDCP (HDCP ohne OEM-/Lizenz-Integration nicht als verfügbar melden) |
| Video | `sdp_codec_nike` (MFC) | Decoder-Firmware, V4L2/Buffer-Synchronisierung, Android Codec2/Media HAL |
| Audio | `sdp_alsa_nike/sdp_audio_machine.c` | ALSA/Audio-HAL, Lautsprecher-/SPDIF- und HDMI-Audiopfade |
| IR/CEC | `drivers/soc/sdp/sdp_micom_irb.c`, `sdp_micom_irs.c`, `sdp_micom_cecif.c` | Android Input-Keylayout; CEC ist in beiden Referenz-DTBs `disabled` |
| Storage | `samsung,sdp-mmc`-DT-Kennung | Partitionslayout nur lesen, Controller-Treiber/Bootlayout verstehen, **keine Schreibtests** |

Der historische `20_DTV_NikeL.zip`-Kernelquellbaum bietet im bisher
überprüften Stand lediglich eine `Nike.M`-Release-Konfiguration, **keine
nachgewiesene exakte Nike.L-Defconfig für 2743.0**. Android-Binder und
Samsung-Smack/SFD-Sicherheitskomponenten aus dem Legacy-Kernel ergeben
keinen fertigen Android-14-Kernel.

Für einen reproduzierbaren nächsten Schritt gibt es neu:

- `q60t_build025_kernel_gap.py`: prüft die **wirklich vorhandene**
  Build-011-Referenz gegen einen **lokal bereitgestellten** Linux-6.6-Quellbaum.
  Gezählt werden **wörtliche** Treffer in C-/Header-Code vs.
  Device-Tree-Deklarationen. Treffer erlauben niemals die Aussage
  „Treiber läuft“.
- Optional liest es ein *gerätespezifisches* Android-VINTF-`manifest.xml`
  ein und stellt deklarierte HAL-Schnittstellen gegenüber. Das Vorhandensein
  eines XML-Eintrags ist **kein** HAL-Laufzeittest.
- Ein gebundener JSON-Report wird **nur neu angelegt**, niemals
  überschrieben. Der Vergleich führt keinen Compiler oder Firmwarecode aus.

## 3. Grafik und Android-HALs

Der DTB-Eintrag `arm,mali-midgard` bezeichnet nur eine kompatible
Treiberfamilie. Die externe Vermutung *Mali-G51/Bifrost r11p0* ist
weiterhin kein verifizierter GPU-Identifier dieses Fernsehers.
Die Wege **Legacy kbase+passende Android-EGL-Bibliotheken** und
**Linux DRM/Panfrost+Mesa** bleiben **getrennte, ungeprüfte Kandidaten**.
Mali-3D-Rendering und die Samsungs eigene **Display-Controller-Ausgabe**
sind zwei verschiedene Aufgaben. Ohne erfolgreichen Scanout über Panel,
TCON/FRC und Buffer-Fences zeigt Android kein Bild.

Für LineageOS 21 (Android 14) müssen mindestens gerätespezifische
VINTF-HALs und Dienste für Composer, Buffer-Allokation, Audio,
Video-Codec, Input/CEC geprüft bzw. implementiert werden. Die
Android-`gsi_tv_arm64`-Ausgabe enthält diese Samsung-Treiber nicht.
Siehe AOSP-Hardware-Composer, VINTF und Mesa-Panfrost in den Quellen unten.

## 4. Boot- und Recovery-Schranke

`sign.bin`, `secos.bin` und `seret.bin` im Referenzupdate und
UEP-Security-Symbole im Kernel sind Hinweise auf eine komplexe
Boot-/Vertrauenskette; der konkrete Trust Anchor ist nicht nachgewiesen.
Samsung stellt eine **offizielle USB-Firmwareaktualisierung** bereit,
aber das ist **kein** nachgewiesener unabhängiger Reparaturweg nach
kaputtem Bootloader oder nicht akzeptierter Signatur.

Vor einem einzigen Testboot auf der echten Hardware müssen alle
folgenden Nachweise vorliegen: Board- und RAM-Identität, Bootmodus,
Signaturpolitik, flüchtige Bootmöglichkeit, geprüfte Stock-Sicherung,
Recovery-Einstieg, erfolgreicher Rollback an einer Ersatzplatine sowie
Stromausfall-/Watchdog-Verhalten. Aktuell: **nicht erfüllt**.

**Keine Flash-Anleitung, keine Secure-Boot-Umgehung, keine Aussage
„safe_to_flash“**. Ein modernes Linux oder ein laufendes Android in QEMU
entschärft diese Hardware-Risiken nicht.

## 5. Was jetzt konkret prüfbar ist

Die CLI-Anleitung mit Offline-Tests, bereits vorhandenen Referenzreports,
optionalem 6.6-Source-Abgleich und lesenden Gerätedaten steht in
[`porting/build025/README.md`](porting/build025/README.md).

**Erreicht:** Prüflogik und technische Lückenmatrix für Hardware,
Kernel, Grafik, HALs und Recovery auf separatem Branch. **Nicht
erreicht:** exakte Live-Hardwareidentifikation, funktionierender
Samsung-Linux-6.6-Kernel, Hardware-Accelerated Composer, realer
Samsung-Boot oder Recovery-Test.

### Primärquellen

- [Samsung-Support Q60T](https://www.samsung.com/de/support/model/GQ50Q60TGUXZG/): offiziell verfügbare `T-NKLDEUC`-USB-Updates.
- [Arm Cortex-A-Prozessorvergleich](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/Cortex-A%20R%20M%20datasheets/Arm%20Cortex-A%20Comparison%20Table_v4.pdf): Cortex-A57 ist ARMv8-A.
- [AOSP AIDL Hardware Composer](https://source.android.com/docs/core/graphics/aidl-hwc) und [AOSP VINTF Device Manifests](https://source.android.com/docs/core/architecture/vintf/objects).
- [Mesa Panfrost](https://docs.mesa3d.org/drivers/panfrost.html): GPU-3D und Display-Controller sind separate Komponenten.
- [AOSP GKI](https://source.android.com/docs/core/architecture/kernel/generic-kernel-image): generische Kernelgrundlagen ersetzen keine gerätespezifischen Treibermodule.

Stand: 2026-11-09. Alle Tizen-/Samsung-Binärdateien bleiben außerhalb des GitHub-Repositories.
