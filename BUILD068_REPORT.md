# Build 068 – Android-Userspace-Pipeline (LineageOS 22.2 ARM32 ATV)

**Branch:** `claude/build068-android-userspace-pipeline` (aus Build 067).
**Status:** Pipeline, Artefakt-Verifier und Doku fertig, offline getestet
(19 Tests + CI-Workflow). **Kein** Android-Build gelaufen, **kein**
Gerätezugriff, **kein** Flash.

Start des neuen Strangs „Android-Userspace“ (Kickoff 11.11.2026). Details,
Belege und Bedienung: [`porting/build068/README.md`](porting/build068/README.md).

## Ergebnisse

1. **`sdk_tv_arm` existiert in LOS 22.2** – offene Frage aus Build 062
   geschlossen. `vendor/lineage` listet `lineage_sdk_tv_arm` (→
   `sdk_atv_armv7.mk` → `aosp_tv_arm.mk`, Board `generic`: `TARGET_ARCH=arm`,
   `armeabi-v7a`, kein 2nd-Arch). `breakfast sdk_tv_arm eng` =
   `lunch lineage_sdk_tv_arm-bp1a-eng`. LineageOS führt das Produkt in seinem
   eigenen `device/google/atv`-Fork weiter.
2. **Aber: kein ARM32-Emulator-Kernel** in `device/generic/goldfish` (nur
   arm64/x86_64). Ein `emulator`-Start ist damit unbelegt/unwahrscheinlich;
   die Pipeline meldet ihn als `SKIPPED`. Der Laufzeittest wandert auf
   System-Image + Build-059-Kernel unter QEMU (Vorschlag Build 069).
3. **Korrektur Binder:** Nicht „32-Bit-Binder (`aosp_arm_ab`)“, sondern
   32-Bit-Userspace + 32-Bit-Kernel + **Binder-Protokoll 8** (64-Bit-Layout).
   Android 15 kennt nur noch 64-Bit-Binder (`TARGET_USES_64_BIT_BINDER`
   deprecated), Linux 6.6 hat kein `ANDROID_BINDER_IPC_32BIT` mehr. Passt zu den
   Messungen aus Build 012/018 – kein zusätzlicher Port nötig.
4. **Host-Gate:** ≥ 64 GiB RAM / ≥ 400 GiB frei bleibt die Vorgabe. Eine VM mit
   20 GB RAM / 60 GB Platte ist NOT READY; Platte ist das harte Limit.

## Neu

| Datei | Zweck |
|---|---|
| `porting/build068/userspace_pipeline.sh` | 9 Stufen (deps → preflight → init → sync → check-target → build → verify → emulator → handback), wiederaufnehmbar, `--dry-run`, gepinnter Manifest-Snapshot (`--pin`), 32-Bit-Guard vor `mka` |
| `porting/build068/verify_userspace_artifacts.py` | statische Prüfung von `$PRODUCT_OUT` (Android 15, armeabi-v7a, zygote32, ELF32/EM_ARM, kein lib64, leanback) |
| `porting/build068/tests/` | 11 Verifier-Tests + 8 Stufentests gegen Fake-LOS-Baum |
| `.github/workflows/build068-userspace-pipeline.yml` | bash -n, shellcheck, Tests, Dry-Run-Nullwirkung |
| `q60t_release_audit.py` | Pipeline-Skript in die Quell-Allowlist aufgenommen |

## Nächster Schritt

Auf dem Buildhost (nach Gate):
`porting/build068/userspace_pipeline.sh --install-deps` → die erzeugte
`handback-*.tar.gz` zur Prüfung zurückgeben.

**Unverändert:** `device/samsung/nikel/BoardConfig.mk`-`$(error)`-Sperre und
alle Boot-/Signatur-Gates aus Build 061/065.
