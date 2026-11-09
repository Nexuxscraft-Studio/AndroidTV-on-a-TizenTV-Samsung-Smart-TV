# Build 015 – SELinux, Initramfs und Android-Kernel-Lücken (09.11.2026)

> **Host-Labor für Samsung Q60T / GQ50Q60TGUXZG.** Kein Android-ROM,
> kein signiertes Samsung-Image, kein TV-Kontakt und keine Flashfreigabe.

## Ausgangsmaterial und reproduzierbare Grenze

- Originalquelle: Samsung `20_DTV_NikeL.zip`, entpackter Linux-4.1.10-Baum.
- Versuchskonfiguration: `Nike.M-Tizen_release_defconfig`, **keine**
  nachgewiesene Nike-L-Konfiguration für die tatsächliche Firmware `2743.0`.
- Cross-Compiler: `arm-linux-gnueabi-gcc` (Linaro 6.2.1 / 20161016);
  **nicht** als exakt Samsungs Toolchain-Release bestätigt.
- Beide existierenden Build-013-Quellpatches und der künstliche
  Versionsheader werden ausschließlich in der Schattenkopie angewendet.
- Alle drei Profile erzeugen ARM32-`zImage` auf dem Entwicklungsrechner.
  Build 013 hatte das `tizen`-Profil bereits erfolgreich getestet.

## Neue experimentelle Kernelprofile

`q60t_compile_probe.py` besitzt den zusätzlichen Schalter `--profile`.
Der bisherige Standard `tizen` bleibt unverändert. Alle Testprofile
erhalten ein **eigenes neues Workspace-Verzeichnis**; die originalen
Samsungquellen werden nicht überschrieben.

| Profil | Kconfig-Änderung | ARM32-Hostcompile |
| --- | --- | --- |
| `tizen` | SMACK/SFD als vorheriger Standard, SELinux `n` | in Build 013 bestätigt |
| `selinux-lab` | SELinux `y` und Standard-LSM `selinux`, SMACK/SFD weiter einkompiliert | **PASS** |
| `android-bootlab` | Wie SELinux-Lab, zusätzlich `BLK_DEV_INITRD`, `IKCONFIG`, `IKCONFIG_PROC` jeweils `y` | **PASS** |

Die Kconfig-Werte wurden mit **echtem** `make olddefconfig` aufgelöst
und anschließend gegen die erwarteten Werte geprüft. Das LSM-Experiment
belegt keine Android-kompatible SELinux-Policy; SMACK und SELinux werden
auch nicht automatisch gleichzeitig als aktive Haupt-LSMs verwendet.

### Erfolgreiche Compilerläufe

| Host-Test | Größe `zImage` | SHA-256 | Resultat |
| --- | ---: | --- | --- |
| SELinux-Lab | 3.685.024 Bytes | `f401aa6158dd60c5804dfd619c03244dbb3ab1a44d15f6a2ce555fa2c4506eb7` | `HOST_KERNEL_COMPILED_NOT_BOOTABLE_VALIDATED` |
| Android-Bootlab | 3.720.480 Bytes | `b12d4d4edb9aa42b956b8612cfa9578b6fcdc364ea175e3542b7e09718edd540` | `HOST_KERNEL_COMPILED_NOT_BOOTABLE_VALIDATED` |

Beide Tests meldeten Exitcode **0**, keine im Buildprotokoll erfassten
Compilerfehler und eine verifizierte experimentelle `.config`.
Die Binärdateien, vollständigen Buildprotokolle, Samsungquellen und
Toolchain werden **nicht** in dieses GitHub-Repository aufgenommen.

### Reproduktion – ausschließlich auf einem Entwicklungsrechner

```bash
python3 q60t_compile_probe.py \
  --source /pfad/zu/entpacktem/linux-4.1.10 \
  --workspace /pfad/zu/NEUEM-build015-selinux \
  --cross-prefix /pfad/zu/linaro/bin/arm-linux-gnueabi- \
  --profile selinux-lab --jobs 4 --timeout 1800

python3 q60t_compile_probe.py \
  --source /pfad/zu/entpacktem/linux-4.1.10 \
  --workspace /pfad/zu/NEUEM-build015-bootlab \
  --cross-prefix /pfad/zu/linaro/bin/arm-linux-gnueabi- \
  --profile android-bootlab --jobs 4 --timeout 1800
```

Erforderlich sind neben dem Samsung-Quellpaket `make`, `patch`, `bc`,
eine Host-C-Toolchain und eine passende ARM32-Cross-Toolchain.
Die Verzeichnisse unter `--workspace` dürfen **noch nicht existieren**.

## Android-Kompatibilität: 12 Prüfmerkmale sind nicht 12 bestandene Boottests

Neu: `q60t_kernel_readiness.py` untersucht nur **ausgewählte** Merkmale
des aufgelösten Kernelprofils und die Quelltext-Indizien für Binder.
Es nimmt dazu eine **historische** offizielle Android-4.4-Konfiguration
als Vergleich, **nicht** eine vollständige Android-14-Konformitätsliste.

| Profil | Aktivierte Teilmenge (12 Checks) | Ergebnis |
| --- | ---: | --- |
| Tizen-Basis | 7/12 | **Nicht Android-bereit** |
| SELinux-Lab | 9/12 | **Nicht Android-bereit** |
| Android-Bootlab | 12/12 | **Nicht Android-bereit** |

Maschinenlesbare Ergebnisse:

- `reports/kernel_gap_build015_tizen.json`
- `reports/kernel_gap_build015_selinux.json`
- `reports/kernel_gap_build015_bootlab.json`

Selbst im letzten Test bestehen wesentliche Blocker:

1. **Binder-Kontexte:** Der alte Treiber registriert nur eine
   `/dev/binder`-Miscdevice und verwendet einen globalen
   `binder_context_mgr_node`; `/dev/hwbinder` und `/dev/vndbinder`
   sind mit voneinander getrennten Kontexten nicht implementiert.
2. **Android 14:** Linux 4.1.10 liegt außerhalb Googles dokumentierter
   Kernel-Unterstützungsmatrix für Android 14.
3. **Samsung-spezifische HALs:** Mali-/DRM-/MFC-Treiber sind kein
   nachgewiesener Android-Grafik-/Medienstapel. Legacy ION ersetzt
   nicht die spätere DMA-BUF-Heaps-Integration.
4. **Sicherer Geräteboot:** Die passende Nike-L-Defconfig, reales
   DT-/RAM-Profil, Bootloadersignatur, Recovery und Rollback sind offen.

Alle Reports melden bewusst `GAPS_FOUND_NOT_ANDROID_READY` und
`flash_authorized=false`.

## Technische Referenzen (Primärquellen)

- [Google: Android Common Kernels und Supportmatrix](https://source.android.com/docs/core/architecture/kernel/android-common)
- [Google: Binder-/HWBinder-/VndBinder-Domänen](https://source.android.com/docs/core/architecture/hidl/binder-ipc)
- [Google: Android SELinux](https://source.android.com/docs/security/features/selinux)
- [AOSP: historische Android-4.4-Basiskonfiguration](https://android.googlesource.com/kernel/common/+/refs/tags/ASB-2020-04-05_4.4-o/android/configs/android-base.cfg)
- [Google: DMA-BUF-Heaps und ION-Migration](https://source.android.com/docs/core/architecture/kernel/dma-buf-heaps)

Weitere Details in [`porting/ANDROID_COMPATIBILITY.md`](porting/ANDROID_COMPATIBILITY.md).

## Tests / Sicherheit

- **96 synthetische Python-Tests bestanden** (inklusive acht neuer
  Tests für optionale Compilerprofile und den Readiness-Audit).
- Neues Opt-in-Profil ist nicht das Standardprofil; fehlende und
  unerwartete Konfigurationswerte führen zum Abbruch vor dem Compilerlauf.
- Original-Quellarchiv und TV nicht verändert; keine Flash- oder
  Update-Funktion im Code.

**Nächster kritischer Schritt:** Binder mit sauber getrennten Kontexten
portieren oder eine unterstützte neuere Kernelbasis für das Samsung-SoC
finden und Hardwareabhängigkeiten neu aufbauen. Ohne gesicherten Boot-
und Wiederherstellungspfad bleibt ein Test auf dem Fernseher tabu.
