# Build 020 – ION unter QEMU, SELinux-Policy-Gates und ARM32-Bionic-Vorbereitung

**Stand:** Implementierung auf separatem Host-Only-Branch. Synthetische
Prüfungen laufen. **Ein echter Build-020-Kernel-Build und QEMU-Gastlauf
werden nicht als erfolgreich behauptet**, solange die Samsung-Quelldateien
und der vorhandene Proxmox-Buildhost nicht zur Ausführung vorliegen.

## Grenzen und unveränderliche Baselines

- Samsung-Originalkernel: **unverändert**; Build-020-Profil bearbeitet nur
  `linux-4.1.10-shadow` und eine neue `.config` im neuen Workspace.
- Build-018-QEMU-Profil `qemu-binder-lab`: **unverändert**; alle neuen
  `ION_DUMMY=y`-Änderungen gelten nur für `qemu-ion-lab`.
- Build-019-Probe: bleibt als `q60t_android_probe_init.c` unverändert;
  Build 020 hat eigene Datei `q60t_ion_probe_init.c`.
- Kein Zugriff auf den Samsung-Fernseher, keine Firmware, kein Flashen.

## 1. QEMU-ION-Dummy: isoliertes Kernelprofil

`q60t_compile_probe.py --profile qemu-ion-lab` übernimmt die bekannten
QEMU-virt-/Binder-Einstellungen und ergänzt **nur in diesem Profil**:

```text
CONFIG_ION=y
CONFIG_ION_DUMMY=y
```

Vor dem Compile wird der **konkrete** Samsung-Linux-4.1.10-Quellstand geprüft:

- `drivers/staging/android/ion/Kconfig` muss `ION_DUMMY` anbieten.
- Der Dummy-Treiber muss vorhanden und im Makefile verdrahtet sein.
- Der tatsächliche ION-UAPI-Header muss die Legacy-Handle-IOCTLs mit
  `len`, `align`, `heap_id_mask`, `handle`, `ION_IOC_ALLOC` und
  `ION_IOC_FREE` enthalten.

Fehlt eines davon, wird die Vorbereitung **abgebrochen**. Es wird keine
ungeprüfte AOSP-Treiberdatei in Samsungs Kernel kopiert. Der Ausgang ist
noch offen, bis die Quellbaumprüfung auf dem Proxmox-Buildhost erfolgt.

Beispiel für einen **neuen, noch nicht existierenden** Workspace (Pfade der
eigenen Umgebung anpassen):

```bash
python3 q60t_compile_probe.py \
  --source /opt/samsung-atv-lab/samsung/build018-original/linux-4.1.10 \
  --workspace /opt/samsung-atv-lab/samsung/build020-qemu-ion-001 \
  --cross-prefix arm-linux-gnueabi- \
  --profile qemu-ion-lab --jobs 2 --timeout 3600
```

Eine bereits existierende Workspace-Ausgabe wird aus Sicherheitsgründen
nicht überschrieben.

## 2. 4-KiB-ION-Allokation im Gast

`q60t_ion_probe_init.c` nutzt die **Legacy**-ION-Schnittstelle:

1. `/dev/ion` öffnen;
2. `ION_IOC_ALLOC` mit `len=4096`, `align=4096`, System-Heap-ID 0;
3. erhaltenen ION-Handle über `ION_IOC_FREE` freigeben;
4. alle drei Schritte separat in der seriellen QEMU-Konsole protokollieren.

```bash
python3 q60t_initramfs_lab.py \
  --cross-prefix arm-linux-gnueabi- \
  --source q60t_ion_probe_init.c \
  --output /opt/samsung-atv-lab/samsung/build020-ion-initrd.cpio.gz

python3 q60t_qemu_runtime.py \
  --workspace /opt/samsung-atv-lab/samsung/build020-qemu-ion-001 \
  --initrd /opt/samsung-atv-lab/samsung/build020-ion-initrd.cpio.gz \
  --timeout 120 --run-id ion020-001

python3 q60t_ion_result.py \
  --log /opt/samsung-atv-lab/samsung/build020-qemu-ion-001/qemu-serial-ion020-001.log
```

Erwartetes Ergebnis (erst nach realem Gasttest belegbar):

```text
Q60T_ION_TEST stage=open result=pass
Q60T_ION_TEST stage=alloc result=pass bytes=4096
Q60T_ION_TEST stage=free result=pass
Q60T_ANDROID_PROBE_FEATURE name=ion result=pass
```

Nur dieses vollständige Protokoll gilt als
`ION_OPEN_ALLOC_FREE_GUEST_PASS_REPORTED`. Ein vorhandenes Device alleine
ist **kein** erfolgreicher Allokationstest.

## 3. SELinux-Voraussetzungen, keine vorgetäuschte Policy

`q60t_selinux_preflight.py` prüft die Kernelkonfiguration, optional die
QEMU-Gastkonsole und optional bereitgestellte Android-Policy-Dateien.
Selinux-LSM `=y` und `DEFAULT_SECURITY_SELINUX=y` bedeuten lediglich
Kernel-Unterstützung. Build 019 meldete im Gast noch **permissive**.

Für ein echtes Android-System muss später eine zur AOSP-Version und den
Vendor-HALs passende Policy aufgebaut und geladen werden. Mindestens zu
klären sind `plat_sepolicy.cil`, `vendor_sepolicy.cil`,
`plat_file_contexts`, `vendor_file_contexts`, `service_contexts`,
`property_contexts`, `seapp_contexts`, Policy-/Kernel-Version und
Binder-/ION-Gerätekontexte. Der Kernel darf **nicht** durch einen erzwungenen
Enforcing-Schalter als Android-kompatibel ausgegeben werden.

```bash
python3 q60t_selinux_preflight.py \
  --workspace /opt/samsung-atv-lab/samsung/build020-qemu-ion-001 \
  --guest-log /opt/samsung-atv-lab/samsung/build020-qemu-ion-001/qemu-serial-ion020-001.log
```

**Gate bleibt rot:** `policy_loaded_into_guest_verified=false`,
`android_selinux_enforcement_ready=false`, bis wir eine echte kompatible
Policy und den Ladevorgang im Gast belegt haben. SELinux wird nicht auf
dem Samsung-TV geändert.

## 4. Erster ARM32-Bionic-Prozess – Vorbereitung

Das Beispiel `q60t_bionic_hello.c` ist ein minimaler Userspace-Prozess.
Der Aufbau erfolgt mit einem **Android-NDK-Compiler**, ausdrücklich
nicht mit dem glibc-Cross-Compiler des statischen QEMU-`/init`.

Beispiel für ein installierter Android NDK auf x86_64-Linux:

```bash
"$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/armv7a-linux-androideabi24-clang" \
  -fPIE -pie -O2 -Wall -Wextra \
  -o q60t_bionic_hello.arm32 q60t_bionic_hello.c

python3 q60t_bionic_preflight.py --elf q60t_bionic_hello.arm32
```

Das Tool akzeptiert ausschließlich ein **ELF32/ARM/ET_DYN** mit dem
Android-Bionic-Interpreter `/system/bin/linker` oder
`/apex/com.android.runtime/bin/linker`. Optional prüft es in einem
staged Rootfs Linker und `system/lib/libc.so`. Das ist **noch keine
Ausführung im Gast**. Für Build 021 brauchen wir zuerst ein rein
temporäres ARM32-Android-Rootfs und einen Launcher mit passendem Loader
und Bionic-Libraries, ohne Samsungs Tizen-Userspace zu überschreiben.

## Qualitätsnachweis

```bash
python3 -m unittest discover -s tests -q
cc -std=gnu11 -Wall -Wextra -Werror -fsyntax-only q60t_ion_probe_init.c
```

Die automatischen Tests prüfen Profile-Isolation, ION-Gastmarker,
SELinux-Statusgrenzen, ELF32/Interpreter, verweigerte Quellbaum-ABI
und die Regeln gegen irreführende Boot-/Flash-Aussagen. CI nutzt nur
synthetische Daten, keinen Samsung-Kernel, kein echtes QEMU-Ergebnis.

## Primärquellen

- [AOSP-Linux-ION-Kconfig und Dummy-Treiber](https://android.googlesource.com/kernel/common/+/efbc4a364bd5469a616668127439e7cfca4c1d7b/drivers/staging/android/ion/Kconfig)
- [AOSP-Linux-ION-Dummy-Implementation](https://android.googlesource.com/kernel/common/+/7dcbebc5490b10bb5b9e136918fa56bf9dcfed32/drivers/staging/android/ion/ion_dummy_driver.c)
- [AOSP SELinux-Policy-Build und Init-Boot](https://source.android.com/docs/security/features/selinux/build)
- [AOSP SELinux implementieren](https://source.android.com/docs/security/features/selinux/implement)
- [AOSP Bionic-Dokumentation](https://android.googlesource.com/platform/bionic/)

**Gesamtstatus: `HOST_IMPLEMENTED_QEMU_ION_BUILD_NOT_YET_VERIFIED`.**
