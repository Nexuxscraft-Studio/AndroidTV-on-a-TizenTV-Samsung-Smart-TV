# Build 018 – QEMU-ARMv7-Binder-Bootlabor (experimenteller Branch)

**Status: Host-Integration implementiert, echter QEMU-Boot noch nicht durchgeführt.**

Branch: `feature/build018-qemu-binder-lab`. Der Samsung-Fernseher wird nicht kontaktiert.

## Warum dieser Branch existiert

Build 016 kompilierte den experimentellen Drei-Kontext-Binder-Treiber für ein
Samsung-Nike.M-Hostprofil. Das war **kein** Boot auf `qemu-system-arm`.
Build 018 bringt ein neues, explizit auswählbares `qemu-binder-lab`-Profil und
eine getrennte QEMU-Start-/Logauswertung in die vorhandenen GitHub-Werkzeuge.
Die ursprünglichen `tizen`-, `binder-lab`- und SELinux-Testprofile bleiben
unverändert auswählbar.

## Technische Umsetzung

- `q60t_compile_probe.py --profile qemu-binder-lab` verwendet den gleichen
  verifizierten Samsung-4.1.10-Quellstand, die existierenden Quell-Patches und
  das Build-016-Binder-Labor **nur in einer neuen Schattenkopie**.
- Das zusätzliche Kconfig-Overlay deaktiviert Samsung SDP und aktiviert ARMv7
  multiplatform, `ARCH_VIRT`, PL011-Konsole, PSCI, virtio-mmio, devtmpfs und
  Initramfs-Unterstützung. Nach `make olddefconfig` wird jede erwartete
  QEMU-/Android-/Sicherheitsoption geprüft. Ein Konflikt stoppt den Build.
- `q60t_qemu_runtime.py` akzeptiert **nur** den nachweislich erfolgreichen
  Build-018-Compile-Bericht, dessen Hash-validiertes `zImage` und die
  QEMU-spezifische `.config`.
- QEMU verwendet `virt,highmem=off`, ARMv7/Cortex-A15, TCG, PL011-Seriell,
  maximal 1 GiB RAM und ausdrücklich **keine Netzwerk-, Hostdisk- oder
  Hardware-Passthrough-Geräte**. Ein Lauf ist auf 5–600 Sekunden begrenzt.
- `qemu-serial.log` und `qemu-runtime-report.json` werden exklusiv erstellt;
  vorhandene Ergebnisse werden nicht überschrieben.
- Selbst ein erkannter Linux-Kernelbanner ist nur **Bootfortschritt**:
  `binder_runtime_verified=false`, `flash_authorized=false` und
  `android_userspace_compatible=false` bleiben unverändert.

QEMU beschreibt `virt` als generische ARM-Testplattform, unter anderem mit
PL011-UART und dem 32-Bit-Cortex-A15:
https://www.qemu.org/docs/master/system/arm/virt

## Test auf einer separaten Debian-/Proxmox-VM

Voraussetzungen: Python 3.10+, `make`, `patch`, `bc`, Host-GCC,
`qemu-system-arm` und ein alter ARM32-GNU-Cross-Compiler (bevorzugt
Linaro GCC 6.2.1 aus dem bereits dokumentierten Build-013-Werkzeugbestand).
Der Standard-GCC aktueller Distributionen ist nicht für Samsung Linux 4.1.10
verifiziert und kann an Assembler-Registerchecks scheitern.

1. Einen **unmodifizierten** Quellbaum aus
   `linux-4.1.10-tizen5.5.tgz` in einem frischen Verzeichnis entpacken.
   Die bereits manuell gepatchte QEMU-Arbeitskopie ist *nicht* geeignet.
2. Im Root dieses GitHub-Repositories einen neuen Workspace wählen:

   ```bash
   python3 q60t_compile_probe.py \
     --source /pfad/zu/original-linux-4.1.10 \
     --workspace /pfad/zu/NEUEM-qemu-build018 \
     --cross-prefix /pfad/zu/linaro/bin/arm-linux-gnueabi- \
     --profile qemu-binder-lab --jobs 4 --timeout 1800
   ```

3. **Nur falls** `compile-report.json` den Status
   `HOST_KERNEL_COMPILED_NOT_BOOTABLE_VALIDATED` enthält:

   ```bash
   python3 q60t_qemu_runtime.py \
     --workspace /pfad/zu/NEUEM-qemu-build018 --dry-run

   python3 q60t_qemu_runtime.py \
     --workspace /pfad/zu/NEUEM-qemu-build018 --timeout 90
   ```

   Ohne `--initrd` ist ein späterer Init-/Rootfs-Fehler **zu erwarten**;
   zuerst interessiert die serielle Kernel-Ausgabe. Mit
   `--initrd /pfad/zu/geprüfter-arm32-initramfs` kann später ein
   eigenständiger Binder-Prozess-/IOCTL-Test ergänzt werden.

4. Die beiden Dateien `qemu-serial.log` und `qemu-runtime-report.json`
   auswerten. Die `--dry-run`-Option führt QEMU überhaupt nicht aus.

## Offene Blocker

1. QEMU-Konfigurationsauflösung/ARM32-Cross-Compile auf der Nutzer-VM
   **noch nicht bestätigt**. Vorab sind Kconfig-Abhängigkeiten des
   Samsung-Vendorbaums und der verwendete GCC zu prüfen.
2. Linux-4.1.10-`zImage` hat unter QEMU `virt` **noch keinen Bootnachweis**.
3. Ein passendes kleines ARM32-Initramfs mit echten Binder-IOCTL-Tests fehlt.
4. Keine vollständige neuere Binder-UAPI, kein Android-Userspace/LineageOS,
   keine Samsung-HAL und kein sicherer Boot-/Rollbackweg auf dem TV.

**Keine TV-Installation, keine Flash- oder Bootloaderfreigabe.**
