# Samsung Q60T → LineageOS: Offline-Labor (Build 024)

Ein **nicht-invasives** Arbeitsprojekt zur Untersuchung der Samsung-Q60T-Firmware
`T-NKLDEUC 2743.0` als Vorbereitung einer möglichen LineageOS-/Android-TV-Portierung.

**Build 024:** Offizieller LineageOS-22.2-(Android-15)-`system/core`-Quellaudit,
ARM64-`/init`-ELF-Prüfung, QEMU-Initramfs-Staging und streng korrelierte
Gastloganalyse. **Noch kein echtes LineageOS-`/init` ausgeführt und kein Android-
oder TV-Boot nachgewiesen.** [BUILD024_REPORT.md](BUILD024_REPORT.md).

**Build 018 wurde im separaten Proxmox/QEMU-Labor erfolgreich getestet:**
ARM32-Linux-4.1.10-Boot, statischer Gast-`/init`, drei Binder-Version-IOCTLs
und ein echter Binder-Ping/Pong zwischen zwei Gastprozessen. Das ist noch
kein vollständiger Android-Userspace. Siehe [BUILD018_REPORT.md](BUILD018_REPORT.md).

**Experimenteller Build 019:** `feature/build019-android-userspace-preflight`
ergänzt einen ARM32-Kernel-ABI-Smoke-Test für Android-relevante Grundlagen
und trennt sie ausdrücklich von unbestätigten Samsung-HALs.
[BUILD019_REPORT.md](BUILD019_REPORT.md). Der Build-019-Gastlauf steht noch aus.
`main` und der reale Samsung-TV bleiben unverändert.

## Aktueller Stand

- Zielgerät: **Samsung GQ50Q60TGUXZG**, 50 Zoll (vom Eigentümer angegeben,
  [von Samsung offiziell als Q60T gelistet](https://www.samsung.com/de/support/model/GQ50Q60TGUXZG/)).
- Auf dem TV angezeigte Firmwareversion: `2743.0` (vom Eigentümer bestätigt).
- Für das **andere** Modell `GQ55Q60TGUXZG` wurde dieselbe Versionsnummer
  unter der Firmwarefamilie `T-NKLDEUC` untersucht. Build 002 hat das
  entsprechende Original-ZIP anhand von SHA-256 **exakt verifiziert** und
  offline entschlüsselt. Build 003 liefert **zwei differenzierte
  Firmware-Device-Trees mit den Profilnamen `nikel-2G` / `nikel-1.5G`**,
  Kernel-UEP-Strings und einen vorsichtigen VDFS-Pfadsurvey. Samsung
  bietet die **gleiche Firmwarefamilie und Version 2743.0 für das genaue
  50-Zoll-Modell** an; der tatsächlich verwendete RAM-Device-Tree
  bleibt dennoch unbekannt.
- Build 004 enthält erstmals ein **experimentelles LineageOS-Android-TV-
  Produktgerüst** unter `porting/device/samsung/nikel/`, zwei getrennte
  Hardwareprofile und einen überprüfbaren `portcheck`. Die beobachteten
  `memory/reg`-Abschnitte und DT-Statusfelder (IR `okay`, CEC `disabled`)
  sind im neuen Hardwarebericht dokumentiert.
- Build 005 bearbeitet die drei technischen Hauptschwierigkeiten:
  **Kernel-Reproduktion**, **Grafik-/Mali-ABI-Analyse** und
  **sicheren Alternativboot samt Rollback**. Die neuen Prüfwerkzeuge und
  Dokumente befinden sich in `porting/`. Ergebnisse sind weiterhin
  blockiert, wenn echte Quelltexte, HAL-Treiber oder Recovery-Belege fehlen.
- Build 006 bestätigt das **exakte Zielmodell und dessen offizielle
  Samsung-Firmwarezuordnung**. Der Modellcode wurde im Portcheck
  festgeschrieben, während die RAM-/Boot-/HAL-Nachweise offen bleiben.
- Build 007 bringt einen **GPL-Quellarchiv- und Hash-Prüfer**, einen
  präzisierten Kernel-Buildplan, **getrennte Mali-kbase-/Panfrost-Wege**,
  einen integrierten Fail-Closed-Check und GitHub-CI für synthetische
  Tests. **Ein Samsung-Kernel wurde mangels passendem Originalquellpaket
  und Toolchain weiterhin nicht erfolgreich gebaut.**
- Build 008 dokumentiert **konkrete offizielle Fundstellen** für Tizen-
  GCC-6.2.1-Quellen, einen Linaro-Cross-Compiler-Kandidaten und Arms
  Mali-Bifrost-r11p0-Kerneltreiber. Die exakte Samsung-Nike-L-
  GPL-Kernelquelle und Defconfig sind **nicht bezogen**. Eine strengere
  Compilerprüfung verhindert einen falschen „passenden Toolchain“-Befund.
- Build 009 bestätigt direkt im **Samsung Open Source Release Center**
  das offizielle Paket **`20_DTV_NikeL.zip` (708,82 MB)** für die
  Modellfamilie `GQ**Q60T**`. Die Portalversion `1000` ist **nicht**
  als zur Firmware `2743.0` passend bestätigt. Der browserbasierte
  Download blieb gesperrt; das Originalarchiv ist nicht lokal vorhanden.
- Build 010: Der Besitzer hat das zuvor gefundene Samsung-Paket über
  HTTPS verfügbar gemacht. Die beiden ZIP-Ebenen wurden fehlerfrei
  geprüft. Darin liegen echte **Linux-4.1.10-Nike-L-Quelltexte**, Samsung-
  Treiber, eine `Nike.M`-ARM-Defconfig und Compilerquellen. Das ist der
  **erste tatsächliche Quellcodefund**, aber noch kein Beleg für
  den exakten Kernelpatchstand der Firmware 2743.0 oder ein baubares ROM.
  Details und Hashes: [BUILD010_REPORT.md](BUILD010_REPORT.md).
- Build 011: **53 Hardware-`compatible`-Kennungen** aus zwei Firmware-
  Device-Trees gegen die tatsächlichen Samsung-Kernel- und Mediaquellen
  abgeglichen. **22** Kennungen haben eine C-/Header-Code-Referenz,
  **30** nur einen DTS-Treffer und **eine** keine wörtliche Referenz.
  Unter den Treffern sind der Nike-L-Boardcode, Mali-Kernelcode, MFC-
  Videocodec und Samsung-Displaycode. Das beweist **keine** Android-HAL
  und keinen sicheren Boot. Details: [BUILD011_REPORT.md](BUILD011_REPORT.md).
- Build 012: Die tatsächlich vorliegenden **neun Nike-Kernelprofile**
  mit **25** Android-/Gerätetreiber-Optionen abgeglichen. Ein Host-Kconfig-
  Lauf hat den alten automatisch erzwungenen Binder-32-Bit-Modus
  aufgedeckt. Ein **Ein-Zeilen-Patch nur in einer Schattenkopie** und
  ein zweiter Kconfig-Lauf bestätigten die Korrektur: Beide resultierenden
  Konfigurationen unterscheiden sich exakt in der Binder-ABI-Option.
  **72 Tests** bestanden; noch kein Kernel kompiliert oder TV kontaktiert.
  Details: [BUILD012_REPORT.md](BUILD012_REPORT.md) und
  [porting/ANDROID_KERNEL_BRIDGE.md](porting/ANDROID_KERNEL_BRIDGE.md).
- Build 013: **Erstmals wurde ein echter ARM32-`zImage` aus dem
  Samsung-4.1.10-Quellpaket erfolgreich auf einem Host kompiliert**, danach
  mit dem neuen `q60t_compile_probe.py` unabhängig erneut. Dafür wurde
  eine von TI veröffentlichte Linaro-GCC-6.2.1-Toolchain mit verifizierter
  MD5-Prüfsumme verwendet. Zwei minimale Patches und ein ausdrücklich
  synthetischer Versionsheader betreffen **nur Schattenkopien**.
  **80 Tests** bestehen. Ein erfolgreicher Compilerlauf ist keine
  installierbare Samsung-Firmware und kein lauffähiges Android.
  Details: [BUILD013_REPORT.md](BUILD013_REPORT.md) und
  [porting/KERNEL_COMPILE_PROBE.md](porting/KERNEL_COMPILE_PROBE.md).
- Build 014: Neue **automatische GitHub-Actions-Paketierung** prüft bei
  jedem Push auf `main` alle synthetischen Tests, Quellcode-Audit und
  die weiterhin gesperrten Boot-/Flash-Gates. Sie erzeugt ein
  **reproduzierbares Quellcode-ZIP samt SHA-256 und Dateimanifest**.
  Bei einem eigens gepushten Versionstag `v*` wird nach erfolgreicher
  Prüfung zusätzlich ein als experimentell markiertes **Prerelease**
  veröffentlicht. **Keine Samsung-Firmware und kein gebauter Kernel**
  werden dabei mitgeliefert. Details: [BUILD014_REPORT.md](BUILD014_REPORT.md).
- Build 015: Zwei neue **ARM32-Kernelprofile erfolgreich kompiliert**:
  `selinux-lab` setzt SELinux als Standard-LSM, und `android-bootlab`
  aktiviert zusätzlich Initramfs und die auslesbare Kernelkonfiguration.
  Eine neue Offline-Prüfung zeigt trotz **12/12 ausgewählter alter
  Kconfig-Merkmale** im Bootlab weiterhin fundamentale Android-Blocker:
  keine nachgewiesenen separaten Binder-Kontexte, Kernel 4.1.10 außerhalb
  der Android-14-Kernelmatrix, keine Android-HAL und keine sichere
  Samsung-Bootkette. **96 synthetische Tests** erfolgreich. Details:
  [BUILD015_REPORT.md](BUILD015_REPORT.md) und
  [porting/ANDROID_COMPATIBILITY.md](porting/ANDROID_COMPATIBILITY.md).
- Build 016: Ein weiteres, streng opt-in **Binder-Dreifachkontext-
  Experiment** erzeugt im Schattenquellbaum drei unterschiedliche
  `/dev/binder`-, `/dev/hwbinder`- und `/dev/vndbinder`-Manager-Kontexte.
  Der **echte ARM32-Kernelbuild ist erfolgreich** (3.720.688 Bytes),
  jedoch **ohne** Binder-Laufzeittest, verifizierte Android-ABI oder
  Samsung-Hardwarefreigabe. Der Diff wird nur im lokalen Workspace
  erzeugt. **103** synthetische Tests grün. Details:
  [BUILD016_REPORT.md](BUILD016_REPORT.md) und
  [porting/BINDER_MULTICONTEXT_LAB.md](porting/BINDER_MULTICONTEXT_LAB.md).
- Build 017: **Reproduzierbarer Binder-UAPI-Abgleich** gegen einen festen
  offiziellen Android-Common-Kernel-Header: 16 untersuchte spätere
  API-Merkmale fehlen im Samsung-Kernel, zusätzlich sind zwei deklarierte
  ältere IOCTLs im Treiber nicht implementiert. Ein kleines eigenes
  **ARM32-C-ABI-Probeobjekt wurde erfolgreich cross-kompiliert**; es
  testet Strukturgrößen und Protokollkonstanten, nicht den Laufzeitbetrieb.
  **110 synthetische Tests** grün. Details: [BUILD017_REPORT.md](BUILD017_REPORT.md)
  und [porting/BINDER_UAPI.md](porting/BINDER_UAPI.md).
- Ein echtes Android-Bootimage, ein entsperrter Bootloader und passende
  Android-Hardwaretreiber **existieren hier noch nicht**.
- Neue Erkenntnisse, Treibermatrix und offene Sicherheitsbedingungen:
  [BUILD009_REPORT.md](BUILD009_REPORT.md),
  [BUILD008_REPORT.md](BUILD008_REPORT.md),
  [BUILD007_REPORT.md](BUILD007_REPORT.md),
  [BUILD006_REPORT.md](BUILD006_REPORT.md) sowie
  [BUILD005_REPORT.md](BUILD005_REPORT.md). Die Portierungswege stehen in
  [porting/KERNEL_BUILD.md](porting/KERNEL_BUILD.md),
  [porting/GRAPHICS_PORT.md](porting/GRAPHICS_PORT.md) und
  [porting/BOOTCHAIN.md](porting/BOOTCHAIN.md).
  Vorherige Fortschritte stehen in [BUILD004_REPORT.md](BUILD004_REPORT.md),
  [BUILD003_REPORT.md](BUILD003_REPORT.md); der erste Forschungsstand
  bleibt in [BUILD002_REPORT.md](BUILD002_REPORT.md) erhalten.

## Sicherheitsgrenzen

Das Labor liest ausschließlich lokale Dateien. Es hat **keine Netzwerk-, SDB-,
ADB-, Flash-, Root- oder Schreibfunktionen für den Fernseher**. Insbesondere
werden keine Samsung-Firmwaredateien verändert oder signiert. `--output`
schreibt bei Analysebefehlen nur einen lokalen JSON-Bericht; der getrennte
Befehl `extract-member` erstellt eine neue lokale Kopie eines ZIP-Eintrags,
nach Größe/CRC-Verifikation und ohne vorhandene Dateien zu überschreiben.

Firmwaredateien von Dritten werden nicht beigelegt. Für die Analyse ist
die passende offizielle Firmware von der Samsung-Supportseite nötig.

## Voraussetzungen

- Python 3.10 oder neuer; für die Basisfunktionen **keine Pip-Pakete**.
- Optional später: REA, Ghidra, Binwalk, Unblob, `dtc`.
- REA wurde in der Analyse bereits einmal mit `npx rea-agents` auf dem
  `dtb.bin` erfolgreich getestet (365 Nodes/1.739 Properties).
- Für das Entschlüsseln eines offiziell bezogenen `upgrade.msd`: separat
  Synacktivs dokumentiertes `firmware/decrypt.py`. Der Decryptor ist hier
  weder enthalten noch wird er automatisch ausgeführt.
- Für die neuen Build-003-Funktionen ebenfalls **keine Abhängigkeiten**.
  Der VDFS-Pfadsurvey liest Rohbytes; er ist **kein Dateisystem-Entpacker**.
- Build 004 benötigt ebenfalls keine zusätzlichen Python-Pakete. Die
  Dateien unter `porting/` sind **Forschungs-Quellcode**, keine lauffähige ROM.
- Build 005: Kernel-Prüfung, ELF-Metadaten und Boot-Evidence-Audit
  funktionieren ebenfalls nur mit Python-Standardbibliothek. Eine reale
  Kernelkompilierung erfordert zusätzlich den **exakten** Samsung-
  GPL-Quellbaum und passenden ARM-Cross-Compiler; ein Samsung-Nike-
  Quellpaket liegt seit Build 010 vor, der **exakte 2743.0-Patchstand
  sowie der passende Cross-Compiler** fehlen weiterhin.
- Build 007: integrierte Prüfungen benötigen weiterhin nur die
  Python-Standardbibliothek; CI testet unter Python 3.11 und 3.12.
- Build 008: Quellenverzeichnis und Tests bleiben offline und benötigen
  keine zusätzlichen Pakete; **kein automatischer Fremdquellendownload**.
- Build 011: Die originalen, lokal entpackten Samsung-Quellen sind
  optionale Eingaben; sie werden weder ins Projekt eingecheckt noch
  ausgeführt. Der statische Abgleich benötigt nur Python.
- Build 012: Der Konfigurationsvergleich selbst ist rein lesend.
  Ein optionaler `make olddefconfig`-Versuch **führt Samsung-Kbuild-
  Hilfsprogramme aus** und darf nur in isolierter Entwicklungsumgebung
  mit getrenntem `O=`-Verzeichnis erfolgen; kein solcher Schritt ist
  mit einem Flash- oder Android-Image-Build gleichzusetzen.
- Build 013: Der ausdrücklich angeforderte Kernel-Compile-Test führt
  Quell-Kbuild-Hilfsprogramme und Cross-Compiler **nur auf einem
  Entwicklungsrechner** aus. Die CLI erstellt Kopien der Samsung-
  Quellen und eine separate Buildausgabe, berührt aber keinen Fernseher.
- Build 014: Die CI lädt niemals originale Samsung-Dateien nach und
  kompiliert keinen Kernel. Ihr Release-Artefakt enthält nur geprüfte
  Projekt-Textquellen; Veröffentlichungen sind auf Versionstags beschränkt.
- Build 015: Auch die neuen SELinux-/Initramfs-Experimente nutzen nur
  getrennte Host-Schattenquellen. **Weder deren zImages noch ihre
  Build-Logs gehören ins GitHub-Release oder auf den Fernseher.**
- Build 016: Das neue Binder-Overlay wird ausschließlich im geschützten
  Schattenquellbaum aktiviert; Quellhash und Quellmarker werden streng
  geprüft. Noch keine Runtime- oder Gerätevalidierung.
- Build 017: Der neue ARM32-C-Quellcode ist **nur als eine explizit
  zugelassene eigene UAPI-Compilerprobe** im Audit freigegeben.
  Samsung-Quellcode, Gerätefirmware und ABI-Testobjekte werden nicht
  ins Quell-Release aufgenommen.

## In fünf Minuten prüfen

```bash
python3 q60t_lab.py firmware-info /pfad/zu/T-NKLDEUC.zip

# Robuste lokale Extraktion der großen MSD-Datei:
python3 q60t_lab.py extract-member /pfad/zu/T-NKLDEUC.zip \
  --member T-NKLDEUC/image/upgrade.msd --output /pfad/zu/neue-upgrade.msd

# Nach einer extern durchgeführten Extraktion/Entschlüsselung:
python3 q60t_lab.py inventory /pfad/zu/decrypted

# Offline-Arbeitsschritte für REA aus den tatsächlich vorhandenen Dateien:
python3 q60t_lab.py rea-plan /pfad/zu/decrypted

# Zwei im Firmwarebundle enthaltene Hardwareprofile unterscheiden:
python3 q60t_lab.py hardware-report /pfad/zu/decrypted/dtb.bin

# Kernel-Banner, eingebettete Konfiguration und Sicherheitsstrings prüfen:
python3 q60t_lab.py kernel-report /pfad/zu/decrypted/uImage

# Unverifizierte Dateipfad-Strings in VDFS2007 suchen (ohne Entpacken):
python3 q60t_lab.py rootfs-strings /pfad/zu/decrypted/platform.img

# Verifizierte Offline-Profile mit der noch gesperrten Portierung abgleichen:
python3 q60t_portcheck.py --project porting \
  --hardware-report reports/hardware_2743.0_build004_final.json

# Vor späterer Veröffentlichung prüfen, dass keine Firmware/Secrets enthalten sind:
python3 q60t_release_audit.py .

# Vollständige synthetische Test-Suite:
python3 -m unittest discover -s tests -v

# Geprüftes Quell-ZIP außerhalb des Projektverzeichnisses erstellen:
mkdir -p /pfad/zu/NEUEM-dist
python3 q60t_package_release.py --source . \
  --output /pfad/zu/NEUEM-dist/q60t-research.zip --label build017
# Dazu entstehen q60t-research.manifest.json und q60t-research.sha256.
# Im Ausgabeordner: sha256sum -c q60t-research.sha256

# Build 005: Kernel-Source-, Toolchain- und Defconfig-Vorprüfung:
python3 q60t_kernel_build.py

# Build 005: Offline-Mali/Grafik-HAL-/ELF-Vorprüfung:
python3 q60t_graphics.py \
  --hardware-report reports/hardware_2743.0_build004_final.json \
  --kernel-report reports/kernel_build005.json

# Build 005: Offline-Signaturkomponenten-/Rollback-Gate-Check:
python3 q60t_boot_safety.py --evidence porting/boot-evidence.json

# Build 007: GPL-Source-Kandidateninventar und SHA-Prüfung (kein Download):
python3 q60t_source_provenance.py

# Build 007: Samsung-kbase- und Panfrost-Ansatz getrennt prüfen:
python3 q60t_gpu_strategy.py \
  --hardware-report reports/hardware_2743.0_build004_final.json \
  --kernel-report reports/kernel_build005.json

# Build 007: Alle Gates in einem Offline-Bericht prüfen:
python3 q60t_build007_preflight.py

# Build 008: Fundstellen und begrenzte Herkunftsnachweise lesen:
# BUILD008_REPORT.md und porting/source-candidates-build008.json

# Build 011: DTB-Kennungen mit lokal entpacktem Samsung-Code abgleichen:
python3 q60t_source_compat.py \
  --dtb /pfad/zu/decrypted/dtb.bin \
  --kernel-source /pfad/zu/linux-4.1.10 \
  --media-source /pfad/zu/tztv-media-nike \
  --report neuer-source-abgleich.json

# Build 012: Kconfig-Android-Gates und sicheres Staging vorbereiten:
python3 q60t_android_kernel.py \
  --source /pfad/zu/linux-4.1.10 \
  --report neuer-kconfig-report.json \
  --fragment-out /pfad/zu/neuer-kandidat.cfg
python3 q60t_kernel_stage.py \
  --source /pfad/zu/linux-4.1.10 \
  --fragment /pfad/zu/neuer-kandidat.cfg \
  --stage-dir /pfad/zu/neues-separates-buildverzeichnis

# Build 013: echter ARM32-Host-Testbuild, niemals auf den TV flashen:
python3 q60t_compile_probe.py \
  --source /pfad/zu/linux-4.1.10 \
  --workspace /pfad/zu/NEUEM-build013-arbeitsverzeichnis \
  --cross-prefix /pfad/zu/linaro/bin/arm-linux-gnueabi- \
  --jobs 4 --timeout 1800

# Build 015: wahlweise experimentell mit SELinux und Initramfs:
python3 q60t_compile_probe.py \
  --source /pfad/zu/linux-4.1.10 \
  --workspace /pfad/zu/NEUEM-build015-arbeitsverzeichnis \
  --cross-prefix /pfad/zu/linaro/bin/arm-linux-gnueabi- \
  --profile android-bootlab --jobs 4 --timeout 1800

# Unabhängiger, rein lesender Android-Kompatibilitäts-Survey:
python3 q60t_kernel_readiness.py \
  --source /pfad/zu/linux-4.1.10 \
  --config /pfad/zu/NEUEM-build015-arbeitsverzeichnis/output/.config \
  --output /pfad/zu/NEUEM-kernel-gap-report.json

# Build 016: Binder-Dreifachkontext-Compilerexperiment (kein TV-Test):
python3 q60t_compile_probe.py \
  --source /pfad/zu/linux-4.1.10 \
  --workspace /pfad/zu/NEUEM-binder-labor \
  --cross-prefix /pfad/zu/linaro/bin/arm-linux-gnueabi- \
  --profile binder-lab --jobs 4 --timeout 1800

# Build 017: aktuelle und original erhaltene Binder-UAPI-Lücken prüfen:
python3 q60t_binder_abi.py \
  --source /pfad/zu/linux-4.1.10 \
  --output /pfad/zu/NEUEM-binder-abi-bericht.json
# ARM32-C-Prüfung: porting/BINDER_UAPI.md

# REA selbst ausführen (Node.js/npm nötig, ohne globale Installation):
npx --yes rea-agents@latest inspect-devicetree /pfad/zu/decrypted/dtb.bin --format json

# Optional: Prüfergebnis auf dem Computer speichern:
python3 q60t_lab.py firmware-info /pfad/zu/T-NKLDEUC.zip --output firmware-info.json
```

Das Tool prüft ZIP-Struktur, `image/info.txt`, den `MSDU11`-Header,
Dateigrößen, SHA-256 und offensichtliche Archivrisiken. Es vergleicht den
SHA-256 des ZIPs zusätzlich mit einem **einzelnen** publizierten Referenzimage
der Version 2743.0; ein anderer Hash belegt für sich genommen **keinen** Fehler.

Bei entschlüsselten Dateien identifiziert es unter anderem `uImage` und
`dtb.bin`, validiert CRC32 im U-Boot-Legacy-Header und die Grundstruktur
eines Flattened Device Tree. Aus einem gültigen Device Tree liest es außerdem
die Modell- und `compatible`-Kennungen (ohne Seriennummern/MAC-Adressen).
Die mehrere Device Trees enthaltende Datei wird auf gültige eingebettete
FDT-Header geprüft.
Build 003 prüft nun zusätzlich FDT-Strukturtokens/Knoten, erzeugt einen
sanitierten CPU-/Gerätekategorienbericht und vergleicht die unterschiedlichen
RAM-Profile, ohne rohe Properties oder mögliche Seriennummern zu verteilen.
`kernel-report` extrahiert – soweit vorhanden – den eingebetteten Linux-
Konfigurationsblock und überprüft feste, harmlose Security-Symbolnamen;
Strings beweisen allein kein aktives Laufzeitverhalten.
`rootfs-strings` identifiziert Dateipfad-Hinweise, **nicht** nachgewiesene
existierende Treiberdateien.
Build 004 dekodiert außerdem die Standardzellen von `/memory/reg`
getrennt je Device Tree. Diese Bereiche sind **nicht die Größe des
eingebauten RAMs**. Ein DT-Knoten ist auch nicht automatisch aktiv:
`status = "disabled"` wird explizit ausgewiesen. Das neue Portgerüst
benutzt die Android-TV-Produktkonventionen, aber `BoardConfig.mk`
blockiert jeden voreiligen Image-Build absichtlich.
Berichte mit `--output` werden nur **neu angelegt**, niemals stillschweigend
überschrieben.
Build 007 prüft zusätzlich lokale GPL-Archiv-Metadaten auf auffällige
Mitgliedsnamen und Links, ohne Inhalte zu entpacken. Eine korrekte Version
oder ein lokal errechneter Hash beweist **keine** Herkunft von Samsung.
Die zwei Mali-Wege werden nicht verwechselt: ein Legacy-`/dev/mali0`-
Userspace ist nicht automatisch mit dem Panfrost-DRM-Treiber kompatibel.
Der integrierte Preflight verlangt weiterhin die `$(error ...)`-Sperre
in `BoardConfig.mk` und meldet für das reale Gerät **BLOCKED**.
Damit wird die Echtheit einer Firmware-Signatur
**nicht** geprüft.

## Weiterer Forschungsweg

1. Vollständigen Samsung-Modellcode und Firmwarefamilie abgleichen.
2. Original-ZIP offiziell beziehen, Hash und Metadaten verifizieren.
3. `upgrade.msd` **offline** mit Synacktivs Anleitung entschlüsseln.
4. `uImage`, `dtb.bin`, `seret.bin` und relevante Kernel-Module inventarisieren.
5. `dtb.bin` mittels REA und dem eigenen Profilvergleich auswerten (erledigt).
6. Samsung-GPL-Quellcode exakt zur Geräteversion prüfen.
7. Signatur- und Bootkette dokumentieren. Erst danach beurteilen, ob ein
   bootfähiger eigener Kernel überhaupt realistisch ist.

Ein Dual-Boot wird **nicht** verfolgt: Der einfachere Zielpfad ist – nur wenn
die Hardware einen sicheren Test-Bootweg zulässt – ein eigenständiger Start
von LineageOS. Ein produktiver Flash ist kein Bestandteil dieses Builds.

## Bekannte Einschränkungen von REA

REA kann mit Binwalk/Unblob Firmwareabschnitte analysieren, einen Device Tree
lesen und U-Boot-Legacy-Images erkennen. Die aktuelle generische
Firmwarefunktion nimmt nur Einzeldateien bis **128 MiB** entgegen. Das
Samsung-Paket ist etwa **1,35 GB**, `platform.img` ebenfalls sehr groß.
Deshalb müssen zuerst kleinere Komponenten mit geeigneten Spezialwerkzeugen
extrahiert werden; die generische REA-Analyse allein reicht nicht aus.
Die aktuell ausgeführte REA-Version hat die *rohe* `uImage` als nicht
unterstütztes Binärformat zurückgewiesen; unsere eigene uImage-Headerprüfung
war erfolgreich. Zum vollständigen Disassemblieren wären zusätzliche
Werkzeuge/Formatvorbereitungen erforderlich.

## Quellen / Herkunft der Referenzdaten

- Offizieller Samsung-Support für die Q60T-Modellfamilie:
  <https://www.samsung.com/de/support/model/QE50Q60TAUXZG/>
- Synacktiv, Q60T-Exploit und MSDU-Decryption:
  <https://github.com/synacktiv/samsung-q60t-exploit>
- `tiz0wn`, dokumentierte Analyse von `GQ55Q60TGUXZG` / `2743.0`:
  <https://github.com/sebastianspicker/tiz0wn/blob/main/docs/firmware-analysis.md>
- REA und Firmwareanleitung:
  <https://github.com/morluto/rea>
  <https://github.com/morluto/rea/blob/main/docs/guides/firmware/firmware-analysis.md>

Dieses Projekt enthält keine proprietären Firmwarebytes oder fremde
Reverse-Engineering-Quelltexte.


## Build 020 – QEMU ION / SELinux / Bionic (separater Branch)

- Zusätzliches **opt-in**-Kernelprofil `qemu-ion-lab` setzt `CONFIG_ION_DUMMY=y` nur in einem eigenen QEMU-Shadow-Build; Build-018-Profil und Samsung-Originalkernel bleiben unverändert.
- `q60t_ion_probe_init.c` öffnet `/dev/ion` und testet über Legacy-IOCTLs tatsächlich **4 KiB Allocate und Free**; `q60t_ion_result.py` überprüft die Gastmarker.
- `q60t_selinux_preflight.py` prüft Kconfig und Policy-Voraussetzungen, behauptet aber **keine** geladene Android-Sicherheitsrichtlinie.
- `q60t_bionic_hello.c` und `q60t_bionic_preflight.py` bereiten die **ELF32-/ARM-/Bionic-Linker-Prüfung** vor – noch kein laufendes Android.
- **Aktuell:** synthetische Tests; Build-020-Kernel und QEMU-ION-Allokation müssen auf dem vorhandenen Proxmox-Labor noch real ausgeführt werden. **Keine Freigabe zum Flashen.**

Alle sicherheitsrelevanten Prüfungen und Commands: [BUILD020_REPORT.md](BUILD020_REPORT.md).


## Build 021 – First Android Bionic Execution (QEMU)

Im separaten Proxmox-Testchat wurde **Build 020 mit ION-4-KiB-Allokation und Freigabe im QEMU-Gast bestätigt**. Das NDK-r30-Bionic-Programm ist bereits ARM32/ELF32 mit `/system/bin/linker` und `libdl.so`/`libc.so` als dynamischen Abhängigkeiten; echter Bionic-Start steht noch aus.

Auf diesem Branch liegen jetzt der *offline* SDK-24-AOSP-Systemimage-Extractor `q60t_aosp_runtime.py`, ein sicherheitsgeprüfter ELF32-Reader `q60t_bionic_elf.py`, das eigene statische Gast-`/init` `q60t_bionic_init.c`, der Initramfs-Packer `q60t_bionic_initramfs.py` und der strikte Guest-Log-Validator `q60t_bionic_guest_result.py`.

**Wichtig:** Keine echten Android-Bibliotheken, Binärimages oder Initramfs-Dateien werden ins Repository hochgeladen. Der erste reale Build-021-Gastlauf ist noch offen; keine Freigabe für den Fernseher. Vollständige Anweisungen: [BUILD021_REPORT.md](BUILD021_REPORT.md).
