# Forschungsprotokoll – Build 008

Stand: 08.11.2026

## Gesicherte Daten

| Eintrag | Status / Quelle |
| --- | --- |
| Gerät | Samsung Q60T, 50 Zoll; Nutzerangabe |
| Genaue Modellkennung | **GQ50Q60TGUXZG**, Besitzerangabe und offizielle Samsung-Modellseite bestätigt |
| Installierte Firmware | `2743.0`; Nutzerangabe |
| Firmwarefamilie des untersuchten ZIPs | `T-NKLDEUC`, durch `info.txt` bestätigt |
| Vergleichsgerät | `GQ55Q60TGUXZG` mit `T-NKLDEUC-2743.0`, siehe tiz0wn |
| Kernel des Vergleichsimages | ARM Linux 4.1.10 in U-Boot-Legacy-`uImage` |
| Device Tree des Vergleichsimages | `dtb.bin` in Firmware-Container |
| Sicherer eigener Bootweg | Noch nicht nachgewiesen |
| LineageOS-Geräteport | Experimentelles, **nicht baubares** Android-TV-Quellcodegerüst vorhanden |

## Entwickelt

- Standardbibliotheks-CLI, läuft offline auf Linux/Windows/macOS.
- Firmware-ZIP-Inspektion: Hash, Member, Pfadkontrolle, `info.txt`, MSDU-Magic.
- Komponenten-Inventar: Dateigröße, Hash, bekannter Dateityp.
- Validierung von U-Boot-uImage-Header und CRC32.
- Prüfung der Grundstruktur eines Flattened Device Tree.
- Erste Hardware-Erkennung über `model`- und `compatible`-Properties im DTB.
- Erkennung mehrerer eingebetteter Device Trees in einer `dtb.bin`-Datei.
- Generierung von REA-CLI-Vorschlägen, **ohne** Kommandos auszuführen.
- Unit-Tests ausschließlich mit künstlichen Testdateien.
- Original-ZIP 2743.0 vollständig geladen, SHA-256 mit publiziertem Bild identisch.
- Streaming-Extraktion mit Größen- und CRC-Verifikation implementiert.
- Firmware offline in neun Komponenten entschlüsselt; Rohdaten werden nicht verteilt.
- Zwei Device Trees erkannt; Nike-L-Kennung ausgelesen.
- Vier Cortex-A57-CPU-Knoten und `VDFS2007`-Header statisch bestätigt.
- REA hat einen Device Tree mit 365 Knoten/1.739 Eigenschaften analysiert.
- Ausführlicher Bericht mit Blockern in `BUILD002_REPORT.md`.
- FDT-Strukturparser mit sanitierter Differenzanalyse der beiden Nike-L-Varianten.
- **2-GiB- und 1,5-GiB-Firmwareprofile** samt unterschiedlichen CMA-/RAM-Bereichen.
- **130** veränderte Properties, **2** nur im ersten und **4** nur im zweiten Tree.
- Kernel-Scanner: Linux-4.1.10-Banner, IKCONFIG-Marker fehlt, UEP/SMACK-Strings vorhanden.
- VDFS2007-Datenstrom vollständig gelesen und gehasht (ohne Dekomprimierung);
  **320** Dateipfad-Referenzen sowie `/dev/mali0` und `/dev/dri/*` identifiziert.
- Historischer VDFS-Unpacker lokal kompilierbar gemacht, nur unvollständige
  Verzeichnisextraktion; Absturz, **keine erfolgreiche Dateidekomprimierung**.
- **14** synthetische Unit-Tests erfolgreich.
- Neuer technischer Bericht `BUILD003_REPORT.md` und drei zusätzliche
  maschinenlesbare Berichte in `reports/`.

## Build 004 – neu entwickelt

- LineageOS-Android-TV-Produktdefinition, `device.mk` und `BoardConfig.mk`
  unter `porting/device/samsung/nikel/`, mit ausdrücklicher Build-Sperre.
- Zwei JSON-Profile mit geprüften DTB-SHA-256 und Byte-Offsets.
- Automatischer `q60t_portcheck.py`: gleicht die statischen Referenzen
  ab, benennt **10 ungeklärte** Portierungs-Gates und verbietet Flashfreigabe.
- Standard-FDT-`/memory/reg`-Decoder: **1.460,5 MiB** summierte
  deklarierte Bereiche im `nikel-2G`-Referenz-DTB, **1.118,25 MiB** im
  `nikel-1.5G`-Tree. Das ist **keine** Gesamt-RAM-Ermittlung.
- Statusprüfung der DT-Knoten: IR-Knoten `mcirb` und `mcirs` in beiden
  Referenzprofilen `okay`; `cecif` (HDMI CEC) jeweils `disabled`.
- Hardware-/HAL-Matrix zur gezielten Entwicklung von Grafik, Input,
  Audio, Video, Netzwerk, Speicher und TV-Funktionen.
- `q60t_release_audit.py` prüft vor späterer Weitergabe auf Binärdateien,
  unerwartete Dateitypen und einige geheime Schlüsselmarker.
- **24** synthetische Python-Unit-Tests erfolgreich.
- Neue Berichte `BUILD004_REPORT.md`,
  `reports/hardware_2743.0_build004_final.json` und
  `reports/port_preflight_build004_final.json`.

## Build 005 – Kernel, Grafik, Bootkette

- **Originalkernel genau identifiziert:** Linux 4.1.10, ARM32,
  Tizen/Linaro GCC `6.2.1`, Build `02.07.2026 08:47:01 UTC`; neuer
  `reports/kernel_build005.json`.
- `q60t_kernel_build.py`: Standardbibliotheks-Prüfung von lokalen
  Kernelquellen (`Makefile`), ARM-Defconfig, Compiler und separatem
  Output-Build; keine unbelegten Source-Matches oder Image-Builds.
- **Original Samsung GPL-Kernelquellen und passender GCC-Cross-Compiler
  konnten bisher nicht bezogen werden; kein erfolgreicher Kernel-Neubau.**
- `q60t_graphics.py`: liest ELF-Architektur, SHA-256 und Shared-Library-
  Abhängigkeiten von späteren Mali-Modulen/Userspace-Bibliotheken, **ohne**
  diese auszuführen. GPU/DTB/Kernel-Bericht auf exakte Referenz-Hashes
  abgeglichen.
- **GPU-Typ nicht aus `arm,mali-midgard` allein bestimmt:** Externe
  Q60T-Forschung nennt Mali-G51/Bifrost r11p0. Treiber- und HAL-Kompatibilität
  nicht nachgewiesen; `reports/graphics_build005.json` ist blockiert.
- `q60t_boot_safety.py`: inventarisiert `uImage`, `dtb.bin`, `sign.bin`,
  `secos*` und `seret` offline. Referenzdateien nach SHA-256 erkannt,
  U-Boot-CRC geprüft; **keine kryptografische Samsung-Signaturprüfung**.
- `porting/boot-evidence.json` und Boot-Safety-Report: **acht offene
  Recovery-/Test-Boot-Gates**. Kein alternativer Boot, keine Flashfreigabe.
- Detaillierte Unterlagen `porting/KERNEL_BUILD.md`,
  `porting/GRAPHICS_PORT.md`, `porting/BOOTCHAIN.md` und
  `BUILD005_REPORT.md`.
- **32** synthetische Unit-Tests erfolgreich.

## Build 006 – Exaktes 50-Zoll-Zielmodell bestätigt

- Hersteller-Modellcode vom Besitzer: **`GQ50Q60TGUXZG`**.
- Samsungs offizielle Supportseite für exakt dieses Modell führt
  `T-NKLDEUC.zip`, Firmwarefamilie `T-NKLDEUC`, Version **`2743.0`**
  (Samsung Firmwareeintrag `7701730`).
- Das ist derselbe dokumentierte Firmware-Download-Eintrag, der auch für
  die 55-Zoll-Referenzversion verwendet wird. **Nicht nachgewiesen ist
  weiterhin, welche `nikel-2G`-/`nikel-1.5G`-Variante der reale TV nutzt.**
- `porting/model-evidence.json`: überprüfbare Herstellerzuordnung und
  klare Trennung zwischen Firmwarefreigabe und tatsächlichem RAM-/Boardprofil.
- `q60t_portcheck.py`: der exakte Modellcode wird mit dieser
  Herstellerquelle verglichen; andere Modellcodes werden abgelehnt.
- Die Portierungsprüfung hat damit **ein nachgewiesenes Gate, neun offene**;
  keine automatische Build-/Flashfreigabe.
- Boot-Safety bleibt absichtlich blockiert: „exaktes Board + RAM + Recovery“
  ist mehr als nur die Handelsmodellnummer.
- Neuer Bericht `BUILD006_REPORT.md`, neue Vorprüfung
  `reports/port_preflight_build006.json` und **33** erfolgreiche Tests.

## Build 007 – GPL-Source-Audit, Mali-Strategie und CI

- `q60t_source_provenance.py`: Kandidatenarchive als ZIP/TAR rein offline
  hashen, Pfad-/Link-/Größenrisiken inventarisieren und separat die Version
  des lokalen Linux-Quellbaums einordnen. **Keine Hersteller-Provenienz
  allein durch Dateinamen oder Hash behauptet**; keine Extraktion.
- `q60t_kernel_build.py`: in der O=-Buildplanung `.config` nun explizit
  aus der angelieferten ARM-Konfiguration übernehmen. Ein generischer
  Linux-4.1.10-Quellbaum erfüllt **nicht** `samsung_gpl_source_available`.
- `q60t_gpu_strategy.py`: Samsungs Mali-kbase-Stack (`/dev/mali0`) und
  Linux-DRM/Panfrost getrennt auf fehlende Voraussetzungen prüfen.
  Beide Wege bleiben nicht funktionsfähig, solange Kernel/ABI/HAL fehlen.
- `q60t_build007_preflight.py`: integrierte Kernel-/Quell-/Grafik-/Geräte-
  Prüfung, prüft ausdrücklich den Build-Blocker im `BoardConfig.mk`.
- GitHub Actions (`.github/workflows/host-only-tests.yml`) für Python
  3.11/3.12, Tests, Veröffentlichungsaudit und negative Build-Gates.
- **46** synthetische Python-Tests erfolgreich.
- Neue Berichte in `reports/*build007.json` und `BUILD007_REPORT.md`.
- Kein neuer Kernel, kein Android-Systemimage und kein Bootexperiment.

## Build 008 – offizielle Bezugsquellen dokumentiert

- Samsung-GPL-Quellpakete für den Q60T sind durch die Synacktiv-Forschung
  historisch belegt; **eine 2743.0-Nike-L-Paket-ID und die Defconfig fehlen**.
- Der Tizen-CDN listet `gcc-6.2.1.tar.gz` (Compilerquelltext, **keine**
  fertig vorbereitete Samsung-ARM-Toolchain).
- Ein von Samsung Research UK dokumentierter ARM32-Linaro-6.2.1-
  Cross-Compiler aus **2016.11** ist ein **nicht verifizierter Kandidat**
  gegenüber dem Samsung-Referenzbanner `20161213`.
- Arm listet GPL-Bifrost-Treiber **r11p0** mit offizieller Paketkennung
  und MD5. Das ist nur ein Kernelbaustein, keine Android-Grafik-HAL.
- Die Host-Kernel-Prüfung kontrolliert nun ARM32-Target und Versionsmatch
  getrennt und akzeptiert keinen Compiler ohne unabhängigen
  Samsung-Toolchain-Herkunftsnachweis als exakt passend.
- **48** synthetische Python-Tests erfolgreich. Downloadstatus und
  Quellenfindungen stehen in `BUILD008_REPORT.md` und
  `porting/source-candidates-build008.json`.
- **Kein Originalkernel gebaut, keine Mali-HAL portiert, kein Boot getestet.**

## Noch nicht gemacht (und nicht behauptet)

- Den tatsächlichen 50-Zoll-TV untersucht oder kontaktiert.
- Proprietäre Kernel-/Treiber- oder Bootloader-Details dieses TV verifiziert.
- Bootloader entsperrt, Partitionen geändert oder Android gestartet.
- Realen TV-RAM gemessen oder das 50-Zoll-Device-Tree-Profil zugeordnet.
- Tizen-GPU-/Display-Treiber in Android-HALs überführt.

## Nächste Freigabestufe

Ein originales Samsung-Archiv aus der **exakten** Gerätevariante wird
benötigt, sofern dessen Veröffentlichung und lokale Analyse zulässig sind.
Erst nach read-only Hardware- und Signaturprüfung folgt eine Entscheidung
über einen Test-Bootweg und eine LineageOS-Portierung. Kein Flash ohne
separaten, verifizierten Wiederherstellungsplan.
