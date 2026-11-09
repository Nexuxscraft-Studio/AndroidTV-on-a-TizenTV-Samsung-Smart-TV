# Build 010 – Samsung-Quellpaket empfangen und offline geprüft

Stand: **09.11.2026**. Ziel: **GQ50Q60TGUXZG**, Referenzfirmware
**T-NKLDEUC 2743.0**.

## Ergebnis

Das zuvor nur im Samsung OSSRC katalogisierte Paket `20_DTV_NikeL.zip`
wurde vom Eigentümer über einen temporären HTTPS-Link auf seinem Server
bereitgestellt und **vollständig heruntergeladen**. Beide ZIP-Ebenen
wurden mit `unzip -t` beziehungsweise `unzip -tq` ohne Fehler geprüft.
Das ist ein vom Benutzer bereitgestelltes Abbild des offiziellen
OSSRC-Downloads; ein unabhängiger Hersteller-SHA-256 wurde **nicht**
publiziert beziehungsweise hier nicht gegengeprüft.

| Datei | Größe in Bytes | SHA-256 |
| --- | ---: | --- |
| Äußeres `20_DTV_NikeL.zip` | 743308262 | `3e38ad1baf54be8ed91c1c18b2c3137692c28e01ca894db9690f632a1fbd3bad` |
| Darin `20_DTV_NikeL.zip` | 743255109 | `ceebe20245945571ff30f9584bc62e4c7fed138f320a55d8e876f3abd05ee20a` |
| `linux-4.1.10-tizen5.5.tgz` | 134448317 | `31a92f0d20248abbe2976bd2da1ab95dde4fed3e010ddcdc1c07494c4fd867b0` |
| `tztv-media-nike.tgz` | 36365646 | `40c2a25eba331b8b04d8d81baf76061493f15f228a74893c7f825f7a1da724b6` |

Die äußere ZIP enthält **zwei** Dateien: `20_DTV_NikeL.txt` (61 B)
und eine weitere ZIP gleichen Namens. Die innere ZIP hat **116**
Einträge, unter anderem Kernel, Samsung-Treiberquellen, VDFS-Werkzeuge,
Audio/Video-Unterpakete und `compiler/gcc.tgz` (221159407 B).

## Kernelbefund

Das Kernel-Tarball enthält **54173** Archiveinträge, etwa 581 MB
deklarierte entpackte Dateidaten und einen echten Linux-Quellbaum.
`Makefile` bestätigt **4.1.10**. Das passt zur Versionsnummer des
extrahierten Referenz-`uImage`, **nicht** automatisch zu dessen Patchstand.

Konkrete Nike-L-Belege im Quellbaum:

- `arch/arm/mach-sdp/board-nike-dt.c`: `samsung,sdp-nikel` in der
  `dt_compat`-Liste.
- `drivers/soc/sdp/common.c`: erkennt `samsung,sdp-nikel` und ordnet
  `SDP_NIKEL_CHIPID` zu.
- `include/soc/sdp/soc.h`: kennt `soc_is_nikel()` und Nike-L.
- `drivers/gpu/arm/t6xx/kbase/`: ARM-Mali-Kerneltreibercode.
- `tztv-media-nike.tgz`: zusätzliche Samsung-Media-/Display-/FRC-
  Quelltexte, **keine** nachgewiesene Android-HAL.

**Konfigurationshinweis:** Unter `arch/arm/configs/` findet sich eine
`Nike.M-Tizen_release_defconfig` mit `CONFIG_ARM=y`, `CONFIG_AEABI=y`,
`CONFIG_ARCH_SDP_NIKE=y`, VDFS4- und IR-Konfigurationen. Eine
`Nike.L-Tizen_release_defconfig` ist im überprüften Archiv **nicht**
vorhanden. Der gemeinsame Nike-Code kann beide Varianten erkennen;
die Nike.M-Konfiguration ist deshalb ein **Kandidat zum Vergleich**, aber
kein bewiesenes Abbild des Q60T-Kernels.

Die Begleitdatei `20_DTV_NikeL.txt` verweist überraschenderweise auf
`20_DTV_NikeM_0` im Samsung-OSSRC. Das ist eine **uneinheitliche
Metadatenangabe**, kein Beleg dafür, dass die gesamte ZIP falsch ist.

Die Kerneldateien im Quellpaket sind überwiegend auf **2020** datiert;
der aus der Firmware extrahierte Kernel-Banner meldet den Build
**02.07.2026**. Ein exakt reproduzierbarer 2743.0-Kernel ist daraus
**noch nicht** belegt.

## Compilerbefund

`compiler/readme_gcc.txt` beschreibt den Aufbau einer Toolchain aus
`compiler/gcc.tgz` mit `gcc/script/run.sh`. In dessen
`gcc/script/config.conf` stehen unter anderem
`TOOLCHAIN_TARGET=armv7l-tizen-linux-gnueabi`, die Architektur `arm`
und historische Tizen/Linaro-Paketbezeichnungen. Das Archiv ist
**Compiler-Quellcode plus Bauskripte**, keine bereits überprüfte oder
ausgeführte ARM-Toolchain. Keine Skripte wurden ausgeführt.

## Bewusst offene Prüfungen

- Ob der Quellstand einschließlich aller Patches mit Firmware **2743.0**
  übereinstimmt.
- Welche Konfiguration (`Nike.M` oder modifiziert) zum realen
  **50-Zoll-Gerät** passt.
- Vollständige passende GCC-Toolchain/Kernel-Buildflags.
- Passende Mali-Kernel-ABI, proprietäre EGL-/Gralloc-/Composer-Bausteine,
  Hardware-Videodekodierung und Android-Framework-Anpassungen.
- Sichere eigene Bootkette, Signaturpolitik, Recovery-/Rollback-Weg.

Das bestehende Preflight-Skript erkennt den lokalen Source-Tree und
die ARM-Konfiguration, bleibt aber planmäßig **`BLOCKED`**, weil es
keine geprüfte exakte Firmware-/Compiler-Provenienz besitzt. Die
Archivprüfung meldet Linux-typische relative Symlinks; diese wurden
manuell als normale Verweise erkannt, sind aber nach der konservativen
Prüfpolitik nicht als automatisch freigegeben markiert.

## Konsequenz für Phase 2

**Ja für die nicht-invasive Phase 2A:** Quellcodevergleich,
Defconfig-/DTS-Rekonstruktion, Testkompilierung in einem isolierten
Host-Verzeichnis und Arbeit an HAL-/Grafik-Schnittstellen.

**Nein für Phase 2B (Test-Boot/Flash):** Noch kein sicheres Bootmedium,
kein Hersteller-Signaturnachweis und kein geprüfter Recovery-Weg.
Keine Änderungen auf dem echten Fernseher durchgeführt.

**Weitergabe:** Diese Samsung-Quellarchive und Firmware-Binärdateien
werden nicht automatisch in ein öffentliches Git-Repository übernommen.
In das Projekt gehören vorerst nur Analyse, Buildskripte, Hashes und
selbst geschriebene Dokumentation.
