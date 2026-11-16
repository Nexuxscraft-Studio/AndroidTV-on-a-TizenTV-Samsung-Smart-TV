# BUILD 122 · Offline-Speicherprüfung für Nike-L

Der Checker vergleicht die Legacy-Headeradressen numerisch mit den aus dem
Samsung-Firmware-DTB bekannten Kernel-RAM-Bänken. Alle Intervalle sind
halboffen. Das Ergebnis für beide Profile ist `UNKNOWN` für Adressübersetzung
und Bootloader-Handoff sowie `NO-GO` für den Hardwareeinsatz.

| Profil | Firmware-`/memory/reg` (Start und Länge) |
| --- | --- |
| nikel-2G | `0x40000000` / 320 MiB, `0xa2000000` / 988 MiB, `0xe4000000` / 152,5 MiB |
| nikel-1.5G | `0x40000000` / 120 MiB, `0x4f000000` / 268 MiB, `0xa2000000` / 480 MiB, `0xca000000` / 250,25 MiB |

Die Werte aus [dem Firmware-Extrakt](../../reports/hardware_2743.0_build004_final.json)
stimmen mit dem BUILD059-DTS-Patch überein. BUILD111
[`stock-reservations.json`](../build111/stock-reservations.json) ordnet den
beiden DTB-Hashes die Reservierungen zu. Der Checker zieht alle
Schnittmengen mit den Bänken ab, einschließlich Stock-CMA mit `reusable`.
BUILD111 übernimmt diese CMA-Bereiche als feste Reservierungen und übernimmt
die zwei `no-map`-Carveouts je Profil mit ihrem Flag. Auch Einträge außerhalb
der Bänke bleiben im Report sichtbar. Die Artefaktprüfung liest die
kompilierten DTBs und vergleicht sämtliche Bankgrenzen, Reservierungen und
`no-map`-Flags. Der Begriff „statisch frei“ bezeichnet den Rest dieser DTB-Map.

| Messung | Ergebnis und Quelle |
| --- | --- |
| Samsung Legacy-Header | ARM32, Load und Entry `0x80008000`, Legacy-Payload 7.040.960 Bytes laut BUILD050, Firmware-Kernelreport und BUILD121-CI-Report. Die Originaldatei lag lokal nicht vor. Mit `--stock` prüft der Checker den bekannten SHA-256 und beide CRCs direkt. |
| BUILD121 Legacy-Header und zImage | Load und Entry `0x80008000`, 12.030.464 Bytes Payload plus 64 Bytes Header. Der Payload ist 4.989.504 Bytes größer als beim Original. Geprüft über SHA256SUMS, beide Legacy-CRCs und ARM-zImage-Magic. |
| Dekomprimiertes BUILD121-Image | 34.070.520 Bytes aus dem CRC-geprüften eingebetteten gzip-Stream, abgeglichen mit dem BUILD121-Report. Die Zieladresse, BSS, Relokation, Workspace und Laufzeitbedarf bleiben unbekannt. |
| DTBs und Initramfs | 7.577 Bytes für 1,5G, 7.453 Bytes für 2G und 796 Bytes für das Initramfs. Die Handoff-Adressen sind unbekannt. |

Die beiden numerischen Ladespannen beginnen außerhalb aller aufgeführten
Kernel-RAM-Bänke. Die Firmware-DTBs beschreiben die dem Kernel deklarierten
Bereiche. Der Header enthält Bootloader-Metadaten. Ob der Bootloader eine
Alias-/Remap-Adresse verwendet oder dem Kernel andere Speicherbereiche
übergibt, bleibt offen. Auch ein ausreichend großer statischer Bereich
liefert keine Aussage über tatsächliche Dekompressions- oder Handoff-Adressen.

## Reproduktion

```sh
python3 -m unittest discover -s porting/build122
python3 porting/build122/memory_check.py --output memory-report.json
python3 porting/build122/memory_check.py --artifacts /path/to/extracted-build121 --output build121-artifact-report.json
```

[`memory-report.json`](memory-report.json) verwendet Repository- und
Referenzwerte. [`build121-artifact-report.json`](build121-artifact-report.json)
wurde aus dem veröffentlichten
[BUILD121-Artefakt 14241379764](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/actions/runs/43900014482/artifacts/14241379764)
erzeugt. Optional vergleicht `--archive` das geprüfte BUILD111-ZIP samt
SHA-256-Sidecar und zImage, rohem Image und Begleitdateien aus demselben Build.

Der BUILD122-Workflow nutzt den vorhandenen Debian-Self-Hosted-Runner. Er
erzeugt zuerst den Referenzreport und vergleicht ihn bytegenau. Danach
verwendet er die vorhandene BUILD111/121-Pipeline mit den bestehenden
Runner-Eingaben und lädt den binär verifizierten Bericht separat hoch. Der
Referenzreport bleibt auch bei einem fehlgeschlagenen Build-Schritt verfügbar.
Ein erfolgreicher Offline-Lauf behält den Hardwarestatus `NO-GO` bei.
