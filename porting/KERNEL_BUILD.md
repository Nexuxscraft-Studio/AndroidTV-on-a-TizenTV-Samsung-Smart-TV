# Teilprojekt 1: Originalkernel 4.1.10 reproduzieren

**Status: Samsung-Quellbaum vorhanden, Android-Kconfig im isolierten
Hostlauf erfolgreich abgeglichen; Originalkernel noch nicht neu gebaut.**

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
veröffentlicht hat. Seit Build 010 liegt das vom Besitzer über HTTPS
bereitgestellte Paket `20_DTV_NikeL.zip` lokal vor. Darin gibt es
Linux-4.1.10-Kernel- und Mediaquellen. **Die exakte Übereinstimmung
mit dem Firmwarepatchstand 2743.0 ist noch nicht belegt**; auch eine
nachweislich richtige `Nike.L`-Defconfig fehlt weiterhin.

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
Das Releasepaket ist seit Build 010 vorhanden. Weiterhin benötigt werden
die exakte Nike-L-/2743.0-Defconfig, ein passender Cross-Compiler und
eine strengere Versions-/Patchstandsprüfung.

## Build 012 – echte Kconfig-Auflösung statt bloßer Befehlsplanung

Die Host-Tools konnten **zweimal erfolgreich `make olddefconfig`**
mit `O=`-Ausgabe ausführen. Im ersten Lauf wurde ein alter
Binder-32-Bit-Modus trotz `n` im Fragment durch einen versteckten
`default y`-Wert aktiviert. In einer separaten Kernelkopie hat ein
kleiner Patch diesen Default geändert; der zweite Lauf behielt dann
`CONFIG_ANDROID_BINDER_IPC_32BIT=n`, während Binder aktiv blieb.
Die restlichen untersuchten Konfigurationswerte und Samsungs Smack-
/SFD-Sicherheit blieben unverändert.

Die vollständige Begründung, Patchdatei und reproduzierbaren Schritte
stehen in [`ANDROID_KERNEL_BRIDGE.md`](ANDROID_KERNEL_BRIDGE.md)
und [`BUILD012_REPORT.md`](../BUILD012_REPORT.md).

**Es gibt weiterhin kein gebautes `zImage` oder Android-Bootimage.
Die passende ARM32-Toolchain fehlt und Binder-/Grafik-/SELinux-
Kompatibilität mit Android ist nicht nachgewiesen.**

## Build 008 – Fundstellen und Compiler-Abgrenzung

Details und Quellenlinks: [BUILD008_REPORT.md](../BUILD008_REPORT.md).

- Der [Tizen-CDN](https://cdn.download.tizen.org/sdk/tizenstudio/tizen_studio_source/source/)
  führt `gcc-6.2.1.tar.gz` als **GCC-Quellarchiv**, nicht als
  fertig verwendbare Samsung-Toolchain.
- Ein [Samsung-Research-UK-Projekt](https://github.com/SamsungResearchUK-IoT-Meetup/samsung-tf-lite/wiki/3.-Build-%26%26-Run)
  nennt einen Linaro-GCC-6.2.1-ARM32-Cross-Compiler **2016.11**.
  Unser Firmwarebanner meldet `Tizen/Linaro GCC 6.2.1 (20161213)`;
  aus gleicher Versionsnummer folgt **keine** identische Toolchain.
- `toolchain_version_matches_reference` und `toolchain_target_is_arm32`
  zeigen nur technische Ähnlichkeit. Die strengere Prüfung
  `matching_tizen_linaro_toolchain` bleibt bis zu einem unabhängig
  belegten Samsung-Compiler-Abgleich `false`.
- Ein 2018er Samsung-**KantS**-Linux-4.1.10-Baum ist nicht der
  **Nike-L**-Baum und darf die fehlenden Originalquellen nicht ersetzen.
