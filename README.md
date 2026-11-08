# Samsung Q60T → LineageOS: Offline-Labor (Build 008)

Ein **nicht-invasives** Arbeitsprojekt zur Untersuchung der Samsung-Q60T-Firmware
`T-NKLDEUC 2743.0` als Vorbereitung einer möglichen LineageOS-/Android-TV-Portierung.

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
- Ein echtes Android-Bootimage, ein entsperrter Bootloader und passende
  Android-Hardwaretreiber **existieren hier noch nicht**.
- Neue Erkenntnisse, Treibermatrix und offene Sicherheitsbedingungen:
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
  GPL-Quellbaum und passenden ARM-Cross-Compiler; diese fehlen derzeit.
- Build 007: integrierte Prüfungen benötigen weiterhin nur die
  Python-Standardbibliothek; CI testet unter Python 3.11 und 3.12.
- Build 008: Quellenverzeichnis und Tests bleiben offline und benötigen
  keine zusätzlichen Pakete; **kein automatischer Fremdquellendownload**.

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
