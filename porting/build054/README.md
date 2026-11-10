# Build 054 – Samsung DRM 6.6 Stage 2 und ARM32-Originalcode-Gegenprobe

**Status:** `PATCH_VALIDATED` · `ARM32_PROBE_PREPARED` · `COMPILATION_NOT_EXECUTED` · `NOT_LOADABLE` · `NOT_FLASHABLE`.

Der Linux-6.6-Port und der ARM32-Originalcode-Test sind **zwei unterschiedliche
Tests mit verschiedenen Kernel-Versionen**. Beide werden ausschließlich auf
einem Debian-Buildserver ausgeführt. Eine erfolgreiche Kompilierung allein
bestätigt **nicht** die Hardware- oder Firmwarekompatibilität eines TVs.

## A: ARM64 / Linux 6.6.162 – Build 053 gezielt fortsetzen

Der neue, kleine Zusatzpatch
`patches/0003-after-build053-drm-headers-ioctl-flags.patch`
wird **auf eine separate Kopie nach Build 053** angewendet. Er passt erstmals
auch die echten Samsung-Header `sdp_drm_drv.h` und `sdp_drm_gem.h` an:

- Die pauschalen, unter Linux 6.6 entfernten `<drm/drmP.h>`-Includes
  werden durch spezifische DRM-Core-Header ersetzt.
- In `sdp_drm_drv.c` werden alle 32 veralteten `DRM_UNLOCKED`-Flags zu
  `0`, wobei die ursprünglichen `DRM_AUTH`-Bits erhalten bleiben.
- Der vorherige harte `return -ENODEV` vor sämtlichen Samsung-Hardwareaufrufen
  und die künstliche Device-Tree-Compatible-ID **bleiben erhalten**.

**Ausdrücklich noch nicht repariert:** `linux/reservation.h`,
`reservation_object`, alter `struct fence`, Samsung-spezifische GEM/CMA-Felder,
GEM-Objektfreigabe über `drm_gem_object_funcs`, weitere DRM-KMS-Callbacks.
**Kein** erfolgreicher Linux-6.6-Build dieser echten Samsung-Dateien ist belegt.

### Auf einer neuen Quellkopie anwenden

Voraussetzung: ein Verzeichnis `build054-stage2-test01/`, das den bereits mit
**genau einem** Build-053-Patch versehenen Baum `tztv-media-nike/` enthält.

```bash
cd /opt/samsung-atv-lab/build054-stage2-test01
patch --dry-run --batch -p1 -i /pfad/zum/Build054/patches/0003-after-build053-drm-headers-ioctl-flags.patch
patch --batch -p1 -i /pfad/zum/Build054/patches/0003-after-build053-drm-headers-ioctl-flags.patch
```

Für einen isolierten diagnostischen Versuch das Build-053-`test-kbuild/Kbuild`
in die neue `tztv-media-nike/sdp_drm_nike/`-Arbeitskopie übernehmen. Danach
bei vorbereitetem **eigenen** ARM64-Kernelobjektverzeichnis:

```bash
cd /opt/samsung-atv-lab/build054-stage2-test01/tztv-media-nike/sdp_drm_nike
make -C /opt/samsung-atv-lab/linux-6.6.162 \
  O=/opt/samsung-atv-lab/build054-arm64-obj \
  ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  M="$PWD" sdp_drm_drv.o
```

Die Fehlermeldungen dieses **Objekt-Builds** bestimmen den nächsten echten
Portierungsschritt; weder Modul-Link noch Test auf TV-Hardware ausführen.

## B: ARM32 / Linux 4.1.10 – unveränderte Samsung-Referenz

Der quellgeprüfte Bericht
[`reports/build054-arm32-vendor-source-evidence.json`](../../reports/build054-arm32-vendor-source-evidence.json)
belegt für das veröffentlichte Samsung-Bundle:

- Die `arch/arm/configs/Nike.M-Tizen_release_defconfig` wählt
  **ARM32 / ARMv7 / Cortex-A15**.
- Das mitgelieferte DRM-Makefile hat `ARCH = arm` und einen
  `armv7l-tizen-linux-gnueabi-`-Cross-Compiler als Standard; **ARM64** ist dort
  über eine zusätzliche Bedingung grundsätzlich vorgesehen.
- Eine Datei im Pfad `arch/arm64/configs/` ist **keine** Bestätigung für ARM64:
  sogar die mitgelieferte `Nike.M-Tizen_debug_defconfig` dort enthält
  ARM32-/Cortex-A15-Einstellungen.
- Das Archiv enthält nicht alle erforderlichen externen
  `vd_kernel-interfaces`-Header, unter anderem fehlen
  `drm/drm_tztv.h` und `linux/videodev2_tztv.h`. Der originale
  Samsung-DRM-Treiber kann deshalb allein aus diesen GPL-Archiven
  **noch nicht vollständig kompiliert werden**.

Das ist eine Referenz zu **Nike.M**, nicht der Nachweis, dass der Q60T
`GQ50Q60TGUXZG` diese CPU benutzt. Für unser Gerät bleibt
**SDP19403 / Nike-L / Cortex-A72 / Mali-G31** eine *vorläufige,
hardwareseitig noch nicht bestätigte Arbeitshypothese*.

### B1. ARM32-Toolchain und Kernel vorbereiten

Auf Debian zum Beispiel folgende Programme bereitstellen:

```bash
apt install gcc-arm-linux-gnueabi binutils-arm-linux-gnueabi \
  build-essential bc bison flex libssl-dev libelf-dev
```

Für die beiden Originalarchive eigene, vorher **nicht vorhandene**
Build-054-Verzeichnisse anlegen; das Beispiel setzt voraus, dass sie bereits
nach `/pfad/linux-4.1.10-tizen5.5.tgz` und `/pfad/tztv-media-nike.tgz`
kopiert wurden:

```bash
mkdir /opt/samsung-atv-lab/build054-arm32-original
tar -xzf /pfad/linux-4.1.10-tizen5.5.tgz \
  -C /opt/samsung-atv-lab/build054-arm32-original
tar -xzf /pfad/tztv-media-nike.tgz \
  -C /opt/samsung-atv-lab/build054-arm32-original
```

Die SHA-256-Werte der Archive vorher mit dem Audit vergleichen. Beide
Archive sind lokal verfügbar, aber **nicht** bereits auf dem Debian-Server
geprüft. Von hier aus wurde keine Cross-Kompilierung auf dem Server ausgeführt.

Den **nicht existierenden** Zielordner `build054-arm32-smoke` angeben:

```bash
bash porting/build054/scripts/run-arm32-probe.sh \
  /opt/samsung-atv-lab/build054-arm32-original/linux-4.1.10 \
  /opt/samsung-atv-lab/build054-arm32-smoke
```

Der Test führt `Nike.M-Tizen_release_defconfig`, `modules_prepare` und den
Compiler-Aufruf **nur für** `nover_arm32_probe.o` aus. Anschließend wird
die ELF-Architektur per ARM-Cross-`readelf` geprüft. Er erzeugt **keine `.ko`**
und lädt nichts. Die Logs liegen im neuen `build054-arm32-smoke/`.
Ein Compiler-/Hosttool-Konflikt mit dem alten Linux 4.1 ist möglich.

### B2. Originalen Samsung-DRM-Code als ARM32 übersetzen

Nach erfolgreichem B1 den nur für ARM32 bestimmten
`test-kbuild-arm32/Kbuild` in den **frisch extrahierten, unveränderten**
`sdp_drm_nike/`-Baum kopieren:

```bash
cp porting/build054/test-kbuild-arm32/Kbuild \
  /opt/samsung-atv-lab/build054-arm32-original/tztv-media-nike/sdp_drm_nike/Kbuild
```

```bash
bash porting/build054/scripts/run-arm32-vendor-diagnostic.sh \
  /opt/samsung-atv-lab/build054-arm32-original/linux-4.1.10 \
  /opt/samsung-atv-lab/build054-arm32-smoke/kernel-obj \
  /opt/samsung-atv-lab/build054-arm32-original/tztv-media-nike/sdp_drm_nike
```

Der Runner prüft den **SHA-256-Hash der originalen `sdp_drm_drv.c`** und
übersetzt ausschließlich `sdp_drm_drv.o`. Bei einem fehlenden
`vd_kernel-interfaces`-Header wird die Kompilierung erwartungsgemäß
scheitern. Header aus anderen Kernel-Versionen nicht blind untermischen.

## Lokal nachprüfen

```bash
python3 -m unittest tests.test_build054_samsung_dualarch -v
python3 -m unittest discover -s tests -q
```

Build-054-Patches sind SHA-256-reproduzierbar und überschreiben keine
vorhandenen Dateien. **Keine** Anleitung enthält `insmod`, Firmware-Flash,
Bootloaderänderungen oder einen Hardwarezugriff auf den TV.

Quellen: [Linux 6.6 GEM](https://docs.kernel.org/6.6/gpu/drm-mm.html),
[Linux-Kbuild-Dokumentation](https://docs.kernel.org/kbuild/kbuild.html).
