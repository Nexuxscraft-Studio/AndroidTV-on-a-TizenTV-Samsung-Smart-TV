# Build 025 – Read-only Samsung Nike-L / modern Linux compatibility lab

**Ausführung ausschließlich auf dem Entwicklungsrechner.** Kein Zugriff
auf den laufenden Fernseher, kein Build/Flash, keine Firmwareänderung.
Die Originalarchive/Quellbäume werden beim Scannen nur gelesen.

## A. Bereits vorhandenen Firmware-Referenzreport prüfen

Vom Projektwurzelverzeichnis aus:

```bash
python3 q60t_build025_kernel_gap.py \
  --legacy-report reports/source_compat_build011.json \
  --output /opt/samsung-atv-lab/build025-legacy-baseline.json
```

Das Programm verlangt den bekannten DTB-Hash der **55-Zoll-Referenz**
und bestätigt absichtlich **keine** Kompatibilität mit dem 50-Zoll-TV.
Wenn der neue Ausgabepfad schon existiert, bricht es ab. Dann einen
anderen Dateinamen benutzen.

## B. Linux 6.6.x nach Samsung-Gerätetreibern durchsuchen

Wenn der **separate, unveränderte** Linux-6.6.162-Quellbaum bereits
auf dem Proxmox-Testgast vorhanden ist:

```bash
python3 q60t_build025_kernel_gap.py \
  --legacy-report reports/source_compat_build011.json \
  --modern-source /opt/samsung-atv-lab/linux-6.6.162 \
  --output /opt/samsung-atv-lab/build025-linux66-gap.json
```

Wichtig für die Ergebnisinterpretation:

- `NO_MODERN_LITERAL_REFERENCE`: Im geprüften Linux-6.6-Quellbereich
  kein wörtlicher `compatible`-Treffer. Das ist **keine Aussage**, dass
  sich ein Treiber unmöglich portieren lässt.
- `MODERN_DTS_LITERAL_ONLY`: Nur eine DT-Deklaration, keine bestätigte
  Implementierung.
- `MODERN_CODE_LITERAL_ONLY`: C-/Header-Treffer, auch innerhalb
  ungenutzten Codes denkbar. **Kein Kompilierungs- oder Laufzeitnachweis.**
- `LINUX_6_6_NOT_SCANNED`: Ein 6.6-Quellbaum wurde nicht angegeben.

Die Analyse scannt die Bereiche `drivers/`, `sound/`, `include/`
und `arch/arm64/`. Die Dateianzahl, Einzelgrößen und Gesamtbytes
sind begrenzt; symbolische Links werden übersprungen. Sie liest
lediglich Quelltexte und führt kein fremdes Build-Skript aus.

## C. Separaten Android-14-HAL-Entwurf prüfen

Erst **wenn wir ein eigenes Nike-L-Device-Tree-/Vendor-Produkt** in
einem lokalen Android-Checkout haben, kann der entsprechende
VINTF-Gerätemanifest-Kandidat zusätzlich geprüft werden:

```bash
python3 q60t_build025_kernel_gap.py \
  --legacy-report reports/source_compat_build011.json \
  --device-manifest /opt/samsung-atv-lab/lineage/device/samsung/nikel/manifest.xml \
  --output /opt/samsung-atv-lab/build025-vintf-gap.json
```

Das ist ein **zukünftiger Pfad als Beispiel**, keine Behauptung,
dass diese Datei bereits existiert. Ein gültiges Manifest muss durch
VINTF-Tests und real gestartete HAL-Dienste ergänzt werden.

## D. Vorhandene Schutzschranke prüfen

```bash
python3 q60t_boot_safety.py \
  --evidence porting/boot-evidence.json
```

Exitcode `1` bedeutet hier normalerweise **korrekt blockiert**.
Die offizielle Samsung-USB-Firmware ist kein Beleg, dass ein TV mit
unbootbarem/unsigniertem Kernel auf diese Weise repariert werden kann.

## E. Geräteidentität – erst bei rechtmäßigem, lesendem Tizen-Zugriff

Es gibt **bisher keine** verifizierte Shell auf dem echten 50-Zoll-TV.
Ohne Zugriff sind Board-/CPU-/RAM-Variante unbekannt; die
55-Zoll-Firmwareprofile dürfen **nicht** automatisch übernommen werden.

Sollte später ein regulärer, lesender Zugang möglich sein, erfassen wir
zunächst **nur**:

- `uname -m`, `uname -r` (laufender Kernel und seine ISA)
- CPU-MIDR/`/proc/cpuinfo`-Architektur und Kerntyp (keine Seriennummern)
- freigegebene `/proc/device-tree/model`- und `compatible`-Eigenschaften
- die echte GPU-Revision und nur unkritische, gerätespezifische
  Peripherie-Kompatibilitäten

**Keine** Partitionen beschreiben, Bootvariablen ändern, Debug-
Schnittstellen erzwingen oder private Schlüssel/Token exportieren.
Auch ein 32-Bit-`uname -m` schließt einen ARMv8-fähigen Prozessor
nicht aus; es beschreibt zunächst den **laufenden Kernel**.

## Ergebnisdefinition

Build 025 ist bestanden, wenn die Offline-Lückenmatrix reproduzierbar
erstellt wird und alle unerfüllten Boot-/Recovery-Gates ausdrücklich
blockiert bleiben. Das ist **nicht** gleichzusetzen mit „Samsung TV
bereit für Android“.

Host-Tests:

```bash
python3 -m unittest discover -s tests -q
python3 q60t_release_audit.py .
```

Alle produktionskritischen Änderungen bleiben gesperrt, bis ein
nachweislich flüchtiger Boot plus unabhängiger Recoveryweg existiert.
