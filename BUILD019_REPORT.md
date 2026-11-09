# Build 019 – Android-Userspace-Vorprüfung und Hardware-Gates

**Status:** Host-Code implementiert und synthetisch getestet; **ein echter
Build-019-Gastlauf wurde noch nicht ausgeführt**. Kein Android-ROM, kein
Firmwareimage und keine Schreiboperation auf dem Samsung-Fernseher.

Zielgerät: **Samsung GQ50Q60TGUXZG**, Firmwarefamilie `T-NKLDEUC`, auf dem TV
gemeldete Version `2743.0`. Forschungsquelle: `20_DTV_NikeL.zip` mit Samsung
Linux 4.1.10. Das QEMU-Profil verwendet bewusst ARM32 `virt`, nicht die
Samsung-SoC-Hardware oder die originale Bootkette.

## Übernahme von Build 018

In der separaten Debian-/Proxmox-Test-VM wurde das Samsung-4.1.10-Testprofil
zuletzt erfolgreich als `zImage` kompiliert und in QEMU gestartet. Ein
statischer ARM32-Gast-`/init` meldete `BINDER_VERSION=8` auf allen drei
Geräten `/dev/binder`, `/dev/hwbinder` und `/dev/vndbinder`. Das anschließende
Experiment zeigte einen erfolgreichen **Binder-Ping/Pong zwischen zwei
Gastprozessen** (`Q60T_BINDER_TRANSACTION_PASS protocol=8 request=PING
reply=PONG`). Dies ist **kein** Android-Userspace-Boot und noch kein Nachweis
einer vollständigen Android-Binder-ABI.

## Was Build 019 neu prüft

`q60t_android_probe_init.c` ist ein eigenständiges statisches ARM32-Programm
für **das bestehende QEMU-Initramfs-Labor**. Es beobachtet ausschließlich
Laufzeitfunktionen des Linux-Gasts:

| Bereich | Beobachtung | Grenze |
| --- | --- | --- |
| Init-Unterbau | `devtmpfs`, `/proc`, `/sys` | Kein AOSP `init` und kein Property-Service |
| Prozesse | `fork`/`waitpid`, Futex | Kein Zygote/ART |
| IPC-/Events | `epoll`, `eventfd`, `inotify` | Keine Android-Service-Registrierung |
| Binder | `BINDER_VERSION=8` auf drei Geräten | Kein neuer vollständiger AOSP-ABI-Test |
| Speichergeräte | Öffnen von `/dev/ashmem` und `/dev/ion` | Keine echte Allocation/Gralloc-HAL-Prüfung |
| Container | Registrierte cgroup-Dateisysteme | Keine Android-controller- oder Task-Profilprüfung |
| Sicherheit | Lesbarer SELinux-Enforcing-Status | Keine Android-Policy oder CTS-Konformität |

Die Auswertung in `q60t_android_userspace.py` verlangt für einen eng
begrenzten **Linux-ABI-Smoke-Test** genau einen Start- und Endmarker, alle
erwarteten Featurezeilen, einen echten 4.1.10-Kernelbanner und kein Panic.
Duplikate, unbekannte/fehlerhafte Werte, unvollständige Logs und fehlende
Pflichtfunktionen werden konservativ abgelehnt. Sie setzt **immer**
`android_boot_ready=false`, `flash_authorized=false` und alle realen
Samsung-Hardware-Gates auf `unverified`.

## Auf dem bestehenden Proxmox-Debian-Labor ausprobieren

Im bereits vorhandenen Repository **auf der Debian-VM** (mit dem bisher
erfolgreichen Linaro-ARM32-Cross-Compiler) arbeiten. Die GitHub-Änderungen
liegen zunächst auf einem separaten Build-019-Branch und benötigen keinen
neuen Kernelbuild:

```bash
# Im Repository: aktuellen Build-019-Branch auschecken, ohne lokale Arbeit zu löschen.
# Vor dem Wechsel git status prüfen und vorhandene Änderungen sichern.

# Die Pfade orientieren sich an unserem erfolgreichen Build-018-Gastlauf.
python3 q60t_initramfs_lab.py \
  --cross-prefix /pfad/zur/linaro/bin/arm-linux-gnueabi- \
  --source q60t_android_probe_init.c \
  --output /opt/samsung-atv-lab/samsung/build018-qemu-007/android019-initramfs.cpio.gz

python3 q60t_qemu_runtime.py \
  --workspace /opt/samsung-atv-lab/samsung/build018-qemu-007 \
  --initrd /opt/samsung-atv-lab/samsung/build018-qemu-007/android019-initramfs.cpio.gz \
  --run-id android019 --timeout 30

python3 q60t_android_userspace.py \
  --log /opt/samsung-atv-lab/samsung/build018-qemu-007/qemu-serial-android019.log \
  --output /opt/samsung-atv-lab/samsung/build018-qemu-007/android019-readiness.json
```

**Wichtig:** `q60t_qemu_runtime.py` kann bei einem 30-Sekunden-Timeout den
Exitcode 124 melden, weil unser Gast-`/init` nach Ausgabe seiner Marker
absichtlich wartet. Der aussagekräftige Status kommt aus dem Build-019-
Auswertebericht. Die Dateien werden ausschließlich neu angelegt und nicht
überschrieben. Vor einem erneuten Test bitte eine neue Run-ID und neue
Ausgabedateinamen wählen, nicht die alten Ergebnisse löschen.

Der Runner verwendet keine QEMU-Netzwerkgeräte, Hostfestplatten oder
Passthrough-Hardware. Es wird nichts auf den TV kopiert oder geflasht.

## Noch offene Android-Userspace-Gates

1. **AOSP/Bionic statt Test-`/init`:** dynamischer ARM32-Linker, Android
   `init`, Property-Service, `servicemanager`, `hwservicemanager`.
2. **Sicherheit:** geladene, durchgesetzte SELinux-Policy mit passenden
   Prozessdomänen; eine gesetzte Kconfig-Option genügt nicht.
3. **Android-Framework:** Zygote/ART, SurfaceFlinger, VINTF und zugehörige
   Framework-/Vendor-Manifeste.
4. **Kernelgeneration:** Linux 4.1.10 ist keine Android-14-GKI-/ACK-Basis.
   Ein neuer Android-Userspace kann deshalb nicht allein über Binder
   kompatibel werden.

## Reale Samsung-Hardwarekompatibilität bleibt getrennt

QEMU emuliert **nicht** das Nike-L-SoC des Q60T. Deshalb bleiben das echte
RAM-/DTB-Profil, der reversible Boot-/Recovery-Pfad, Mali/EGL/Gralloc/HWC,
Audio, Samsung-MFC-Video, IR/CEC und Streaming-DRM unabhängig von diesem
Labor unbestätigt. Ausgangsmatrix: [`porting/HAL_MATRIX.md`](porting/HAL_MATRIX.md).

**Priorität für Build 020:** Erst ein minimaler echter ARM32-Bionic-/AOSP-
Userspace-Dienst in QEMU mit dokumentierter dynamischer Linker-/SELinux-
Fehlerkette, dann schrittweise HAL-Schnittstellen. Nicht auf dem TV starten,
solange eine reversible Bootkette nicht nachgewiesen wurde.

## Quellen

- [AOSP Binder-IPC-Domänen](https://source.android.com/docs/core/architecture/hidl/binder-ipc)
- [AOSP SELinux-Implementierung](https://source.android.com/docs/security/features/selinux/implement)
- [AOSP VINTF-Manifest](https://source.android.com/docs/core/architecture/vintf)
- [Android Common Kernels](https://source.android.com/docs/core/architecture/kernel/android-common)
