# Build 073 – Q60T Diagnose-App (Tizen 5.5, read-only)

**Zielgerät:** Samsung GQ50Q60TGUXZG, Tizen 5.5, Developer Mode aktiviert.

Eine eigenständige, einfache Tizen-Web-App, die nur **öffentliche,
dokumentierte und lesende** APIs abfragt:

- `tizen.systeminfo.getPropertyValue()` – `BUILD`, `CPU`, `MEMORY`,
  `DISPLAY`, `PANEL`
- `tizen.systeminfo.getCapability()` – CPU-Architektur, Plattformprozessor
  (falls verfügbar), Modell- und Buildmerkmale, Grafik-Bildschirmfeature
- `webapis.productinfo` – Modell, Modellcode, vollständiges Modell, Firmware
  und Pluginversion (ohne `getDuid`)
- Saubere Darstellung von API-Zugriffssperren und nicht unterstützten Werten

**Wichtig:** `MEMORY.status` gibt **nur Speicherdruck**, nicht RAM-Kapazität an.
`CPU.load` liefert CPU-Auslastung, nicht CPU-Frequenz, Kernzahl oder
SoC-Identität. `PANEL` (ab Tizen 5.5) und Prozessorbezeichnung sind je nach
Gerät/SDK möglicherweise nicht verfügbar. Es werden keine Bootloader-,
Kernel- oder Root-Informationen versprochen.

Die App sendet **keine** Netzwerkdaten, speichert nichts, ändert keinerlei
Systemeinstellungen und benötigt nur öffentliche Leseberechtigungen. Sie
versucht weder `sdb shell` noch `kexec` und benutzt keine Firmware- oder
TrustZone-Schnittstellen. Die Installation des Web-App-Pakets selbst erfolgt
regulär über Tizen Studio; nicht als Kernel- oder Firmwareflash.

## Voraussetzungen (MacBook / Samsung TV)

- Tizen Studio CLI, Samsung TV Extension und Samsung Certificate Extension.
- Mac und TV im selben lokalen Netzwerk, Tizen Developer Mode aktiviert.
- SDB verbindet sich mit dem TV (vorliegend: `192.168.178.20:26101`).
- **Samsung TV certificate profile** mit Author- und Distributor-Zertifikat.
  Im Distributor-Zertifikat muss die **DUID des eigenen Fernsehers**
  hinterlegt sein. Tizen Studio Certificate Manager kann sie beim verbundenen
  Gerät automatisch übernehmen. **Keine DUID oder Zertifikatsdatei im Repo
  oder Chat veröffentlichen.**

Offizieller Zertifikatsweg:
https://developer.samsung.com/smarttv/develop/getting-started/setting-up-sdk/creating-certificates.html

## 1. Projekt vom GitHub-Branch holen

Auf dem Mac einen bestehenden privaten Checkout aktualisieren:

```bash
cd ~/AndroidTV-on-a-TizenTV-Samsung-Smart-TV
git fetch origin feature/build073-tizen-diagnostics
git switch --create feature/build073-tizen-diagnostics --track origin/feature/build073-tizen-diagnostics
```

Falls der Branch lokal bereits existiert, stattdessen
`git switch feature/build073-tizen-diagnostics` verwenden. Alternative:
über die GitHub-Weboberfläche diesen Branch auswählen und als ZIP laden.

## 2. Tizen-Studio-CLI prüfen

```bash
~/tizen-studio/tools/ide/bin/tizen version
~/tizen-studio/tools/sdb devices
```

Ohne `tizen` CLI oder Samsung-TV-Erweiterung funktioniert der Build auf
diesem Mac noch nicht. Erforderliche Erweiterungen im Package Manager
installieren, nicht systemfremde Binärdateien verwenden.

## 3. Samsung-TV-Zertifikat erstellen (einmalig)

Öffne den **Tizen Studio Certificate Manager**, erstelle ein Profil
`Q60TDev` mit `Samsung → TV`, Author-Zertifikat und dem Public-Level
Distributor-Zertifikat für die **DUID des verbundenen Q60T**. Benötigt
Samsung Developer Account. Zertifikatsdateien/Passwörter nicht weitergeben.

## 4. Bauen, signieren, installieren

Alle Befehle ab Repository-Hauptordner:

```bash
APP="$PWD/porting/build073/tizen-diagnostics"
TIZEN="$HOME/tizen-studio/tools/ide/bin/tizen"
SDB="$HOME/tizen-studio/tools/sdb"
"$SDB" devices
"$TIZEN" build-web -- "$APP"
"$TIZEN" package -t wgt -s Q60TDev -- "$APP/.buildResult"
WGT="$(find "$APP/.buildResult" -maxdepth 1 -name '*.wgt' -type f -print -quit)"
test -n "$WGT" || { echo "Kein signiertes WGT gefunden"; exit 1; }
"$TIZEN" install -s "192.168.178.20:26101" --name "$(basename "$WGT")" -- "$(dirname "$WGT")"
"$TIZEN" run -s "192.168.178.20:26101" -p NvxQ60T073.Diagnostics
```

**Die IP ist die zuletzt vom Benutzer bestätigte TV-Adresse.** Falls DHCP
sie verändert hat, die SDB-Verbindung und die IP entsprechend aktualisieren.
Der App-Paketname heißt `NvxQ60T073`, App-ID
`NvxQ60T073.Diagnostics`; es handelt sich um eine **Entwicklungsinstallation**,
nicht um eine Store-App.

Falls ein Signaturfehler / Error 205 / 1010 auftritt: Profil, Samsung TV
Certificate Extension und DUID-Eintrag prüfen. Bei einem Fehler der
`tizen package`-CLI zuerst die Meldung auswerten, nicht das WGT manuell
nachsignieren oder verändern. Eine Standard-Tizen-Signatur reicht auf einem
Samsung-TV möglicherweise nicht.

## 5. Ergebnis auf dem Fernseher

In der App sind vier Bereiche sichtbar: Gerät & Firmware, CPU & Plattform,
Anzeige und technische Grenzen. Mit der Fernbedienung:
- **OK** auf „Erneut auslesen“: Werte neu laden.
- **▲ / ▼**: scrollen.
- **Zurück**: die Diagnose-App schließen.

Wenn die Abfrage erfolgreich ist, Foto/Screenshot **ohne private IDs**
anfertigen; Diagnoseergebnisse können wir anschließend mit Build 059,
Build 071 und Build 072 vergleichen.

Es wird keine DUID angezeigt und keine Seriennummer übertragen. Das
Programm behauptet ausdrücklich **nicht**, dass ein kexec- oder RAM-Boot
auf dem TV möglich wäre.

## Statische Offline-Prüfung

```bash
python3 -m unittest discover -s porting/build073/tests -v
```

Das prüft die App-Struktur, die Privilegien und den Ausschluss
identifizierender API-Aufrufe. Ein tatsächlicher TV-App-Test ist **noch
nicht** durchgeführt worden.

### Offizielle Referenzen

- https://developer.samsung.com/smarttv/develop/api-references/tizen-web-device-api-references/systeminfo-api.html
- https://developer.samsung.com/smarttv/develop/api-references/samsung-product-api-references/productinfo-api.html
- https://developer.samsung.com/smarttv/develop/getting-started/using-sdk/command-line-interface.html
- https://developer.samsung.com/smarttv/develop/getting-started/setting-up-sdk/creating-certificates.html
