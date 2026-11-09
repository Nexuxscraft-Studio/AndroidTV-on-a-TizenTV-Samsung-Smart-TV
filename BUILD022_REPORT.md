# Build 022 – Q60T-Hardware und moderner LineageOS-Kernel: Migrationsaudit

**Status: `HOST_ONLY_HARDWARE_AUDIT_BLOCKED_FOR_DEVICE_BOOT`.**

Build 022 setzt **nicht** auf Android 7 oder Linux 4.1.10 als endgültige
Plattform. Diese Versionen dienten ausschließlich als Kernel-/Bionic-Labor.
Das langfristige Ziel ist **LineageOS Android TV** mit einem möglichst
aktuellen, für das konkrete Samsung-Q60T-Board tatsächlich tragfähigen
Kernel. Die LineageOS-Version und der finale Kernelzweig sind **noch nicht
ausgewählt**.

## Reale Befunde aus den vorhandenen Referenzdaten

Die unveränderten Berichte `reports/hardware_2743.0.json` (Build 003) und
`reports/source_compat_build011.json` (Build 011) wurden erneut geprüft.
Beide Berichte nennen denselben Referenz-DTB-SHA-256:

`9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2`

| Eigenschaft | Profil 1 | Profil 2 |
| --- | --- | --- |
| Referenz-DTB-Profil | `nikel-2G` | `nikel-1.5G` |
| CPU-Knoten | 4 | 4 |
| `compatible` | `arm,cortex-a57`, `arm,armv8` | identisch |
| Physischer RAM des Q60T bestätigt? | Nein | Nein |
| Bootloader erlaubt ARM64-Kernel? | Unbekannt | Unbekannt |

**Wichtige neue Schlussfolgerung:** Die Referenz-DTBs legen einen
ARMv8-fähigen SoC nahe. Der bisherige `uImage`-Pfad der Samsung-Firmware
benutzt jedoch einen **ARM32-Kernel**. Aus CPU-Architektur und einem
erfolgreichen ARM32-QEMU-Test folgt **nicht**, dass Samsungs Bootkette
einen eigenen AArch64-Kernel startet. Eine solche Fähigkeit wurde auch
auf dem realen Fernseher nicht geprüft.

## Build-022-Werkzeug und Sicherheitsgrenzen

`q60t_kernel_migration.py` erzeugt einen nachprüfbaren JSON-Bericht aus
vorhandenen **lokalen, schreibgeschützten** Forschungsdaten. Es prüft:

1. Gültige Berichtstypen, DTB-Fingerprints und Konsistenz der Profile.
2. CPU-Knoten pro Profil sowie ARMv8-`compatible`-Kennungen.
3. Samsung-Nike-L-, Mali-, DRM-/HDMI-, Videocodec-, Audio- und
   IR-Kompatibilitätskennungen gegen den alten Quellreferenzbericht.
4. Optional **echte Roh-DTB-Bytes**, die erneut gehasht und geparst werden.
5. Optional ein **unverändertes Referenz-`uImage`**, dessen Legacy-Header
   und beide CRCs geprüft werden. Die Architektur-ID wird protokolliert.
6. Alle weiterhin blockierten Voraussetzungen für einen eigenen Kernelboot.

Ein wörtlicher Treiber-Quelltexttreffer ist nur ein Treffer. Er beweist
**keinen** portierten Linux-6.x-Treiber und keine Android-HAL. Die
Fingerprints in importierten JSON-Berichten allein belegen auch nicht,
dass Build 022 die rohen DTB-Dateien nochmals geprüft hat; dafür ist die
optionale Eingabe `--raw-dtb` erforderlich.

Weder das Werkzeug noch die Berichte haben Funktionen zum Entsperren,
Modifizieren, Signieren, Booten oder Flashen eines Samsung-TV.

## Auf dem Debian-/Proxmox-Entwicklungshost ausführen

Die GitHub-Branch bleibt getrennt von `main` und Build 021. Der hier
verwendete SSH-Key ist der bereits konfigurierte Projekt-Key:

```bash
cd /opt/samsung-atv-lab/q60t-github

GIT_SSH_COMMAND='ssh -i /root/.ssh/id_ed25519_q60t -o IdentitiesOnly=yes' \
  git fetch origin feature/build022-q60t-kernel-migration

git switch --track -c feature/build022-q60t-kernel-migration \
  origin/feature/build022-q60t-kernel-migration

python3 q60t_kernel_migration.py \
  --hardware-report reports/hardware_2743.0.json \
  --source-compat-report reports/source_compat_build011.json \
  --output /opt/samsung-atv-lab/samsung/build022-kernel-audit-001.json
```

Falls der lokale Branch bereits existiert, `git switch` nur nach Prüfung
des lokalen Arbeitsstands verwenden. Das Analyseprogramm verweigert
absichtlich das Überschreiben einer bestehenden Ergebnisdatei.

Zur kurzen Ergebniskontrolle:

```bash
python3 -m json.tool \
  /opt/samsung-atv-lab/samsung/build022-kernel-audit-001.json \
  | grep -E 'status|armv8|arm64|bootloader|safe_to_flash|flash_authorized'
```

### Optional: rohe Referenzartefakte unabhängig gegenprüfen

Nur wenn die **bereits offline gesicherten** Referenzdateien tatsächlich
vorliegen, die beiden Argumente ergänzen. Dateipfade sind Beispiele und
müssen auf existierende Dateien zeigen:

```bash
python3 q60t_kernel_migration.py \
  --hardware-report reports/hardware_2743.0.json \
  --source-compat-report reports/source_compat_build011.json \
  --raw-dtb /PFAD/ZUR/REFERENZ-FIRMWARE/dtb.bin \
  --stock-uimage /PFAD/ZUR/REFERENZ-FIRMWARE/uImage \
  --output /opt/samsung-atv-lab/samsung/build022-kernel-audit-with-raw-input.json
```

Es wird **kein** TV über Netzwerk oder USB angesprochen. Das Stock-`uImage`
wird nicht gestartet. Auch korrekt gehashte Referenzartefakte beweisen
nicht, dass der konkrete 50-Zoll-TV dasselbe RAM- und Boardprofil nutzt.

## Warum wir nicht blind auf Linux 6.x springen

| Prüfpunkt | Build-022-Stand |
| --- | --- |
| ARMv8-fähige CPUs in Referenz-DTBs | **Deklariert** (4 × Cortex-A57) |
| Echte Q60T-CPU- und RAM-Variante | **Unverifiziert** |
| ARM64-Kernel-Entry durch Samsungs Bootloader | **Unverifiziert** |
| Genauer Quellpatchstand der Firmware 2743.0 | **Unverifiziert** |
| Moderne DRM/HDMI/Panel-/Mali-Treiber | **Nicht portiert** |
| Android Gralloc/Composer, Codec, Audio, Fernbedienung | **Nicht validiert** |
| Reversibler Testboot und getestetes Recovery | **Nicht nachgewiesen** |

Google nennt beispielsweise `android14-6.1`, `android15-6.6` und
`android16-6.12`. **Diese AOSP-GKI-Zweige gelten für ARM64** und sind
hier ausschließlich technische Vergleichsziele, **keine** bereits für
Samsung Nike-L ausgewählten oder portierten Kernel.

## Empfohlene nächste Aufgaben

1. Die **exakte** SoC-/RAM-Variante des GQ50Q60TGUXZG unabhängig
   bestätigen, idealerweise per überprüfbaren, rein lesenden Daten.
2. Bootspezifische Unterschiede ARM32 ↔ AArch64 und Secure Boot
   ausschließlich offline aufzeichnen; kein TV-Experiment.
3. Die Samsung-Treiber nach Herkunft und Linux-6.x-Portierungsaufwand
   aufteilen: CPU/Clocks, eMMC/Regulatoren, DRM/HDMI/Panel, Mali,
   MFC/Audio, IR/CEC.
4. Separat einen **LineageOS-Android-TV-Userspace** unter einer passenden
   virtuellen modernen Kernel-Umgebung vorbereiten. QEMU-Erfolge sind
   keine Samsung-Hardwaretests.
5. Einen echten TV-Test nur dann planen, wenn ein **nichtpersistenter
   Bootweg**, verifizierbare Sicherungen und ein praktisch geübter
   Wiederherstellungsweg vorliegen.

## Tests und Primärquellen

```bash
python3 -m unittest discover -s tests -q
```

Zehn eigenständige synthetische Build-022-Tests prüfen ARMv8-
Referenzbefunde, die weiterhin verweigerten Boot-Gates, Hash-/Profile-
Konsistenz und fehlersichere Verarbeitung von Offline-Eingaben. Der
Build-022-Analyselauf mit den beiden eingecheckten echten Referenzberichten
ergab den Status `HOST_ONLY_HARDWARE_AUDIT_BLOCKED_FOR_DEVICE_BOOT`.

- [AOSP – Android Common Kernels / Kompatibilitätsmatrix](https://source.android.com/docs/core/architecture/kernel/android-common)
- [AOSP – Kernel-Überblick, ARM64/GKI](https://source.android.com/docs/core/architecture/kernel)
- [LineageOS – Buildanleitungen](https://wiki.lineageos.org/)
- Samsung-Firmware- und Quellenbelege: `BUILD003_REPORT.md`,
  `BUILD011_REPORT.md`, `BUILD021_REPORT.md`.

**Endstatus:** kein moderner Kernel gebaut, LineageOS noch nicht gestartet,
kein TV angefasst, `safe_to_flash=false`.
