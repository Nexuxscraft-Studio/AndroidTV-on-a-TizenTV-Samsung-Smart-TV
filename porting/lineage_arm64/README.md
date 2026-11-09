# Build 024 – echter LineageOS-21-ARM64-First-Stage-Init unter QEMU

**Ausgewählt nur für den QEMU-Versuch:** offizieller LineageOS-Branch
`lineage-21.0` (Android 14, API 34). Offizieller ARM64-TV-GSI-Buildtarget
`gsi_tv_arm64`. **Kein** offizielles ARM64-TV-Emulator-Target
`sdk_tv_arm64` und **kein** fertiges QEMU-`virt`-Device-Target für diese
Konfiguration. Die GSI allein ist kein bootfähiges QEMU-`virt`-ROM.

Quellen-Lock: `lineage21-source-lock.json`; der genaue offizielle
Manifest-Commit und dessen `default.xml`-Blob-SHA sind vermerkt. AOSP-
Basis ist `android-14.0.0_r67`. Die Lock-Prüfung umfasst **nicht** alle
projektübergreifenden Git-Objekte; dafür später die vollständigen
Manifest-/Repo-Revisionsstände dokumentieren.

## Getrennte Build-Umgebung auf dem Proxmox-Linux-Labor

Der im anderen Testlabor **gemeldete** ARM64-Linux-6.6.162-Boot mit
Binder, memfd, DMA-BUF und SELinux-FS ist die Kernel-Vorbedingung. Das
ist noch keine Android-SELinux-Policy oder ein Android-Systemdienst.

1. Vorherigen Samsung-Kernel und Linux-6.6.162-Testlauf unverändert lassen.
2. Für LineageOS ausreichend SSD-Platz, RAM und Netzwerk vorsehen; der
   komplette Source-Sync und Android-Build sind umfangreich. Nur aus
   offiziellen LineageOS-/AOSP-Repositories laden.
3. Separaten Quellordner verwenden, z. B.
   `/opt/samsung-atv-lab/lineage21-arm64`.

```bash
# In einem zuvor eigens angelegten, leeren LineageOS-Verzeichnis:
repo init -u https://github.com/LineageOS/android.git \
  -b lineage-21.0 --git-lfs --no-clone-bundle

# Der ermittelte Commit muss mit dem Lock übereinstimmen:
git -C .repo/manifests rev-parse HEAD
git -C .repo/manifests hash-object default.xml

# Keine beliebige aktualisierte Branchspitze über den Lock hinweg verwenden.
# Revisionsabweichungen zuerst klären und separat dokumentieren.
# Erst dann: repo sync
```

Der Stand im Lock ist Commit
`121f4ec5f11dc98ff2c427bc9d23165e914c54bb` und Manifest-Blob
`8837b599e325c839b38c6a9905b3f6b28fba53ed`.

Quellprüfung **ohne Download und ohne Schreibzugriff**:

```bash
python3 q60t_lineage_arm64_source.py \
  --checkout /opt/samsung-atv-lab/lineage21-arm64
```

Ohne `--checkout` lässt das Werkzeug nur den recherchierten Quellen-Lock
anzeigen. Keine Zeile des LineageOS-Quellbaums wird dabei verändert.

## Offiziellen ARM64-TV-Build erzeugen – erst nach vollständigem Sync

Die [LineageOS-Emulator-Dokumentation](https://lineageos.github.io/lineage_wiki/emulator.html)
nennt für LineageOS 21 `gsi_tv_arm64` als TV-GSI-Target:

```bash
source build/envsetup.sh
breakfast gsi_tv_arm64 eng

# First-stage-Init gezielt aus den echten LineageOS-Quellen bauen:
m init
```

Falls `breakfast` oder `m init` scheitert, Buildsystem und Target zuerst
reparieren. **Kein fremdes Android-`init` als Ersatz unterschieben.**
Danach die tatsächlich erzeugte ARM64-First-Stage-`init` im `out/`-
Ordner ermitteln; der genaue Pfad ist buildabhängig. Nur eine echte
statisch gelinkte AArch64-ELF-Datei ohne `PT_INTERP` ist hier zulässig.

## Erstes experimentelles Android-`init`-Initramfs

```bash
# FIRST_STAGE_INIT auf den realen, geprüften Pfad in
# /opt/samsung-atv-lab/lineage21-arm64/out/... setzen.
python3 q60t_lineage_arm64_initramfs.py \
  --checkout /opt/samsung-atv-lab/lineage21-arm64 \
  --first-stage-init "$FIRST_STAGE_INIT" \
  --kernel-config /opt/samsung-atv-lab/build023-arm64-kernel/.config \
  --output /opt/samsung-atv-lab/build024-lineage-initrd.cpio.gz \
  --report-output /opt/samsung-atv-lab/build024-lineage-stage.json
```

Das Werkzeug verlangt den offiziellen gepinnten Manifest-Checkout,
einen echten AArch64-`/init`-ELF aus dessen `out/` und wesentliche
Kernel-Kconfig-Schalter. Es verpackt das Init **ohne** Samsung-Firmware,
ohne fremde Android-Systembibliotheken und ohne Vortäuschen von
init.rc- oder SELinux-Ergebnissen.

**Wichtig:** Das dadurch erzeugte Initramfs enthält noch kein Android-
`system.img`, kein `vendor.img`, keine `fstab`-Gerätedefinitionen und
keine gültige Android-Policy. Android-14-Produktionsgeräte verwenden für
First-Stage-Init häufig das `init_boot`-Konzept; unser QEMU-`-initrd`
ist ausdrücklich **nur ein Forschungslabor**, kein Android-Firmware-
Layout. Der Prozess kann bereits in der ersten Mount-Phase scheitern.

## QEMU-Test und echte Gast-Evidenz

```bash
python3 q60t_arm64_qemu.py \
  --kernel /opt/samsung-atv-lab/build023-arm64-kernel/arch/arm64/boot/Image \
  --initrd /opt/samsung-atv-lab/build024-lineage-initrd.cpio.gz \
  --output-dir /opt/samsung-atv-lab \
  --run-id lineage024-001 --timeout 60

python3 q60t_lineage_arm64_init_result.py \
  --log /opt/samsung-atv-lab/qemu-serial-lineage024-001.log \
  --qemu-metadata /opt/samsung-atv-lab/qemu-meta-lineage024-001.json \
  --stage-report /opt/samsung-atv-lab/build024-lineage-stage.json
```

Ein Marker `init: init first stage started!` gilt **nur** als
erster tatsächlich berichteter Android-Init-Start, wenn die
QEMU-Log-SHA und die Initramfs-SHA mit den Staging-Artefakten
übereinstimmen. Es ist **noch kein** vollständiger First-Stage-
Abschluss, Android-Zweitstart oder LineageOS-Boot.

## SELinux und Property Service: gesonderte Freigabestufen

```bash
python3 q60t_lineage_arm64_sepolicy.py \
  --product-root /opt/samsung-atv-lab/lineage21-arm64/out/target/product/DEIN_TARGET \
  --kernel-config /opt/samsung-atv-lab/build023-arm64-kernel/.config
```

Die Untersuchung erwartet mindestens Plattform- und Vendor-Policy-
Eingaben. Bei einer reinen GSI fehlt oft die zu unserer QEMU-`virt`-
Hardware gehörende Vendor-Policy. Erst wenn wir passende system/vendor
Partitionen, `file_contexts`, `property_contexts`, `init.rc`, `fstab`
und eine mit Android-Werkzeugen erfolgreich geprüfte Policy haben,
können wir SELinux-Setup und Second-Stage-Init testen.

Dann folgen einzeln:

1. Android-Init-First-Stage einschließlich tatsächlicher Mounts.
2. `selinux_setup` und enforcing Policy nach `secilc`/`neverallow`-Prüfung.
3. Android-Second-Stage-Init und Property Service.
4. `ueventd`, `logd`, `servicemanager`, `hwservicemanager` mit echten
   Prozess-/Binder-Belegen.
5. Erst danach Zygote, ART, HALs und grafischer Android-TV-Userspace.

Wir bauen **keine** pauschal permissive oder `allow *`-Policy, um einen
grünen Bootstatus zu erzwingen.

## Samsung-TV bleibt vollständig getrennt

Der GQ50Q60TGUXZG wird in diesem Build weder erreicht noch geflasht.
Wir haben bislang keine verifizierte ARM64-SoC-Identifikation,
keinen neuen Samsung-Mali-/Display-/Audio-Treiberport und keinen
sicheren Recovery-Bootweg. Ein QEMU-ARM64-Android-Start ändert diese
Hardware-Grenzen nicht.

### Offizielle Quellen

- [LineageOS ARM64-TV-GSI und Emulator-Builds](https://lineageos.github.io/lineage_wiki/emulator.html)
- [Offizieller LineageOS-21.0-Manifest-Branch](https://github.com/LineageOS/android/tree/lineage-21.0)
- [Android 13+ `init_boot`-Layout](https://source.android.com/docs/core/architecture/partitions/generic-boot)
- [Android-SELinux-Build aus Plattform-/Vendor-Policy](https://source.android.com/docs/security/features/selinux/build)
- [Android Common Kernel/GKI nach Android-Version](https://source.android.com/docs/core/architecture/kernel/android-common)
