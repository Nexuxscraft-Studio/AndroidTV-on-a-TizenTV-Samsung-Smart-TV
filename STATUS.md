# Forschungsprotokoll – Build 015

Stand: 09.11.2026

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

## Build 009 – konkretes Samsung-Originalarchiv identifiziert

- Samsung OSSRC selbst zeigt für die Q60T-Suche den Eintrag
  `20_DTV_NikeL`, Modellmuster **`GQ**Q60T**`**, Releaseversion `1000`.
- Zwei konkrete Downloads sind gelistet: `20_DTV_NikeL.txt` (61 B) und
  **`20_DTV_NikeL.zip` (708,82 MB)**.
- Der Download hinter dem Portal-Dialog wurde durch eine
  Browser-Sicherheitsbeschränkung gestoppt. **Kein Originalarchiv
  empfangen, kein Kernel-Build gestartet**. Keine Umgehung.
- Die genaue Fundstelle und die nächsten Prüfungen stehen in
  `BUILD009_REPORT.md`. Das bestehende Kandidaten-JSON wurde mit
  überprüften Portalmetadaten ergänzt.
- Firmware-2743.0-Gleichheit, Sourcehash, Defconfig und Rollback
  bleiben **ungeklärt**.

## Build 010 – erhaltenes Quellarchiv untersucht

- Benutzer hat das Samsung-Paket `20_DTV_NikeL.zip` über einen eigenen
  HTTPS-Link bereitgestellt. Es wurde vollständig heruntergeladen:
  **743308262 Bytes**, SHA-256
  `3e38ad1baf54be8ed91c1c18b2c3137692c28e01ca894db9690f632a1fbd3bad`.
- Beide ZIP-Ebenen sind technisch intakt. Die innere enthält 116
  Pakete/Einträge; der Kernel `linux-4.1.10-tizen5.5.tgz` enthält
  **54173** Einträge.
- Erstmals liegt der **tatsächliche Samsung-Q60T-Quellbaum lokal** vor:
  Kernel 4.1.10 mit `samsung,sdp-nikel` in Board- und SoC-Code,
  Mali-kbase, VDFS sowie zusätzliche Media-/Hardwarequellen.
- Die mitgelieferte ARM-Defconfig heißt `Nike.M-Tizen_release_defconfig`;
  **keine** Datei `Nike.L-Tizen_release_defconfig` gefunden. Der
  Paket-Begleittext verlinkt auf `NikeM`; genaue Freigabezuordnung
  bleibt zu prüfen.
- Der Compiler ist als Quellpaket mit Bauskripten, nicht als verifizierte
  fertige Toolchain vorhanden. **Kein Kernelbuild und kein Bootversuch.**
- Alle Einzelheiten und Hashwerte in `BUILD010_REPORT.md`.

## Build 011 – Firmware-DTB und Quelltreiber abgeglichen

- `q60t_source_compat.py`: vergleicht **53 verschiedene `compatible`-Kennungen**
  aus zwei Referenz-Device-Trees mit den extrahierten Kernel- und
  Media-Quellen; ausschließlich lokale, begrenzte Textanalyse.
- **11** Kennungen mit Kernel-Code-Referenz, **11** mit Media-Code-
  Referenz, **30** nur mit DTS-Deklaration, **1** ohne wörtlichen Treffer
  (`samsung,tztv-hdmi-sw`).
- Besonders relevant: `samsung,sdp-nikel` im Kernel, `arm,mali-midgard`
  im GPU-Code, `samsung,sdp-drm` im Display-Code und `samsung,sdp-mfc`
  in Samsung-MFC-Quellen. **Keine Android-HAL daraus nachgewiesen.**
- Nur `Nike.M`-Defconfig-Varianten vorhanden; exakte 2743.0-Herkunft,
  Toolchain, Rebuild und sichere Bootkette bleiben offen.
- **53** synthetische Tests bestanden. Alle Ergebnisse in
  `BUILD011_REPORT.md` und `reports/source_compat_build011.json`.

## Build 012 – Android-Kconfig und Binder-ABI nachgestellt

- Alle **9** Samsung-Nike-ARM-Defconfigs und **25** Konfigurationsziele
  statisch mit 1.072 Kconfig-Dateien abgeglichen.
- Binder, Ashmem, Memcg und SELinux sind in allen neun Profilen
  deaktiviert. Release-Konfiguration hat außerdem ION und OverlayFS
  ausgeschaltet; die beiden moderneren Symbole BinderFS und DMA_HEAPS
  sind nicht als ARM-Kconfig-Deklaration vorhanden.
- Neue `q60t_android_kernel.py`, `q60t_kernel_stage.py` und
  `q60t_kconfig_verify.py`: reproduzierbare Host-Konfiguration
  mit unmodifiziertem Vendor-Sicherheitsprofil.
- **Zwei echte Host-`make olddefconfig`-Läufe erfolgreich**, keiner
  davon ein Kernel- oder Android-Image-Build.
- Kritischer Fund: die namenlose `ANDROID_BINDER_IPC_32BIT`-Option
  wird durch Samsung-Kconfig ohne Patch wieder `y`. Ein **Ein-Zeilen-
  Patch ausschließlich in einer Schattenkopie** setzt sie auf `n`.
  Die beiden aufgelösten `.config`-Dateien unterscheiden sich genau
  in dieser einen Option; Binder bleibt eingeschaltet.
- **72 synthetische Tests erfolgreich**, separate Kconfig-
  Prüfberichte in `reports/*build012.json`; ausführlicher
  [`BUILD012_REPORT.md`](BUILD012_REPORT.md).
- Kein ARM-Cross-Compiler vorhanden, keine Kernelkompilierung,
  keine Android-HAL, **kein Zugriff auf den TV**.

## Build 013 – ARM32-Linux-Kernel erstmals erfolgreich kompiliert

- Original-Samsung-Archiv erneut per SHA-256 bestätigt; Originalquellen
  bleiben unverändert.
- Offizielle TI-Linaro-Cross-Toolchain GCC 6.2.1 (20161016) heruntergeladen,
  Herausgeber-MD5 bestätigt. **Nicht** mit Samsungs in `BUILD.sh`
  verlangter Compilerkennung `20161213` gleichsetzen.
- Experimentelle `Nike.M`-Android-Kconfig mit Binder-ABI-Patch und
  unveränderten Smack-/SFD-Sicherheitsoptionen erfolgreich aufgelöst.
- Nur in Schattenkopien: Host-DTC-`yylloc`-Kompatibilitätspatch,
  ausdrücklich künstlicher Versionsheader, Debug-Header-Include-Pfad.
- **Echter `make zImage` mit ARM32-Linaro-6.2.1 erfolgreich**;
  zweiter automatisierter Testlauf ebenfalls erfolgreich (Exitcode 0).
- Neuer wiederholbarer Builder `q60t_compile_probe.py`, Bericht
  `reports/arm32_compile_build013.json`, Anleitung
  `porting/KERNEL_COMPILE_PROBE.md`.
- **80 synthetische Tests** und Projekt-Release-Audit **PASS**.
- Kein originales Nike-L-Profil, keine verifizierte 2743.0-Buildidentität,
  keine Android-HAL, keine Freigabe zum Booten/Flashen.
- Details: `BUILD013_REPORT.md`.

## Build 014 – Automatisierte GitHub-Quellpakete

- `q60t_package_release.py`: deterministische, auditierte ZIP-Erstellung
  mit Dateimanifest und SHA-256-Prüfsumme; keine Samsung-Binärdateien.
- Bestehende Zieldateien bleiben geschützt; das Ziel muss außerhalb des
  Projektbaums liegen. Ein Sicherheits-Audit ist vor jedem Paket Pflicht.
- GitHub Actions führt bei Commits auf `main` und beim manuellen Start
  Tests, die weiterhin negativen Boot-/Flash-Gates und die Paketierung
  aus. GitHub-Artefakte werden 30 Tage vorgehalten.
- Bei bewusst gepushten `v*`-Tags wird nach erfolgreichem Paketierungsjob
  ein als experimentell markiertes GitHub-Prerelease erstellt.
- **88 synthetische Tests erfolgreich**; vollständige Dokumentation
  `BUILD014_REPORT.md`.
- **Kein** Android-ROM, kein installierbares Tizen-Update und keine
  Freigabe zur Ausführung auf dem Fernseher.

## Build 015 – Echte SELinux- und Initramfs-Host-Kernelbuilds

- Zwei Opt-in-Profile im `q60t_compile_probe.py`: `selinux-lab` mit
  `SECURITY_SELINUX=y`, `DEFAULT_SECURITY="selinux"` und
  `android-bootlab` zusätzlich mit `BLK_DEV_INITRD=y`, `IKCONFIG=y`,
  `IKCONFIG_PROC=y`. Im Standardprofil bleibt Samsung-SMACK/SFD aktiv.
- **Beide neuen ARM32-`zImage`-Compilerläufe erfolgreich** (Exitcode 0),
  `3.685.024` bzw. `3.720.480` Bytes, jeweils verifizierte `.config`.
  Die Compiler-Binärdateien liegen außerhalb des Projekt-Repositories.
- `q60t_kernel_readiness.py` vergleicht eine **begrenzte, historische**
  Android-Basis-Teilmenge; aktiviert sind 7/12 (Tizen), 9/12 (SELinux-Lab)
  bzw. 12/12 (Bootlab). **Keines** ist ein funktionierendes Android.
- Im Treiber weiterhin **nur eine globale Binder-Kontextverwaltung**;
  separate Binder-IPC-Domänen sind nicht verifiziert. Android 14
  unterstützt offiziell nicht die Kernelbasis Linux 4.1.10.
- Neuer Bericht `BUILD015_REPORT.md`, technische Einordnung
  `porting/ANDROID_COMPATIBILITY.md` und drei JSON-Reports.
- **96** synthetische Unit-Tests erfolgreich; Boot-/Flashfreigabe
  weiter **BLOCKED**, kein Fernseher kontaktiert.

## Noch nicht gemacht (und nicht behauptet)

- Den tatsächlichen 50-Zoll-TV untersucht oder kontaktiert.
- Proprietäre Kernel-/Treiber- oder Bootloader-Details dieses TV verifiziert.
- Bootloader entsperrt, Partitionen geändert oder Android gestartet.
- Realen TV-RAM gemessen oder das 50-Zoll-Device-Tree-Profil zugeordnet.
- Tizen-GPU-/Display-Treiber in Android-HALs überführt.

## Nächste Freigabestufe

Das von Samsung für die Q60T-Familie bereitgestellte **Nike-L-Quellarchiv
ist jetzt vorhanden**. Für den exakten Firmwarestand 2743.0 müssen noch
Quell-/Defconfig-/Toolchain-Gleichheit, reale Boarddaten und eine
unabhängig geprüfte Wiederherstellung geklärt werden. Statische
Portierungsarbeiten dürfen beginnen; **kein Flash oder eigener Boot**
ohne separat verifizierten sicheren Rückweg.
