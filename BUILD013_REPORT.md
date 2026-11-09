# Build 013 – Erster erfolgreicher ARM32-Linux-Kernel-Testbuild

**Datum:** 09.11.2026  
**Zielmodell:** Samsung GQ50Q60TGUXZG / T-NKLDEUC 2743.0 (Besitzerangabe)  
**Sourcekandidat:** offizielles Samsung-Archiv `20_DTV_NikeL.zip`, Kernel Linux 4.1.10

## Ergebnis

**Erstmals konnte der tatsächlich im Samsung-Quellpaket enthaltene
Linux-4.1.10-Kernel auf einem Linux-Entwicklungsrechner für ARM32 bis
zum `zImage` erfolgreich kompiliert werden.** Danach gelang ein
vollständig vom neuen Python-Werkzeug gesteuerter **zweiter Build**.

```text
  LINK    vmlinux
  LD      vmlinux.o
  LD      vmlinux
  SORTEX  vmlinux
  OBJCOPY arch/arm/boot/Image
  Kernel: arch/arm/boot/Image is ready
  OBJCOPY arch/arm/boot/zImage
  Kernel: arch/arm/boot/zImage is ready
```

Das ist **nur ein Host-Kompilierungserfolg**. Das Resultat ist **kein
verifiziertes Image für den Q60T**, kein Android-TV-Build, kein
Bootloader- oder Flash-Erfolg. Der reale Fernseher wurde nicht
verbunden, verändert oder gestartet.

## 1. Quell- und Compilerherkunft

| Gegenstand | Nachweis / Einschränkung |
| --- | --- |
| Samsung-Archiv | 743.308.262 Bytes; SHA-256 `3e38ad1baf54be8ed91c1c18b2c3137692c28e01ca894db9690f632a1fbd3bad` |
| Samsung-Quellkernel | `linux-4.1.10-tizen5.5.tgz`; unveränderte Vorlage außerhalb der Build-Arbeitskopie |
| Kandidat-Konfiguration | `Nike.M-Tizen_release_defconfig`, SHA-256 `54dab3e4d55462362d074e6ee11bac7be4d201cb0daa6b18de1454f162f06bc0` |
| Samsung-Original-Compiler | `BUILD.sh` verlangt Compiler-Banner `20161213`; **nicht verfügbar/verifiziert** |
| Erprobte Cross-Toolchain | TI-Linaro GCC 6.2.1, Compiler-Banner `20161016`, GNU binutils 2.27 |
| Compilerarchitektur | `arm-linux-gnueabi` (ARM32), **nicht** verifizierter Samsung-Nike-L-Compiler |

Die TI-Toolchain wurde von der offiziellen
[TI-Downloadseite](https://software-dl.ti.com/sdoemb/sdoemb_public_sw/arago_toolchain/2017_01/index_FDS.html)
bezogen und gegen die dort veröffentlichte MD5-Prüfsumme
`afc80fe3e45d2992433b639c242f8ac6` geprüft.
Ein erster Versuch mit Ubuntu ARM-Cross-GCC **13.3.0** scheiterte
zunächst am alten `yylloc`-Symbol und anschließend an GCC-13-/Assembler-
Inkompatibilitäten. Diese Versuche sind **keine** fehlgeschlagenen
Samsung-TV-Starttests.

## 2. Minimalanpassungen – nur in Schattenkopien

Das Originalarchiv und der entpackte Originalquellbaum wurden beim
Kompilieren nicht verändert. Der ARM-Compiler arbeitete ausschließlich
auf einer separaten Kopie mit externem `O=`-Verzeichnis:

1. `0001-android-binder32-modern-abi.patch`: Der alte, promptlose
   `CONFIG_ANDROID_BINDER_IPC_32BIT`-Default wird von `y` auf `n`
   gesetzt. Android-Binder selbst bleibt `y`.
2. `0002-legacy-dtc-yylloc-host-gcc.patch`: Im Device-Tree-Compiler
   doppelte Definition von `yylloc` bereinigt. Keine TV-Funktion geändert.
3. Fehlender, sonst von Samsung-`BUILD.sh` erzeugter
   `include/linux/vdlp_version.h` durch einen ausdrücklich als
   `HOST_ONLY_TEST` / `NO_FLASH` bezeichneten Platzhalter ersetzt.
4. Die bestehende Header-Suchstruktur `kernel/t2ddebugd/include`
   dem Cross-Compiler bekannt gegeben.
5. Das Host-Hilfsprogramm `bc` für die Kernel-Zeitkonstanten bereitgestellt.

**Sicherheitsoptionen nach tatsächlichem `make olddefconfig`:**

| Konfiguration | Resultat |
| --- | --- |
| Android-Binder | `y` |
| Alter Binder-32-Bit-Modus | `n` |
| Ashmem, Memcg, ION | jeweils `y` |
| Ext4, OverlayFS, TUN | jeweils `y` |
| Samsung Smack | `y` – nicht deaktiviert |
| Samsung SFD | `y` – nicht deaktiviert |
| SELinux | `n` – nicht als fertiges Android-Sicherheitsmodell behauptet |

## 3. Reproduzierbarer Build 013

Das neue CLI [`q60t_compile_probe.py`](q60t_compile_probe.py) führt
einen kontrollierten Offline-Build aus:

- Quellversion und zwei Originaldatei-Hashes prüfen;
- Symlinks auf Austritte aus dem Quellbaum prüfen (14 geprüft);
- Existenz von GNU-ARM32-GCC/Assembler, `bc` und Host-Tools feststellen;
- Ausgabeverzeichnis muss **neu** und vom Original getrennt sein;
- Schattenquellbaum anlegen, zwei Projektpatches ohne Fuzz anwenden,
  experimentellen Versionsheader schreiben;
- kontrolliert `make olddefconfig`, Ziel-/Sicherheitsoptionen abgleichen,
  danach erst `make -jN zImage` aufrufen;
- Kompilierlog, Exitcode, SHA-256 und eventuelle Fehlermeldungen in
  `compile-report.json` protokollieren.

**Vollautomatischer Wiederholungslauf:**

| Prüfung | Ergebnis |
| --- | --- |
| `olddefconfig` | erfolgreich, Exitcode 0 |
| Alle 11 abgeglichenen Kernel-/Sicherheitsoptionen | wie beabsichtigt |
| `make zImage` | **erfolgreich, Exitcode 0** |
| `file zImage` (manueller Build) | `Linux kernel ARM boot executable zImage (little-endian)` |
| ARM32-`zImage` des automatisierten Builds | **3.622.592 Bytes** |
| SHA-256 des automatisierten `zImage` | `95752132f34257595f87fba787bd021fae1b905de1b92e36bae3ba411798e45f` |
| Python-Tests | **80 bestanden** (Build 012: 72) |
| Projekt-Releasetest | **PASS**, kein Originalarchiv im Projekt |

Ein unabhängig zuvor manuell durchgeführter erfolgreicher Test erzeugte
ein `zImage` mit **3.621.400 Bytes**, SHA-256
`52943243c2cbd2515834b423ca6b77ec8e1491a2e749521f3ebe523758aea97f`.
Die verschiedenen Hashes zeigen ausdrücklich: **Zweimal erfolgreich
kompiliert bedeutet hier noch keinen bitidentischen Reproducible Build**.
Toolchain-/Datumseinflüsse und gesamte Binäridentität wären gesondert
zu prüfen. Die automatische Ausführung ist hingegen reproduzierbar.

Eine eigene Anleitung mit Aufrufbeispielen steht unter
[`porting/KERNEL_COMPILE_PROBE.md`](porting/KERNEL_COMPILE_PROBE.md).
Der Quellcode-Release enthält **bewusst weder das Samsung-Archiv noch
ein Kernel-Binärimage**.

## 4. Was für Android TV noch fehlt

1. **Exakte** Nike-L-Defconfig und Quellzuordnung für Firmware `2743.0`
   und den tatsächlichen 50-Zoll-TV.
2. Samsung-Toolchain-/Buildparameter mit der vom Hersteller verlangten
   Identität und produktionsgerechten Versions-/Signaturparametern.
3. Geräteidentische Device-Tree-/RAM-/Board-Fingerprints; keine
   experimentelle Bilddatei auf das reale Gerät spielen.
4. Android-kompatible SELinux-/Binder-/Kernel-ABI und funktionsfähiger
   Android-Userspace mit Display-/GPU-, Audio- und Media-HAL.
5. Technisch verifizierte Bootkette, unabhängiger Recovery-/Rollbackpfad
   und passende Sicherheitssignaturen.

**Phase:** experimenteller Kernel-Compile-Nachweis in **Phase 2A**.
**Nicht erreicht:** lauffähige Android-TV-Firmware oder Phase-2B-Bootfreigabe.
