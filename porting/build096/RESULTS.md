# Build 096 – Ergebnisse

Verifizierter Lauf: [Actions-Run 43588299972](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/actions/runs/43588299972)
auf dem Debian-Self-Hosted-Runner, Commit `927b8ad`, Artefakt
`build096-qemu-and-audit` (ID 14111447227). Alle 13 Schritte grün.

## QEMU-Boot (generische virtuelle Hardware, nicht Samsung)

| Frage | Ergebnis | Nachweis |
| --- | --- | --- |
| ARM32-Kernel kompiliert | ja | `zImage` (Magic 0x016f2818), `vmlinux` ELF32 ARM, Banner `Linux version 6.6.162 (build096@qemu-virt)`, clang 19.0.1 / LLD 19.0.1 |
| QEMU startet Linux | ja | QEMU 10.0.13, `-M virt -cpu cortex-a15 -smp 2 -m 256 -nographic -nodefaults`; `Machine model: linux,dummy-virt`, `PSCIv1.1`, arch_timer 62,5 MHz, `SMP: Total of 2 processors activated`, `ttyAMA0 at MMIO 0x9000000` |
| `/init` wird ausgeführt | ja | `Run /init as init process`, danach `build096-init: kernel release 6.6.162`, `cpu ARMv7`, `dt compatible linux,dummy-virt` |
| Marker erscheint | ja | `BUILD096_ARM32_QEMU_BOOT_OK` als eigene Zeile (Serial-Zeile 83), danach `reboot: Power down`, QEMU-Exit 0, ≈0,5 s |
| Reproduzierbar | ja | Zweiter Build in anderem Verzeichnis byte-identisch |

Prüfsummen (beide Builds identisch):

    84ddba82feb8d852efd6d16e0ec8cff50ad6ec0c9add6cb5505270d2e7fe54f1  zImage
    b914fdae2410ccca92986e13b85e00ab9890ec3778afa430233a31c5c67805e0  initramfs.cpio.gz
    275e21241a93c683aae4fae34cd560ed51d4760855bc2473360934e889134950  init
    72462e4ca84fec981c093a871084d22b7dfb6b550a1acaa27451f96cc29df26f  kernel.config

Der Reproduzierbarkeitstest fand im Vorlauf
([43588125836](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/actions/runs/43588125836))
einen echten Fehler: `gen_init_cpio -t` setzt die mtime regulärer Dateien nicht.
Behoben durch Festsetzen der mtime von `/init` (`927b8ad`).

## Samsung-Audit (statisch, getrennt)

Ergebnis: 0 Vertragsverletzungen, 11 offene Befunde.

- Nike-L-ARM32-Konfiguration in diesem Lauf neu erzeugt: SHA-256
  `fcdf34f8…d5d`, **bitidentisch** zu Build 094 `kernel.config` (Build-095-Manifest).
- Beide Q60T-DTBs neu kompiliert und **bitidentisch** zu Build 094:
  1g5 `91e1d8f2…38de`, 2g `17f67e31…6e63`; Fixtures ebenfalls identisch.
- Build-094-Artefakt erneut gegen Build-095-Manifest verifiziert.
- CPU/RAM: 4 × `arm,cortex-a57`, PSCI-Enable; RAM 4 Bänke/1118,25 MiB (1,5G)
  bzw. 3 Bänke/1460,5 MiB (2G) ab 0x40000000.
- PSCI 0.2 über SMC; GIC-400 bei 0x431000/0x432000; Timer
  `arm,armv8-timer`/`arm,armv7-timer`, 24 MHz.
- UART `serial@190a00` (`samsung,sdp-uart2`) aktiv, `serial0:115200n8`, Treiber passt.
- Clock-Controller `samsung,sdp1804-clock` ← 24-MHz-`fixed-clock`.
- Display, HDMI, Mali, GPU-Power-Domain, Ethernet, MICOM, CEC, IRB/IRS, eMMC,
  USB, VBUS: alle `disabled`. Keine OPP-Tabelle, keine Thermal-Zone im Board-DT.

### Neun Module

| Modul | Quelle | Config | Build-Nachweis (Build 094) | `.ko` vorhanden | Software-Gate vor MMIO | Hardware getestet |
| --- | --- | --- | --- | --- | --- | --- |
| sdp_display.ko | ja | m | ELF32 ARM REL + `LD [M]` | nein | ja (Interlock) | nein |
| sdp_hdmi.ko | ja | m | ELF32 ARM REL + `LD [M]` | nein | nein | nein |
| panfrost.ko | ja (upstream) | m | ELF32 ARM REL + `LD [M]` | nein | – | nein |
| sdp_mac.ko | ja | m | ELF32 ARM REL + `LD [M]` | nein | nein | nein |
| sdp_micom_irb.ko | ja | m | ELF32 ARM REL + `LD [M]` | nein | nein | nein |
| sdp_micom_irs.ko | ja | m | ELF32 ARM REL + `LD [M]` | nein | nein | nein |
| sdp_nikel_cpu_clk.ko | ja (extern) | – | ELF32 ARM REL + `LD [M]` | nein | ja (-EOPNOTSUPP) | nein |
| sdp_nikel_cpufreq.ko | ja (extern) | – | ELF32 ARM REL + `LD [M]` | nein | ja (-EOPNOTSUPP) | nein |
| sdp_nikel_thermal.ko | ja (extern) | – | ELF32 ARM REL + `LD [M]` | nein | ja (-EOPNOTSUPP) | nein |

Build 094 archivierte nur ELF-Berichte und Link-Logs, keine `.ko`-Dateien;
Build 096 baut die Module bewusst nicht neu.

### Offene Befunde

1. Board-DT-Knoten `drm@5d0000` (`samsung,sdp-drm`) hat keinen passenden
   Treiber; `sdp_display.ko` bindet nur das Fixture
   `samsung,nikel-drm-hw-preparation`, und sein Interlock lehnt jeden Probe ab.
2. `sdp_hdmi`, `sdp_mac`, `sdp_micom_irb`, `sdp_micom_irs` mappen MMIO im Probe
   ohne Software-Gate; nur `status = "disabled"` verhindert das Binden.
3. UART ohne `clocks`; Baudrate wird aus dem Bootloader-Divisor abgeleitet.
4. Kein `/reserved-memory`; Secure-World-/Video-/GPU-Bereiche sind nur durch
   Lücken zwischen den Bänken impliziert.
5. Keine OPP-/Regler-/Thermal-Werte; CPUFreq/Thermal bleiben Fixture-only.

## Weiterhin fehlende Hardwarevoraussetzungen

- Kein Q60T wurde mit Linux 6.6 gestartet; Retail-Boot bleibt **blockiert**.
- Kein nachgewiesener, nicht persistenter Einstiegspunkt (KEXEC/RAM-Boot) und
  kein ARM32-Handoff-Vertrag des Samsung-Loaders.
- Kein erprobter Wiederherstellungsweg auf gleichwertiger Hardware.
- Nicht bestätigt: tatsächlicher CPU-Typ/Einsprungmodus, PSCI-Firmwareverhalten,
  GIC-/Timer-Zustand nach Loader, UART-Takt und Pinmux, reale Speicherbelegung.
- Für Display/HDMI/Mali/Ethernet/IR fehlen Taktindizes, Reset-/Power-Sequenzen
  und Interrupt-Polaritäten; keine Treiberbindung an echte Hardware.
