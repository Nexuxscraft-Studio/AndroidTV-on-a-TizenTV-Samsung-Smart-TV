# Build 050 – Samsung-Hardware-Referenzprüfung

**Host-only / read-only:** Die beiden Build-050-Werkzeuge prüfen getrennt
historische Firmware-/Quellreports sowie ausgewählte unveränderte Textdateien
aus den Samsung-OSS-Tarballs. Sie schreiben **niemals** auf den Fernseher,
führen keine heruntergeladenen Skripte aus und installieren keine
Vendor-Binärdateien.

Vom Root des Projekt-Repositories aus:

```bash
python3 q60t_build050_hardware_evidence.py \
  --output /opt/samsung-atv-lab/build050-hardware-evidence.json
```

Wenn das originale äußere `20_DTV_NikeL.zip` zur **rein lesenden**
SHA-256-Prüfung lokal verfügbar ist, optional hinzufügen:

```bash
python3 q60t_build050_hardware_evidence.py \
  --original-oss-archive /pfad/zum/originalen/20_DTV_NikeL.zip \
  --output /opt/samsung-atv-lab/build050-archive-verified.json
```

Hash des bereits inventarisierten **äußeren** 743-MB-OSS-ZIPs:
`3e38ad1baf54be8ed91c1c18b2c3137692c28e01ca894db9690f632a1fbd3bad`.
Ein abweichender Hash wird abgelehnt; das erste Werkzeug führt keinerlei
Code aus der ZIP aus.

## Direkte Codeprüfung aus dem jetzt verfügbaren Originalarchiv

Die vollständige äußere ZIP wurde erfolgreich geprüft. Die darin liegende
innere ZIP hat SHA-256
`ceebe20245945571ff30f9584bc62e4c7fed138f320a55d8e876f3abd05ee20a`.
Aus der inneren ZIP benötigt die zusätzliche Codeprüfung drei getrennt
bereitgestellte Original-Tarballs; die Quellarchive selbst werden **nicht**
in das Git-Repository eingecheckt.

| Archiv | SHA-256 |
| --- | --- |
| `linux-4.1.10-tizen5.5.tgz` | `31a92f0d20248abbe2976bd2da1ab95dde4fed3e010ddcdc1c07494c4fd867b0` |
| `tztv-media-nike.tgz` | `40c2a25eba331b8b04d8d81baf76061493f15f228a74893c7f825f7a1da724b6` |
| `tztv-bootmode.tgz` | `7feb006983b35431df9408aef4ea176c7204578d7ba0e1b898dd10e364e58516` |

Ausführung auf einem separaten Analysehost mit vorhandenen TGZs:

```bash
python3 q60t_build050_vendor_code_audit.py \
  --kernel-tgz /pfad/linux-4.1.10-tizen5.5.tgz \
  --media-tgz /pfad/tztv-media-nike.tgz \
  --bootmode-tgz /pfad/tztv-bootmode.tgz \
  --output /pfad/zum/neuen-build050-quellreport.json
```

Der Bericht muss an einem **noch nicht bestehenden** Zielpfad angelegt
werden (Überschreiben ist bewusst gesperrt). Das Skript verwendet nur
`tarfile.extractfile` auf fest benannte, begrenzte Textdateien, niemals
`extractall`, und führt keinen Vendor-Code aus.

**Achtung:** Die originale `Nike.M`-Defconfig hat Binder, SELinux und ION
deaktiviert, anders als die zuvor modifizierte Build-015-Testkonfiguration.
Das ist kein Laufzeitbefund für Nike-L.

## Linux-6.6-API-Gap-Prüfung

Die nächste Stufe gleicht vier originalgetreue Quelltext-/Makefile-Dateien
mit ausgewählten DRM- und Panel-Schnittstellen des offiziellen Linux-6.6-
Kernelbaums ab. Ohne Kompiler und ohne Hardwarezugriff:

```bash
python3 q60t_build050_linux66_port_gaps.py \
  --kernel-tgz /pfad/linux-4.1.10-tizen5.5.tgz \
  --media-tgz /pfad/tztv-media-nike.tgz \
  --output /pfad/zum/neuen-linux66-gap-bericht.json
```

Ergebnis: `reports/hardware_build050_linux66_port_gaps.json`.
Die ausführliche Migrationsmatrix steht unter
[`LINUX66_PORTING_MATRIX.md`](LINUX66_PORTING_MATRIX.md).
Dieser Bericht ist ein **Compiler-Vorbereitungsinventar**, kein
nachgewiesener Treiberbuild.

## Erste Quellcodefixes / Stage 1

Der experimentelle, ausdrücklich nicht hardwaregebundene Panel-6.6-Patch
liegt unter [`patches/0001-nike-linux66-stage1-compile-only.patch`](patches/0001-nike-linux66-stage1-compile-only.patch).
Er wird reproduzierbar aus den Original-TGZs mit
`q60t_build050_stage1_source_fixes.py` erzeugt. Ein Patch-Trockenlauf
gegen die echten Quelldateien war erfolgreich; eine Kompilierung ist
noch **nicht** nachgewiesen. Die vollständigen Sicherheitsgrenzen und
Testkommandos stehen unter [`STAGE1_FIXES.md`](STAGE1_FIXES.md).

```bash
python3 -m unittest tests/test_build050_hardware_evidence.py -v
python3 -m unittest tests/test_build050_vendor_code_audit.py -v
python3 -m unittest tests/test_build050_linux66_port_gaps.py -v
python3 -m unittest tests/test_build050_stage1_source_fixes.py -v
python3 -m unittest discover -s tests -q
python3 q60t_release_audit.py .
```

Die Datei `reports/hardware_build050_evidence.json` enthält den
verifizierten Stand aus den sieben historischen Referenzreports. Ihr
Status `REFERENCE_IDENTIFIED_LIVE_TV_UNVERIFIED` bedeutet **nicht**,
dass der tatsächliche 50-Zoll-Fernseher untersucht wurde.

Alle nächsten Hardware-Schritte bleiben von einem bestätigten,
flüchtigen Bootweg sowie einem unabhängigen, geprüften Recovery- und
Rollbackweg abhängig. **Keine Flash- oder Bootloaderänderung.**
