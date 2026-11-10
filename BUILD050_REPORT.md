# Build 050 – Samsung Nike-L Hardware-Forensik (read-only)

**Ziel:** Samsung Q60T `GQ50Q60TGUXZG` (50 Zoll), gemeldete Firmware `2743.0`.  
**Untersuchungsbasis:** bereits extrahierte Berichte der **Samsung-55-Zoll-Referenzfirmware** `T-NKLDEUC 2743.0` **und jetzt direkt gelesene Original-C-Quellen** aus dem vom Projekt bereitgestellten Nike-L-OSS-Paket `20_DTV_NikeL.zip`.  
**Branch:** `feature/build050-samsung-hardware-forensics` (aus Build 025).  
**Bewertung:** `REFERENCE_IDENTIFIED_LIVE_TV_UNVERIFIED`. **Kein Zugriff auf den realen Fernseher, kein Flash und kein Geräteboot.**

## 1. Was wir über CPU und SoC belegen können

- Beide untersuchten Referenz-Device-Trees (DTB-Bundle SHA-256
  `9698e1aeca3f614bfb536dc73f8f02fc9acc8f34887070c333f47324c7b342e2`)
  nennen `samsung,sdp-nikel` und **vier** Knoten `arm,cortex-a57` / `arm,armv8`.
- Die SoC-Familie heißt somit in diesen Firmwaredaten **Samsung SDP Nike-L**.
  Ein genauer Chip-/Silizium-Identifier (Revision, Die-ID, Teilenummer)
  wurde **nicht** verifiziert. Insbesondere gilt die Auswertung **nicht**
  als Live-Beweis für die 50-Zoll-Platine.
- Cortex-A57 ist ARMv8-A, also prinzipiell AArch64-fähig. Der ausgelieferte
  **4.1.10-uImage-Kernel** hat aber U-Boot-Arch-ID **2 (ARM32)**; das
  belegt keinen ARM64-Bootweg des tatsächlichen Geräts.
- Zwei Referenzprofile: `2 GiB` (FDT-`/memory/reg` summiert **1460,5 MiB**)
  und `1,5 GiB` (**1118,25 MiB**). Die Summen sind *keine* gemessenen
  Gesamt-RAM-Größen und beweisen nicht, welches Profil der TV nutzt.

## 2. Firmware, Bootkette und Signaturprüfung

| Referenzbeleg | Nachweis | Was daraus **nicht** folgt |
| --- | --- | --- |
| `uImage` SHA-256 `6603f3f5082d6ef74471f9233ce17063658daf10e1d9440a8a9c75749a5e72b2` | U-Boot-Legacy-Header `Linux-4.1.10`, ARM32, Load/Entry `0x80008000`, Header-/Payload-CRC gültig | Keine kryptografische Signaturauthentizität und kein ARM64-Start |
| Referenz-DTB-Bootargs | `root=/dev/mmcblk0p18`, `rootfstype=vdfs`, `init=/sbin/init`, `ro` | Keine aktuelle Partitionstabelle oder Schreibfreigabe des 50-Zoll-Geräts |
| `sign.bin`, `secos.bin`, `secos_drv.bin`, `seret.bin` | Komponenten sind im Referenzpaket inventarisiert | Kein identifizierter Trust Anchor, keine bewiesene Akzeptanz fremder Images |
| Kernel-Strings `SfdUepVerifyExecutableBinary`, `SfdUepVerifyFileSignature`, `security.SMACK64EXEC` | Hinweise auf Signatur-/Ausführungskontrollen im Tizen-Stack | Keine bestätigte aktive Bootloader-Prüfkette oder wirkliche Durchsetzung |

Die wirkliche Bootkette (ROM, erste Bootloaderstufen, Vertrauensanker,
Signaturformat, Fallback, Recovery) ist **noch nicht rekonstruiert**.
Das Vorhandensein einer USB-Firmware-Aktualisierung beweist keinen
unabhängigen Wiederherstellungsweg nach einem fehlerhaften Kernelboot.

## 3. Grafik, Display und wichtige Peripherie

Aus `reports/hardware_2743.0_build004_final.json` und
`reports/source_compat_build011.json` lassen sich für **beide**
Referenz-DTBs folgende *Anhaltspunkte* korrelieren:

| Funktion | Device-Tree-Kennung | Legacy-Quellhinweis |
| --- | --- | --- |
| Mali-GPU | `arm,mali-midgard` | `sdp_gpu_nike/drivers/gpu/arm/midgard/mali_kbase_core_linux.c` |
| Display/DRM | `samsung,sdp-drm` | `sdp_drm_nike/sdp_drm_drv.c` |
| Panel | `samsung,sdp1202-panel` | Kernel: `drivers/gpu/drm/panel/panel-sdp.c` (alter Quellbericht) |
| FRC | `samsung,sdp-frc-l` | `sdp_frc_nike/nikel/sdp_frc_drv.c` |
| HDMI | `samsung,sdp-hdmi` | `sdp_hdmi_nike/sdp_hdmi_main.c` |
| Video-Decoding | `samsung,sdp-mfc` | `sdp_codec_nike/sdp_mfc.c` |
| Audio | `samsung,sdp-mc-audio` | `sdp_alsa_nike/sdp_audio_machine.c` |
| Fernbedienung | `samsung,sdp-mc-irb` | Kernel-MICOM-Treiber |
| Storage | `samsung,sdp-mmc` | Nur DTS-Deklaration im Build-011-Quellabgleich |

Ein `compatible`-String ist **kein** GPU-ID-Register und kein Build- oder
Funktionstest. Die konkrete GPU-Modellnummer (z. B. G51) und Revision
sind **unbestätigt**. Mali-GPU-3D und die proprietäre Samsung-Panel-
Ausgabe sind verschiedene Treiberaufgaben; Panfrost/Mesa ersetzt
TCON, FRC, Backlight und Hardware Composer nicht.

## 4. Welche Android-Kernel-Funktionen sind Kandidaten?

Ein früherer **Nike.M**-Konfigurationsversuch auf Linux 4.1.10
(`reports/kernel_gap_build015_bootlab.json`) ergab:

| Konfiguration | Gemeldeter Nike.M-Teststand | Bedeutung |
| --- | --- | --- |
| `CONFIG_ANDROID_BINDER_IPC` | `y` | Im **veränderten Teststand** aktiviert; **nicht** im unveränderten Nike.M-Release-Defconfig |
| `CONFIG_SECURITY_SELINUX` | `y` | Im **veränderten Teststand** aktiviert; **nicht** im unveränderten Nike.M-Release-Defconfig |
| `CONFIG_ION` | `y` | Im **veränderten Teststand** aktiviert; **nicht** im unveränderten Nike.M-Release-Defconfig |
| `CONFIG_CGROUPS` | `y` | Cgroup-Unterbau in Testkonfiguration |
| `CONFIG_SECCOMP_FILTER` | `y` | Seccomp-Unterbau in Testkonfiguration |
| `CONFIG_BPF_SYSCALL` | `n` | Kein entsprechender BPF-Syscall im Teststand |

**Wichtige Korrektur durch direkte Prüfung des Originalquellcodes:**
Das tatsächlich im Archiv liegende **unveränderte**
`arch/arm/configs/Nike.M-Tizen_release_defconfig` hat
`CONFIG_ANDROID_BINDER_IPC=n`, `CONFIG_SECURITY_SELINUX=n`,
`CONFIG_ION=n`, `CONFIG_SECURITY_SMACK=y`, `CONFIG_BPF_SYSCALL=n`,
`CONFIG_CGROUPS=y`, `CONFIG_SECCOMP_FILTER=y` und `CONFIG_ARM=y`.
Die obenstehenden `y`-Werte von Build 015 waren somit eine **aufgelöste/
modifizierte Laborkonfiguration**, keine Samsung-Werkseinstellung.
Eine exakte `Nike.L`-Release-Defconfig wurde weiterhin **nicht** nachgewiesen;
keiner dieser Werte ist eine Live-Aussage zum 50-Zoll-TV.

Für den separaten **Linux-6.6-/LineageOS-21-Laborzweig** sind zu
prüfen: Binder-/hwbinder-/vndbinder-Geräte und Protokoll, Android-
SELinux-Policy und Labels, memfd/DMA-BUF, cgroups, seccomp, eBPF,
Mount-/Storage-Pfade und Android-spezifische KMI/Device-Module.
**Linux 6.6 Mainline ist nicht automatisch ein Android-14-GKI**.
Der Build-023-QEMU-Erfolg mit `virt` belegt keine Samsung-Treiber.

## 5. Neue reproduzierbare Build-050-Prüfung

`q60t_build050_hardware_evidence.py` korreliert die sieben schon
vorhandenen Referenz-JSON-Berichte **mit Hash-/Architekturabgleich**.
Es schreibt ein neues strukturiertes Ergebnis
`reports/hardware_build050_evidence.json` und erhält durchweg
`safe_to_flash: false`.

- **Überprüft:** Zwei DTBs, vier Cortex-A57-Knoten je DTB, Referenz-
  Peripherie, ARM32-`uImage` samt CRC, Security-Artefaktinventur,
  ursprüngliche Quellreferenzen und acht gesperrte Recovery-Gates.
- **Jetzt unabhängig direkt gelesen:** Die über
  `https://noverhost.de/20_DTV_NikeL.zip` bereitgestellten 743.308.262 Byte
  wurden auf SHA-256 `3e38ad1baf54be8ed91c1c18b2c3137692c28e01ca894db9690f632a1fbd3bad`
  geprüft. Die enthaltene zweite `20_DTV_NikeL.zip` entspricht
  `ceebe20245945571ff30f9584bc62e4c7fed138f320a55d8e876f3abd05ee20a`.
  Die drei relevanten `*.tgz` wurden daraus isoliert; **13 Originaldateien**
  sind ohne Codeausführung und ohne Vendor-Installation geprüft worden.
- **Nicht überprüft:** tatsächlicher 50-Zoll-SoC, CPU-MIDR/GPU-ID,
  Bootloader-Signaturdurchsetzung, Linux-6.6-Samsung-Treiber und
  Hardware-Recovery.

Ausführung und Testvorgaben: [`porting/build050/README.md`](porting/build050/README.md).

## 6. Befunde aus dem direkt gelesenen Original-C-Quellcode

Das neue Werkzeug `q60t_build050_vendor_code_audit.py` prüft die SHA-256
aller drei Quellarchive und protokolliert pro Datei deren Inhaltshash und
die Zeilennummern wörtlicher Merkmale. Das reproduzierbare Ergebnis steht in
`reports/hardware_build050_direct_source.json`, mit dem ausdrücklichen Status
`SOURCE_CODE_CONFIRMED_TV_UNVERIFIED` und `safe_to_flash: false`.

| Originaldatei | Tatsächlicher Befund | Portierungsfolge für Linux 6.6 |
| --- | --- | --- |
| `arch/arm/mach-sdp/board-nike-dt.c` | `samsung,sdp-nikel` **und** `samsung,sdp-nikem`, `DT_MACHINE_START`, ARM32-Sekundär-CPU-Einstieg (`u32 entry`) | Alte ARM32-Machine-/SMP-Logik nicht 1:1 nach ARM64 übertragbar; kein bestätigter Samsung-AArch64-Boot |
| `sdp_drm_nike/sdp_drm_drv.c` | `drm_platform_init`, `drm_driver.load/.unload`, `drm_put_dev` | Veraltete DRM-Registrierung und Lebenszyklus-Callbacks müssen an aktuelle DRM-/Component-APIs angepasst werden |
| `sdp_gpu_nike/.../mali_kbase_core_linux.c` | Mali-Midgard-`kbase` mit DDK-/Userspace-Versionsaustausch | Treiber/HAL/Userspace-Versionen und DMA/IOMMU APIs müssen zusammenpassen; keine konkrete GPU-ID nachgewiesen |
| `.../platform/sdp/mali_kbase_platform_sdp.c` | Samsung-spezifische Clock-/Resetsteuerung und DVFS; Tabelle `MuseM_DVFS_table` | Keine fremden DVFS-Takte als Nike-L-Fakten übernehmen; echte Register, Clocks und Reset-Topologie fehlen |
| `sdp_frc_nike/nikel/sdp_frc_drv.c` | Samsung-TCON-/FRC-Abhängigkeiten | Reiner Mali/Panfrost-Port würde nicht automatisch ein TV-Bild ausgeben |
| `sdp_hdmi_nike/sdp_hdmi_main.c` | HDMI- und HDCP-Bezüge im Quellcode | Belegt **weder** funktionierenden HDMI-Android-Pfad **noch** gültige HDCP-Schlüssel |
| `arch/arm64/boot/dts/sdp/sdp1600.dtsi` | ARM64-A57-Device-Tree für **`samsung,sdp1600`** | **Nicht** mit einem Nike-L-ARM64-Device-Tree verwechseln |
| `tztv-bootmode/tztv-bootmode.c` | Tizen-Bootmodus-/Frühwarn-Status | Kein Beleg für unabhängiges Recovery oder tolerierten Fremdkernel |

Das ist eine **API- und Abhängigkeitsinventur**, **noch kein kompilierter
Linux-6.6-Hardwaretreiber**. Der Original-Quellbestand bleibt lokal; in
GitHub werden nur Hashes, Quellpfade und eigene Prüfauswertungen abgelegt.

### Zweite Phase: Quellcode ↔ offizielle Linux-6.6-Header

Die direkte Prüfung von `sdp_drm_drv.c`, `panel-sdp.c` sowie den beiden
Samsung-Makefiles gegen die echten DRM-Header des Linux-Tags `v6.6`
erfasst nun **27** migrationspflichtige Originalcode-Merkmale, davon
**17 kritisch**. Dazu gehören entfernte `drm_driver`-GEM-Felder,
geänderte `drm_panel`-Signaturen und ein veraltetes `vrefresh`-Feld.
Die beiden Makefiles besitzen einen **optionalen ARM64-Buildzweig**, aber
auch ausdrückliche ARM32-Mach-Include-Pfade. Weder eine erfolgreiche
ARM64-Kompilierung noch ein ARM64-Geräteboot sind damit nachgewiesen.

Der Original-Panelcode kennzeichnet seinen 1080p-Modus zudem ausdrücklich
als **Dummy**; Auflösung, Timing, TCON- und Power-Werte sind **nicht**
für den Q60T nutzbar. Das Script
`q60t_build050_linux66_port_gaps.py` erzeugt den read-only-Bericht
`reports/hardware_build050_linux66_port_gaps.json`; die konkrete
Migrationsreihenfolge steht unter
[`porting/build050/LINUX66_PORTING_MATRIX.md`](porting/build050/LINUX66_PORTING_MATRIX.md).

### Dritte Phase: erste echte, hardwaregesperrte Quellcodefixes

`q60t_build050_stage1_source_fixes.py` erstellt einen **Unified-Diff**
auf Basis der hashverifizierten Samsung-Quelldateien. Der erste Patch
`porting/build050/patches/0001-nike-linux66-stage1-compile-only.patch`
modernisiert ausgewählte Panel-APIs für Linux 6.6, entfernt einen
veralteten fbdev-CMA-Callback und lässt den DRM-Treiber ohne
Encoder/Connector ausdrücklich fehlschlagen. Er verhindert eine
unbeabsichtigte Samsung-Panelbindung, indem nur die testinterne Kennung
`nover,compile-only-sdp-panel` verwendet wird.

Ein **Patch-Trockenlauf gegen die beiden Originaldateien ist gelungen**.
Es wurde jedoch weder gegen Linux 6.6 kompiliert noch ein Gerät gestartet.
Die weiterhin erforderlichen DRM-/GEM-Umbauten und die Testanleitung
stehen in [`porting/build050/STAGE1_FIXES.md`](porting/build050/STAGE1_FIXES.md).

## 7. Nächste Hardware-Nachweise – vor jedem echten Boot

1. **Exaktes Board:** Über einen regulär verfügbaren, rein lesenden
   Tizen-Zugang Board-/SoC-/CPU-MIDR, GPU-ID, RAM und aktives DTB
   dokumentieren. Keine Auslesung privater Schlüssel oder geschützter
   Speicherbereiche.
2. **Bootprotokoll:** Nachweis der Kernel-Übergabeparameter, EL1/EL2,
   PSCI, GIC, Timer, MMU, Clocks/Resets und `reserved-memory` gegen
   Linux-ARM64-Bootvertrag; zunächst nur offline und an Ersatzhardware.
3. **Sicherheitskette:** Offiziell dokumentierte Start-/Recoverywege
   und beobachtetes Signaturverhalten klären, ohne Schutzmechanismen
   zu umgehen.
4. **Treiber:** Original `sdp_drm_nike`-/`sdp_gpu_nike`-C-/Headercode
   mit einem getrennten Linux-6.6-Quellbaum vergleichen; nötige
   Clock/IOMMU/DMA-/DRM-Änderungen priorisieren.
5. **Recovery:** Volatilen Boot und *unabhängige* Rückkehr zum
   unveränderten Stock-System auf passender Ersatzplatine nachweisen,
   inklusive Watchdog/Stromausfall. Bis dahin: **kein Flash**.

### Primärquellen und Projektnachweise

- Originalreports: `reports/hardware_2743.0_build004_final.json`,
  `source_compat_build011.json`, `decrypted_components.json`,
  `kernel_2743.0.json`, `graphics_build005.json`,
  `boot_safety_build005.json`, `kernel_gap_build015_bootlab.json`.
- [Linux – Booting AArch64 Linux](https://docs.kernel.org/arch/arm64/booting.html)
- [AOSP – Generic Kernel Image](https://source.android.com/docs/core/architecture/kernel/generic-kernel-image)
- [AOSP – Verified Boot](https://source.android.com/docs/security/features/verifiedboot)
- [Mesa – Panfrost](https://docs.mesa3d.org/drivers/panfrost.html)

Stand: 2026-11-10. Kein TV wurde berührt.
