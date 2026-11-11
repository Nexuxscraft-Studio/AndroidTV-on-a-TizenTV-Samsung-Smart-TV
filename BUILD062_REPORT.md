# Build 062 – LineageOS-22.2-ARM32-Baubarkeit und Treiberprüfung

**Zielgerät:** Samsung `GQ50Q60TGUXZG` (50 Zoll), Firmware `2743.0`, SoC Nike-L.
**Branch:** `claude/build062-lineageos-arm32-driver-verify` (aus Build 060/061).
**Status:** Reine Web-/Quell-Verifikation und Planungsanalyse. **Kein** TV-Zugriff,
**kein** Android-Build auf echter Hardware, **kein** Flash. Fortsetzung der in
Build 061 festgezurrten **ARM32**-Entscheidung.

Aufbauend auf Build 061 (Bootchain: EL3 = AArch32 → arm64 nicht bootbar → Ziel
ARM 32-Bit) prüft Build 062 zwei Fragen: **(A)** Lässt sich LineageOS 22.2
(Android 15) als 32-Bit-ARM-Android-TV bauen? **(B)** Wie steht es um die Treiber
gegen ARM32?

---

## Teil A – LineageOS-22.2-ARM32-Baubarkeit

### A1. 32-Bit-ARM-Android-TV in LOS 22.2 ist produktiv bewiesen

Der **Chromecast with Google TV (4K)** (LineageOS-Codename `sabrina`) läuft
offiziell **LineageOS 22.2 (Android 15)** mit:
- SoC Amlogic S905D3G, CPU Cortex-A53 **arm64**, **Android-Userspace `arm`
  (32-Bit)**, GPU **ARM Mali-G31** (Bifrost).
- Quelle: LineageOS-Wiki-Geräteseite `sabrina`.

Damit ist belegt, dass LOS 22.2 einen **32-Bit-ARM-Android-TV-Userspace inkl.
Mali-Bifrost-GPU** produktiv baut und ausliefert. Das ist stärker als jeder
Emulator-Nachweis.

### A2. Unser Unterschied zu sabrina: der Kernel ist AArch32

sabrina hat einen **arm64-Kernel** mit 32-Bit-Userspace. Wir müssen laut Build 061
sowohl Userspace **als auch Kernel** in AArch32 fahren (Firmware erzwingt EL1 =
AArch32). Zielkonfiguration daher **durchgängig 32-Bit**:
- `TARGET_ARCH := arm`, 32-Bit-Binder (AOSP-`aosp_arm_ab`-Stil), nicht die
  `aosp_arm`-Variante mit 64-Bit-Binder.
- Kernel = **Build-059-Linux-6.6.162-ARM32-Nike-L** (`CONFIG_ARM_LPAE=y`,
  `CONFIG_ARCH_MULTI_V7=y`), **nicht** der 4.1.10-Stock-Kernel.

### A3. Der Kernelwechsel löst die alten Android-Lücken (Build 012–017)

Die in Build 012–017 dokumentierten Blocker betrafen den **4.1.10-Stock-Kernel**
(Binder = ein Kontext, Protokoll 7/8, 16 fehlende UAPI-Merkmale; SMACK statt
SELinux; ION statt dma-buf-heaps). Auf dem **Linux-6.6.162-ARM32**-Kernel sind
Binder (mit binderfs, Mehrfachkontext, aktueller ABI), SELinux und dma-buf-heaps
**upstream vorhanden**. Der Kernelwechsel von 4.1.10 auf 6.6.162 beseitigt diese
Lücken strukturell; sie müssen nicht einzeln zurückportiert werden.

### A4. Korrektur zu Build 060: Emulator-Target `sdk_tv_arm` ist unsicher

Build 060 nennt `sdk_tv_arm-eng` als erstes Ziel. Aus den AOSP-Quellen:
- Ein CTS-Commit entfernt die arm7-Emulator-Targets und hält fest, dass alle
  Referenzen auf **`aosp_tv_arm`** zu entfernen seien (Bug 258197384). Die
  aktuellen ATV-Produkte sind `aosp_tv_arm64` und `aosp_tv_x86`; ein 32-Bit-ARM-
  TV-**Emulator**-Target (`aosp_tv_arm`/`sdk_atv_armv7`) ist Legacy.
- **Folgerung:** Dass LOS 22.2 noch ein `sdk_tv_arm` anbietet, ist **nicht
  bestätigt** und muss direkt am Lineage-Manifest geprüft werden (die
  Wiki-Emulatorseite stand für diesen Check nicht zur Verfügung).
- **Fallback-Pfade für den Userspace-Smoke-Test, falls `sdk_tv_arm` fehlt:**
  (1) den Geräte-Target `lineage_nikel` (TARGET_ARCH=arm) gegen QEMU-`virt`
  testen – wie Build 018–022 es mit Kernel/Init/Binder bereits taten;
  (2) ein 32-Bit-ARM-ATV-GSI (`aosp`-arm-Produkt + ATV-System) unter QEMU.

### A5. AOSP-15-Randbedingungen für reines 32-Bit (aus Build 061/Recherche)

- Reine 32-Bit-ARM-Produkte (`aosp_arm`, `aosp_arm_ab` = „AOSP on ARM32")
  existieren im Android-15-Baum; Toolchain `armv7a-linux-androideabi` vorhanden.
- 32-Bit-ARM nur **4K-Pages** (16K arm64-exklusiv) – für uns irrelevant.
- Google hat den **Default-Dev-Pfad** auf 64-Bit-Cuttlefish umgestellt; 32-Bit
  ist „gepflegt, aber abgehängt"; Prebuilts/HALs werden dünner. → baubar, aber
  unsupported-Sonderweg mit Pflege-Aufwand.

### A6. Host-Gate (Build-060-`host_preflight.py`)

Empfehlung x86_64, **≥64 GiB RAM, ≥400 GiB** frei, `git`/`git-lfs`/`repo`.
Lauf in der reinen Analyseumgebung: **NOT READY** (7,8 GiB RAM, 30 GiB frei,
`repo` fehlt). Der echte Build muss auf dem großen x86_64-Buildhost
(Proxmox-VM) laufen.

---

## Teil B – Treiberprüfung gegen ARM32

Grundlage: Nike-L-DTB/HAL-Matrix (Build 004/005/011/025/050) und Samsung-GPL-Quellen
(`20_DTV_NikeL.zip`). Alle SoC-Treiber stammen aus dem **4.1.10**-GPL-Baum und
müssen auf **6.6.162** vorwärtsportiert werden (große API-Drift 4.1→6.6).

### B0. Durch den 6.6-Kernel bereits gelöst (kein Port nötig)

Binder (aktuelle ABI, binderfs, Mehrfachkontext), SELinux, dma-buf-heaps,
cgroups/namespaces – upstream in 6.6.162 vorhanden.

### B1. GPU (P0) – realistischer offener Pfad vorhanden

- DT-Kennung generisch `arm,mali-midgard`; unabhängige Q60T-Forschung berichtet
  **Mali-G51 / Bifrost r11p0**. GPU-ID am echten Gerät noch zu verifizieren.
- **Panfrost (Mesa, offen) unterstützt Mali-G51** (Bifrost v7) mit **GLES 3.1 /
  GL 3.1** – aktuelle Mesa-Doku listet G31/G51/G52/G76; der G51-Support kam per
  Mesa-Commit (Jan 2022, `MODEL(0x7090,"G51","TSIx",r1p1)`).
- **Gralloc:** ARM stellt ein **Apache-lizenziertes Bifrost-Android-Gralloc-Modul**
  bereit (offen integrierbar). Alternativ ARM-Bifrost-kbase-Blob + ARM-Gralloc.
  Die Tizen-`libmali.so` ist **kein** Android-HAL.
- **Abhängigkeit:** Panfrost braucht einen **DRM/KMS-Display-Controller** (kmsro) –
  siehe B2. Ohne KMS-Display kein Panfrost-Bild.
- Quellen: `docs.mesa3d.org/drivers/panfrost.html`,
  `developer.arm.com/downloads/-/mali-drivers/android-gralloc-module`.

### B2. Display (P0) – größte Eigenleistung

- `samsung,sdp-drm` + `samsung,sdp1202-panel`. Benötigt einen **DRM/KMS-Treiber**
  auf 6.6 plus **drm_hwcomposer** (offener Android-HWC, AIDL für Android 13+).
- Build 058 hat `sdp_drm_util`/`sdp_drm_fence` als Startpunkt portiert; ein
  vollständiger KMS-Pfad (modeset, VSync, Panel-Init, Backlight/Timing via
  `samsung,tztv-tcon*`/`sdp-frc`) fehlt. Dies ist der kritische P0-Block, weil
  Panfrost (B1) daran hängt.

### B3. CPU-Clock/DVFS/Thermal (P0-nah) – Prototyp vorhanden

Build 058 liefert `sdp_nikel_cpu_clk`/`cpufreq`/`thermal` für 6.6.162-ARM32
(Prototyp, DTS disabled). Weiterführen und am Boot verifizieren.

### B4. Core-SoC (P0) – teils vorhanden, meist „disabled"

Build 059: UART-Konsole (`ttySDP0`), `ARCH_SDP`, Clocks (`clk-sdp1804`, nur
lesend), GPIO, eMMC-Node (`dw_mmc-exynos`, disabled), USB EHCI/OHCI (disabled),
Q60T-DTS 1.5G/2G. eMMC ist für ein reales Boot-Target P0 (Partitionen,
Datenzugriff).

### B5. Medien/IO (P1–P2) – nur Knoten-Ebene

Video-Decoder (`samsung,sdp-mfc` → MediaCodec/Codec2/V4L2), Audio
(`samsung,sdp-audio` → Audio-HAL), HDMI/CEC (CEC in beiden Referenz-DTBs
`disabled`), IR (`okay`), Ethernet (`samsung,sdp-mac`), USB-Host, WLAN/BT
(Chipsatz unklar). Alles noch ohne Android-HAL-Nachweis. DRM/Widevine-Streaming
ist auch bei erfolgreichem Boot nicht garantiert.

---

## Gesamtbewertung

- **LineageOS 22.2 als 32-Bit-ARM-Android-TV ist baubar** – durch sabrina
  produktiv belegt. Für unser Gerät zusätzlich **arm32-Kernel** (Build-059-6.6.162)
  statt arm64-Kernel; Userspace `TARGET_ARCH=arm` + 32-Bit-Binder.
- **Der Kernelwechsel auf 6.6.162 ist der Hebel**: er löst die Binder-/SELinux-/
  dma-buf-Lücken des 4.1.10-Stock-Kernels strukturell.
- **GPU-Risiko ist beherrschbar**: Mali-G51 ist Panfrost-fähig (GLES 3.1), offenes
  Gralloc vorhanden. Der **kritische Pfad ist der Display-KMS-Treiber** (B2), an
  dem Panfrost hängt.
- **Reihenfolge (bestätigt Build 060):** (1) 32-Bit-ARM-Android-15-Userspace im
  Emulator/QEMU beweisen (ohne Samsung-Treiber); (2) 6.6.162-ARM32-Kernel am
  Gerät (Bootchain/Signatur separater Gate aus Build 061); (3) Display-KMS +
  Panfrost + Gralloc → erstes Bild; (4) Input/Audio/Video; (5) Netzwerk/DRM.

**Offene Verifikationen:** `sdk_tv_arm` im LOS-22.2-Manifest; reale GPU-ID am
Gerät; 32-Bit-Binder-Transaktions-ABI auf 6.6.162. Die `BoardConfig.mk`-
`$(error)`-Sperre und alle Boot-Gates bleiben.

## Quellen
- LineageOS-Wiki, Gerät `sabrina` (LOS 22.2, Android:arm, Mali-G31).
- AOSP CTS-Commit zur Entfernung der arm7-TV-Emulator-Targets (Bug 258197384);
  `device/google/atv` Produkt-Makefiles (`aosp_tv_arm64`, `sdk_atv_*`).
- `docs.mesa3d.org/drivers/panfrost.html` (Bifrost G31/G51/G52/G76, GLES 3.1).
- `developer.arm.com/downloads/-/mali-drivers/android-gralloc-module` (Bifrost, Apache).
- Projektintern: `porting/HAL_MATRIX.md`, `porting/ANDROID_COMPATIBILITY.md`,
  `porting/build059/`, `porting/build058/`, `BUILD061_REPORT.md`.
