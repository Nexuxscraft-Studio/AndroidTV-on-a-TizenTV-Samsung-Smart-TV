# Q60T-Kernel: Android-Kompatibilität und realistische Portierungsstufen

Stand: 09.11.2026 · Build 017 · **kein TV-Zugriff, keine Flashfreigabe**

## Ausgangslage: Was unser erfolgreicher Host-Build beweist

Das Originalarchiv `20_DTV_NikeL.zip` enthält Samsung-Linux-4.1.10-Quellen,
jedoch unter den auffindbaren Profilen nur `Nike.M-..._defconfig`.
Unsere `Nike.M-Tizen_release_defconfig` ist deshalb lediglich ein
**Compiler-/Hardwarekandidat**, keine verifizierte Konfiguration für den
`GQ50Q60TGUXZG` mit `T-NKLDEUC-2743.0`.

Der Quelltext `arch/arm/mach-sdp/board-nike-dt.c` akzeptiert zwar
ausdrücklich **beide** Kennungen `samsung,sdp-nikem` und
`samsung,sdp-nikel`. Daraus folgt **nicht**, dass das mitgelieferte
`Nike.M`-Profil, die Device-Tree-Daten oder die Bootparameter mit dem
50-Zoll-Nike-L-Gerät übereinstimmen. Ein zur Firmware gehörender
Nike-L-DTS-Buildpfad ist noch nicht nachgewiesen.

Build 013 erzeugte mit einer nicht herstelleridentischen GCC-6.2.1-Toolchain
einen ARM32-`zImage` in einem Schattenquellbaum. Ein Host-Compile belegt weder
Android-Laufzeitfähigkeit noch Bootloader-/DTB-/HAL-Kompatibilität.

## Offizielle Android-Anforderungen und Unterschiede

Google dokumentiert für Android 14 als offiziell unterstützte gemeinsame
Kernel die Familien 5.10, 5.15 und 6.1. **Linux 4.1.10 steht nicht in
dieser Matrix**. Eine eigene Portierung auf 4.1.10 wäre deshalb ein
umfangreicher, nicht unterstützter Sonderweg, nicht ein einfacher
Konfigurationswechsel.

- Android-Kernelmatrix:
  <https://source.android.com/docs/core/architecture/kernel/android-common>
- AOSP-Kernelkonfigurationen:
  <https://android.googlesource.com/kernel/configs/+/refs/heads/main/README.md>
- Konkreter älterer AOSP-4.4-Konfigurationsvergleich (kein Android-14-Nachweis):
  <https://android.googlesource.com/kernel/common/+/refs/tags/ASB-2020-04-05_4.4-o/android/configs/android-base.cfg>
- Android-Binder-HAL-/IPC-Domänen:
  <https://source.android.com/docs/core/architecture/hidl/binder-ipc>
- SELinux-Anforderung:
  <https://source.android.com/docs/security/features/selinux>

### Binder ist mehr als `CONFIG_ANDROID_BINDER_IPC=y`

Der Samsung-Quellcode enthält in `drivers/android/binder.c` ein einzelnes
`struct miscdevice` mit dem Namen `binder`. Die dazugehörige Kconfig-Datei
kennt **keine** `CONFIG_ANDROID_BINDER_DEVICES`. Der UAPI-Header definiert
Protokollversion **7** für das alte 32-Bit-Binder-Format und **8** für das
neuere Format. Seit Build 013 ist der veraltete Binder-32-Bit-Modus im
Testprofil deaktiviert.

Für Android 8 und neuer dokumentiert Google getrennte Binder-Kontexte
(`/dev/binder`, `/dev/hwbinder`, gegebenenfalls `/dev/vndbinder`).
**Nur zusätzliche Gerätedateien anzulegen genügt nicht**: Der alte Treiber
besitzt noch keinen nachgewiesenen, voneinander isolierten Kontext pro
Gerät. Entweder ist ein überprüfter Binder-Backport oder eine wesentlich
neuere Kernelbasis erforderlich; reine Symbolprüfung bestätigt keine ABI.

Build 016 enthält jetzt einen **separaten, nicht produktionsreifen**
Binder-Dreifachkontext-Prototyp als Opt-in-Hostprofil. Dessen ARM32-
Kompilierung war erfolgreich, aber weder Kontextisolation zur Laufzeit
noch die Android-Binder-ABI sind nachgewiesen. Das ist ausdrücklich
**noch kein** vollständiger Binder-Backport. Siehe
[`porting/BINDER_MULTICONTEXT_LAB.md`](BINDER_MULTICONTEXT_LAB.md).

Build 017 zeigt darüber hinaus die **eigentliche ABI-Lücke**: Der Samsung-
Header beschreibt längst nicht alle modernen Binder-Objekte und IOCTLs,
und die beiden alten `BINDER_SET_IDLE_*`-IOCTLs sind zwar deklariert,
aber nicht als `case`-Handler implementiert. 16 neuere untersuchte
AOSP-Merkmale fehlen. Unsere ARM32-Strukturgrößenprobe wurde
erfolgreich kompiliert; das ersetzt keine ABI-Laufzeitprüfung. Details:
[`porting/BINDER_UAPI.md`](BINDER_UAPI.md).

### SELinux und Samsungs Sicherheitsmodell

Im stocknahen Forschungsprofil ist `CONFIG_SECURITY_SMACK=y`,
`CONFIG_SECURITY_SFD=y` und `CONFIG_SECURITY_SELINUX=n`; das Standard-LSM
ist `smack`. Androids Sicherheitsarchitektur verwendet dagegen SELinux.
Der vorliegende Linux-4.1.10-Framework-Code unter `security/security.c`
verwaltet einen primären LSM-Hook-Satz. **Beide LSMs einkompilieren**
bedeutet daher nicht, dass SMACK und SELinux gleichzeitig ihre Richtlinien
anwenden. Samsungs SFD-/UEP-Hooks wurden nicht für Android validiert.

Build 015 ergänzt dafür einen **freiwilligen, host-only** Testmodus:

```bash
python3 q60t_compile_probe.py \
  --source /pfad/zu/entpacktem/linux-4.1.10 \
  --workspace /pfad/zu/NEUEM-selinux-testordner \
  --cross-prefix /pfad/zu/linaro/bin/arm-linux-gnueabi- \
  --profile selinux-lab --jobs 4 --timeout 1800
```

Die ursprünglichen Samsungquellen und die Standard-Build-013-Konfiguration
bleiben unberührt. Nur in der **Schattenkonfiguration** wird SELinux
ausgewählt und als Standard-LSM gesetzt. `SMACK` und `SFD` bleiben für
eine erste Compilerprobe einkompiliert. Es fehlt weiterhin eine passende
Android-SELinux-Policy; dieser Test ist **kein Boot- oder Freigabenachweis**.

**Beide Host-Compilerproben waren erfolgreich:** Das SELinux-Testprofil
hat ein `zImage` mit 3.685.024 Bytes erzeugt; das weitergehende Profil
`android-bootlab` mit SELinux, `BLK_DEV_INITRD=y`, `IKCONFIG=y` und
`IKCONFIG_PROC=y` ebenfalls (3.720.480 Bytes). Das zweite Profil wird mit
`--profile android-bootlab` ausgewählt. Beide sind ausdrücklich nicht zum
Booten oder Flashen freigegeben; geprüfte Hashes stehen in
[`BUILD015_REPORT.md`](../BUILD015_REPORT.md).

### Weitere im Testprofil beobachtete Lücken

- `CONFIG_BLK_DEV_INITRD=n`: Kein aktivierter Standard-Initramfs-Weg.
- `CONFIG_IKCONFIG=n` und dadurch `CONFIG_IKCONFIG_PROC=n`: Die für
  Android-Kernel-Diagnostik nützliche Konfiguration ist nicht eingebettet.

Im neuen **Bootlab-Profil** wurden die beiden oben genannten Lücken
experimentell geschlossen und der Hostkernel erneut kompiliert.
Das ist keine Aussage über eine passende Android-Initramfs oder Bootkette.
- `CONFIG_BPF_SYSCALL=n`: Ein Zeichen der älteren Kernelbasis; daraus
  folgt noch keine vollständige Bewertung der heutigen Android-eBPF-APIs.
- `CONFIG_ION=y` ist im Forschungsprofil vorhanden. Android 12 mit
  GKI 2.0 hat den ION-Pfad durch DMA-BUF-Heaps abgelöst; die alte
  Speicherallokation reicht für eine neue Android-Grafik-HAL nicht als
  Kompatibilitätsnachweis. Offizielle Migrationsbeschreibung:
  <https://source.android.com/docs/core/architecture/kernel/dma-buf-heaps>
- GPU- und Videotreiber aus dem Tizen-Quellbaum sind keine fertige
  Android-Grafik-/Media-HAL.

Maschinenlesbarer Vergleich aus einem vollständig aufgelösten `.config`:

```bash
python3 q60t_kernel_readiness.py \
  --source /pfad/zu/entpacktem/linux-4.1.10 \
  --config /pfad/zu/getrenntem-output/.config \
  --output /pfad/zu/NEUEM-report.json
```

Der Vergleich ist nur ein **ausgewählter Konfigurations- und Binder-Survey**,
keine vollständige CDD-Prüfung. Der erzeugte JSON-Bericht verweigert
die Schlussfolgerungen „Android bereit“ und „Flash freigegeben“ ausdrücklich.

## Nächste technische Meilensteine

1. **SELinux-Kconfig und ARM32-Host-Compile** prüfen; etwaige konkrete
   Compilerprobleme reproduzierbar beheben, ohne Originaldateien zu ändern.
2. **Binder-Kontextfähigkeit** untersuchen und gegen einen historischen
   offiziellen Android-Common-Kernel-Stand diffen; mindestens drei
   voneinander getrennte Binder-Kontexte sicherstellen.
3. **Initramfs und Kernelkonfiguration** in separatem Laborprofil testen;
   dazu später eine minimale Android-Userspace-Umgebung zum ABI-Test,
   zunächst unter Emulation, nicht auf dem Samsung-TV.
4. **DTB-/Boardprofil** des exakten 50-Zoll-Geräts bestätigen, danach
   Clock-/Power-/Display-/Mali-/MFC-Abhängigkeiten portieren.
5. **Sicherer alternativer Boot und Wiederherstellung** müssen unabhängig
   nachgewiesen sein, ehe irgendein eigener Kernel auf echter Hardware
   getestet wird. Auch Root-Recherchen anderer Samsung-Modelle ersetzen
   diesen Q60T-spezifischen Beleg nicht.

## Klare Grenze

Die Quellen bleiben Forschungs- und Buildmaterial. Weder ein erfolgreicher
`zImage`-Build noch ein aktiviertes SELinux ersetzt einen verifizierten
Android-Userspace, Hardware-HALs, einen signaturkompatiblen Bootweg und
einen Rollbackplan. **Nichts auf den Fernseher flashen.**
