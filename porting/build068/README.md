# Build 068 – Android-Userspace-Pipeline (LineageOS 22.2, ARM32, Android TV)

**Status:** Pipeline + Verifikation fertig und offline getestet. **Noch kein**
Android-Build gelaufen (braucht den großen x86_64-Buildhost). Kein TV-Zugriff,
kein Flash, keine Firmware-/Signaturänderung.

Ziel: aus dem LineageOS-22.2-Quellbaum reproduzierbar einen **reinen
32-Bit-ARM-Android-TV-Userspace** bauen und das Ergebnis maschinell prüfen –
als Vorstufe, bevor dieser Userspace auf dem Build-059-Kernel (6.6.162 ARM32)
gestartet wird.

---

## 1. Verifikation `sdk_tv_arm` in LOS 22.2 (offene Frage aus Build 062)

**Ergebnis: Das Target existiert.** Direkt an den Quellen geprüft
(Shallow-Clones, Stand Branch `lineage-22.2`):

| Ebene | Datei | Inhalt |
|---|---|---|
| Manifest `LineageOS/android` | `default.xml` | `device/google/atv` → **LineageOS-Fork** `android_device_google_atv` (nicht AOSP) |
| `vendor/lineage` @ `87f03bd` (19.04.2026) | `build/target/product/AndroidProducts.mk` | listet `lineage_sdk_tv_arm.mk` und `lineage_gsi_tv_arm.mk` |
| | `build/target/product/lineage_sdk_tv_arm.mk` | erbt `device/google/atv/products/sdk_atv_armv7.mk` |
| | `vars/aosp_target_release` | `aosp_target_release=bp1a` |
| `device/google/atv` (LOS-Fork) @ `e54d546` (09.03.2025) | `products/sdk_atv_armv7.mk` → `aosp_tv_arm.mk` | `PRODUCT_DEVICE := generic` |
| `build/make` (LOS) | `target/board/generic/BoardConfig.mk` | `TARGET_ARCH := arm`, `armv7-a-neon`, `armeabi-v7a`, **kein** `TARGET_2ND_ARCH` |

`breakfast sdk_tv_arm eng` löst in `vendor/lineage/build/envsetup.sh` zu
**`lunch lineage_sdk_tv_arm-bp1a-eng`** auf. Die in Build 062 zitierte
AOSP-Entfernung von `aosp_tv_arm` betrifft AOSP-CTS; LineageOS hält das
ARM32-TV-Produkt in seinem eigenen `device/google/atv`-Fork.

### Zwei Einschränkungen (nicht übersehen)

1. **Kein ARM32-Emulator-Kernel.** `device/generic/goldfish` (LOS 22.2) hat
   Boards/Kernel nur für `arm64` und `x86_64` (`board/kernel/arm64.mk`,
   `x86_64.mk`; kein `arm.mk`). `lineage_sdk_tv_arm` nutzt das generische
   GSI-Board. Daraus folgt: Der Build liefert System-/Vendor-Images, aber ein
   lauffähiger `emulator`-Start ist **nicht belegt und unwahrscheinlich**. Die
   Pipeline prüft das im Baum und meldet den Emulator-Schritt dann als
   `SKIPPED` – nie als Erfolg.
   **Konsequenz:** Der Laufzeittest gehört ohnehin auf *unseren* Kernel:
   System-Image + Build-059-6.6.162-ARM32 unter `qemu-system-arm -M virt`
   (Build-067-Harness erweitern) → Vorschlag Build 069.
2. **Existenz ≠ baut.** LineageOS liefert für `lineage_sdk_tv_arm` keine
   offiziellen Builds. Ob es in 22.2 fehlerfrei durchkompiliert, zeigt erst der
   Lauf. Fallback ohne Codeänderung: `--target gsi_tv_arm`
   (`lineage_gsi_tv_arm-bp1a-userdebug`, ebenfalls ARM32-TV, reines GSI).

## 2. Korrektur: Binder-ABI ist 64-Bit-Protokoll, auch auf ARM32

Build 062 und die Kickoff-Übergabe nennen als Ziel „32-Bit-Binder
(`aosp_arm_ab`-Stil)“. **Das ist für Android 15 falsch:**

- `build/make/core/config.mk` (LOS 22.2): `TARGET_USES_64_BIT_BINDER` ist
  deprecated – *„All devices use 64-bit binder by default now.“*
- `build/make/target/product/aosp_arm.mk`: GSI für Geräte mit
  *„ARM 32 bits user space, 64 bits binder interface“*. Ein `aosp_arm_ab`
  existiert in LOS 22.2 nicht mehr.
- Linux **6.6** `drivers/android/Kconfig`: es gibt **kein**
  `ANDROID_BINDER_IPC_32BIT` mehr; ohne `BINDER_IPC_32BIT` gilt in
  `uapi/linux/android/binder.h` `binder_uintptr_t = __u64`,
  **Protokollversion 8**.

**Richtige Zielkonfiguration:** 32-Bit-Userspace (`TARGET_ARCH=arm`,
`armeabi-v7a`, `zygote32`) **+** 32-Bit-Kernel (6.6.162 ARM32) **+**
Binder-Protokoll 8 (64-Bit-Layout). Das passt zu dem, was Build 012/018 am
ARM32-Kernel bereits gemessen haben (Protokoll 8). Es ist kein zusätzlicher
Port nötig.

## 3. Host-Gate

`userspace_pipeline.sh` ruft das Build-060-Gate (`host_preflight.py`) auf:
x86_64, **≥ 64 GiB RAM, ≥ 400 GiB frei** (LineageOS-Empfehlung für 21+),
`git`/`git-lfs`/`repo`. Eine VM mit 20 GB RAM und 60 GB Platte ist
**NOT READY** – der Plattenplatz ist dabei das harte Problem, nicht nur eine
Empfehlung. RAM unter 64 GiB kann mit großem Swap/zram und kleinem `--jobs`
funktionieren, ist aber unbelegt; dafür gibt es bewusst nur den expliziten
Schalter `--allow-undersized`.

Ein vorhandener alter LOS-Baum (z. B. 22.1) kann per `--los-dir` weiterverwendet
werden: `init` setzt ihn auf `lineage-22.2` um, `repo sync` nutzt die
vorhandenen Git-Objekte.

## 4. Benutzung (auf dem Buildhost, Ubuntu 24.04)

```bash
git clone https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV.git q60t
cd q60t && git checkout claude/build068-android-userspace-pipeline

# 0) Was würde passieren? (ändert nichts)
porting/build068/userspace_pipeline.sh --dry-run

# 1) Komplett: Pakete, Gate, repo init/sync, Target-Check, Build, Prüfung, Handback
porting/build068/userspace_pipeline.sh --install-deps \
  --los-dir /opt/lineage-22.2 --work-dir ~/build068-run

# Wiederaufnahme nach Abbruch: einfach erneut starten (fertige Stufen werden
# übersprungen) oder gezielt:  --from build   /   --only verify
# Fallback-Target:             --target gsi_tv_arm
# Wenig RAM:                   --jobs 4 --allow-undersized
# Exakt reproduzieren:         --pin ~/build068-run/manifest-pinned.xml
```

| Stufe | Tut | Ergebnisdatei (`--work-dir`) |
|---|---|---|
| `deps` | fehlende Pakete melden / mit `--install-deps` installieren | – |
| `preflight` | Build-060-Gate + RAM/Swap/zram/df | `preflight.json`, `host.txt` |
| `init` | `repo init -b lineage-22.2 --git-lfs` (optional `--shallow`) | – |
| `sync` | `repo sync -c --no-tags`, 3 Versuche, **gepinnter Manifest-Snapshot** | `manifest-pinned.xml`, `logs/sync.log` |
| `check-target` | Target im *eigenen* Baum prüfen, Release-Tag, Emulator-Kernel vorhanden? | `check-target.json` |
| `build` | `breakfast`; Abbruch wenn `TARGET_ARCH≠arm` oder `TARGET_2ND_ARCH` gesetzt; `mka` | `build-vars.txt`, `logs/build.log` |
| `verify` | statische Artefaktprüfung (s. u.) | `verify.json` |
| `emulator` | nur mit `--run-emulator` **und** vorhandenem ARM32-Kernel | `emulator.txt` |
| `handback` | kleines Archiv mit allen Ergebnissen | `handback-<zeit>.tar.gz` |

**Rückgabe:** Die `handback-*.tar.gz` (wenige 100 KB) im Chat anhängen – damit
lässt sich das Ergebnis hier prüfen, ohne Images hochzuladen.

## 5. Was `verify_userspace_artifacts.py` prüft

Liest `$PRODUCT_OUT`, startet nichts:
Android 15/SDK 35 · `ro.product.cpu.abi=armeabi-v7a` · keine 64-Bit-ABI-Listen ·
`ro.zygote=zygote32` · ELF32/EM_ARM für `app_process32`, `servicemanager`,
`init`, `linker` · kein `lib64`/`app_process64`/`linker64` ·
`android.software.leanback` deklariert · welche Images entstanden sind.
Fehlende Eingaben → `MISSING`/`INCOMPLETE`, niemals `PASS`.

## 6. Tests (offline, auch in CI)

```bash
python3 -m unittest discover -s porting/build068/tests -v
```
19 Tests: Verifier mit synthetischen Artefakten; die Pipeline-Stufen gegen einen
Fake-LOS-Baum (echte LOS-22.2-Makefile-Struktur + Stub-`envsetup.sh`) inkl.
32-Bit-Guard, `mka`-Fehlerweitergabe, Emulator-SKIP und Handback.

## 7. Aussagekraft

- **Beweist (nach Lauf):** LOS 22.2 baut einen reinen ARM32-Android-TV-Userspace
  reproduzierbar (gepinnte Revisionen), statisch geprüft.
- **Beweist nicht:** Boot, Binder-Laufzeit, Grafik, irgendetwas am Q60T. Die
  `BoardConfig.mk`-`$(error)`-Sperre von `device/samsung/nikel` bleibt.

## Quellen

- LineageOS-Wiki Emulator: `sdk_tv_<arch>` arm/x86/x86_64 für LOS 21+, Host
  64 GB RAM / 400 GB – https://lineageos.github.io/lineage_wiki/emulator.html
- `LineageOS/android` (lineage-22.2) `default.xml`;
  `LineageOS/android_vendor_lineage` `build/target/product/*`, `vars/`,
  `build/envsetup.sh`; `LineageOS/android_device_google_atv` `products/`;
  `LineageOS/android_device_generic_goldfish` `board/`;
  `LineageOS/android_build` `core/config.mk`, `target/board/generic/`,
  `target/product/aosp_arm.mk`.
- Linux v6.6 `drivers/android/Kconfig`, `include/uapi/linux/android/binder.h`.
