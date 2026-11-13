# Build 079 — Original SWUVerifierTV: ELF und Systemd (nur statisch)

**Zielgerät:** Samsung GQ50Q60TGUXZG, extrahierte Referenzfirmware 2743.0.  
**Evidenz:** Terminalausgabe des Nutzers vom 13.11.2026.  
**Status:** ARM32-Verifikationsdienst gefunden; **keine kryptografische Signaturprüfung nachgewiesen**.

## Primärbefund aus dem extrahierten RootFS

Der Nutzer fand im extrahierten Tizen-RootFS:

| Datei | Beobachtung |
| --- | --- |
| `/usr/bin/SWUVerifierTV` | ELF32, little-endian, ARM EABI5, PIE, dynamisch gelinkt, **stripped**, Interpreter `/lib/ld-linux.so.3` |
| `/usr/lib/systemd/system/swu-verifier-tv.service` | `Type=dbus`, `ExecStart=/usr/bin/SWUVerifierTV`, `BusName=org.tizen.tv.swu.verifier.TV` |
| `swu-verifier-tv.timer` | `OnActiveSec=1`, `Unit=swu-verifier-tv.service` |
| `swu-core-tv.service` | `ExecStart=/usr/bin/SWUCoreTV --idle-timeout 30`; `Requisite=swu-verifier-tv.service deviced.service`, `After=...` |
| `swu-service.service` | `ExecStart=/usr/bin/SWUService --idle-timeout 30`; dieselben `Requisite` und `After` |
| `org.tizen.tv.swu.verifier.TV.busname` | `Name=org.tizen.tv.swu.verifier.TV`, `Service=swu-verifier-tv.service` |

Der Verifier-Dienst fordert `deviced.service` und wird nach ihm
gestartet. Die beiden anderen SWU-Dienste deklarieren den Verifier als
Systemd-Voraussetzung. **Das beweist nur die Dienstkonfiguration**,
keine zwingende Reihenfolge einzelner kryptografischer Operationen
innerhalb der Prozesse.

Auffälligkeit: `swu-verifier-tv.service` prüft
`ConditionPathExists=!/opt/backup/OS_UPGRADE_FLAG`, während
`swu-core-tv.service` und `swu-service.service`
`!/mnt/backup/OS_UPGRADE_FLAG` prüfen. Noch nicht bekannt, ob
`/opt/backup` und `/mnt/backup` auf denselben Speicher verweisen.
Keinen Fehler behaupten, ohne die Originalkonfiguration zu prüfen.

## Die Namen im echten ARM32-Programm

Die `strings -a -t x`-Ausgabe des originalen ELF zeigt
unter anderem diese C++-Namen:

- `SWU::Common::UpgradeGraph::RSAValidation` — an verschiedenen
  Boost-Serializer- und RTTI-/Typ-Informationen
- `SWU::Common::UpgradeGraph::AESEncryption`
- `SWU::Common::UpgradeGraph::CRC32Validation`
- `SWU::Core::FlashHandler::FlashSink`
- `SWU::Platform::ISystemControl::getExternalAppVerificationResult()`

Diese Namen sind **mehr** als ein generischer RSA-String, weil sie zum
Samsung-SWU-Klassenmodell gehören. Sie sind aber noch **kein Beleg**,
dass sich eine ausführbare RSA-Verifikationsroutine im ELF befindet, dass
sie aufgerufen wird oder dass ein bestimmter Samsung-Schlüssel verwendet
wird. Die Beispiele `_ZTV...`, `_ZTI...`, `_ZTS...` sowie
Boost-Serialisierungsnamen können **allein aus Datentypen und
Serialisierung** entstehen.

Das dynamische `NEEDED`-Inventar nennt
`libSWUProductionConfig.so`, `libavoc.so`, `libdeviced.so.1`,
`libmicom.so.0` und andere. In der gelieferten direkten
`NEEDED`-Liste war **keine** `libcrypto.so`. Diese Abwesenheit
**schließt weder eine statisch eingebundene Implementierung noch
`dlopen` oder eine indirekte Bibliothek aus**.

## Zusammenhang mit Build 078: wichtig, aber noch keine direkte Kante

In [Synacktivs öffentlichem Q60T-Decryptor](https://github.com/synacktiv/samsung-q60t-exploit/blob/main/firmware/decrypt.py)
heißt das MSD-Metadaten-TLV für RSA `OURSAValidationDesc`.
Der originale, vom Nutzer untersuchte Verifier enthält den C++-Typnamen
`UpgradeGraph::RSAValidation`. **Beide sind kompatible Konzepte.**
Weder ein direkter Parser-zu-Prüfer-Aufruf noch eine Entsprechung
der 256-Byte-Partition-Endfenster mit RSA-Signaturen ist belegt.

**Wichtig:** Die 16 × `0x10` aus Build 078 erklären sich plausibel
durch nicht entferntes AES-CBC-PKCS#7-Padding im Extraktionstool
und sind **kein bewiesener proprietärer Signaturmarker**.

## Owner-Test: Erstes Build-079-Audit auf Original-ELF bestanden

Der Projektinhaber führte am 13.11.2026 das Read-only-Audit auf dem
extrahierten RootFS aus und erhielt **`STATIC_ELF_AND_SYSTEMD_METADATA_ONLY`**.

- `/usr/bin/SWUVerifierTV`: **1.921.360 Bytes**,
  SHA-256 `0af2d2b00d96b8eff32032dd1001b7b688b124e9cf0b9bdf5862e55eea183149`.
- `ELF32`, Little Endian, ARM-Maschinencode `40`: bestätigt.
- `readelf`-Bibliotheks- und Dynamic-Symbol-Analyse: erfolgreich.
- `RSAValidation`, `AESEncryption`, `CRC32Validation`, `FlashSink`
  und `getExternalAppVerificationResult`: als ELF-Strings vorhanden.
- Keine wörtlichen Treffer auf `OURSAValidationDesc`, `RSA_verify` oder
  `EVP_PKEY_verify`. Dies ist **kein Ausschluss anderer Prüffunktionen**.
- `RSAValidation` hat nachweislich definierte `FUNC`-Symbole im ELF,
  doch die zuerst angezeigten Beispiele stammen aus
  **Boost-Serialisierung/Typkonversion**, nicht aus einer kryptografischen
  Verify-Methode. `_ZTIN...RSAValidationE` ist `OBJECT`-Typinformation.

### Analyzer-Verbesserung nach dem Ersttest

Die erste Version zeigte nur die **ersten 30** passenden
Dynamic-Symbole und bevorzugte daher zufällig die vielen Boost-Einträge.

Die aktualisierte Version prüft **alle** passenden `.dynsym`-Einträge,
priorisiert definierte, direkt zur Samsung-Klasse
`SWU::Common::UpgradeGraph::RSAValidation` gehörende Methoden
(auch const-qualifizierte), und trennt Boost-/RTTI-Metadaten sowie
Konstruktoren/Destruktoren. Besonders nützlich sind im JSON jetzt:

- `readelf.matching_dynamic_symbols_total`
- `readelf.defined_rsa_class_function_count`
- `readelf.rsa_class_non_ctor_dtor_method_candidate_count`
- `readelf.rsa_class_non_ctor_dtor_method_candidates`

**Wichtig:** Auch eine direkte Methode ist noch kein Nachweis eines
kryptografischen Prüfpfads. Das neue Ranking ist nur ein Recherche-Filter.

Die neu ergänzten **acht synthetischen Unit-Tests** und der geänderte
Analyzer wurden zum Zeitpunkt des Commits **noch nicht erneut
auf dem Debian-Server ausgeführt**.

### Vollständiger Symbolscan und Klassifikationskorrektur (Owner, 13.11.2026)

Der Owner meldete **acht bestandene synthetische Tests** (Ausgabe `OK`)
und den ersten vollständigen `.dynsym`-Scan:

- `matching_dynamic_symbols_total = 539`
- `defined_rsa_class_function_count = 11`
- `rsa_class_non_ctor_dtor_method_candidate_count = 6` **vor Korrektur**
- Unter den sechs Einträgen waren jedoch zwei **Konstruktor-ABI-Varianten**
  `RSAValidation::RSAValidation(unsigned int, const std::vector<unsigned char>&)`
  (`C1`, `C2`). Sie wurden fälschlich als Methoden einsortiert, weil der
  vorige Filter nur parameterlose `C1Ev`/`C2Ev`-Muster erkannte.
- Die vier eigentlichen Methoden lauten
  `expandsData() const`, `getRSAKeyId() const`, `clone() const`
  und `signature() const`.

Der Korrekturcommit erkennt `C1/C2/C3` sowie `D0/D1/D2` **unmittelbar
hinter `RSAValidation`**, unabhängig von der kodierten Parameterliste.
Er gibt `rsa_class_ctor_dtor_count` separat aus. Ein neuer synthetischer
Regressionstest prüft genau die vom Nutzer gemeldeten sechs Namen
und erwartet **2 Konstruktoren + 4 Methoden**.

**Die erwarteten Zahlen nach Korrektur sind noch nicht am Original-ELF
erneut bestätigt.** Es ist ebenso wenig eine kryptografische
Verifikation wie ein erfolgreicher Hardware-Boot nachgewiesen.
Die Testanzahl steigt auf **9**, deren Ausführung nach dem Fix ist offen.

## Reproduzierbare, rein lesende Folgestufe

```bash
cd /opt/samsung-atv-lab/repo
git fetch origin
git switch --track origin/feature/build079-swu-static-verifier

python3 -m unittest discover -s porting/build079/tests -v
python3 porting/build079/swu_static_audit.py \
  --rootfs /opt/samsung-atv-lab/samsung/firmware-2743/rootfs-extracted/root
```

Das Werkzeug gibt **nur gezielte Marker, kurze dynamische
Symbol-Informationen und Service-Eigenschaften** aus. Es verwendet
`readelf` zur Dateianalyse; kein Samsung-Programm wird ausgeführt.
Im Fall fehlender `readelf`-Installation bleiben Binärheader, Marker und
Units lesbar; das tool meldet die fehlende ELF-Zusatzanalyse.

### Nächste REA-Prüfung

1. In der `readelf -W --dyn-syms`-Ausgabe nach
   `RSAValidation` suchen und `FUNC` von `OBJECT`, `UND`, RTTI
   und Boost-Serialisierungsmetadaten unterscheiden.
2. Falls eine **echte Funktionsimplementierung** nachgewiesen wird:
   `objdump`/Ghidra auf Aufrufer, Parameter und überprüfte Rückgabepfade
   ausrichten. Reine String-Treffer reichen nicht.
3. `SWUCoreTV`, `SWUService`, `libSWUProductionConfig.so` und ggf.
   indirekte Update-Bibliotheken nach **tatsächlichen Importen,
   Implementierungen und Aufrufen** untersuchen.
4. Den Unterschied zwischen **MSD-Update-Autorisierung** und der
   **frühen Hardware-Boot-Autorisierung** beibehalten.

**Bislang keine RSA-Signatur kryptografisch geprüft, kein öffentliches
Trust-Anchor-Verhalten der Zielhardware belegt, kein TV-Boot, keine
Firmwaremodifikation.** Die neun synthetischen Build-079-Tests und die
Originaldatei-Prüfung sind zum Zeitpunkt dieses Commits noch nicht ausgeführt.
