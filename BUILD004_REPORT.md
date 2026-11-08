# Build 004 – Erster LineageOS-Android-TV-Portbaum und überprüfte RAM-/Input-Profile

**Stand:** 08.11.2026  
**Ergebnis:** Reproduzierbares Forschungsskelett für Samsung Nike-L, zwei
explizite RAM-Referenzprofile, echte Device-Tree-Auswertung bis zu
Speicherbereichen und Aktivierungsstatus, maschinelle Portierungsprüfung.

**Kein funktionierendes oder flashbares LineageOS-Image. Kein Zugriff auf
den Fernseher, keine Firmwaremodifikation.**

## 1. Warum noch kein Android-TV-Image möglich ist

Der Nutzer hat einen Samsung Q60T mit 50 Zoll und berichtet Firmware
`2743.0`. Der vollständige Modellcode und der tatsächlich verwendete
Board-/RAM-Typ sind unbekannt. Die bisher geprüfte Firmware `T-NKLDEUC-2743.0`
ist die **55-Zoll-Referenz** `GQ55Q60TGUXZG`; eine identische
Versionsnummer allein beweist **keine** vollständige Kompatibilität.

Der Samsung-Kernel ist Linux **4.1.10, ARM32**. Ein funktionsfähiger
LineageOS-Port benötigt mindestens einen passend gebauten Kernel,
einen vorab getesteten reversiblen Bootweg, Android-kompatible
Grafik-, Display-, Audio- und Videotreiber und ein funktionierendes
Recovery. Keines dieser zentralen Elemente ist heute nachgewiesen.

## 2. Neue technische Implementierung

| Bestandteil | Jetzt vorhanden | Sicherheitsbedingung |
| --- | --- | --- |
| `porting/device/samsung/nikel/AndroidProducts.mk` | Produktregistrierung und `userdebug`-Lunchauswahl | Build wird gesperrt |
| `lineage_nikel.mk` | Android-TV-Produktdefinition mit ATV-Grundlagen von LineageOS | Kein lauffähiger Geräteport |
| `device.mk` | Einhängepunkt für künftige verifizierte Vendor-/HAL-Komponenten | Noch absichtlich leer |
| `BoardConfig.mk` | Board-Namensraum und **explizite Makefile-Fehlersperre** | Keine erfundenen Partitionen/Images |
| `profiles/*.json` | Zwei DTB-Profile mit geprüften SHA-256, Offsets und RAM-Referenzdaten | `usable_for_flashing=false` |
| `port-state.json` | Zehn unabhängige Freigabe-Gates | Alle zehn offen |
| `q60t_portcheck.py` | Abgleich von Profildateien, Firmware-DTBs, RAM-Karten und Status | `BLOCKED`, `flash_authorized=false` |
| `q60t_release_audit.py` | Quellcode-/Binär-/Secret-Heuristik vor einer späteren Freigabe | Keine formale Lizenzprüfung |

Das Android-TV-Gerüstskelett folgt in seiner Produktidee der
[offiziellen LineageOS-Gerätestruktur für das Android-TV-Gerät „beast"](https://github.com/LineageOS/android_device_google_beast).
Sein Vorhandensein ist **kein Beleg**, dass der proprietäre Samsung-Kernel
den aktuellen Android-Userspace ausführen könnte.

## 3. Device Trees: RAM-Bereiche erstmals dekodiert

Die zwei FDTs wurden aus einer offline entschlüsselten offiziellen
Referenzfirmware gelesen und anhand ihrer Hashes zugeordnet. Die Angaben
in `dtsversion` lauten `nikel-2G` und `nikel-1.5G`.

| Messwert im Referenz-DTB | `nikel-2G` | `nikel-1.5G` |
| --- | --- | --- |
| FDT-Offset im Bundle | `0` | `86.016` Byte |
| Nodes | 365 | 367 |
| FDT-`/memory/reg`-Bereiche | 3 | 4 |
| Summe der als Memory-`reg` deklarierten Bereiche | **1.460,5 MiB** | **1.118,25 MiB** |
| RAM-Profilbezeichner aus Bootargumenten | „2G“ | „1.5G“ |

Die Bereiche im 2G-Profil liegen ab `0x40000000` (320 MiB), `0xa2000000`
(988 MiB) und `0xe4000000` (152,5 MiB). Beim 1.5G-Profil sind es
`0x40000000` (120 MiB), `0x4f000000` (268 MiB), `0xa2000000` (480 MiB)
und `0xca000000` (250,25 MiB).

**Wichtig:** Der FDT-Eintrag beschreibt Adressabschnitte, die der Kernel
als Speicher nutzen soll. Reservierungen, Speicherlücken und firmwareseitige
Layoutentscheidungen können bedeuten, dass die Summe **kleiner als der
physisch verbaute RAM** ist. Auch das `2G`-Etikett ist keine Messung am
50-Zoll-Gerät. Der Analyzer bezeichnet diese Daten daher ausdrücklich
als *deklariert*, nicht als installierten RAM.

Der Decoder liest höchstens 32 Einträge aus Standard-32-/64-Bit-Zellen,
verwirft ungültige Zellenlängen und exportiert keine rohen proprietären
Device-Tree-Properties oder individuellen Gerätenummern.

## 4. Input-/CEC-Erkenntnis: Knoten vorhanden ≠ aktiv

Die neue Auswertung berücksichtigt die `status`-Eigenschaft jedes
Knotens. Bei beiden Referenz-DTBs wurden festgestellt:

| Komponente | DT-Pfad | Deklarierter Zustand |
| --- | --- | --- |
| IR-Schnittstelle `mcirb` | `/soc/mcirb` | `okay` |
| IR-Schnittstelle `mcirs` | `/soc/mcirs` | `okay` |
| HDMI CEC | `/soc/cecif` | **`disabled`** |
| Mali Midgard | `/soc/sdpgpu@00500000` | Status nicht spezifiziert |

Das ist nützlich für den späteren Android-Input-Stack. Es belegt aber
**weder**, dass die Fernbedienung bereits Android-Keyevents liefert,
**noch**, dass CEC hardwareseitig unmöglich ist: Tizen könnte den
Treiber dynamisch aktivieren oder einen anderen Pfad verwenden.
Die Android-Integration und die echten Signale auf dem TV sind ungeprüft.

Unter `porting/HAL_MATRIX.md` stehen die priorisierten Schnittstellen für
GPU/SurfaceFlinger, Panel, HDMI/CEC, Fernbedienung, Audio, Samsung-MFC,
Netzwerk, eMMC, WLAN und DRM. Treiber oder Tizen-Libraries werden nicht
fälschlich als Android-HAL deklariert.

## 5. Portierungsprüfung und Tests

Ausführen aus dem Projektordner:

```bash
python3 q60t_portcheck.py --project porting \
  --hardware-report reports/hardware_2743.0_build004_final.json

python3 q60t_release_audit.py .

python3 -m unittest discover -s tests -v
```

**Erwartetes Ergebnis:** Der Portcheck meldet `BLOCKED` und beendet sich
mit Code **1** (kein unerwarteter Fehler), weil alle zehn entscheidenden
Freigaben fehlen. Auch ein in Zukunft voll ausgefülltes Gate-Manifest
erteilt **keine automatische Flashberechtigung**; es wäre noch eine
gesonderte menschliche Review erforderlich. Die Makefile-Sperre bleibt
in jedem Fall aktiv.

**24 synthetische Unit-Tests** bestanden im Arbeitskontext. Darunter sind
CRC-/Header-Checks, Safe-Archive-Handling, FDT-Bounds, RAM-`reg`-Zellen,
DT-`status`, Profilabgleich, Ablehnung vertauschter RAM-Daten,
nicht überschreibbare Reports sowie Freigabeaudits.

Das Release-Audit läuft ausschließlich auf lokalen Text- und
Quellcodedateien und lehnt auffällige Binärdateien oder Schlüsselmarker
ab. Es garantiert weder die Abwesenheit aller Geheimnisse noch die
rechtliche Veröffentlichungserlaubnis. **Im abgegebenen Quellpaket
sind keine Samsung-Firmwareimages, Kernel-Binaries oder fremden
Reverse-Engineering-Quelltexte enthalten.**

## 6. Grenzen der bisherigen Firmware-Extraktion

`platform.img` (`VDFS2007`) wurde bisher nur roh auf harmlose Pfadstrings
untersucht. Daraus ergeben sich **320 mögliche Pfadreferenzen**, aber
keine verifizierten exportierbaren Einzeldateien oder Android-HALs.
Ein historischer C-Unpacker stürzte beim Dateiinhaltsentpacken ab. Ein
neuerer Rust-Entpacker war in dieser Umgebung ohne Rust-Toolchain nicht
kompilierbar. Den unsicheren C-Binärdecoder haben wir ohne verlässliche
Isolation nicht erneut mit weitreichenden Dateirechten gestartet.

## 7. Nächste nachvollziehbare Meilensteine

1. **Exakte 50-Zoll-Modellkennung + passender Samsung-Firmwarezweig**;
   keine Annahme aus der 55-Zoll-Referenz.
2. **Genaue Samsung-GPL-Kernelquellen und Konfiguration** sichern,
   den ausgelieferten Kernel reproduzierbar bauen.
3. **Signatur-/Recovery-/Testboot-Kette** offline prüfen, ohne den TV zu
   verändern, bis ein sicherer und reversibler Testpfad nachgewiesen ist.
4. **Echte Android-Treiberstrategie** für Mali/Display/Composer,
   Input/CEC, Sound und Video entwickeln. Besonders alte Android- und
   Tizen-Binärtreiber sind nicht ohne Weiteres miteinander kompatibel.
5. Erst mit diesen Voraussetzungen einen **minimalen, reversiblen
   Bootversuch** vorbereiten; danach LineageOS/Android TV bauen.

## 8. Belegdateien

- `reports/hardware_2743.0_build004_final.json`: Hash-verifizierte
  55-Zoll-DTB-Strukturen, `memory/reg`, DT-Status, Hardwarekategorien.
- `reports/port_preflight_build004_final.json`: zehn noch offene Gates,
  Profil- und Aktivierungsübersicht, Flashfreigabe ausdrücklich `false`.
- `reports/kernel_2743.0.json`: Linux-Banner, Kernel-Security-Strings.
- `reports/rootfs_strings_2743.0.json`: unverifizierte Dateisystempfade.
- `BUILD002_REPORT.md` und `BUILD003_REPORT.md`: ältere Forschungsstufen.

Alle Befunde sind auf **ein bestimmtes offizielles 55-Zoll-Referenzpaket**
begrenzt. Eine direkte Kompatibilitätsaussage für den 50-Zoll-Q60T oder
ein Versprechen von Netflix/Prime-Video-/Apple-TV-DRM-Kompatibilität
ist daraus nicht ableitbar.
