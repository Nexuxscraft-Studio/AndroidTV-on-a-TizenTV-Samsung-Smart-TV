# Android-Userspace Kickoff – Übergabe (Samsung Q60T / Nike-L)

Übergabedokumentation für den nächsten Entwicklungsabschnitt (**Android-15-
Userspace**). Stand: 11.11.2026. **Keine Binärdateien oder proprietären
Firmwarebestandteile** sind in diesem Repo enthalten; es werden nur eigene
Analysen, Gerüste und Fakten dokumentiert.

**Legende:** ✅ bestätigt (CI-grün / belegt) · 🟡 teilweise / Gerüst · ⛔ offen /
blockiert / hardwareabhängig.

---

## 1. Entwicklungsstand der Builds 059–067

| Build | Thema | Status |
|---|---|---|
| **059** | Linux-6.6.162-ARM32-Nike-L-Kernelbasis (+Patches, Config-Fragmente, Diag-Init) | ✅ baut (alle Profile) |
| **060** | Android-15/LOS-22.2-ARM32-Foundation, Host-Gate (`host_preflight.py`), Device-Gerüst | 🟡 Planung + Gerüst |
| **061** | Bootchain-Forensik (`seret`/`secos`/`ddr.init`/`sign.bin`) | ✅ Analyse |
| **062** | LineageOS-22.2-ARM32-Baubarkeit + Treiberprüfung | ✅ Analyse |
| **063** | Treiber-Bring-up-Framework (sdp-drm-KMS-Skelett, GPU/CPU/Core-SoC) | ✅ CI-compile-grün |
| **064** | P1/P2-Peripherie-Scaffolds + Treiber-Gesamtplan | ✅ DTS-grün |
| **065** | Auswertung der Samsung-GPL-Kernelquellen | ✅ Analyse |
| **066** | Boot-Zugang, Framebuffer-Handoff, GPL-Clock/Audio/MFC | ✅ DTS-grün |
| **067** | QEMU-ARM32-Boot-Harness | ✅ Boot bis Userspace |

**Zentrale bestätigte Erkenntnisse:**
- ✅ Ziel ist **ARM 32-Bit** (Kernel + Userspace). ⛔ **arm64 ist nicht bootbar**:
  EL3/Secure-Monitor läuft AArch32 → `SCR_EL3.RW` nicht setzbar (Build 061).
- ✅ Kernelbasis = **Linux 6.6.162 ARM32** (Build 059), nicht der 4.1.10-Stock.
  Dadurch sind Binder/SELinux/dma-buf-heaps upstream vorhanden (die 4.1.10-Lücken
  aus Builds 012–017 entfallen strukturell).
- ✅ **Display/GPU/Video-Decode sind proprietär** (Tizen-„VD"-Blob; Build 065).
  GPL liefert nur Glue (`drm_tztv_helper.c`) + Dummy-Panel (`panel-sdp.c`).
- ✅ **kexec ist im Stock-Kernel NICHT aktiv** (`# CONFIG_KEXEC is not set`) →
  kexec-aus-Stock entfällt; eigener Kernel hängt am signierten Bootweg.
- ✅ Security im Stock = **SMACK/SFD** (kein SELinux).

---

## 2. ARM32-Kernel-Kompilierung und QEMU-Boot (bestätigt)

### 2a. Kompilierung ✅
Der Build-059-Kernel (Linux 6.6.162 + Nike-L-Patches) **kompiliert sauber über
alle Architekturen und Profile**: arm64 + arm32 × tiny/full/android. Die neuen
Treiber (`sdp_uart`, `clk-sdp1804`, `gpio-sdp`) werden mit **`W=1 -Werror`**
gebaut; Pflicht-Symbole werden geprüft; Kernel-Images + Q60T-DTBs + ein
AOSP-Android-6.6-Coverage-Report werden erzeugt. Zusätzlich ist das Build-063-
`sdp-drm`-KMS-Skelett CI-compile-geprüft (W=1 -Werror, ARM32).

### 2b. QEMU-Boot ✅
Das Build-059-zImage (multi_v7 ARM32 + eingebettete `q60t-diag-init`) **bootet
unter `qemu-system-arm -M virt` bis in den Userspace**. Beleg aus dem Serial-Log:
```
Booting Linux on physical CPU 0x0
CPU: ARMv7 Processor ...
psci: PSCIv1.1 detected in firmware
smp: Brought up 1 node, 1 CPU
CPU: All CPU(s) started in SVC mode.
... q60t-diag-init ... q60t#        (interaktive Userspace-Shell erreicht)
build067: BOOT OK - reached userspace init (6.6.162 ARM32 on QEMU virt)
```
QEMU-Invocation (Build 067): `-M virt -cpu cortex-a15 -m 512 -nographic
-no-reboot -nic none -kernel zImage -append "console=ttyAMA0 earlycon panic=-1"`
(`-nic none` nötig, weil die virt-Maschine sonst ein virtio-NIC mit fehlender
`efi-virtio.rom` anlegt).

### 2c. Abgrenzung (offen) ⛔
- QEMU `virt` (`linux,dummy-virt`) ist **nicht** das Nike-L-Board; der Boot
  beweist nur den Kernel→Userspace-Handoff in Emulation.
- **Android-Userspace war NICHT dabei** — gebootet wurde nur Kernel + winzige
  Diagnose-Init (nolibc), kein Zygote/SurfaceFlinger/bionic.
- Boot auf dem realen Q60T ist unbewiesen (signierte Bootkette, Build 061).

---

## 3. Relevante GitHub-Actions-Runs und Artefakte

| Workflow | Run-ID | Ergebnis | Artefakte |
|---|---|---|---|
| `build059-nikel-kernel.yml` (Kernel-Matrix) | 42993167972 | ✅ 7/7 success | je Arch/Profil: `Image`/`zImage`, `System.map`, `config`, `sdp-nikel-q60t-1g5/2g.dtb`, `q60t-diag-init`, `android-coverage.txt`, `SHA256SUMS` |
| `build067-qemu-boot.yml` (QEMU-Boot) | 42996973454 | ✅ BOOT OK (Log) | `build067-qemu-log` (QEMU-Serial-Log) |
| `build063-driver-compile.yml` (Treiber W=1 -Werror) | — | ✅ compile-grün | `sdp_drm.o`, DTBs |
| `build064-dts-check.yml` / `build066-dts-check.yml` | — | ✅ dtc-grün | — |

Pull Requests: **#2** Build 061 · **#3** Build 062 · **#4** Build 063 · **#5**
Build 064 · **#6** Build 065 · **#7** Build 066 · **#8** Build 067.
Artefakte werden 30 Tage vorgehalten. Kernel-Pin: Linux `v6.6.162`
(gregkh/linux, Commit `5139929c698c273e07cb0635732f6a918a7b8e78`).

---

## 4. LineageOS-22.2-ARM32-Kompatibilität

- ✅ **32-Bit-ARM-Android-TV in LOS 22.2 ist produktiv belegt:** Chromecast with
  Google TV (`sabrina`) läuft LOS 22.2 (Android 15) mit **Android-Userspace
  `arm` (32-Bit)** + Mali-G31 (Bifrost). → der 32-Bit-ARM-ATV-Userspace baut und
  läuft in LOS 22.2.
- ✅ **AOSP-15 behält reine 32-Bit-ARM-Produkte** (`aosp_arm`, `aosp_arm_ab` =
  „AOSP on ARM32"). Für unser Gerät: durchgängig 32-Bit → `TARGET_ARCH=arm`
  **+ 32-Bit-Binder** (`aosp_arm_ab`-Stil), weil der Kernel AArch32 ist.
- 🟡 **Einschränkungen:** 32-Bit nur 4K-Pages; Google hat den Default-Dev-Pfad auf
  64-Bit umgestellt; Prebuilts/HALs werden dünner → unsupported-Sonderweg.
- ⛔ **Offen (Build 062):** ob LOS 22.2 noch ein Emulator-Target **`sdk_tv_arm`**
  anbietet, ist **unbestätigt** (AOSP hat `aosp_tv_arm` entfernt, CTS-Bug
  258197384) → am Lineage-22.2-Manifest prüfen. Fallback: Geräte-Target/GSI unter
  QEMU (wie Builds 018–022).
- Google-Apps: **MindTheGapps `15.0.0-arm-ATV`** (nicht die Phone-Variante), erst
  nach sauberem Open-Source-Start.

---

## 5. Noch offene Samsung-Hardwaretreiber

Muster (Build 065/066): **Kern-Infrastruktur ist GPL, TV-Media/Display/GPU
proprietär.** Alle DT-Knoten bleiben `disabled`, bis am Gerät verifiziert.

| Subsystem | Prio | Weg | Status |
|---|---|---|---|
| Core-SoC (UART/Clk/GPIO) | P0 | eigen (6.6), Build 059 | ✅ baut |
| eMMC `0x10000000` | P0 | `dw_mmc-exynos` (upstream) | 🟡 reale Config bekannt (Build 065), Node aktivieren |
| **Display** (`sdp-drm`) | **P0** | **proprietär!** → `simpledrm`-FB-Handoff (Build 066) oder RE | ⛔ offener Kernpunkt |
| GPU (Mali-G51) | P0 | **Panfrost** (upstream, GLES 3.1) + gbm_gralloc | 🟡 Config/DT/Plan (Build 063) |
| CPU-DVFS/Thermal | P0 | `cpufreq-dt` + `thermal-of` + reale PLL-Offsets (`clk-sdp.c`) | 🟡 Plan (Build 063/066) |
| Video-Decode (MFC) | P1 | proprietär (nur Upstream s5p-mfc vorhanden) | ⛔ offen |
| Audio | P1 | ASoC-Basis (I2S/S/PDIF) GPL; SRP-DSP proprietär | 🟡 Plan |
| HDMI/CEC/IR/Ethernet/USB | P1–P2 | Upstream-Subsysteme + Vendor-Glue | 🟡 DT/Plan (Build 064) |
| DRM/Widevine-Streaming | P2 | keine HW-DRM-HAL | ⛔ nicht garantiert |

**Kritischer Pfad fürs erste Bild:** `simpledrm` (FB-Handoff) **oder** RE des
VD-Display-IP → Panfrost → gbm_gralloc → `drm_hwcomposer` → SurfaceFlinger.
Reale Adressen: `porting/build065/SOC_ADDRESS_MAP.md` (Firmware-DTB bleibt für
Display/GPU maßgeblich, da GPL-Basis-DTS ≠ Serienboard, a7×2 vs a57×4).

---

## 6. Nächste Schritte zur Android-15-Userspace-Integration

**Geht NICHT auf GitHub-Runnern** (AOSP/LOS-Build braucht großen Host:
x86_64, ≥64 GiB RAM, ≥400 GiB frei; `git`/`git-lfs`/`repo`).

1. ⛔ **`sdk_tv_arm` im LOS-22.2-Manifest verifizieren** (offene Frage, §4).
2. 🟡 **Emulator-/QEMU-Userspace zuerst** (ohne Samsung-Treiber), auf dem
   Buildhost:
   ```bash
   repo init -u https://github.com/LineageOS/android.git -b lineage-22.2 \
     --git-lfs --no-clone-bundle
   repo sync
   source build/envsetup.sh
   breakfast sdk_tv_arm eng     # bzw. Fallback-Target
   mka
   # prüfen: getprop ro.product.cpu.abi (erwartet armeabi-v7a), ro.zygote, uname -m
   ```
3. 🟡 **Device-Tree** `device/samsung/nikel` auf `TARGET_ARCH=arm` + 32-Bit-Binder
   ausrichten; `$(error)`-Sperre bleibt bis Boot/HAL belegt.
4. 🟡 **Kernel einhängen:** den Build-059-6.6.162-ARM32-Kernel als Device-Kernel
   konfigurieren.
5. ⛔ **Erstes Bild** über `simpledrm`-FB-Handoff am Gerät erproben (setzt
   Bootloader-Framebuffer + UART-Zugang voraus).
6. ⛔ **Signierter Bootweg + Recovery** müssen belegt sein, bevor irgendetwas auf
   das Gerät flasht.

**Reihenfolge:** Emulator-Userspace-Nachweis → Device-Kernel-Boot (Signatur-Gate)
→ Display (simpledrm) + Panfrost + gralloc → Input/Audio → Medien/Netz.

---

## 7. Quellen-Register (kein Neu-Upload nötig)

Vollständige Fassung: Projekt-Doc `android-userspace-kickoff-und-quellen.md`.
Kurz:
- `noverhost.de/samsung-q60t-bootchain-2743.zip` (7,6 MB) und
  `noverhost.de/Samsung-Q60T-Tizen-2743-FullOS.zip` (1,14 GB) sind **per
  Browser-Range abrufbar** → Einzeldateien ziehbar, kein Upload nötig.
- `noverhost.de/20_DTV_NikeL.zip` (743 MB) → innere ZIP →
  `linux-4.1.10-tizen5.5.tgz` (134 MB, gzip, **nicht** range-adressierbar) → nur
  bei tiefem Source-Digging einmalig hochladen; wichtige Fakten sind bereits im
  Repo extrahiert (`SOC_ADDRESS_MAP.md`, Build 065/066).
- Reale SoC-Adressen, Treiber-Status und alle Analysen liegen versioniert im Repo.

---

## 8. Dauerhafte Grenzen

Grüne CI-Läufe beweisen **Compile-Barkeit, DTS-Syntax und Kernel-Boot in
Emulation** — **nicht** Funktion auf dem realen Q60T. Die `BoardConfig.mk`-
`$(error)`-Sperre und alle Boot-/Flash-Gates bleiben bestehen. Kein Flash ohne
verifizierten, reversiblen Bootweg und Recovery-Nachweis.
