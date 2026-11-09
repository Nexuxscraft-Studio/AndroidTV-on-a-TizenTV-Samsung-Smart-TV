# Build 013: ARM32-Kompilierung – strikt offline am Entwicklungsrechner

**Build 015 ergänzt zwei separat auswählbare Kernelversuche:**
`--profile selinux-lab` schaltet in der Schattenkonfiguration SELinux
als Standard-LSM ein; `--profile android-bootlab` aktiviert zusätzlich
`BLK_DEV_INITRD`, `IKCONFIG` und `IKCONFIG_PROC`. **Beide Profile haben
einen echten ARM32-Hostcompile erfolgreich durchlaufen**, Details und
Hashes in [`BUILD015_REPORT.md`](../BUILD015_REPORT.md).
Ohne `--profile` bleibt das bisherige `tizen`-Standardprofil unverändert.

Dieses Experiment verwendet den von Samsung bereitgestellten Linux-4.1.10-
Quellbaum aus `20_DTV_NikeL.zip`. **Es erzeugt keine installierbare Samsung-
Firmware, kein Android-ROM und keinen sicheren Flash-/Bootpfad.** Das
ursprüngliche Archiv wird nicht im Projekt verteilt.

## Wichtige Unterschiede zum echten Fernseher

1. Die mitgelieferten Nike-Konfigurationen heißen `Nike.M-...`; die zum
   konkreten Q60T passende Nike-L-Defconfig ist **nicht** nachgewiesen.
2. Das Samsung-`BUILD.sh` prüft die Compilerkennung `20161213`. Die für
   den Hosttest verwendbare, separat herunterladbare TI-Linaro-Toolchain
   meldet GCC `6.2.1 20161016`. **Sie ist kein nachgewiesener Ersatz für
   den exakten Samsung-Compiler.**
3. Das Samsung-Skript erzeugt `include/linux/vdlp_version.h` mit einer
   vom Benutzer einzugebenden Kernel-Basis-/CL-Nummer. Da diese fehlt,
   erzeugt der Test ausschließlich im **kopierten Quellbaum** einen
   ausdrücklich als `HOST_ONLY_TEST` markierten Platzhalter.
4. Es gibt weder geprüfte Bootloader-Signaturen noch Hardware-/Grafik-HALs,
   einen funktionierenden Android-Userspace oder eine Recoverystrategie.

## Host-Werkzeuge

Linux mit `python3`, `make`, `gcc` (Host-Compiler), `patch`, `bc` und einem
ARM32-Linux-Cross-Compiler (GCC + GNU assembler).

Ein historisch passenderer, aber **nicht herstelleridentischer** Compiler
ist die von **Texas Instruments** herausgegebene Toolchain
[`gcc-linaro-6.2.1-ti2017.01-armv5-x86_64_arm-linux-gnueabi.tar.xz`](https://software-dl.ti.com/sdoemb/sdoemb_public_sw/arago_toolchain/2017_01/exports/gcc-linaro-6.2.1-ti2017.01-armv5-x86_64_arm-linux-gnueabi.tar.xz).
Das offizielle [TI-Releaseblatt](https://software-dl.ti.com/sdoemb/sdoemb_public_sw/arago_toolchain/2017_01/index_FDS.html)
nennt GCC 6.2 und binutils 2.27; TI gibt im
[MD5-Prüfsummenblatt](https://software-dl.ti.com/sdoemb/sdoemb_public_sw/arago_toolchain/2017_01/exports/md5sum.txt)
für das Archiv `afc80fe3e45d2992433b639c242f8ac6` an.

## Reproduzierbarer Test

Aus dem Projektverzeichnis (`q60t-lineage-lab`):

```bash
python3 q60t_compile_probe.py \
  --source /pfad/zu/entpacktem/linux-4.1.10 \
  --workspace /pfad/zu/NEUEM-build013-arbeitsverzeichnis \
  --cross-prefix /pfad/zu/linaro/bin/arm-linux-gnueabi- \
  --jobs 4 --timeout 1800
```

Optional vorab `--preflight`: prüft Quellen, Symlinks, Tools und
Compilerkennung **ohne** ein Arbeitsverzeichnis anzulegen.

Das Programm bricht absichtlich ab, wenn sein Arbeitsverzeichnis schon
existiert, ein Symlink aus dem Quellbaum ausbricht oder die bekannten
Kernel-Hashes nicht passen. Es kopiert die Quellen in ein eigenes
Verzeichnis; **nur dort** werden folgende experimentelle Anpassungen
vorgenommen:

- `0001-android-binder32-modern-abi.patch`: Kconfig-Binder-ABI-Default
  `y` auf `n`, ohne Smack/SFD abzuschalten.
- `0002-legacy-dtc-yylloc-host-gcc.patch`: behebt eine doppelte globale
  `yylloc`-Definition im vom Host-GCC gebauten Device-Tree-Compiler.
- Host-Test-Marker `include/linux/vdlp_version.h`, der **keine** echte
  Firmwareversion vorgibt.
- Für den Compiler wird der in den Samsung-Quellen vorhandene
  `kernel/t2ddebugd/include`-Pfad bereitgestellt.
- Nur bei explizitem `--profile` wird danach ein zusätzliches
  SELinux-/Initramfs-Konfigurationsoverlay angewendet und im
  `STAGE_MANIFEST.json` als verändertes experimentelles Sicherheitsprofil
  kenntlich gemacht.

Erst `make olddefconfig`, dann – **nur bei exaktem Abgleich** der acht
Android-Forschungsoptionen und der profilabhängigen Sicherheits- und
Bootkonfiguration –
`make zImage` mit `ARCH=arm` und explizitem `CROSS_COMPILE`.
Es wird nie das Samsung-Skript `BUILD.sh` ausgeführt: Dieses ist
interaktiv und führt auch Aufräum-, Signatur- und Systemschritte aus.

Nach Abschluss stehen im Arbeitsverzeichnis ein `compile-report.json`,
`kconfig.log`, `compile.log` sowie im Erfolgsfall `output/arch/arm/boot/zImage`.
Der Bericht lässt `signed_or_flashable_image_produced` stets auf `false`.

**Ein `zImage`-Build ist nur eine Compilerprobe. Bitte den erzeugten
Kernel nicht auf den TV übertragen oder flashen.**
