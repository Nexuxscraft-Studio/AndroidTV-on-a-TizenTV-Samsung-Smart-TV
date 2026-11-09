# Build 016 – Dreifach-Binder-Kernel als Host-Prototyp (09.11.2026)

> **Ergebnis: ARM32-Cross-Compile PASS.** Keine Android-Laufzeit,
> kein realer Samsung-Boot, kein signiertes Firmwareimage. **Nicht flashen.**

## Problem und neue Entwicklung

Der von Samsung gelieferte Linux-4.1.10-Binder-Treiber verwendet nur
`/dev/binder` und verwaltet seinen Service-Manager in globalen Variablen.
Androids Binder-IPC-Dokumentation unterscheidet dagegen die separaten
Geräte-/Dienstkontexte `/dev/binder`, `/dev/hwbinder` und
`/dev/vndbinder`. Eine Umbenennung oder das Anlegen dreier Device-Nodes
ohne Kontexttrennung würde nicht ausreichen.

Mit **`q60t_binder_lab.py`** gibt es nun ein eigenständiges
quelltextgebundenes Labor-Overlay. Es verlangt den exakten Samsung-
Binder-Quellhash und scheitert bei fehlenden oder doppelt vorkommenden
Quellmarkern. Die Nutzerquellen werden **nicht** bearbeitet: Das Tool
wird nur für den durch den Compile-Probe angelegten Schattenbaum genutzt.

Experimentell umgesetzte Mechanismen:

- Drei registrierte Miscdevices mit **drei eigenen Kontextobjekten**.
- `binder_proc` ist beim Öffnen dem Kontext des ausgewählten Gerätes
  zugeordnet; der gemeinsame globale Context-Manager-Knoten ist durch
  einen pro-Domäne-Knoten und eine pro-Domäne-UID ersetzt.
- Die Behandlung von Manager-Handle `0`, Referenzallokation,
  Transaktionsauflösung und Freigabe verwendet den jeweiligen Kontext.
- Zusätzliche Checks verhindern referenzierte Zielprozesse aus anderen
  Binder-Domänen, solange die Modellannahmen des alten Treibers gelten.
- Hostseitig wird ein prüfbarer Unified-Diff generiert:
  `binder-multicontext-lab.patch` im neuen Testworkspace.

Die vollständige, ausdrücklich unvalidierte Designbeschreibung steht in
[`porting/BINDER_MULTICONTEXT_LAB.md`](porting/BINDER_MULTICONTEXT_LAB.md).

## Ausgeführter Build

```bash
python3 q60t_compile_probe.py \
  --source /pfad/zu/entpacktem/linux-4.1.10 \
  --workspace /pfad/zu/NEUEM-build016-binder-lab \
  --cross-prefix /pfad/zu/linaro/bin/arm-linux-gnueabi- \
  --profile binder-lab --jobs 4 --timeout 1800
```

| Prüfung | Beobachtung |
| --- | --- |
| Quellversion | Samsung Linux 4.1.10, `Nike.M`-Profil **nur als Kandidat** |
| Binder-Original-SHA-256 | `2c94aa4a57c3d19e9586e2185b8a3d97f95148e5d1a56926ca7ae876d01ac777` |
| Modifizierter Schatten-Binder-SHA-256 | `78c4df70dca56aeb98ca5ffa8f46b38d92a7cec216a0334331aea7f0905a0176` |
| SELinux/Initramfs/IKCONFIG | Alle eingeschaltet und in `.config` verifiziert |
| `make olddefconfig` | **Exitcode 0**, keine Fehler |
| ARM32 `make zImage` | **Exitcode 0**, keine Fehler |
| `zImage`-Dateigröße | **3.720.688 Bytes** |
| `zImage` SHA-256 | `adabc3e9679b1ba68c0296c2373ead02818a1645a785cba07517a4075b8f8a66` |
| Original-Samsungquellen geändert | **Nein** |
| Laufzeit/Android-VTS/Hardwareboot geprüft | **Nein** |

Die neu generierte Patchdatei hat zusätzlich einen erfolgreichen
`patch --dry-run --fuzz=0` gegen den unveränderten Samsung-Kernelbaum
bestanden. Sie und das `zImage` bleiben **ausschließlich im lokalen
Host-Testworkspace**, nicht im GitHub-Quellcodepaket.

## Readiness-Analyse

`reports/kernel_gap_build016_binder_lab.json` bestätigt:

- Drei-Kontext-Quellstruktur statisch erkannt.
- **Keine** Binder-Laufzeitfähigkeit daraus abgeleitet.
- Linux 4.1.10 außerhalb der offiziellen Android-14-Kernelmatrix.
- Kein gesicherter Nike-L-2743.0-Bootpfad, keine HAL, kein Rollback.
- Ergebnis bleibt `GAPS_FOUND_NOT_ANDROID_READY` und
  `flash_authorized=false`.

## Qualitätssicherung und Grenzen

- **103 synthetische Python-Tests erfolgreich**, darunter neue fail-closed
  Tests für unbekannte Binderquellen und ungenaue Quellmarker.
- Android-Bootlab und unverändertes `tizen`-Profil funktionieren als
  unabhängige Host-Experimente weiter.
- Die Codeerweiterung ist **kein geprüfter Upstream-Binder-Backport**;
  sie wurde weder unter einem Android-Userspace getestet noch auf dem
  realen SoC ausgeführt. Kernel-Abstürze, Security-/ABI-Probleme und
  Interaktionen mit Samsungs SFD/UEP sind noch möglich.

**Nächste sinnvolle Stufe:** In einer sicheren ARM32-Emulationsumgebung
das IPC-Verhalten aller drei Manager mit Android-kompatiblem Userspace
und automatisierten Negativtests prüfen; danach modernere Binder-ABI-
Anforderungen einzeln auditieren. Signatur- und Recoveryfrage für
den realen Q60T **vor jedem Hardwaretest** separat klären.
