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
python3 porting/build060/host_preflight.py --build-dir /opt

# Unabhängige, netzwerkfreie Selbsttests
python3 -m unittest discover -s porting/build060/tests -v
```

## Erster echter ARM32-TV-Userspace-Build (auf geeignetem x86_64-Buildhost)

**Nur nach bestandenem Host-Gate** und falls der Nutzer den großen
Source-Download ausdrücklich gestartet haben will:

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
