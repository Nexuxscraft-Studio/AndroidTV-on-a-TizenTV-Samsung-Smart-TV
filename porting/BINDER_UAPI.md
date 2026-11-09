# Samsung Q60T: Binder-ABI-Tests ohne Fernseher

Build 017 · **Auswertung und Cross-Compile nur am Entwicklungsrechner**

Die drei experimentellen Binder-Kontexte des Build 016 beseitigen
nicht automatisch alle Unterschiede zum heutigen Android-Kernel-ABI.
Ein Treiber kann eine bekannte Protokollnummer ausgeben und trotzdem
wichtige Transaktionen, IOCTLs oder Objekttypen nicht beherrschen.

## Statische Gap-Audits

Aus dem Projektverzeichnis:

```bash
python3 q60t_binder_abi.py \
  --source /pfad/zu/entpacktem/linux-4.1.10 \
  --output /pfad/zu/NEUEM-vendor-abi-report.json

# Auch gegen einen separat erstellten Build-016-Schattenbaum möglich:
python3 q60t_binder_abi.py \
  --source /pfad/zu/build016-binder-lab/linux-4.1.10-shadow \
  --output /pfad/zu/NEUEM-binder-lab-abi-report.json
```

`--output` erstellt **nur neue Dateien**. Das Werkzeug schreibt weder
in die Samsungquellen noch auf einen Fernseher. Die Eingabeversion muss
Linux 4.1.10 sein. Nicht vorhandene, verlinkte oder zu große
Binder-Header und -Quellen werden abgelehnt.

## ARM32-Linux-UAPI-Layout wirklich cross-kompilieren

Hier müssen die von `make headers_install` **installierten** Header
verwendet werden. Der unaufbereitete Kernel-Include-Pfad ist dafür
nicht geeignet.

```bash
# 1. Kopierte (!) Samsung-Kernelquellen, z.B. der Build-016-Schattenbaum:
make -C /pfad/zu/build016-binder-lab/linux-4.1.10-shadow \
  ARCH=arm INSTALL_HDR_PATH=/pfad/zu/NEUEM-abi-workspace/headers \
  headers_install

# 2. Compilerprobe: ELF-Objekt schreiben, nicht ausführen:
/pfad/zu/linaro/bin/arm-linux-gnueabi-gcc \
  -std=gnu11 -Wall -Wextra -Werror \
  -I /pfad/zu/NEUEM-abi-workspace/headers/include \
  -c porting/probes/binder_uapi_arm32.c \
  -o /pfad/zu/NEUEM-abi-workspace/binder_uapi_arm32.o

# 3. Ergebnis kontrollieren:
file /pfad/zu/NEUEM-abi-workspace/binder_uapi_arm32.o
```

Der Probequellcode prüft **genau** die alte Kernel-UAPI-Strukturgröße
für das im Host-Profil ausgewählte 64-Bit-Binder-Wire-Layout auf ARM32.
Das ist nützlich für die spätere Portierung – aber kein Beweis für
Lauffähigkeit mit Android-14-Systemdiensten.

## Interpretationsgrenze

Der eingefrorene Vergleichsheader stammt aus dem offiziellen
[Android-Common-Kernel](https://android.googlesource.com/kernel/common/+/d04d0acdaf98506fca2e6501ed6adcdcc7d31a1f/include/uapi/linux/android/binder.h).
Eine fehlende Deklaration zeigt eine **konkrete Portierungslücke**;
die Existenz eines Symbols bestätigt umgekehrt weder einen funktionierenden
Kernelhandler noch Sicherheits- oder Userspace-Kompatibilität.

Ein vollständiger Test braucht danach eine echte VM/Emulation mit
Service-Managern und negativen Binder-IPC-Testfällen. Ein Modellcode,
ein Compilererfolg oder eine erfolgreiche UAPI-Prüfung ermöglichen
**keinen** sicheren Flash auf den Samsung-TV.
