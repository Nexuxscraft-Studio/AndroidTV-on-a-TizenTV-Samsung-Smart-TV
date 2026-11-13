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
Firmwaremodifikation.** Die sechs synthetischen Build-079-Tests und die
Originaldatei-Prüfung sind zum Zeitpunkt dieses Commits noch nicht ausgeführt.
