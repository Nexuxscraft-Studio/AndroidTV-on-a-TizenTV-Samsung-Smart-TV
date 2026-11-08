# Teilprojekt 2: GPU/Display-Anbindung an Android TV

**Status: ABI-Analysewerkzeug + Integrationsvertrag vorhanden; noch keine
funktionsfähige Mali-/Gralloc-/Composer-HAL.**

## GPU-Treiber nicht vorschnell zuordnen

Der Samsung-Nike-L-Device-Tree enthält die generische Kennung
`arm,mali-midgard` am Pfad `/soc/sdpgpu@00500000`. Das allein bestimmt
die **reale GPU-Generation nicht zuverlässig**. Eine neuere unabhängige
Q60T-Untersuchung berichtet auf dem untersuchten 2743.0-Modell
**Mali-G51 (Bifrost), Treiber r11p0**.
Unsere Referenzfirmware hat diese Version im bisher untersuchten
`uImage` nicht selbst bestätigt; die vollständige Extraktion des
komprimierten VDFS-Modulbaums ist noch nicht gelungen.

Deshalb gilt: Kein fremder Midgard-/Bifrost-Treiber wird durch Umbenennen
einer `.so`-Datei automatisch Samsung-kompatibel. Die genaue Kbase-KABI,
Mali-GPU-ID und der Android-Grafikpfad müssen zusammenpassen.

## Android-TV-Displaypfad

Für eine sichtbare Android-Oberfläche werden mindestens benötigt:

1. **Kernel:** passender Mali-Kernelmodul-/DRM-Stack, Interruptionen,
   Power-Management, IOMMU/CMA und Synchronisationsfences.
2. **EGL/GLES:** zur Kernel-ABI passende ARM-Userspace-Library.
3. **Gralloc:** Android-Bufferspeicher mit passendem Mapper und Allocator.
4. **Hardware Composer:** Android-13+-AIDL-`composer3` oder ein vom
   konkreten Android-Stand unterstützter alternativer HAL-Pfad.
5. **Samsung-Display:** Modesetting/Panelinitialisierung (sdp-drm,
   TCON, FRC), VSync und sichtbarer Scanout.

Arm bietet eigene [Mali-User-Space-Binärtreiber](https://developer.arm.com/Downloads/-/Mali%20GPUs%20User-Space%20Binary%20Drivers)
für **bestimmte** Entwicklungsboards und GPU-Versionen. Sie lassen sich
nicht ohne Hardware-/Versions-/Lizenzprüfung übertragen. Google
dokumentiert [Hardware Composer](https://source.android.com/docs/core/graphics/implement-hwc)
und die [AIDL-Composer3-Schnittstelle](https://source.android.com/docs/core/graphics/aidl-hwc).

## Neue ELF-Analyse

`q60t_graphics.py` liest beliebige **lokal bereitgestellte** Kandidaten
`libmali.so` und `mali.ko` im ELF-Format, ohne sie auszuführen. Es
bestimmt ELF-Architektur, 32-/64-Bit-Klasse, SHA-256 und `DT_NEEDED`-
Bibliotheken. Im Host-Report werden diese Angaben mit dem **ARM32**-
Referenzkernel verglichen. Das ist lediglich die erste ABI-Hürde.

```bash
python3 q60t_graphics.py \
  --hardware-report reports/hardware_2743.0_build004_final.json \
  --kernel-report reports/kernel_build005.json

# Wenn die eigenen, rechtmäßig bezogenen ELF-Dateien vorliegen:
python3 q60t_graphics.py \
  --hardware-report reports/hardware_2743.0_build004_final.json \
  --kernel-report reports/kernel_build005.json \
  --libmali /pfad/zu/libmali.so \
  --kernel-module /pfad/zu/mali.ko
```

Der Status bleibt ausdrücklich `BLOCKED`, selbst wenn beide ELF-Dateien
ARM32 sind. Von einem funktionierenden Android-Hardware-Composer,
geschützter Videowiedergabe oder einem stabilen Bild können wir erst
nach einer echten Integration und Messung sprechen.

**Keine proprietären ELF-Dateien im Quellpaket.**

## Build 007 – zwei getrennte Entwicklungsrichtungen

`q60t_gpu_strategy.py` nutzt dieselben verifizierten Referenzberichte
wie `q60t_graphics.py` und untersucht bei Bedarf lokale Kernelquellen,
`libmali.so` und `mali.ko` – ohne sie auszuführen.

1. **Legacy kbase:** Die Tizen-Firmware nennt `/dev/mali0`. Benötigt
   werden eine zum Kernel passende kbase-Version, ARM32-Userspace-EGL,
   kompatible Buffer-Allocator/Mapper, Android-Composer und Samsung-
   Panel-Scanout. Die bloße Existenz von `drivers/gpu/arm/bifrost`
   beweist weder Bau noch Treiberfunktion.
2. **DRM/Panfrost:** Mesa/Panfrost unterstützt Bifrost-GPUs wie G51,
   benötigt jedoch einen passenden **Linux-DRM-Kerneltreiber** samt
   Displayintegration. Das ist **kein** direkter Ersatz für Samsungs
   vorhandenen kbase-Kernel/`/dev/mali0` und kein fertiger Backport
   auf den alten 4.1.10-Kernel.

```bash
python3 q60t_gpu_strategy.py \
  --hardware-report reports/hardware_2743.0_build004_final.json \
  --kernel-report reports/kernel_build005.json
```

Quellen: [Arm Bifrost GPL-Kerneltreiber](https://developer.arm.com/Downloads/-/Bifrost%20Mali%203rd%20Gen%20GPU%20Architecture),
[Mesa Panfrost](https://docs.mesa3d.org/drivers/panfrost.html),
[AOSP AIDL Hardware Composer](https://source.android.com/docs/core/graphics/aidl-hwc).

**Ergebnis Build 007:** Beide Pfade `BLOCKED` bis exakte Quellen,
Treiber-ABI, HALs und reale Anzeigeausgabe geprüft sind.

## Build 008 – präziser Arm-Kernelquellen-Kandidat

Die offizielle [Arm-Bifrost-Downloadseite](https://developer.arm.com/Downloads/-/Bifrost%20Mali%203rd%20Gen%20GPU%20Architecture)
listet den Linux-GPL-Kerneltreiber `BX301A01B-SW-99002-r11p0-01rel0.tgz`
vom **09.03.2018** (Arm-MD5:
`b5dd72297b50e700278adc372fafea94`). Das ist ein konkreter
**Quellkandidat**, kein verifizierter Treiber für die Samsung-Firmware
`2743.0`. Arm weist auf die nötige versionskompatible kommerzielle
DDK-/Userspace-Komponente hin. Der original Samsung-Kbase-ABI,
DRM-/Panel-/Composer-Pfad und die Rechte zur Weiterverteilung fehlen
weiterhin. Details: [BUILD008_REPORT.md](../BUILD008_REPORT.md).
