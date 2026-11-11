# Build 060 – Android 15 / LineageOS 22.2 Android TV (ARM32)

Status: **Vorbereitungs- und Compiler-Gate, nicht gebootet**. Fortsetzung von
`claude/build059-nikel-linux66-base` für Samsung Q60T / Nike-L. Kein TV-Zugriff,
keine Firmwareänderung und keine Flash-/Signaturversuche.

## Belastbare Ausgangsbasis

- Offizielle LineageOS-Wiki: Das Android-TV-Emulatorziel `sdk_tv_arm` existiert
  für LineageOS 21+; die Version `lineage-22.2` gehört zu Android 15.
  https://lineageos.github.io/lineage_wiki/emulator.html
- Offizielle MindTheGapps-Version: `15.0.0-arm-ATV` (vollständige oder minimale
  TV-Variante). **Nicht** `15.0.0-arm` für Smartphones verwechseln.
  https://github.com/MindTheGapps/15.0.0-arm-ATV/releases
- **Bestätigter Referenzfall:** Chromecast mit Google TV (`sabrina`) hat in
  `lineage-22.2` einen ARM32-Android-TV-Userspace (`TARGET_ARCH := arm`,
  `TARGET_CPU_ABI := armeabi-v7a`) **auf einem ARM64-Kernel**
  (`TARGET_KERNEL_ARCH := arm64`). Dies beweist die Build-Unterstützung des
  Userspace, nicht die Machbarkeit einer ARM32-Kernel-Startkette auf Nike-L.
  https://github.com/LineageOS/android_device_amlogic_common/blob/lineage-22.2/BoardConfigAmlogic.mk
- Der `sabrina`-Baum bindet ein externes `mali-driver/bifrost`-Modul ein.
  Das ist **kein** Beleg für Panfrost-Unterstützung der Q60T-GPU; Gerät,
  Kernel, GPU-Revision und Grafik-HAL müssen separat validiert werden.
  https://github.com/LineageOS/android_device_amlogic_g12-common/blob/lineage-22.2/BoardConfigCommon.mk
- Bestehender ARM32-Nike-L-Linux-6.6.162-Kernel: `porting/build059/kernel/`.
  Der dortige Profilname `android` prüft Kernel-Kconfig, kompiliert aber
  **keinen Android-Userspace** und beweist keinen Boot auf dem Fernseher.
- `porting/device/samsung/nikel/BoardConfig.mk` enthält zu Recht eine
  absichtliche `$(error ...)`-Sperre. **Nicht entfernen**, bis signierter
  Bootweg, Recovery, Partitionierung und Hardwaretreiber nachgewiesen sind.

## Ziel des ersten Meilensteins

Ein echter, reproduzierbarer **32-Bit-LineageOS-22.2-Android-TV-Userspace** für
den ARM-Emulator (`sdk_tv_arm-eng`). Danach im Emulator starten, ADB-ABI,
Zygote und Android-Version prüfen. Der Emulator ist keine Q60T-Emulation.

Nicht versprechen: Panfrost, Samsung-DRM, Ton, DRM-Streaming, Videodecoder,
Hardware-Boot oder Google-TV-Zertifizierung. MindTheGapps erst nach sauberem
Open-Source-Start hinzufügen; Google-Apps können nicht Teil unseres
redistribuierten Source-Releases sein.

## Host-Gate (vor `repo sync`)

LineageOS empfiehlt für LineageOS 21+ einen 64-Bit-x86-Linux-Buildhost mit
ca. **64 GiB RAM und 400 GiB freiem Speicher**. Unser bisheriger 4-GB-Test-VPS
ist für den kompletten Userspace-Build nicht geeignet, wohl aber für kleinere
Kernel- und Strukturtests.

```bash
# Im Projektrepository; testet nur den aktuell verfügbaren Speicherplatz
# Die kleinen Basiswerkzeuge vorher installieren (z. B. Ubuntu 24.04):
sudo apt-get update
sudo apt-get install -y git git-lfs repo
python3 porting/build060/host_preflight.py --build-dir /opt

# Unabhängige, netzwerkfreie Selbsttests
python3 -m unittest discover -s porting/build060/tests -v
```

## Erster echter ARM32-TV-Userspace-Build (auf geeignetem x86_64-Buildhost)

**Nur nach bestandenem Host-Gate**, auf einem Ubuntu-24.04-Buildhost und falls
der Nutzer den großen Source-Download ausdrücklich gestartet haben will.
Auf Debian können Paketnamen abweichen; dort die Abhängigkeiten einzeln
gegen die Distribution prüfen:

```bash
sudo apt-get update
sudo apt-get install -y repo git git-lfs bc bison build-essential ccache \
  curl erofs-utils flex g++-multilib gcc-multilib gnupg gperf imagemagick \
  kmod protobuf-compiler python3-protobuf lib32readline-dev lib32z1-dev \
  libdw-dev libelf-dev libgnutls28-dev lz4 libsdl1.2-dev libssl-dev \
  libxml2 libxml2-utils lzop pngcrush rsync schedtool squashfs-tools \
  xsltproc xxd zip zlib1g-dev
git lfs install
sudo mkdir -p /opt/lineage-22.2
sudo chown "$(id -u):$(id -g)" /opt/lineage-22.2
cd /opt/lineage-22.2

# Registrierte git-Identität erforderlich (auf Nutzerkonto setzen)
repo init -u https://github.com/LineageOS/android.git -b lineage-22.2 \
  --git-lfs --no-clone-bundle
repo sync
source build/envsetup.sh
breakfast sdk_tv_arm eng
mka
```

### Reproduzierbares Build060-Gate

Mit dem eingecheckten Build-Gate wird das Ziel **vor** dem eigentlichen
Kompilieren auf `TARGET_ARCH=arm` und ein `sdk_tv_arm`-Produkt geprüft.
`--mode check` startet keine vollständige `mka`-Kompilierung und lädt keine
Quellen herunter. Das Skript erwartet einen **bereits synchronisierten**
LineageOS-22.2-Quellbaum:

```bash
# Nach repo sync, im Projekt-Checkout:
python3 porting/build060/lineage_build.py \
  --source /opt/lineage-22.2 --mode check

# Voller Android-TV-Build nur nach ausdrücklicher Freigabe auf geeignetem Host:
python3 porting/build060/lineage_build.py \
  --source /opt/lineage-22.2 --mode build --confirm-large-build
```

Zwei getrennte Workflows:

- `build060-arm32-atv-preflight.yml`: kostenloser, kleiner CI-Testlauf der
  Build- und Diagnose-Logik, **ohne** Android-Quellen oder Kernelbau.
- `build060-arm32-atv-full.yml`: **nur manuell** mit Bestätigung
  `BUILD_ARM32_ATV`. Benötigt einen eigenen GitHub-Runner mit den Labels
  `self-hosted`, `Linux`, `X64`, `android-build` und eine Repo-Variable
  `LINEAGE_22_2_SOURCE_ROOT` (absoluter Pfad zum synchronisierten Tree).
  Ohne diesen Runner wird der Job nicht ausgeführt. Ein Workflow muss
  zunächst auf dem Default-Branch verfügbar sein, um regulär per
  `workflow_dispatch` gestartet zu werden. Ein grüner Preflight ist kein
  erfolgreiches Android-ROM.

### Linux-6.6-ARM32-Android-Gate

Der moderne Kernel enthält Binder, SELinux und dma-buf-Infrastruktur;
deren tatsächliche Kconfig-Aktivierung, Schnittstellen und Android-Integration
sind **nicht** allein durch die Kernelversion bestätigt. Nach Build059
die **aufgelöste**, final generierte ARM32-`.config` prüfen:

```bash
python3 porting/build060/kernel_config_gate.py \
  --config /pfad/zu/build059-arm32/.config
python3 porting/build060/driver_audit.py --repo .
```

Der Config-Check unterscheidet harte Projekt-Basisflags und weitere
Review-Flags. `PASS_STATIC_CONFIG_ONLY` ist **kein** Android-CDD/VTS-Test
und kein Nachweis, dass der Samsung-Bootloader das Image akzeptiert.

Der Treibercheck zählt ausschließlich im Checkout vorhandene **Quellen**;
er führt keine Samsung-Hardware aus und liest keine proprietären Archive.
Die Lage muss mit dem externen Media-Paket `tztv-media-nike.tgz` ergänzt werden.
Bekannte Grenzen aus Build058: Panfrost/GPU-Clock, CPU-Clock und DRM-`util`/
`fence` lieferten ARM32-Objekte; GPU-`modpost`, CPUFreq/Thermal und
Samsung-DRM-Core/GEM sind weiterhin nicht abgeschlossen.

Nach Erfolg `emulator` starten (offizielle Anleitung) und via `adb shell`
bestätigen:

```bash
getprop ro.build.version.release
getprop ro.product.cpu.abi
getprop ro.zygote
uname -m
```

Bei einem ARM32-Ziel wird `ro.product.cpu.abi` auf `armeabi-v7a` erwartet;
`ro.zygote` sollte nur 32-Bit-Zygote-Prozesse starten. **Die konkrete
Binder-Protokoll-Bitness separat aus dem Build und Kernel prüfen**; 32-Bit-
Userspace garantiert nicht automatisch eine 32-Bit-Binder-Transaktions-ABI.

## Nach diesem Gate: Samsung-Hardwareport

1. Android-15-Kernelanforderungen gegen `build059` prüfen (Binder, SELinux,
   cgroups, namespaces, dma-buf-heaps, Grafik, Speicherlayout und LPAE).
2. Separaten ARM32-Q60T-Gerätebaum erstellen; vorhandene Research-only-
   `BoardConfig.mk`-Sperre ausdrücklich beibehalten.
3. Mit qemu-system-arm die Kernel-Bootgrundlagen unabhängig testen.
4. Erst nach geklärter Signaturkette und dokumentierter Wiederherstellung:
   vorsichtige Geräteexperimente. Keine Hardwaretests in Build 060.

Das Samsung-Bootloaderproblem ist **nicht** mit ARM32 allein gelöst. Ein
erfolgreicher Emulator-Build ist ein Build-Nachweis, kein Samsung-ROM.
