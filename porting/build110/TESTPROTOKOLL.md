# BUILD110 Testprotokoll — 14.11.2026

| Prüfung | Ergebnis |
|---|---|
| BUILD109 Eingangs-SHA256 | PASS: `d5db24db1417d725b3948b908a8057db5f742b564f918e72f320660c5e95440d` |
| Zwei lokale Paketbauten und äußerer SHA256 | PASS: bytegleich; `ff436275bbbe93696b6b195bc62905d4c1161b879f040a92b56498940948da3d` |
| Verändertes `initramfs.cpio` mit gültigem ZIP-CRC | PASS: Verifier lehnt ab |
| Statischer DTB/Kconfig-Abgleich, fdtget/DTC 1.8.1 | Beide Profile: 4 Cortex-A57, PSCI/SMC und GIC-400 deklariert. 4 bzw. 3 RAM-Bänke; keine DT-Reservierungen. SDP-UART modular. MMC, USB, GPU und SDP-DRM/HDMI geprüft und deaktiviert. |
| QEMU 11.1.3, ARM32 virt, GICv2, Cortex-A15, emulierter PL011 | PASS: Linux 6.6.162, /init und Bootmarker. Kein Samsung-DTB; kein Displaytest. |
| GQ50Q60TGUXZG | NO-GO, kein Gerätezugriff und kein Hardware-Boot. |

Auszug aus der lokalen QEMU-Ausgabe:

```text
[    0.000000] OF: fdt: Machine model: linux,dummy-virt
[    1.240114] Run /init as init process
BUILD110_INITRAMFS_OK pid1
[    1.251806] BUILD110_INITRAMFS_OK pid1
PASS QEMU virt only; Samsung DTBs were not used
```
