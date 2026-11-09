# Build 022 – LineageOS für ARM32-QEMU-virt vorbereiten

**Stand:** Reproduzierbare Host-Vorprüfung, **kein** fertiger LineageOS-Build,
kein Android-Init-Start, kein ausgewählter Release und kein TV-Flash.

Dieses Verzeichnis hält die reale Samsung-Hardware bewusst getrennt von
unserer `qemu-system-arm -machine virt,highmem=off`-Testplattform. Der
erfolgreiche Build-020-ION-Test und der Build-021-Bionic-Ansatz bleiben
unverändert; die beiden Umgebungen sind **noch kein** LineageOS-Device-Port.

## 1. Offizielle Revisionsbasis und Kandidaten

`lineage-source-candidates.json` enthält recherchierte Branch-Head-SHAs
und Git-Blob-SHAs des offiziellen `default.xml`-Manifests:

| Android-Basis | Offizieller LineageOS-Branch | Android API | Status |
| --- | --- | --- | --- |
| 7.1 | `cm-14.1` | 25 | Zu prüfen; `lineage-14.1` existiert **nicht** |
| 8.1 | `lineage-15.1` | 27 | Zu prüfen; Treble/VINTF beachten |
| 9 | `lineage-16.0` | 28 | Zu prüfen; stärkere Kernel-/HAL-Hürden |
| 10 | `lineage-17.1` | 29 | Zu prüfen; First-stage-Init und SELinux-Hürden |

**Keine Version ist festgelegt.** Alter Linux-4.1.10-Kernel plus
recherchierter Branch bedeutet weder Android-Kompatibilität noch einen
Build-/Recovery-Weg. Sicherheitsupdates alter Branches sind separat zu
bewerten; sie werden hier nicht behauptet.

Offizielle Quelle: <https://github.com/LineageOS/android>.

Die nötigen LineageOS-Projekt-Repositories umfassen viele Gigabytes.
Im kleinen GitHub-Forschungsrepo liegen **keine** Android-Systemimages,
proprietären Samsung-Quellen oder vollständigen LineageOS-Checkouts.

## 2. Offizielles Manifest im isolierten Labor prüfen

Auf einer Linux-Build-VM mit `git` und Googles `repo`-Werkzeug:

```bash
# Einen Kandidaten einzeln prüfen – dies ist KEINE finale Release-Entscheidung.
mkdir -p /opt/samsung-atv-lab/lineage022-cm141
cd /opt/samsung-atv-lab/lineage022-cm141
repo init -u https://github.com/LineageOS/android.git -b cm-14.1

# Vor einem späteren Sync den tatsächlichen Manifest-Commit prüfen.
git -C .repo/manifests rev-parse HEAD
git -C .repo/manifests hash-object default.xml
```

Für `cm-14.1` ist in `lineage-source-candidates.json` eine konkrete
Manifest-Commit-SHA und Blob-SHA vermerkt. Wenn die aktuelle Branchspitze
anders ist, **nicht** blind weiterarbeiten, sondern Vergleich und
Quellrevision dokumentieren. Für einen reproduzierbaren Versuch kann die
eingetragene Commit-SHA in einer separaten Labor-Kopie ausgecheckt werden.
Die Prüfsummen verifizieren ausschließlich das Manifest, **nicht** die
gesamten (noch nicht synchronisierten) Quell-Repositories.

Für die Offlineprüfung die **unveränderte** `.repo/manifests/default.xml`
übergeben. Ein abweichender Git-Blob-Hash führt zum Abbruch:

```bash
python3 q60t_lineage_preflight.py \
  --candidate cm-14.1 \
  --source-manifest /opt/samsung-atv-lab/lineage022-cm141/.repo/manifests/default.xml \
  --kernel-config /opt/samsung-atv-lab/samsung/build020-qemu-ion-001/output/.config \
  --output /opt/samsung-atv-lab/samsung/build022-cm141-preflight.json
```

`--output` darf **nicht existieren**; es wird nichts überschrieben. Das
Programm startet keine VM, keinen Download und kein Samsung-Gerät. Zum
ersten Test ohne die beiden optionalen Dateien:

```bash
python3 q60t_lineage_preflight.py --candidate cm-14.1
```

Das liefert erwartungsgemäß `NOT_PROVIDED` für Manifest und Kernel-
Konfiguration und **keinen** Kompatibilitäts- oder Boot-Erfolg.

Ein späteres `repo sync -c --no-tags` ist erst nach verfügbaren
Speicher-/Netzwerkressourcen und Manifest-Verifikation sinnvoll.
Keine Samsung-Originaldateien oder bereits erfolgreiche Build-021-Dateien
werden durch den Sync verändert: eigener Quellordner erforderlich.

## 3. Android-TV-/ARM32-Product-Target: Was für QEMU wirklich fehlt

Die bisherigen QEMU-Parameter:

```text
qemu-system-arm -machine virt,highmem=off -cpu cortex-a15 -m 1024
                -nic none -kernel <Build-020-zImage>
                -initrd <experimentelles-cpio.gz>
                -append "console=ttyAMA0,115200 ..."
```

Dies ist ein ARMv7-**virt**-Board. Standard-Android-Emulator-Targets für
Goldfish/Ranchu bilden diese Hardware **nicht** automatisch ab.

Vor `lunch` und einer offiziellen Build-Pipeline benötigen wir in einem
dedizierten neuen LineageOS-Device-Tree mindestens:

1. `device/<vendor>/<product>/BoardConfig.mk` für ARMv7,
   Kernel-/Device-Tree-/Boot-Image-Format, Partitionen und `virt`-Konsole.
2. `AndroidProducts.mk` und passendes Produkt-Makefile; erst dann kann ein
   `lineage_<product>-userdebug`-Target existieren.
3. Android-TV-spezifische Produkt-Einstellungen statt Smartphone-
   Oberflächenannahmen; keine falsche Cuttlefish-/Goldfish-HAL-Nutzung.
4. `init*.rc`, `ueventd*.rc`, Mount-Layout, SELinux-Policy, File-Contexts,
   Android-Init- und Bionic-Abhängigkeitsclosure für ARM32.
5. Abgleich des Linux-4.1.10-Kernels mit dem *jeweiligen* Android-Branch
   (Binder-Protokoll, Ashmem/ION, Namespaces, cgroups, seccomp, SELinux,
   Systemaufrufe, init/ueventd, Treble/VINTF/Partionschema).

`qemu-virt-arm32.json` ist ein **Hardwareprofil**, kein gebautes
`BoardConfig.mk`. `android-init-stages.json` ist die überprüfbare
Reihenfolge; jeder echte Gaststart bleibt noch aus.

## 4. Android-Init und Basisdienste erst mit Gastbelegen

Nach vollständigem LineageOS-Quell-Sync, eigenem ARM32-Virt-Device-Port
und **erfolgreichem** Kernel-/SELinux-/ELF-Gate einzeln:

1. Originales ARM32-`init` samt abhängigen Bionic-Bibliotheken im
   eigenständigen QEMU-Ramdisk-Lab bereitstellen.
2. Linux-Boot und Android-Init-First-Stage nachweisen.
3. Android-Init-Second-Stage sowie Property Service nachweisen.
4. Erst danach `ueventd`, `logd`, `servicemanager` prüfen; kein Zygote-
   oder TV-UI-Erfolg wird aus deren Existenz abgeleitet.

Serielle QEMU-Ausgabe lässt sich **lesend** untersuchen:

```bash
python3 q60t_lineage_init_evidence.py \
  --log /opt/samsung-atv-lab/samsung/build022-qemu-serial.log
```

Das Ergebnis unterscheidet sichtbare Log-Hinweise strikt von der
**belegten Ausführung originaler LineageOS-Binaries**. Ein einfaches
Log-Muster kann keine Binär-Provenienz oder korrekte SELinux-Policy
beweisen; dafür sind zusätzliche Hash-, ELF-, Prozess- und
QEMU-Laufzeitbelege nötig. Alte Build-021-Bionic-Marker gelten nicht als
Android-Init-Start.

## 5. Samsung-Hardware und Sicherheitsgrenzen

Der echte **Samsung GQ50Q60TGUXZG** bleibt unangetastet. CPU/SoC,
Bootloader, Secure Boot, Flash-Layout, Mali-GPU, Display, Audio und
Remote-Eingabe brauchen eigene identifizierende Daten. Kein QEMU-Test
ersetzt diese Hardware-Recherche. **Kein Flashen, kein modifizierter
Firmware-Boot und keine suggerierte Wiederherstellbarkeit.**

## Referenzen (Primärquellen)

- [LineageOS – offizielles Android-Manifest](https://github.com/LineageOS/android)
- [LineageOS – Build von Quellen](https://wiki.lineageos.org/devices/)
- [AOSP – Kernelanforderungen je Android-Version](https://source.android.com/docs/core/architecture/kernel)
- [AOSP – VINTF / Kernel-Matching](https://source.android.com/docs/core/architecture/vintf)
- [AOSP – Android Init](https://android.googlesource.com/platform/system/core/+/refs/heads/main/init/)
