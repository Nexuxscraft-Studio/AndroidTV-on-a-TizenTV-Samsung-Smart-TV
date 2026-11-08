# Teilprojekt 1: Originalkernel 4.1.10 reproduzieren

**Status: Werkzeugkette vorbereitet, Originalkernel noch nicht neu gebaut.**

## Verifizierte Buildparameter aus der Firmware

Die offizielle `T-NKLDEUC-2743.0`-Referenzfirmware enthält ein gültiges
ARM32-U-Boot-`uImage` mit einem Linux-4.1.10-Payload. Aus dem Banner in
diesem exakten Image lassen sich folgende Werte extrahieren:

| Merkmal | Aus der Referenzfirmware |
| --- | --- |
| Kernelversion | `4.1.10` |
| Architektur des Images | 32-Bit ARM |
| Compiler | Tizen/Linaro GCC `6.2.1` (`20161213`) |
| Hersteller-Build | `abuild@B4404DRG` (nur eingebetteter Buildstring) |
| Buildzeit | `Thu Jul 2 08:47:01 UTC 2026` |
| Laufzeitkonfiguration im Image | Kein `IKCFG_ST` vorhanden |
| Kernel-Hash SHA-256 | `6603f3f5082d6ef74471f9233ce17063658daf10e1d9440a8a9c75749a5e72b2` |

**GCC 6.2.1 allein garantiert keine Binärreproduktion.** Samsung-Quellen,
Defconfig, Toolchain-Patches, genaue Compilerflags, eingebettete
Buildmetadaten und etwaige proprietäre Module müssen ebenfalls passen.

## Bezugsweg für Samsung-GPL-Quellen

Synacktivs Q60T-Forschung bestätigt, dass Samsung den Kernel und viele
Treiberquellen im [Samsung Open Source Release Center](https://opensource.samsung.com/uploadSearch?searchValue=Q60T)
veröffentlicht hat. Der konkrete, zu **2743.0** passende Quellcode wurde
im aktuellen Arbeitskontext **nicht bezogen**. Die direkte Portalabfrage
war hier nicht erfolgreich; ein beliebiger Linux-4.1.10-Tarball wäre kein
Ersatz.

- Referenz: [Synacktiv GreHack 2021, „Rooting Samsung Q60T“](https://www.synacktiv.com/sites/default/files/2021-11/GreHack2021_Rooting_Samsung_Q60T_Smart_TV.pdf).
- Samsung zu Kernel-/Defconfig-Buildgrundlagen:
  [Tizen-Quellcode-Dokumentation](https://github.com/Samsung/tizen-docs/blob/master/docs/platform/porting/kernel.md).

## Neue Prüfkette

`q60t_kernel_build.py` untersucht einen **lokalen, vom Benutzer bezogenen
Kernelquellbaum** sowie dessen `.config` und einen ARM-Cross-Compiler.
Es erwartet mindestens:

1. Kernel-`Makefile` mit `VERSION=4`, `PATCHLEVEL=1`, `SUBLEVEL=10`.
2. `arch/arm/Makefile`, eine ARM-Konfiguration und passende Basisflags.
3. Tizen/Linaro-GCC-Version **6.2.1** als Referenz (keine andere Version
   wird als exakt passend bezeichnet).
4. **Separat verifizierte Herkunft** des Samsung-Sourcepakets.

```bash
python3 q60t_kernel_build.py

# Sobald Originalquellen, Originalconfig und Compiler vorhanden sind:
python3 q60t_kernel_build.py \
  --source /pfad/zu/samsung-linux-4.1.10 \
  --config /pfad/zu/nikel-defconfig \
  --cross-compile /pfad/zu/toolchain/bin/arm-linux-gnueabi- \
  --output-dir /pfad/zu/build-kernel
```

Der Befehl **baut heute noch kein Image**. Er erzeugt einen prüfbaren
Kommandoentwurf mit `ARCH=arm`, getrenntem `O=`-Buildverzeichnis und
`zImage` als Arbeitsziel. Build 007 ergänzt beim Vorliegen aller Eingaben
die bisher fehlende Konfigurationsübernahme: `mkdir -p O=...`,
`cp <Originalconfig> O=.../.config`, dann `make ... olddefconfig` und
`make ... zImage`. Die Herkunftsfreigabe ist absichtlich
`false` bis das konkrete Samsung-Paket unabhängig verifiziert wurde.
Mit der vorliegenden Originalfirmware ist nur der **Referenzbanner**
nachgewiesen, kein eigener erfolgreicher Build.

Es gibt hier keine Optionen, um etwas auf den TV zu übertragen oder
einen Bootloader umzuprogrammieren.

## Build 007 – separates Archiv-/Herkunftsinventar

Das neue `q60t_source_provenance.py` erstellt einen SHA-256 über ein
lokales ZIP-/TAR-Archiv, untersucht Metadaten (inklusive Link-/Pfadrisiken)
und liest die Version eines lokalen Kernelquellbaums. Es entpackt oder
kompiliert **nichts**. Ein Hashverweis, der nur aus derselben Datei
berechnet wurde, ist kein unabhängiger Quellenbeleg.

```bash
python3 q60t_source_provenance.py \
  --archive /pfad/zum/originalen-samsung-source.zip \
  --source /pfad/zum/linux-4.1.10 \
  --expected-sha256 <unabhaengig-gepruefter-sha256>
```

Der Status kann maximal `MANUAL_REVIEW_REQUIRED` werden; das bedeutet
**nicht**, dass das Paket passend zur Firmware 2743.0 freigegeben ist.
Das Samsung-Portal ließ sich in der verwendeten Umgebung nicht abrufen.
Die historische Quelle von Synacktiv benennt ausdrücklich die
[Q60T-Suche im Samsung OSSRC](https://opensource.samsung.com/uploadSearch?searchValue=Q60T).
Benötigt werden das tatsächliche Releasepaket, dessen Build-Anleitung,
die Nike-L-Defconfig, Compiler und eine Prüfung der Herkunft.
