# Build 009 – Originales Samsung-Nike-L-Sourcepaket im OSSRC gefunden

Stand: **08.11.2026**. Gerät: Samsung **GQ50Q60TGUXZG**,
Firmware **T-NKLDEUC 2743.0**.

## Konkreter Originalfund

Das [Samsung Open Source Release Center](https://opensource.samsung.com/uploadSearch?searchValue=Q60T)
lieferte bei der Suche nach `Q60T` **genau einen Eintrag**:

| Eigenschaft | Direkt im offiziellen Portal abgelesen |
| --- | --- |
| Klassifikation | `TV > DTV > LED` |
| Bezeichnung | `20_DTV_NikeL` |
| Modellauswahl | Enthält ausdrücklich **`GQ**Q60T**`** |
| Angezeigte Releaseversion | **`1000`** – nicht mit Firmware `2743.0` gleichzusetzen |
| Originales Quellarchiv | **`20_DTV_NikeL.zip`** |
| Begleitdatei | `20_DTV_NikeL.txt` |
| Vom Portal angezeigte ZIP-Größe | **708,82 MB** |
| Browserseitig erkennbare Katalogkennung | `8871` |

Damit ist die zuvor offene Frage, **ob und unter welcher Kennung
Samsung einen GPL-Nike-L-Quellcode anbietet**, für die Q60T-Modellfamilie
positiv beantwortet. Ein direkter Dateilink war im Portal nicht
vorhanden; der Download wird aus einem Dialog nach Zustimmung zu
Samsungs rechtlichen Nutzungsbedingungen ausgelöst.

## Unvollständig – ausdrücklich keine Kernel-Reproduktion

Der Versuch, die Datei im browserbasierten Downloadfenster abzurufen,
konnte wegen einer Browser-Sicherheitsbeschränkung nicht abgeschlossen
werden. Diese Beschränkung wurde **nicht umgangen**. Daher gibt es
hier weiterhin **keine lokale ZIP**, keinen SHA-256 aus dem Originalpaket,
keine extrahierte Linux-4.1.10-Quelle und keine Nike-L-Defconfig.

Das Portal-Release **1000** kann ein quelloffenes Basispaket der
2020er-Baureihe sein. Dass dessen Inhalt und Patches **bitgenau** zum
`T-NKLDEUC 2743.0`-Kernel vom Juli 2026 passen, ist **nicht belegt**.
Die Firmware-/Kernel-Signaturrestriktionen und die Android-HAL-
Inkompatibilität bleiben davon unberührt.

## Nächster manueller Schritt zur tatsächlichen Codeprüfung

1. Die [offizielle Q60T-Suche im Samsung OSSRC](https://opensource.samsung.com/uploadSearch?searchValue=Q60T)
   in einem regulären Browser öffnen.
2. Beim Eintrag `20_DTV_NikeL` die Spalte **Source** öffnen.
3. Die von Samsung angebotenen `20_DTV_NikeL.txt` und
   `20_DTV_NikeL.zip` über die vorgesehenen Download-Schaltflächen
   beziehen und die gegebenenfalls angezeigten Lizenzbedingungen prüfen.
4. **Noch nichts auf den Fernseher spielen.** Stattdessen die Datei
   lokal hashen, die ZIP-Inhaltsliste sicher inspizieren und nach
   `linux-4.1.10`, `arch/arm/configs/`, `sdp-nikel`, Mali-kbase und
   eventuell beiliegenden Build-Anleitungen suchen.
5. Wenn das Archiv zu groß für einen direkten Chat-Upload ist, zunächst
   Dateiliste und Hash bereitstellen; erst danach entscheiden, welcher
   Quelltextteil für die weitere Analyse benötigt wird.

Die bestehende Sicherheitsprüfung
`q60t_source_provenance.py --archive <originales ZIP>` kann das Archiv
**ohne Entpacken oder Ausführen** inventarisieren und einen SHA-256
berechnen. Für einen tatsächlichen Kernelbau benötigen wir zusätzlich
Original-Defconfig, Compile-Flags und den kompatiblen Compiler.

Die offizielle Fundstelle ist im maschinenlesbaren
`porting/source-candidates-build008.json` nachgetragen.

**Ergebnis:** Offizieller, modellpassender **Quellpaketeintrag gefunden**;
Dateidownload und Quellenvalidierung **noch offen**; auf dem TV
**nichts verändert**.
