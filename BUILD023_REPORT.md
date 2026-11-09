# Build 023 – Linux 6.6 ARM64 QEMU-virt Kernel Lab

**Branch:** `feature/build023-arm64-linux66-qemu`  
**Testkandidat:** offizieller Linux-Longterm-Branch **6.6.162** (Release 2026-11-06).  
**Entwicklungsstand:** getrennte Host-Buildwerkzeuge, ARM64-PID1,
Initramfs-/QEMU-Runner, Gast-Log-Auswertung und read-only Samsung-
Treiberinventur. **Kein tatsächlicher ARM64-QEMU-Boot auf diesem Host**:
der ausführbaren Umgebung fehlen AArch64-GCC und QEMU-System-AArch64.

### Sicherheits- und Architekturgrenze

- Experimentelle Plattform ist ausschließlich **QEMU `virt`, AArch64
  Cortex-A57**, **keine Samsung-Gerätehardware**.
- Samsung Q60T (GQ50Q60TGUXZG) besitzt im vorhandenen Material einen
  Linux-4.1.10-ARM32-Port. Ob der **tatsächliche SoC** AArch64 kann, ist
  **nicht bewiesen**; ein QEMU-ARM64-Boot klärt diese Frage nicht.
- Samsung-Firmware, Build 018, 020, 021 und 022 bleiben unberührt.
- Es gibt **kein** Android-Init, Android-Sicherheitsrichtlinie,
  LineageOS-Userspace, GPU/HAL oder TV-Boot-/Flash-Freigabe.

### Dateien

| Datei | Zweck |
| --- | --- |
| `q60t_arm64_kernel.py` | Unabhängiger Linux-6.6.162-ARM64-Image-Build mit Kconfig-Prüfung |
| `q60t_arm64_probe_init.c` | Statischer ARM64-PID1; Binder-IOCTLs, SELinux-FS, memfd, DMA-BUF-Heap |
| `q60t_arm64_initramfs.py` | Deterministisches gzip/newc-Initramfs, nur ELF64 AArch64 |
| `q60t_arm64_qemu.py` | Gebundener, netzwerk- und diskfreier QEMU-`virt`-Test |
| `q60t_arm64_guest_result.py` | Serielle Gastmarker mit QEMU-Metadaten-Hash korrelieren |
| `q60t_samsung_driver_audit.py` | Lesen von Kernel-Dateipfaden, ohne Samsung-Code zu kopieren |
| `tests/test_build023.py` | Synthetische, hostseitige Tests ohne QEMU/Root/Download |

### Host-Vorbereitung

1. Quellpaket und Detached-Signatur nur von
   [kernel.org/pub/linux/kernel/v6.x](https://www.kernel.org/pub/linux/kernel/v6.x/)
   beziehen; Signatur gegen **unabhängig verifizierten Linux-Kernel-
   Signaturschlüssel** prüfen. PGP-Signatur ist für das **entpackte**
   Tar-Archiv, nicht die `.tar.xz`-Datei.
2. Originalen Linux-6.6.162-Quellbaum **getrennt** vom Samsung-4.1.10-
   Quellbaum ablegen. Kein Download erfolgt durch das Buildskript.
3. GNU-AArch64-Cross-Compiler und `qemu-system-aarch64` in einer Debian-
   Build-VM installieren; Quellcode braucht `make`, `flex`, `bison`,
   `libssl-dev`, `libelf-dev`, `bc`, `python3` sowie passende Host-Tools.
4. `q60t_arm64_kernel.py` erzeugt einen **neuen** Ausgabeordner mit
   ARM64-`defconfig`, ausgewählten Android-Kernel-Schaltern, aufgelöster
   `olddefconfig` und gebautem `arch/arm64/boot/Image`. Nach `olddefconfig`
   fehlende essenzielle Kconfig-Schalter führen ausdrücklich zum Abbruch.

### Exakter Laborablauf (auf dem Proxmox-Linux-Testgast)

```bash
# 0. Nur bei verfügbarer, vertrauenswürdig geprüfter Quelle.
# Buildskripte aus unserem Build-023-GitHub-Branch.
python3 q60t_arm64_kernel.py \
  --source /opt/samsung-atv-lab/linux-6.6.162 \
  --output /opt/samsung-atv-lab/build023-arm64-kernel \
  --cross-prefix aarch64-linux-gnu- --jobs 4

# 1. Ein eigenständiges statisches ELF64-/init mit eigener C-Probe bauen.
python3 q60t_arm64_initramfs.py \
  --output /opt/samsung-atv-lab/build023-arm64-initrd.cpio.gz

# 2. Isoliertes QEMU virt ohne Disk/Netzwerk booten; Timeout ist erwartet.
python3 q60t_arm64_qemu.py \
  --kernel /opt/samsung-atv-lab/build023-arm64-kernel/arch/arm64/boot/Image \
  --initrd /opt/samsung-atv-lab/build023-arm64-initrd.cpio.gz \
  --output-dir /opt/samsung-atv-lab \
  --run-id arm64023-001 --timeout 60

# 3. Erst jetzt den Gastbericht anhand der echten QEMU-Dateien erstellen.
python3 q60t_arm64_guest_result.py \
  --log /opt/samsung-atv-lab/qemu-serial-arm64023-001.log \
  --metadata /opt/samsung-atv-lab/qemu-meta-arm64023-001.json

# 4. Original-Samsung-Quellen ausschließlich lesend inventarisieren.
python3 q60t_samsung_driver_audit.py \
  --source /opt/samsung-atv-lab/samsung/build018-original/linux-4.1.10 \
  --output /opt/samsung-atv-lab/build023-samsung-driver-inventory.json
```

Für jedes erneute Experiment eine **neue Run-ID und einen neuen
Ausgabeordner** verwenden; die Skripte überschreiben keine alten Ergebnisse.

### Erwartete serielle Marker (erst nach echtem Gaststart gültig)

```text
Linux version 6.6.162 ...
Q60T_ARM64_GUEST_INIT_STARTED version=023 qemu_only=1 no_flash=1
Q60T_ARM64_UNAME machine=aarch64 release=6.6.162
Q60T_ARM64_BINDER name=binder status=pass protocol=...
Q60T_ARM64_BINDER name=hwbinder status=pass protocol=...
Q60T_ARM64_BINDER name=vndbinder status=pass protocol=...
Q60T_ARM64_SELINUX status=pass enforce=0 policy_loaded=unverified
Q60T_ARM64_MEMFD status=pass bytes=4096
Q60T_ARM64_DMA_HEAP status=pass bytes=4096
Q60T_ARM64_GUEST_PROBE_FINISHED version=023
```

Die `status=pass`-Zeilen sind **Sollwerte**, keine hier vorgetäuschten
Messungen. `selinuxfs` und der `enforce`-Wert beweisen **nicht**, dass
eine passende Android-SELinux-Policy geladen wurde. Ein Binder-IOCTL
ist nicht dasselbe wie ein Android-Service-Manager oder eine echte
Binder-Transaktion zwischen zwei Prozessen. Hierfür sind spätere Builds
erforderlich.

Eine `qemu_timeout_reached`-Meldung bedeutet nur, dass unser statischer
PID1 wie vorgesehen weiterlief und QEMU beendet wurde. Ein echter
Boot-Fortschritt wird **nur** mit passendem Kernelbanner, ARM64-`uname`,
Gastmarkern und korrektem QEMU-Log-Hash als *reported* gezählt.

### Modernisierung der Android-Kernelgrundlagen

| Alter Q60T-Kernel | ARM64-Linux-6.6-Labor |
| --- | --- |
| ARM32, Linux 4.1.10 | AArch64, Linux 6.6.162 |
| Legacy ION und Ashmem-Proben | DMA-BUF-Heap und memfd-Tests |
| Binder Version 8, ARM32-Experiment | Separate ARM64-Binder-Version-IOCTLs |
| SELinux vorhanden, Policy unbestätigt | SELinux-FS und Enforce-Wert, Policy unbestätigt |
| Proprietäre Samsung-GPU/Display-Treiber | Nur generische QEMU-virt-Hardware; kein Mali-Port |

### Tests und Primärquellen

```bash
python3 -m unittest discover -s tests -q
cc -std=gnu11 -Wall -Wextra -Werror -fsyntax-only q60t_arm64_probe_init.c
python3 q60t_release_audit.py .
```

- [Kernel 6.6.162 und Signaturdatei, kernel.org](https://www.kernel.org/pub/linux/kernel/v6.x/)
- [Linux-Kernel-Signaturen verifizieren, kernel.org](https://www.kernel.org/signature.html)
- [Longterm-Versionen und EOL, kernel.org](https://www.kernel.org/releases.html)
- [Android binderfs, Linux-Kerneldokumentation](https://docs.kernel.org/admin-guide/binderfs.html)
- [Linux-Kernel-Kbuild-Makefiles](https://docs.kernel.org/kbuild/makefiles.html)

**Release-Gate:** Host-Implementierung abgeschlossen, tatsächlicher
ARM64-Gast- und Treiberportierbarkeitstest noch ausstehend. Keinerlei
TV-Flash-Freigabe oder LineageOS-Version festgelegt.
