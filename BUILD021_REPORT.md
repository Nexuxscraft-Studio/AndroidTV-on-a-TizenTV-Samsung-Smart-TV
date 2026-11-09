# Build 021 – Erster dynamisch gelinkter ARM32-Bionic-Prozess unter QEMU

**Status:** Build-021-Hostcode entwickelt und synthetisch getestet.
**Noch offen:** Beschaffung/Extraktion echter Android-Systembibliotheken auf
dem Proxmox-Buildhost, Initramfs-Erstellung mit echten ARM32-Binärdateien und
die erste reale Gast-Ausführung. Kein Erfolg wird ohne QEMU-Log behauptet.

## Vorbedingungen und unveränderte Baselines

- Der Build-020-QEMU-ION-Test wurde laut Proxmox-Testlabor erfolgreich
  durchgeführt: `/dev/ion`, 4 KiB Allokation und Freigabe.
- Das mit Android-NDK r30 kompilierte Programm
  `/opt/samsung-atv-lab/samsung/build020-qemu-ion-001/q60t_bionic_hello.arm32`
  ist bereits als ELF32 ARM / ET_DYN geprüft: Interpreter
  `/system/bin/linker`, `DT_NEEDED` `libdl.so` und `libc.so`.
- QEMU verwendet weiter den **bereits vorhandenen** Build-020-Kernel im
  Workspace `build020-qemu-ion-001`; kein weiterer Kernel-Build erforderlich.
- Originalkernel, Build-018/019 und Build 020 bleiben unangetastet.
- **Keine** TV-Zugriffe, kein Flash, keine Emulator-Netzwerkverbindung.

## 1. Echte ARM32-Bionic-Laufzeit von Google beziehen

Verwendet wird die offizielle Android-SDK-Systemimage-Paketkennung:

`system-images;android-24;default;armeabi-v7a`

Warum **API 24 / Android 7.0**? Das bereits vorhandene Bionic-Testprogramm
wurde mit `armv7a-linux-androideabi24-clang` gebaut; diese Version ist ein
bewusst konservativer erster Userspace-Versuch für den alten Linux-4.1.10-Kernel.
**Das ist kein Ziel für die finale Android-TV-Version.**

1. Falls nötig, die offiziellen [Android SDK Command-line Tools](https://developer.android.com/tools/sdkmanager)
   installieren. Bereits vorhandene Tools wiederverwenden.
2. Das folgende Paket mit dem **offiziellen SDK-Manager** suchen/installieren:

```bash
# SDK_ROOT und SDKMANAGER an die vorhandene Installation anpassen.
SDK_ROOT=/opt/samsung-atv-lab/toolchains/android-sdk
SDKMANAGER="$SDK_ROOT/cmdline-tools/latest/bin/sdkmanager"

"$SDKMANAGER" --sdk_root="$SDK_ROOT" --list \
  | grep 'system-images;android-24;default;armeabi-v7a'

# Nur ausführen, wenn die offizielle Paketkennung verfügbar ist.
"$SDKMANAGER" --sdk_root="$SDK_ROOT" --install \
  'system-images;android-24;default;armeabi-v7a'
```

Die SDK-Lizenzen werden **nicht automatisch** angenommen. Ein fehlendes
`default/armeabi-v7a`-Paket wird nicht durch Google-APIs-/Play-Store-Images,
NDK-Linkstubs oder zufällige Webseiten-Binärdateien ersetzt.

## 2. Linker, libc, libdl aus system.img extrahieren und prüfen

```bash
# Auf Debian/Proxmox-Gast (nur wenn noch nicht vorhanden):
sudo apt-get install e2fsprogs android-sdk-libsparse-utils

python3 q60t_aosp_runtime.py \
  --sdk-image-dir "$SDK_ROOT/system-images/android-24/default/armeabi-v7a" \
  --output /opt/samsung-atv-lab/samsung/build021-aosp-runtime
```

Der Offline-Extractor nutzt bei sparse Images `simg2img` und anschließend
das lesende Werkzeug `debugfs`. Es wird **nichts gemountet** und keine
Samsung-Partition verändert. Exportierte Dateien bleiben außerhalb GitHub:

- `system/bin/linker`
- `system/lib/libc.so`
- `system/lib/libdl.so`
- `system/lib/libm.so` (vorsorglich für Bionic-Abhängigkeiten)
- `runtime-manifest.json` mit SDK-Paketrevision, Image-SHA256, SHA256 jeder
  extrahierten Datei und ELF-/DT_NEEDED-Prüfergebnissen.

Der Validator verlangt ARM32-Little-Endian-ELF, dynamische Bibliotheken,
auflösbare Laufzeit-Abhängigkeiten und die passende SDK-Revision/API 24.
**Die tatsächliche Ausführbarkeit** sowie Symbole/Runtime-Verhalten
bleiben bis zum QEMU-Test unbewiesen. Die Software verifiziert die Signatur
des offiziellen SDK-Managers nicht selbst, sondern dokumentiert die lokale
Paketprovenienz und prüft anschließend alle Staging-Hashes.

## 3. Eigenes ARM32-Initramfs mit dynamischem Android-Prozess

`q60t_bionic_init.c` wird mit dem bestehenden Linaro/GNU-ARM32-Compiler
**statisch** zu `/init` gebaut. Der Launcher startet im Gast das
**dynamische** Programm `/system/bin/q60t_bionic_hello`, wartet auf dessen
Exit-Status und gibt eine eigene Ergebniszeile aus.

```bash
# Das bereits als ELF32/ARM/Bionic geprüfte Build-020-Binary wiederverwenden.
python3 q60t_bionic_initramfs.py \
  --runtime-root /opt/samsung-atv-lab/samsung/build021-aosp-runtime \
  --program /opt/samsung-atv-lab/samsung/build020-qemu-ion-001/q60t_bionic_hello.arm32 \
  --cross-prefix arm-linux-gnueabi- \
  --output /opt/samsung-atv-lab/samsung/build021-bionic-initrd.cpio.gz
```

Wenn der ARM32-GCC nicht über `PATH` verfügbar ist, bei `--cross-prefix`
den tatsächlichen Linaro-Binärpfad bis `arm-linux-gnueabi-` einsetzen.

Der Packer validiert **vorab** das Programminterpreterfeld
`/system/bin/linker`, die `DT_NEEDED`-Einträge, die Hashes aller Bibliotheken
und die Herkunft des SDK-Staging-Manifests. Das Ausgabeziel muss neu sein;
vorhandene Initramfs-Dateien werden niemals überschrieben.

## 4. QEMU mit dem erfolgreichen Build-020-Kernel ausführen

```bash
python3 q60t_qemu_runtime.py \
  --workspace /opt/samsung-atv-lab/samsung/build020-qemu-ion-001 \
  --initrd /opt/samsung-atv-lab/samsung/build021-bionic-initrd.cpio.gz \
  --timeout 120 --run-id bionic021-001

python3 q60t_bionic_guest_result.py \
  --log /opt/samsung-atv-lab/samsung/build020-qemu-ion-001/qemu-serial-bionic021-001.log
```

**Erwartete serielle QEMU-Marker:**

```text
Linux version 4.1.10 ...
Q60T_GUEST_INIT_STARTED host_only=1 no_flash=1
Q60T_BIONIC_EXEC_BEGIN version=021
Q60T_BIONIC_HELLO version=020 host_only=1
Q60T_BIONIC_EXEC_RESULT status=pass exit=0
```

Ein Erfolg ist **nur** `BIONIC_CHILD_EXIT_ZERO_GUEST_REPORTED`, wenn
Kernelbanner, vollständige Gastmarker in Reihenfolge und Exitcode 0
auftauchen, ohne Kernel-Panic oder `execve`-Fehler. Nur das dynamisch
gelinkte Bionic-Programm druckt die `Q60T_BIONIC_HELLO`-Zeile.

Der bestehende `q60t_qemu_runtime.py`-Report nennt dabei weiterhin
`build: "020"`, weil er das **Kernelprofil** beschreibt. Der separate
`q60t_bionic_guest_result.py` bewertet den **Build-021-Userspace**.

## 5. Grenzen und nächste Gates

- Android-`init`, Property Service, Binder-Servicemanager, Zygote, ART,
  SurfaceFlinger, HALs und Mali-GPU sind dadurch **noch nicht gestartet**.
- Die Android-SELinux-Policy ist weiterhin **nicht geladen/verifiziert**;
  der QEMU-Gast war im letzten Test permissive.
- Eine erfolgreiche QEMU-Bionic-Ausführung ist **kein** sicheres
  Boot-/Flash-Verfahren auf einem echten Q60T.
- Erst wenn das volle Gastprotokoll vorliegt, können wir Build 022 für
  weitergehende Android-Init- und Property-Service-Tests planen.

## Host-Selbsttests

```bash
python3 -m unittest discover -s tests -q
cc -std=gnu11 -Wall -Wextra -Werror -fsyntax-only q60t_bionic_init.c
```

GitHub-CI führt **ausschließlich synthetische** Tests und Source-Audit
aus. Echte SDK-Systembibliotheken, `system.img`, `*.arm32`-Programme und
generierte Initramfs-Dateien werden **nicht** in GitHub eingecheckt.

## Primärquellen

- [Android SDK `sdkmanager` und Paket-Installation](https://developer.android.com/tools/sdkmanager)
- [Android Emulator System-Images und Dateien](https://developer.android.com/studio/run/emulator-commandline)
- [AOSP Bionic Quellcode, libc/libdl und dynamischer Linker](https://android.googlesource.com/platform/bionic/)
- [AOSP Linker-Kompatibilitätsregeln](https://android.googlesource.com/platform/bionic/+/HEAD/android-changes-for-ndk-developers.md)

**Gesamtstatus vor Proxmox-Test:**
`BUILD021_HOST_IMPLEMENTED_BIONIC_GUEST_EXECUTION_NOT_YET_VERIFIED`.
