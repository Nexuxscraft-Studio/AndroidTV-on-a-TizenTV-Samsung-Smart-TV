# Build 002 – Technischer Forschungsbericht

**Datum:** 08.11.2026  
**Status:** Tatsächliche Firmware offline geprüft und entschlüsselt;
**kein bootfähiges LineageOS-Image**.

## 1. Herkunft und Integrität

Die offizielle Samsung-Firmware `T-NKLDEUC.zip` aus dem Releaseordner
`20260915171117277` wurde vollständig heruntergeladen.

| Prüfung | Ergebnis |
| --- | --- |
| Firmwarefamilie | `T-NKLDEUC` |
| Version | `2743.0` (`major 2743`, `minor 0`) |
| Builddatum | 2026-07-02 |
| ZIP-Größe | 1.349.064.478 Bytes |
| SHA-256 | `cb717ed98daf9580eb5b84bccbad5adac82f75dd021ed028f1ee1bb6c4abde32` |
| Vergleich | Exakter Match mit veröffentlichter Analyse des `GQ55Q60TGUXZG` |
| MSDU-Header | `MSDU11`, vorhanden |
| Upgrade-MSD-CRC32 | `4bb5de84`, durch Streaming-Extraktion bestätigt |
| Upgrade-MSD-SHA-256 | `f539f984a9be884ea2816ce91658fde0a90be8311d3c762bc6ce30e3b0e6744a` |

**Wichtig:** Das Image ist eine gemeinsame Samsung-Firmwarefamilie. Dass
ein 50-Zoll-Q60T dieselbe Versionsnummer anzeigt, belegt nicht, dass
die Auswahl des konkreten Device Trees identisch ist. Der vollständige
Modellcode des Nutzers fehlt weiterhin.

## 2. Entschlüsselte Bestandteile

Die `upgrade.msd` wurde nach einer vollständigen, größen- und CRC-geprüften
Extraktion mit dem separat bezogenen Synacktiv-Decryptor analysiert.
**Alle neun Bestandteile wurden offline extrahiert.**

| Datei | Bytes | Rolle (vorläufig) |
| --- | ---: | --- |
| `ddr.init` | 311.312 | DDR-Initialisierung |
| `seret.bin` | 3.137.552 | Boot-/Security-Code |
| `uImage` | 7.041.296 | Linux-Kernel im U-Boot-Legacy-Format |
| `dtb.bin` | 1.564.688 | Gebündelte Device Trees |
| `sign.bin` | 1.040 | Signaturbezogene Daten |
| `secos.bin` | 4.186.128 | Secure-OS-Bestandteil |
| `secos_drv.bin` | 1.040.400 | Secure-OS-Treiber |
| `platform.img` | 1.328.484.368 | Tizen-Hauptsystem (`VDFS2007`-Header bestätigt) |
| `factory_peq.img` | 3.080.208 | Audio-Kalibrierung / SquashFS |

Es wurden **keine** proprietären Samsung-Images in das herunterladbare
Projektpaket aufgenommen, nur Metadaten und eigene Analysewerkzeuge.

## 3. Kernel und Hardware

- `uImage`: ARM-Kernel `Linux-4.1.10`, **nicht komprimiert**.
- Lade- und Einsprungadresse: `0x80008000`.
- SHA-256 `uImage`:
  `6603f3f5082d6ef74471f9233ce17063658daf10e1d9440a8a9c75749a5e72b2`.
- U-Boot-Header-CRC32 **gültig** und Kernel-Payload-CRC32 **gültig**.
- `dtb.bin` SHA-256:
  `9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2`.
- Zwei gültige Device Trees erkannt: Offsets 0 und 86.016 Bytes;
  beide melden `Samsung DTV based on Nike-L SoC`, Größen 48.770 und 49.322 Bytes.
- Kompatibilitätskennungen enthalten `samsung,sdp-nikel`, `arm,mali-midgard`,
  `samsung,sdp-drm`, `samsung,sdp-mfc`, `samsung,sdp-hdmi` und
  `samsung,sdp1202-panel`. Dies sind **Device-Tree-Deklarationen**, keine
  auf einem konkreten 50-Zoll-Gerät gemessenen Komponenten.
- Der untersuchte Device Tree beschreibt **vier CPU-Knoten** (`cpu@0` bis
  `cpu@3`) mit `arm,cortex-a57` und `arm,armv8` – ARMv8-fähige Kerne, obwohl
  das Samsung-Kernelimage derzeit ein 32-Bit-ARM-Image ist.
- Statische Kernel-Bootargumente enthalten `root=/dev/mmcblk0p18`,
  `rootfstype=vdfs` und `ro`. Das sind Firmwareangaben, keine am
  eingeschalteten Gerät bestätigte Partitionsbelegung.

REA (Reverse Engineer Anything) hat den ersten Device Tree erfolgreich
eingelesen: **365 Nodes / 1.739 Properties**, Coverage-Status `complete`.
Ein Versuch, das rohe `uImage` über `rea inspect-artifact` zu öffnen, wurde
von der momentan verwendeten REA-Version mit `unsupported binary format`
abgelehnt. Der eigene U-Boot-Headerprüfer funktioniert dagegen.

## 4. LineageOS-Port: Machbarkeitsanalyse

| Bereich | Einschätzung | Begründung |
| --- | --- | --- |
| Hardwarebeschreibung | Teilweise vorhanden | Device Trees sind lesbar, aber nicht alle Treiberdetails |
| Linux-Kernel | Großer Umbau nötig | Version 4.1.10, stark Samsung-spezifisch |
| Android-Grafik / Oberfläche | Sehr schwierig | Eigene Display-/Mali-Anbindung und Android HWC/Gralloc nötig |
| Audio / Fernbedienung / Tuner | Ungeklärt | Samsung-spezifische Gerätepfade und Nutzerlanddienste |
| Secure Boot / Firmware-Signatur | Kritischer Blocker | Firmwareblobs tragen RSA-Signaturen; ein Leseschlüssel ist kein Signierschlüssel |
| Sicherer Test-Boot | Noch nicht nachgewiesen | Kein freier Bootpfad, kein Recoveryverfahren geprüft |

Google listet in der Android-Common-Kernel-Kompatibilitätsmatrix für aktuelle
Android-Versionen deutlich neuere Kernel als 4.1.10. Das ist kein formaler
Beweis, dass jeder inoffizielle Alt-Kernel-Port unmöglich wäre, aber ein
deutlicher Hinweis auf großen Entwicklungs- und Wartungsaufwand.

**Entscheidung für die weitere Arbeit:** Noch kein Android-Image für den
Samsung-TV bauen oder flashen. Zuerst muss ein reversibler, nicht-destruktiver
Test-Bootweg nachgewiesen werden. Ein Root-Zugang zu Tizen würde die
Signaturprüfung beim Start nicht automatisch aufheben.

## 5. Nächste technische Meilensteine

1. Vollständigen Modellcode des 50-Zoll-Geräts feststellen.
2. Firmware-/Boardkompatibilität der beiden Device Trees zuordnen.
3. Bootkette und Signaturprüfungen weiter analysieren, **offline**.
4. Proprietäre Display-, GPU- und Multimedia-Treiber erfassen; dabei
   Lizenzen beachten und keine geschützten Dateien verteilen.
5. Erst bei belastbarem Test-Bootpfad ein minimales Linux-/Android-Bootexperiment
   erwägen, mit überprüftem Wiederherstellungsweg.

## Quellen

- Samsung Support – Q60T: <https://www.samsung.com/de/support/model/QE50Q60TAUXZG/>
- Synacktiv – Q60T Firmwareanalyse/Decryptor: <https://github.com/synacktiv/samsung-q60t-exploit>
- `tiz0wn` – Vergleichs-Firmware SHA-256 und Analysedokumentation:
  <https://github.com/sebastianspicker/tiz0wn/blob/main/docs/firmware-analysis.md>
- REA: <https://github.com/morluto/rea>
- Google Android Common Kernel-Matrix:
  <https://source.android.com/docs/core/architecture/kernel/android-common>
- Android Hardware Composer / Gralloc:
  <https://source.android.com/docs/core/graphics/implement-hwc>

Die persönlichen Geräte-, Konto- und Netzwerkdaten des Nutzers wurden nicht
ausgelesen; das Gerät wurde nicht kontaktiert.
