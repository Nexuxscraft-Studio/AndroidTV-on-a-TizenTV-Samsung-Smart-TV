# Build 069 – Android-GSI auf dem 6.6.162-ARM32-Kernel unter QEMU

**Ziel:** Das in Build 068 gebaute `lineage_gsi_tv_arm` (`system.img`,
`ramdisk.img`) mit dem Build-059-Kernel (Linux 6.6.162 ARM32, Profil
`android` + QEMU-virtio) unter `qemu-system-arm -M virt` starten und messen,
wie weit Android-`init` kommt. **Nur Emulation** – kein TV, keine Firmware,
keine Signaturen.

## Ablauf (`run_android_qemu.sh`, auf Runner `debian`)

1. **kernel** – Linux v6.6.162 (Commit gepinnt) + Build-059-Patches,
   `multi_v7_defconfig` + AOSP `android-base.config` (android-6.6) +
   `nikel-*.config` + [`qemu-virt.config`](qemu-virt.config); Toolchain = das
   LLVM-Prebuilt aus dem LOS-Baum (nichts zu installieren). Ohne Diag-Initramfs.
   Build 059 `build.sh` hat dafür `EXTRA_FRAGMENTS` bekommen (abwärtskompatibel).
2. **images** – `system.img` read-only (QEMU `snapshot=on`, ggf. `simg2img`),
   Dateisystem erkannt (ext4/erofs). Das GSI hat kein Geräte-fstab → eine
   **Kopie** der Ramdisk bekommt `fstab.qemuarm`
   (`/dev/block/vda /system … first_stage_mount`) via
   [`ramdisk_tool.py`](ramdisk_tool.py) (newc-cpio, gzip/lz4).
3. **boot** – `qemu-system-arm -M virt -cpu cortex-a15 -smp 4 -m 3072`,
   `androidboot.hardware=qemuarm androidboot.selinux=permissive`, Zeitgrenze.
4. **analyse** – [`boot_milestones.py`](boot_milestones.py) liest das serielle
   Log: Kernel-Start → `/init` → first stage → Switch-Root → SELinux →
   second stage → servicemanager/logd/zygote → boot_completed, plus
   Fehlerstellen mit Kontext.

Auftrag: [`runner/request.env`](runner/request.env) pushen →
Workflow `build069-android-qemu-boot.yml`.

## Erwartung (ehrlich)

Ein GSI ohne Vendor-Partition hat **keine Vendor-SELinux-Policy, keine HALs,
kein VINTF-Manifest**. Realistisch für M1: Kernel startet Android-`init`,
first-stage mountet `/system`; spätestens beim SELinux-Policy-Laden oder bei
Vendor-Diensten wird es abbrechen. Genau diese Bruchstelle zu messen ist das
Ziel – sie bestimmt die minimale Vendor-Schicht (M2), die später auch die
Vorlage für `device/samsung/nikel` ist.

## Ergebnisse

### Lauf M1-a (11.11.2026, Run 43052983486)

- Kernel 6.6.162 ARM32 `android` + QEMU-virtio gebaut in ~3 min (LLVM 19
  aus `prebuilts/clang/.../clang-r536225`); `android-base.config` 249/259
  (offen u. a. `ASHMEM` – upstream seit 5.18 entfernt, Android nutzt memfd).
- `system.img` = ext4, als `vda` erkannt; GSI-Ramdisk = gzip, 12 Einträge
  (`init`, keine `first_stage_ramdisk`), `fstab.qemuarm` ergänzt.
- **Erreicht: Kernel → `Run /init as init process`.** Android-`init`
  (first stage) bricht nach 0,82 s ab:
  `mount("selinuxfs", "/sys/fs/selinux", …) failed Invalid argument` →
  `InitFatalReboot`.
- **Ursache:** `CONFIG_LSM` aus `multi_v7_defconfig` ohne `selinux` –
  SELinux einkompiliert, aber nie initialisiert. Betrifft auch den TV-Kernel
  (Profil `android`). **Fix:** neues Fragment
  `porting/build059/kernel/configs/nikel-android.config`
  (`CONFIG_LSM=…selinux…`, `DEFAULT_SECURITY_SELINUX`), automatisch im
  Profil `android`.
