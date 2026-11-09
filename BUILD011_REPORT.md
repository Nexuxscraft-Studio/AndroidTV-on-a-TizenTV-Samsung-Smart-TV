# Build 011 – Nike-L-Device-Tree gegen Samsung-Treiberquellen

Stand: **09.11.2026**. Zielmodell: **GQ50Q60TGUXZG**; untersuchte
Referenzfirmware: **T-NKLDEUC 2743.0** (nicht live am TV gelesen).

## Ergebnis

Die aus Build 010 lokal vorliegenden Samsung-Quelltexte wurden erstmals
systematisch mit den `compatible`-Kennungen der zwei Device Trees in der
entschlüsselten Referenzfirmware verglichen. Das neue reine Host-Werkzeug
`q60t_source_compat.py` erzeugte den maschinenlesbaren Bericht
[`reports/source_compat_build011.json`](reports/source_compat_build011.json).

**53 verschiedene Kennungen** aus den ausgewählten Hardwarekategorien:

| Befundklasse | Anzahl | Bedeutung |
| --- | ---: | --- |
| `KERNEL_CODE_REFERENCE` | 11 | Kennung wörtlich in einer Kernel-C-/Header-/Assembler-Quelldatei |
| `MEDIA_CODE_REFERENCE` | 11 | Kennung wörtlich in Samsung-Media-/Display-C-/Header-/Assembler-Code |
| `DTS_DECLARATION_ONLY` | 30 | Kennung nur in DTS/DTSI-Quelltexten gefunden |
| `NO_LITERAL_SOURCE_REFERENCE` | 1 | Keine wörtliche Referenz in den gescannten Quelltexten |

Ein Quelltexttreffer beweist **weder ein funktionsfähiges Treiber-Binding
noch Android-Unterstützung**. Eine DTS-Deklaration allein beweist auch
nicht, dass der dazugehörige Treiber in diesem Quellarchiv vorliegt.

## Besonders relevante konkrete Treffer

| Hardware | DT-Kennung | Fundstelle | Aussage |
| --- | --- | --- | --- |
| Board | `samsung,sdp-nikel` | Kernel: `arch/arm/mach-sdp/board-nike-dt.c`, `drivers/soc/sdp/common.c` | Nike-L-Erkennung ist vorhanden |
| GPU | `arm,mali-midgard` | Media: `sdp_gpu_nike/drivers/gpu/arm/midgard/mali_kbase_core_linux.c` | Mali-Kernelcode vorhanden; GPU-ABI/Android-EGL ungeprüft |
| Display | `samsung,sdp-drm` | Media: `sdp_drm_nike/sdp_drm_drv.c` | Samsung-Display-Kernelcode vorhanden; kein Android-Composer |
| Panel | `samsung,sdp1202-panel` | Kernel: `drivers/gpu/drm/panel/panel-sdp.c` | Eine Panel-Code-Referenz vorhanden; Panelprofil nicht verifiziert |
| HDMI | `samsung,sdp-hdmi` | Media: `sdp_hdmi_nike/sdp_hdmi_main.c` | HDMI-Code-Referenz vorhanden |
| Video | `samsung,sdp-mfc` | Media: `sdp_codec_nike/sdp_mfc.c` | MFC-Codec-Kernelcode vorhanden; kein Android-MediaCodec/Codec2 |
| Audio | `samsung,sdp-mc-audio` | Media: `sdp_alsa_nike/sdp_audio_machine.c` | ALSA-/Audio-Code-Referenz vorhanden; keine Android-Audio-HAL |
| Infrarot | `samsung,sdp-mc-irb` | Kernel: `drivers/soc/sdp/sdp_micom_irb.c` | IR-Treiberreferenz vorhanden |
| HDMI-Umschaltung | `samsung,tztv-hdmi-sw` | **Kein wörtlicher Treffer** | Andere Benennung, externe Implementierung oder fehlendes Paket möglich; Ursache offen |

Die Medienquellen enthalten außerdem passende Treiberreferenzen zu
`samsung,sdp-frc-l`, `samsung,sdp-frc-8k` und `samsung,sdp_pqe_frc`.
Das macht die Panel-/Video-Pipeline besser nachvollziehbar, ersetzt
aber kein Testsignal und keine Android-Grafikanbindung.

## Daten und Prüfumfang

| Eingabe | Identität / Prüfumfang |
| --- | --- |
| Referenz-`dtb.bin` | SHA-256 `9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2`; genau zwei gültige DTs |
| Samsung-Quell-ZIP | SHA-256 `3e38ad1baf54be8ed91c1c18b2c3137692c28e01ca894db9690f632a1fbd3bad` (vom Nutzer bereitgestellt) |
| Kernelquelle | `linux-4.1.10-tizen5.5.tgz` aus Build 010; 41.968 Quellcodedateien und 534.653.495 Bytes gelesen |
| Mediaquelle | `tztv-media-nike.tgz`; 1.293 Quellcodedateien und 63.371.652 Bytes gelesen |
| Dateisystemgrenzen | 9 Kernel-Symlinks übersprungen, 1 übergroße Mediendatei nicht eingelesen |
| ARM-Defconfigs | Neun `Nike.M-..._defconfig`-Varianten; **keine** `Nike.L`-Datei nachgewiesen |

Der Scanner liest ausschließlich Dateien mit bekannten Quelltext-Endungen,
begrenzt Dateianzahl und -größe, ignoriert Symlinks und sucht nach ganzen
Kennungen statt ungeprüften Teilstrings. Er führt **keinen** fremden
Quellcode aus. Sein Abgleich kann dadurch bewusst unvollständig sein:
Makros, generierte Tabellen, nicht mitgelieferte Binärmodule oder
abweichende Bezeichnungen werden nicht zuverlässig erkannt.

## Testlauf und Sicherheitsstatus

- `python3 -m unittest discover -s tests -q`: **53 synthetische Tests
  erfolgreich** (Build 010: 48).
- Alle Ausgaben deklarieren `status: ANALYSIS_ONLY`,
  `android_hal_verified: false`, `kernel_built: false` und
  `flash_authorized: false`.
- Das Quellpaket ist **nicht** als exakter Patchstand für den
  Firmwarekernel 2743.0 bestätigt; die `Nike.M`-Konfiguration ist
  weiterhin nur ein Kandidat.
- **Kein** Kernel und **kein** Android-Image wurde gebaut, **kein**
  Bootloader oder TV kontaktiert, kein Flash-/Bootversuch durchgeführt.

## Nächste Schritte innerhalb Phase 2A

1. `Nike.M`-Defconfig mit dem tatsächlich enthaltenen Treiberstack und
   den Nike-L-DTS-Bäumen vergleichen; mögliche Kernel-Buildfehler
   zunächst nur auf einem isolierten Entwicklungscomputer ermitteln.
2. Display-, GPU- und MFC-ABI sowie proprietäre Tizen-Bibliotheken
   getrennt von den fehlenden Android-HAL-Schichten dokumentieren.
3. Exakten 2743.0-Kernelpatchstand, reales Board-/RAM-Profil und
   Toolchain weiter prüfen.
4. **Phase 2B bleibt gesperrt:** Ohne gesicherten alternativen Bootweg,
   herstellerkonforme Signaturkette und nachgewiesenes Recovery/Rollback
   keine Arbeit am laufenden Fernseher.
