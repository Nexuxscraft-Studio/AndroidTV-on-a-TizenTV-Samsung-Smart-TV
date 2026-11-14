# Build 096 – ARM32 QEMU Boot Validation & Samsung Hardware Audit

Basis: Build 095 (`feature/build095-safe-boot-readiness`, PR #25, zum
Zeitpunkt des Branchens offen und nicht gemergt). Zwei streng getrennte Teile:

1. **QEMU-Boot-Test** – Vanilla Linux 6.6.162 ARM32 auf der generischen
   QEMU-Maschine `virt` mit Cortex-A15. Kein Samsung-Patch, kein Samsung-DT,
   keine Samsung-MMIO-Adresse. QEMU erzeugt den virtuellen Device Tree selbst.
2. **Samsung-Audit** – statische Prüfung der echten Nike-L-Integration
   (Konfiguration, DTBs, neun Module) gegen die Nachweise aus Build 094/095.

Ein grüner QEMU-Lauf beweist, dass dieser 6.6.162-ARM32-Kernel **in Emulation**
bis in den Userspace startet. Er beweist nichts über den Samsung Q60T, dessen
Bootkette oder die Nike-L-Treiber. Retail-Boot bleibt **blockiert**.

## QEMU-Boot-Test

| Datei | Zweck |
| --- | --- |
| [qemu-virt-arm32.config](qemu-virt-arm32.config) | Minimalfragment auf `allnoconfig`: ARCH_VIRT, LPAE, PSCI, SMP (2), PL011-Konsole, Initrd (gzip), devtmpfs, proc/sysfs, ELF. Keine Module, kein Netz, kein DRM. |
| [init.c](init.c) | Statisches `/init` gegen nolibc (soft-float ARMv7). Prüft PID 1, Kernel-Release 6.6.162, ARMv7, DT `linux,dummy-virt`, gibt erst dann den Marker aus und schaltet per PSCI ab. Der Marker-String steht nicht als Literal im Binary. |
| [build-qemu-kernel.sh](build-qemu-kernel.sh) | Gepinntes Tarball (SHA-256), `allnoconfig` + Fragment, Prüfung jeder Fragmentzeile, `zImage` mit LLVM, `/init`, `initramfs.cpio.gz` (gen_init_cpio, feste Zeitstempel), Prüfsummen. |
| [qemu_boot_test.py](qemu_boot_test.py) | Startet `qemu-system-arm -M virt -cpu cortex-a15 -nographic -nodefaults -no-reboot`, Konsole `ttyAMA0` in `serial.log`, Timeout, Abbruch bei Panic, Klassifikation, `boot-report.json`. |

Lokal (Debian mit clang/lld, flex, bison, qemu-system-arm):

    bash porting/build096/build-qemu-kernel.sh /tmp/b096
    python3 porting/build096/qemu_boot_test.py run --zimage /tmp/b096/out/zImage \
        --initrd /tmp/b096/out/initramfs.cpio.gz --out /tmp/b096/report

Ergebnis-Klassen (Exit-Code): `PASS` (0), `KERNEL_PANIC` (10), `INIT_FAILURE`
(11), `BOOT_HANG` (12), `NO_SERIAL_OUTPUT` (13), `POWEROFF_HANG` (14),
`QEMU_ERROR` (15), `MARKER_INVALID` (16). `PASS` verlangt: Kernel-Banner
6.6.162, Machine-Model `linux,dummy-virt`, `Run /init as init process`, danach
`BUILD096_ARM32_QEMU_BOOT_OK` als eigene Zeile, keine Panic/Oops/Init-Fehler,
Power-down durch den Gast und QEMU-Exit 0.

## Samsung-Audit

[samsung-config-dtb.sh](samsung-config-dtb.sh) wendet den Build-059→093-Patchstapel
in derselben Reihenfolge wie Build 094 an, erzeugt die Nike-L-Konfiguration mit
denselben Schritten wie `porting/build094/build-arm.sh` und kompiliert nur die
beiden Q60T-DTBs und die zwei deaktivierten Fixtures (dtc). Kein zImage, keine
Module, kein ARM64.

[samsung_audit.py](samsung_audit.py) prüft ARM32-Konfiguration, CPU/RAM, PSCI,
GIC/Timer, UART, Clock-Controller, Display/HDMI, Mali/Panfrost, Ethernet,
IRB/IRS und CPUFreq/Thermal und vergleicht mit `porting/build095/manifest.json`
und dem gepinnten Build-094-Artefakt (14109975921). Für jedes der neun Module
werden getrennt ausgewiesen: Quelle integriert, Build-Nachweis (Build 094 ELF +
`LD [M]`), tatsächlich vorhandene `.ko`-Datei, Hardwaretest (immer „nein“).

Fehler (Exit 1) sind Vertragsverletzungen, z. B. ein aktivierter
Experimentalknoten oder Abweichung von Build 094/095. Offene Hardwarefragen sind
Befunde, keine Fehler.

## CI

[`.github/workflows/build096-arm32-qemu.yml`](../../.github/workflows/build096-arm32-qemu.yml)
läuft auf dem Debian-Self-Hosted-Runner bei Push auf
`feature/build096-arm32-qemu-validation` oder manuell und lädt
`build096-qemu-and-audit` (Serial-Log, Boot-Report, QEMU-Kommando, Kernel-Configs,
Prüfsummen, zImage, Initramfs, DTBs, Audit-JSON/-Markdown) hoch. Keine
Paketinstallation, kein Flash, kein Zugriff auf den Fernseher.

## Sicherheit

Keine Samsung-Firmware, kein Bootloader, keine Registeraktivierung, keine
DRM-Sperre verändert. Alle Experimentalknoten bleiben `disabled`; der Audit
schlägt fehl, falls sich das ändert.
