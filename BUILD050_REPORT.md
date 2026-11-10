# Build 050 – Samsung Nike-L Hardware-Forensik (read-only)

**Ziel:** Samsung Q60T `GQ50Q60TGUXZG` (50 Zoll), gemeldete Firmware `2743.0`.  
**Untersuchungsbasis:** bereits extrahierte Berichte der **Samsung-55-Zoll-Referenzfirmware** `T-NKLDEUC 2743.0` und des Nike-L-OSS-Pakets `20_DTV_NikeL.zip`.  
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
| `CONFIG_ANDROID_BINDER_IPC` | `y` | Binder-Quellbasis vorhanden, **keine** Android-14-ABI-Validierung |
| `CONFIG_SECURITY_SELINUX` | `y` | SELinux-Kernelbasis, **keine** Android-Policy-Validierung |
| `CONFIG_ION` | `y` | Legacy-Allocator, **keine** moderne Gralloc/DMA-BUF-Integration |
| `CONFIG_CGROUPS` | `y` | Cgroup-Unterbau in Testkonfiguration |
| `CONFIG_SECCOMP_FILTER` | `y` | Seccomp-Unterbau in Testkonfiguration |
| `CONFIG_BPF_SYSCALL` | `n` | Kein entsprechender BPF-Syscall im Teststand |

**Nicht mit dem echten Nike-L-Firmware-Kernel verwechseln:** Eine
exakte `Nike.L`-Release-Defconfig wurde bislang nicht nachgewiesen.
Diese Kconfig-Werte sind daher **keine** Live-Aussage zum Q60T.

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
- **Nicht direkt neu gelesen:** das **743-MB-Originalarchiv** und der
  darin enthaltene vollständige Linux-Quellbaum; beide liegen in
  dieser Entwicklungsumgebung nicht vor. Bei späterer lokaler
  Bereitstellung kann `--original-oss-archive` die bekannte SHA-256
  read-only verifizieren; anschließend ist eine echte Code-/API-
  Portierungsprüfung separat notwendig.
- **Nicht überprüft:** tatsächlicher 50-Zoll-SoC, CPU-MIDR/GPU-ID,
  Bootloader-Signaturdurchsetzung, Linux-6.6-Samsung-Treiber und
  Hardware-Recovery.

Ausführung und Testvorgaben: [`porting/build050/README.md`](porting/build050/README.md).

## 6. Nächste Hardware-Nachweise – vor jedem echten Boot

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
