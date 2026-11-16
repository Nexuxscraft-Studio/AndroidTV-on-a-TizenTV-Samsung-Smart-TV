# Build 121 · Q60T Nike-L ARM32 Legacy-uImage

Der Build läuft auf dem selbstgehosteten Actions-Runner `debian`. Er
verwendet die Linux-6.6.162-Konfiguration, DTB-Patches, Prüfsummen und
QEMU-Prüfung von Build 111. Zwei unabhängige Build-Verzeichnisse müssen
bytegleiche Build-111-ZIPs und bytegleiche Legacy-uImages ergeben.

## Runner-Eingaben

Die folgenden GitHub-Actions-Repository-Variablen müssen vor dem Lauf
gesetzt sein. Beide Dateien liegen lokal auf Debian und müssen für das
Runner-Konto lesbar sein.

| Variable | Inhalt |
| --- | --- |
| `BUILD121_LINUX_TARBALL` | Absoluter Pfad zu `linux-6.6.162.tar.xz`. Build 096 prüft den im Repository festgelegten SHA-256. |
| `BUILD121_STOCK_UIMAGE` | Absoluter Pfad zum originalen Samsung-Q60T-Nike-L-uImage, mit Legacy-Header an Offset null. |
| `BUILD121_STOCK_UIMAGE_SHA256` | SHA-256 der vollständigen Referenzdatei aus dem lokalen Firmware-Inventar. |

Zusätzlich zu den Build-111-Werkzeugen benötigt Debian `mkimage` aus
`u-boot-tools` und `file`. Der Build bezieht keine Kernelquellen oder Pakete
aus dem Netz. Checkout sowie Upload der Ergebnisse verwenden GitHub Actions.
Der Push-Trigger ist auf den Build-121-Branch und seine Dateien begrenzt.
Der Workflow kann über den Dispatch-Trigger manuell gestartet werden,
sobald GitHub den Workflow auf dem Default-Branch registriert hat.

## Ergebnisse und Grenzen

- Das Legacy-uImage enthält das ARM-`zImage`. `mkimage -C none` beschreibt
  die fehlende äußere Kompression. Der zImage-Dekompressor und sein
  eingebetteter gzip-Kernel bleiben erhalten.
- Der Build prüft beide CRC32-Felder, Header- und Payload-Länge, ARM32-Magic
  und die Übereinstimmung des Payloads mit dem gebauten Kernel. Der Report
  enthält die Header beider Dateien, Feldvergleiche und die Ausgabe von
  `mkimage -l` und `file`. Die Originaldatei wird nur gelesen.
- Lade- und Einsprungadresse stammen ausschließlich aus der geprüften
  Referenz. Der Report prüft für beide DTB-Profile, ob der Ladebereich in
  einem zusammenhängenden statisch freien RAM-Bereich liegt und der
  Einsprung zum Anfang des zImage passt. Fehlgeschlagene Speicherchecks
  stehen im Report. Das Paket bleibt als Offline-Prüfartefakt verfügbar.
- Die DTBs für 1,5 und 2 GiB, das Build-111-Test-Initramfs und die
  Kernel-Konfiguration liegen als einzelne Dateien neben dem uImage.
  `SHA256SUMS` deckt auch den JSON-Bericht ab. Build-Logs erscheinen in
  einem separaten Actions-Artefakt.

Die uImage-Formatkompatibilität liefert keinen Nachweis für einen
erfolgreichen Start oder Secure Boot auf einem Samsung-TV. Die statischen
Checks erfassen weder die Dekompression und Relokation noch die reale Lage
von DTB und Initramfs beim Booten. Der Workflow endet bei lokalen
Dateiprüfungen und der QEMU-Prüfung von Build 111.

## Tests

```sh
python3 -m unittest discover -s porting/build121
```
