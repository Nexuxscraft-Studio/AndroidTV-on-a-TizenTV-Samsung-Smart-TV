# BUILD110: RAM-PID-1 und Prüfung vor dem ersten Hardwarestart

**QEMU GO, TV NO-GO.** Für den Samsung Q60T GQ50Q60TGUXZG,
Nike-L/SDP1804, T-NKLDEUC 2743.0. Dies ist ein Laborarchiv ohne
Gerätestartbefehl. Ausgangspunkt:
[PR #30](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/pull/30),
BUILD108 `fd8cabcfb3d02fe906f3969bd7bf34aa3b8d18ad`,
[Run 43641459553](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/actions/runs/43641459553).
BUILD110 liest das gepinnte lokale BUILD109-ZIP und übernimmt das
ARM32-zImage und beide Q60T-DTBs bytegleich. Keine Module im neuen Archiv.

`initramfs.cpio` ist ein deterministisches unkomprimiertes newc-Archiv.
`/init` ist ein statisches ARM-EABI-ELF ohne Interpreter. Es meldet
`BUILD110_INITRAMFS_OK pid1` über den geerbten Konsolen-FD und den
Kernel-Logpuffer, dann wartet es. Es enthält weder Shell noch Mounts,
Modullader, Blockgeräte oder Netzwerk. Das ist eine Aussage über PID 1,
keine Zusicherung über alle eingebauten Treiber des wiederverwendeten Kernels.

Python 3.8+, `fdtget` (Debian: `device-tree-compiler`), für QEMU zusätzlich
`qemu-system-arm`. Aus dem Repo-Root, ohne Root oder Netzwerk:

```sh
B109=/pfad/BUILD109-Q60T-OFFLINE-ONLY.zip
B110=BUILD110-Q60T-OFFLINE-ONLY.zip
python3 porting/build110/build110.py build "$B109" "$B110"
python3 porting/build110/build110.py verify "$B109" "$B110"
python3 porting/build110/build110.py qemu "$B109" "$B110"
unzip -p "$B110" report.json
```

Verify prüft den gepinnten Eingang, die ZIP-Inventarliste, die interne
SHA256SUMS, den cpio-Inhalt und erzeugt den Integrationsbericht erneut.
Das äußere SHA256-Sidecar ist separat mit `sha256sum -c "$B110.sha256"`
prüfbar. Auf dem Runner `debian` die exakte BUILD109-Datei bereitstellen
und die Repository-Variable `BUILD110_BUILD109_ARCHIVE` auf ihren absoluten
Pfad setzen. Der Workflow prüft zwei bytegleiche Archive und bootet mit
QEMUs eigenem virt-DTB und PL011. Er hat keinen TV-Schritt.

## Entscheidung für den TV

**Ein technischer Blocker:** Ein vom Hersteller zugelassener, reversibler
ARM32-RAM-Handoff für eigenen Code ist auf diesem Gerät mit 2743.0 nicht
belegt. SDB-Zugriff und die vorhandenen BUILD108-Binärdateien belegen
keinen Handoff. Die bisherigen Audits liefern keinen Startbefehl.

**Ein Experiment:** Auf dem exakten Modell mit 2743.0 einen vom Hersteller
für diese Firmware dokumentierten RAM-Diagnosestart mit einem offiziell
zugelassenen, flüchtigen ARM32-Testpayload beobachten. Als Ergebnis einen
extern erfassten Diagnosemitschnitt mit Modell/Firmware, Handoff,
eindeutigem Payload-Marker und anschließendem normalen Stock-Boot nach
Kaltstart sichern. Nur durchführen, wenn der Hersteller den Einstieg,
das Testpayload, den Diagnosekanal und die Nichtpersistenz dokumentiert.
Ohne diese Unterlagen bleibt das Experiment aus; ein Firmware-Update
oder ein undokumentierter Servicebefehl dient nicht als Ersatz.

**GO für einen BUILD110-Geräteversuch** erst, wenn alle folgenden Kriterien
belegt sind:

- Der Handoff akzeptiert den vorgesehenen Kernel/DTB/Initramfs in RAM,
  mit belegten ARM32-Einstiegsbedingungen und sicherem Rückweg zum Stock-Boot.
- Das aktive CPU/GIC/RAM-Profil und die effektiven Speicherreservierungen
  sind bestätigt. Kernel, DTB, Initramfs und der Dekompressionsbereich
  passen ohne Überschneidung in belegten freien RAM. Kein Raten anhand
  der Profilnamen.
- Die auf dem Gerät beobachtbare, stockbelegte Konsole ist im frühen
  Kernel verfügbar. `stdout-path` allein reicht nicht: der wiederverwendete
  Kernel hat `CONFIG_SERIAL_SDP=m`. Die unveränderten DTBs übernehmen die
  Stock-Reservierungen nicht. Beides muss vor einem GO behoben und verifiziert sein.
- Das Startartefakt besteht die Offline-Prüfung; Speichercontroller für
  persistente Medien bleiben deaktiviert, ebenso Display/HDMI. Der
  SDP-DRM-Probe-Interlock bleibt aktiv. QEMU verwendet keinen TV-DTB.

**Abbruch / NO-GO** bei einem fehlenden Nachweis oder abweichender
Gerätekennung. Als Hardwareerfolg zählen erst die Linux-6.6.162-Bootzeile
und der PID-1-Marker vom realen TV, gefolgt vom normalen Stock-Boot.
Das Samsung-Display-Testbild ist ein separater Schritt nach diesem Erfolg.
