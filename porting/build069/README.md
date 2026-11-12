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

### Lauf M1-b (Run 43053991206) – mit SELinux-LSM-Fix

`LSM: initializing lsm=capability,selinux,integrity` → first stage init läuft:
`/system` (ext4, `vda`) gemountet, **`Switching root to '/system'`**,
SELinux-Setup beginnt – und bricht ab:
`Failed to read /vendor/etc/selinux/plat_sepolicy_vers.txt` →
„Unable to open SELinux policy“. Erwartet: ein GSI hat keine Vendor-Partition
und damit keine Vendor-Hälfte der Split-Policy.

## M2 – Minimal-Gerät `qemu_arm_tv` mit Vendor-Partition

[`device/qemu_arm_tv/`](device/qemu_arm_tv) (wird von der Build-068-Pipeline
nach `device/nexuxscraft/qemu_arm_tv` im LOS-Baum kopiert,
`--target qemu_arm_tv` → `lunch lineage_qemu_arm_tv-bp1a-userdebug`):

- gleiche ATV-Systembasis wie `lineage_gsi_tv_arm`
  (`atv_generic_system`/`system_ext`/`product`, Lineage `common_full_tv`),
  plus `base_vendor.mk`, `atv_vendor.mk` (TV-Vendor-SEPolicy),
  `generic_ramdisk.mk` (first-stage init);
- Board: ARM32 `armv7-a-neon`, **eigene `vendor.img` (ext4)**, keine
  dynamischen Partitionen; virtio-Platten `vda`=system, `vdb`=vendor,
  `vdc`=userdata (`fstab.qemuarm`, auch in der Ramdisk);
- `ro.zygote=zygote32` explizit (32-Bit-Produkte bekommen keinen Default),
  `PRODUCT_SHIPPING_API_LEVEL 35`, minimales VINTF-Manifest (target-level
  202404), Build-VINTF-Prüfung für die Emulation abgeschaltet.

Das ist zugleich die Vorlage für `device/samsung/nikel` (dort später echte
Partitionen, HALs, eigener Kernel).

### M2 Gerätebuild 1 (Run 43056019061)

Kati-Abbruch nach 2 min: `lineage_qemu_arm_tv includes non-existent modules
in PRODUCT_PACKAGES: android.hardware.wifi` (aus `atv_generic_system.mk`; bei
AOSP-TV liefert das die Goldfish-Vendor-Schicht). Die Allow-List ist pro
Produkt schreibgeschützt (`enforce-product-packages-exist`), ein `+=` wirkt
nicht (Lauf 2, Run 43056830608). → leeres Phony-Paket gleichen Namens in
`device/qemu_arm_tv/Android.mk` (nur für dieses Gerät); QEMU hat kein WLAN.

### M2 Gerätebuild 3 (Run 43058291735) – erfolgreich

`lineage_qemu_arm_tv-bp1a-userdebug`: **build completed successfully (14:11)**
(Cache aus Build 068). `system.img`, **`vendor.img`** (ext4, 512 MiB, nahe am
Limit), `ramdisk.img`. Verifier **GESAMT PASS**, jetzt inkl.
**`ro.zygote=zygote32`** und `ro.vendor.product.cpu.abilist=armeabi-v7a,armeabi`.

### M2-Boot 1 (Run 43060887976)

`/system` (vda) **und `/vendor` (vdb)** gemountet, **SELinux-Policy geladen**
(Split-Policy, File-Contexts aus system/system_ext/product/vendor). Abbruch:
`SELinux: (dev vda, type ext4) has no security xattr handler` → alle Dateien
`unlabeled`, `restorecon /system/bin/init` scheitert (ro) → `InitFatalReboot`.
Ursache: `CONFIG_EXT4_FS_SECURITY` fehlt. **Fix** in
`nikel-android.config` (gilt auch für den TV-Kernel): `EXT4_FS_SECURITY`,
`EXT4_FS_POSIX_ACL`, `EROFS_FS_XATTR`/`SECURITY`, `TMPFS_XATTR`/`POSIX_ACL`.

### M2-Boot 2 (Run 43061373504, nach ~9 min abgebrochen)

Mit `EXT4_FS_SECURITY`: **`init: init second stage started!`**, Produkt-Props
(`lineage_qemu_arm_tv`, ABI `armeabi-v7a`), `init.rc`/`init.qemuarm.rc`/
`init.zygote32.rc` geparst; laufen: `ueventd`, `apexd` (33 APEX, Bootstrap-
APEX gemountet), `logd`, **`servicemanager`**, `vold`, `tombstoned`.
LineageOS-Debuggerd meldet `ABI: 'arm'`, Fingerprint
`Nexuxscraft/lineage_qemu_arm_tv/qemu_arm_tv:15/BP1A.250505.005/...`.
**Bruchstelle:** `keystore2` bricht ab („Trying to construct mandatory
security level TEE“, kein KeyMint-HAL) → `vold` wartet endlos auf
`android.security.maintenance`. **Fix:** Software-KeyMint
`android.hardware.security.keymint-service` (AOSP-Referenz, nur Emulation).

### M2-Boot 3 (Run 43063918737) – Neustart-Schleife

Mit Software-KeyMint startet `vendor.keymint-default`; zweite Stufe läuft bis
`post-fs-data`, aber **`/data` ist nicht gemountet** (alle `mkdir /data/…`:
„Read-only file system“) → `apexd` (`reboot_on_failure`) →
`reboot,apexd-failed`. Ursache: `init.qemuarm.rc` rief nur
`mount_all … --late` (mountet nur `latemount`-Einträge). **Fix:** `--early`
in `on fs`, `--late` in `on late-fs`.

### M2-Boot 4 (Run 43064493718)

Mit `mount_all --early/--late`: **`/data` gemountet/formatiert, `keystore2`
+ Software-KeyMint stabil**, `apexd` aktiviert alle APEX, `vdc cryptfs
init_user0`, `derive_classpath`, `art_boot`, `odsign` laufen. Abbruch nach
~123 s Gastzeit: `NetBpfLoad: CRITICAL FAILURE LOADING BPF PROGRAMS FROM
/apex/com.android.tethering/etc/bpf/` → `reboot,bpfloader-failed`.

**Wichtig (Quelle `packages/modules/Connectivity/bpf/loader/NetBpfLoad.cpp`,
LOS 22.2):** Android 15 lehnt **32-Bit-Kernel ≥ 6.7 immer** ab; 32-Bit-Kernel
≥ 5.16 und 32-Bit-Userspace auf ≥ 6.2 sind **nur für ARM-TV/Wear** erlaubt.
Unsere Kombination (ARM32 ATV, Kernel 6.6) liegt genau im letzten zulässigen
Fenster – ein Kernel-Sprung auf 6.12 wäre für ARM32 ausgeschlossen.

### M2-Boot 5/6 – BPF-Ursache gefunden

- `BPF_PROG_LOAD` für `offload@mainline.o:schedcls_tether_downstream6_ether`:
  Verifier ok („processed 612 insns“), Rückgabe **524 `ENOTSUPP`** (das
  „Operation not permitted“ war ein veralteter errno).
- Kernel-Log: **`*** NOT YET: opcode c3 ***`** = `BPF_STX|BPF_ATOMIC|BPF_W`.
  Der ARM32-JIT kann keine Atomics – weder in 6.6 noch in Mainline 7.4-rc2.
- 6.6.162 enthält den Stable-Backport von **86bc9c742426** („bpf: Avoid
  __bpf_prog_ret0_warn when jit fails“): `jit_needed = fp->jit_requested`
  → kein Interpreter-Fallback mehr. `NetBpfLoad` erzwingt `bpf_jit_enable=1`.
  Upstream hat die daraus folgende ARM-Regression (OpenWRT/ARMv6) mit
  **df0cb5cb50bd** („bpf: Allow fall back to interpreter for programs with
  stack size <= 512“) behoben – nicht in 6.6.y.
- **Fix:** Build-059-Patch
  `0010-bpf-restore-interpreter-fallback-when-JIT-fails.patch`
  (6.6-Äquivalent von df0cb5cb50bd: `jit_needed = false`; Kfunc/`JIT_ALWAYS_ON`
  erzwingen weiterhin JIT). Gilt auch für den TV-Kernel. `build.sh` wendet
  Patches jetzt einzeln an (bereits angewendete werden erkannt).

### M2-Boot 8 (Run 43069165445) – BPF gelöst, Zygote startet

Mit Patch 0010: **`bpfloader` exit 0**, `update_verifier` ok,
**`init: starting service 'zygote'`** (erstmals), `netd`, `audioserver`,
`vendor.cas-default`, **`surfaceflinger`** starten. Dann:
`surfaceflinger` SIGABRT (wiederholt), `audioserver` SIGSEGV →
„process with updatable components 'surfaceflinger' exited 4 times before
boot completed“ → Neustart. Ursache: das Gerät hat **keinen Grafik-HAL**
(Composer/Allocator/Mapper/GLES) und QEMU keine GPU; ebenso kein Audio-HAL.

## Stand M2 / nächster Schritt M3

| Meilenstein | Stand |
|---|---|
| Kernel 6.6.162 ARM32 → `/init` | ✅ |
| first stage, `/system`+`/vendor`, SELinux-Policy | ✅ |
| second stage, `/data`, apexd, keystore2+KeyMint(SW), vold | ✅ |
| bpfloader (Patch 0010) | ✅ |
| zygote gestartet | ✅ |
| surfaceflinger / system_server / boot_completed | ❌ Grafik fehlt |

Kernel-Fixes, die auch für den TV-Kernel gelten (Build-059-Profil
`android`): `CONFIG_LSM` mit selinux, ext4/erofs/tmpfs-Security-xattrs,
Patch 0010 (BPF-Interpreter-Fallback).

**M3 (Grafik):** QEMU `virtio-gpu` (KMS) + `drm_hwcomposer` (HWC3) +
`minigbm` (Allocator/Mapper) + Software-GLES; dazu ein Default-Audio-HAL.
Das ist dieselbe Architektur wie für den TV geplant (drm_hwcomposer + gbm,
dort mit Mesa/Panfrost statt Software-GLES).

## M3 – Grafik und Audio (11.11.2026, Boots 3–10)

Diagnose: `qemu_logcat_kmsg.sh` leitet Logcat (`*:W`) als `L> …` in den
Kernel-Log; `extract_tombstones.sh` liest Tombstones aus `userdata.img`;
`run_android_qemu.sh` stoppt QEMU 90 s nach einer Crash-Schleife oder
`boot_completed` selbst. Seit Boot 9 läuft QEMU mit VNC
(`-vnc 127.0.0.1:1`, Runner-Port 5901), `-serial stdio` und Monitor-Socket
`/tmp/android-qemu-monitor.sock`.

| Boot | Befund (aus Log/Tombstone) | Fix |
|---|---|---|
| 3/4 | SurfaceFlinger SIGABRT `no suitable EGLConfig found`; Ursache: `vulkan.pastel.so … not found` im `default`-Namespace → ANGLE-Init scheitert | – |
| Probe 3/3b | `ro.treble.enabled=false`: `PRODUCT_ENFORCE_VINTF_MANIFEST_OVERRIDE := false` (M2) schaltet `PRODUCT_FULL_TREBLE` ab (`build/make/core/config.mk:790`) → Legacy-Linkerconfig ohne `sphal` | Override entfernt (VINTF-Check läuft jetzt und ist grün) |
| 5 | EGL ok; RenderEngine `output buffer not gpu writeable`; minigbm `DRM_IOCTL_MODE_CREATE_DUMB failed (4, 13)` = EACCES auf dem Render-Node | Kernel-Patch **0011** (Dumb-ioctls auf Render-Nodes, entspricht ACK „ANDROID: Allow DRM_IOCTL_MODE_*_DUMB for render clients“) |
| 6 | SurfaceFlinger stabil; zygote/system_server: `Failed to create ashmem` (6.6 hat kein `CONFIG_ASHMEM`) | `sys.use_memfd=true` (libcutils nutzt dann memfd; `init.rc` setzt sonst `false`) |
| 7 | system_server läuft; audioserver SIGSEGV (kein `IModule`/`IFactory`) | Vendor-APEX `com.android.hardware.audio` (Beispiel-HALs sind `installable:false`) |
| 8 | Core-HAL registriert `IModule/default` nie: Cuttlefish-`audio_policy_configuration.xml` bindet die hier fehlende Bluetooth-Datei ein → „Invalid XML config file“ → AudioService ohne Streams → `TvInputManagerService` wirft → system_server stirbt | eigene `audio_policy_configuration.xml` ohne Bluetooth |
| 9 | Audio-HAL ok, system_server stabil, keine Neustart-Schleife. **Kein Bild:** `LocalDisplayAdapter: Can't find display mode with id -1`, `Default display is null` | Display-Diagnose `qemu_display_diag.sh` (`D> …`: DRM-State, `/sys/class/drm` Modi, `dumpsys SurfaceFlinger/display`, HWC) |
| 10 | ausstehend (Runner-Job hing in GitHub, siehe unten) | – |

Für den TV-Kernel relevant: Patch 0011 und memfd statt ashmem.
`debug.sf.nobootanimation=1` ist noch gesetzt – deshalb kein Bootlogo,
auch wenn das Display funktioniert.

CI-Hinweis: Run 43095047193 hing in GitHub (Job `offline-tests` lokal
fertig, nie als beendet gemeldet; Abbrechen/Löschen per API abgelehnt).
Die Concurrency-Gruppe heißt deshalb jetzt `build068-selfhosted-v2`.
