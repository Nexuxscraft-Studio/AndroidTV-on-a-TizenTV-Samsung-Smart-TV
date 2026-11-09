# Build 018 – QEMU-ARMv7-Binder-Bootlabor (experimenteller Branch)

**Status: ARM32-Kernel und statischer ARM32-`/init` unter QEMU gestartet; drei Binder-Versions-IOCTLs erfolgreich.**

### Bestätigter Initramfs-/Binder-ABI-Test (09.11.2026)

Im QEMU-Lauf `build018-qemu-007` mit dem generierten Initramfs hat der
Gast die folgenden Meldungen ausgegeben:

```
Q60T_GUEST_INIT_STARTED host_only=1 no_flash=1
Q60T_BINDER_VERSION_IOCTL_PASS name=binder protocol=8
Q60T_BINDER_VERSION_IOCTL_PASS name=hwbinder protocol=8
Q60T_BINDER_VERSION_IOCTL_PASS name=vndbinder protocol=8
Q60T_BINDER_ABI_PROBE_FINISHED transaction_tested=0
```

Ein `Kernel panic` trat nicht auf. Der QEMU-Exitcode 124 bedeutet hier
den planmäßigen 30-Sekunden-Timeout, da `/init` nach den Tests in einer
Warteschleife bleibt. Dies ist ein **Gastnachweis des `BINDER_VERSION`-IOCTLs**,
kein kompletter Binder-Transaktionstest und kein Android-Start.

Der erste JSON-Bericht markierte den Gaststart und IOCTL-Pass fälschlich
als `false`, obwohl die Rohkonsole die Marker enthielt. Der Parser erwartete
LF-Zeilenenden, die PL011-Konsole liefert jedoch auch CRLF/CRCRLF. Eine
nachfolgende Parserkorrektur normalisiert Carriage-Returns nur im
Auswertungsbuffer; die Original-Logs und SHA-256-Hashes bleiben unverändert.

### Reproduzierter QEMU-Meilenstein (09.11.2026)

Auf der separaten Debian-13-Test-VM wurde mit Linaro GCC 6.2.1 ein
Samsung-abgeleitetes Linux-4.1.10-`zImage` gebaut. Der Lauf mit
`build018-qemu-007` zeigt eine PL011-Konsole, `ashmem: initialized`, den
Linux-4.1.10-Banner und einen späteren **erwarteten** Rootfs-Fehler:

```
VFS: Cannot open root device "(null)" or unknown-block(0,0)
Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)
```

Dieser Panic entsteht, weil der bisherige Lauf weder initramfs noch Disk
hatte; er ist **kein** Beleg für Android oder Binder-IOCTL-Funktion.

### Isolierter Test: statisches ARM32-/init

`q60t_binder_init.c` ist ein minimales, statisch gelinktes ARM32-Programm,
das im Gast `/dev` (devtmpfs), `/proc` und `/sys` bereitstellt. Es fragt
`BINDER_VERSION` an `/dev/binder`, `/dev/hwbinder` und `/dev/vndbinder`
per echtem `ioctl()` ab. Für das Kernelprofil mit
`CONFIG_ANDROID_BINDER_IPC_32BIT=n` wird Binder-Protokollversion **8**
erwartet. Der Gast gibt eindeutige, auswertbare Marker aus; er führt
**keine Binder-Transaktion** und keinen Android-Userspace aus.

`q60t_initramfs_lab.py` kompiliert ausschließlich mit dem angegebenen
ARM32-Cross-Compiler (`-static`), validiert ELF32/ARM und das Fehlen eines
ELF-Interpreters und schreibt eine reproduzierbare `newc`-`cpio.gz`-Datei.
Vorhandene Ausgabedateien werden niemals überschrieben.

Im bereits erfolgreichen `build018-qemu-007`-Workspace:

```bash
cd /opt/samsung-atv-lab/q60t-github
GIT_SSH_COMMAND='ssh -i /root/.ssh/id_ed25519_q60t -o IdentitiesOnly=yes' git pull --ff-only

python3 q60t_initramfs_lab.py \
  --cross-prefix /opt/samsung-atv-lab/toolchains/gcc-linaro-6.2.1-ti2017.01-armv5-x86_64_arm-linux-gnueabi/bin/arm-linux-gnueabi- \
  --output /opt/samsung-atv-lab/samsung/build018-qemu-007/binder-lab-initramfs.cpio.gz

python3 q60t_qemu_runtime.py \
  --workspace /opt/samsung-atv-lab/samsung/build018-qemu-007 \
  --initrd /opt/samsung-atv-lab/samsung/build018-qemu-007/binder-lab-initramfs.cpio.gz \
  --run-id binder-001 --timeout 30

grep -E 'Q60T_GUEST_|Q60T_BINDER_|Kernel panic|Run /init' \
  /opt/samsung-atv-lab/samsung/build018-qemu-007/qemu-serial-binder-001.log
```

`--run-id` erzeugt beispielsweise `qemu-serial-binder-001.log` und
`qemu-runtime-report-binder-001.json`. Die Dateien des ersten QEMU-Tests
bleiben erhalten. Jede Run-ID muss neu sein. Auch ein erfolgreiches
`BINDER_VERSION`-IOCTL ist nur ein **begrenzter Gast-ABI-Nachweis**:
`binder_runtime_verified=false`, `binder_transactions_executed=false`,
`android_userspace_compatible=false` und `safe_to_flash=false`.

Der statische ARM32-Build und der QEMU-Lauf sind auf der Nutzer-VM
erfolgreich ausgeführt worden. GitHub Actions prüft weiterhin nur synthetische
ELF-/Initramfs- und Log-Parser-Fälle, keinen virtuellen ARM-Boot.

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
- Für QEMU deaktiviert das Overlay ausdrücklich `POWER_SAVING_MODE`,
  `ALWAYS_INSTANT_ON` und `VDFS4_FS`: Diese Samsung-Funktionen referenzieren
  physische Micom-GPIO-Adressen bzw. einen `mach/hw_decompress.h`-Header,
  den es auf der virtuellen ARM-`virt`-Plattform nicht gibt. Die beiden
  initialen Build-018-Compilerfehler wurden auf diese Abhängigkeiten
  zurückgeführt. Diese Abschaltung betrifft **nur** `qemu-binder-lab`,
  nicht die Samsung-Quellen oder das reguläre `binder-lab`-Profil.
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

   Ohne `--initrd` ist der Rootfs-Panic inzwischen beobachtet und erklärt.
   Der oben dokumentierte separate Initramfs-Binder-Test ergänzt diesen Lauf.

4. Die beiden Dateien `qemu-serial.log` und `qemu-runtime-report.json`
   auswerten. Die `--dry-run`-Option führt QEMU überhaupt nicht aus.

## Offene Blocker

1. ARM32-Cross-Compile ist mit Linaro GCC 6.2.1 auf der Nutzer-VM gelungen.
2. QEMU-Boot bis zum statischen ARM32-Userspace-`/init` ist nachgewiesen.
3. Drei `BINDER_VERSION`-IOCTLs (jeweils Protokoll 8) sind im Gast
   erfolgreich; vollständige Binder-Transaktionen bleiben offen.
4. Keine vollständige neuere Binder-UAPI, kein Android-Userspace/LineageOS,
   keine Samsung-HAL und kein sicherer Boot-/Rollbackweg auf dem TV.

**Keine TV-Installation, keine Flash- oder Bootloaderfreigabe.**
