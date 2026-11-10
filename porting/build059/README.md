# Build 059 – Nike-L-Basiskernel auf Linux 6.6.162 (arm64 + arm32)

Neuanfang mit Claude, aufbauend auf Build 058. Ziel dieses Builds ist **ein
einziger, vollständiger Kernel** für den Samsung Q60T (Nike-L-SoC), der von
unten nach oben wächst – statt einzelner Treiber-Prototypen ohne Plattform.

Stufe 1 (dieser Build): Linux 6.6.162 mit Nike-L-Device-Tree, eigenem
UART-Treiber und Konsole. Ziel beim ersten echten Start wäre eine Shell
über die serielle Schnittstelle (initramfs), sonst nichts.

## Inhalt

| Pfad | Zweck |
|---|---|
| `kernel/patches/0001-…uart…patch` | Neuer Treiber `drivers/tty/serial/sdp_uart.c` für `samsung,sdp-uart2` mit Konsole (`ttySDP0`) und `earlycon`, plus DT-Binding |
| `kernel/patches/0002-…ARCH_SDP…patch` | Plattform `ARCH_SDP` für arm64 und arm32 (nur Device Tree, CPUs über PSCI) |
| `kernel/patches/0003-…dts…patch` | `sdp-nikel.dtsi` + Q60T-Boards für die Profile `nikel-1.5G` und `nikel-2G`; die arm32-Varianten binden die arm64-Dateien ein |
| `kernel/patches/0004-clk…patch` | Neuer Treiber `drivers/clk/clk-sdp1804.c`: liest die 13 PLLs und leitet `arm_clk`, `apb_pclk`, `ddr2/3_clk`, `emmc_clk` ab – **nur lesend**, keine Gates, kein Umprogrammieren |
| `kernel/patches/0005-…clock-controller…patch` | Clock-Controller `0xF50000` + 24-MHz-`fin_pll` im Device Tree |
| `kernel/patches/0007-…USB…patch` | Drei EHCI/OHCI-Paare (Upstream `generic-ehci`/`generic-ohci`), **deaktiviert** bis VBUS-Schaltung (GPIO) portiert ist |
| `kernel/patches/0008-gpio…patch` | Neuer Treiber `drivers/gpio/gpio-sdp.c` (28 Bänke × 8 Pins, aus Samsungs `pinctrl-sdp.c`); Laden ändert keinen Pin |
| `kernel/patches/0009-…GPIO…VBUS…patch` | GPIO-Controller `0xF52000` (aktiv) und USB-VBUS-Regler an GPIO 86 (deaktiviert) |
| `kernel/patches/0006-…eMMC…patch` | eMMC-Knoten `mmc@100000` für den Upstream-Treiber `dw_mmc-exynos` (Variante exynos7), konservativ 52 MHz, **deaktiviert** |
| `initramfs/q60t-diag-init.c` | Winziges Diagnose-`init` (nur Kernel-`nolibc`, keine C-Bibliothek), wird als initramfs **in jedes Image eingebettet** |
| `kernel/configs/` | Konfigurations-Fragmente (`common`, `arm64`, `arm`) und Pflicht-Symbole |
| `kernel/build.sh` | Reproduzierbarer Build: Patches anwenden, konfigurieren, prüfen, bauen |
| `tools/fdt2dts.py` | DTB → DTS ohne `dtc` (nur Standardbibliothek) |
| `tests/` | Host-Tests (u. a. Speicherbänke gegen `porting/profiles/*.json`) |
| `../../.github/workflows/build059-nikel-kernel.yml` | CI: 6 Builds (arm64/arm × tiny/full/android) mit Artefakten |

## Was aus welcher Quelle stammt

- **Device Tree:** Werte aus dem Firmware-DTB `T-NKLDEUC 2743.0` (SHA-256
  der beiden Trees stimmen mit `porting/profiles/` überein): 4× Cortex-A57,
  PSCI 0.2 über SMC, GIC-400 (`0x431000`/`0x432000`), Architected Timer
  24 MHz, PMU (SPI 220–223), vier UARTs, Speicherbänke.
- **UART:** Registerlayout, Bitbedeutungen und Interrupt-Ablauf aus Samsungs
  `sdp_uart2.c` (GPL-Paket `20_DTV_NikeL`). Wichtige Eigenheiten:
  - zwei Interrupts pro Port, **Index 0 = TX, Index 1 = RX**
  - Interruptursachen in `UTRSTAT` werden per Schreiben einer 1 quittiert
  - „enhanced“-Ports haben 64 Byte FIFO mit anderem `UFSTAT`-Layout
  - Konsole ist `serial@190a00` (bei Samsung `ttyS0`, hier `ttySDP0`)
- **Takt:** `clk-sdp1804.c` übernimmt aus Samsungs `clk-sdp.c` die
  PLL-Offsets, die Formel `f = (fin·m + (fin·k)>>16) / (p·2^s)` und die
  festen Teiler (`apb_pclk = COREPLL0/8`, `emmc_clk = COREPLL2/2`). Die UART
  ist absichtlich **noch nicht** an `apb_pclk` gehängt: Sie rekonstruiert ihren
  Eingangstakt aus dem vom Bootloader gesetzten Teiler (`UBRDIV`, 115200 Baud).
  Beim ersten Start beide Werte im Log vergleichen (`sdp1804-clk: apb_pclk …`
  und `uartclk … derived from boot divisor`); erst wenn sie passen, UART per
  `clocks = <&clock SDP1804_APB_PCLK>` anbinden.

## Diagnose-init (eingebettet als `/init`)

Startet der Kernel, braucht er weder eMMC noch Root-Dateisystem: das
eingebettete `q60t-diag-init` hängt `/proc`, `/sys`, `/dev` und debugfs ein und
gibt auf der seriellen Konsole sofort aus:

- Kernelversion und Kommandozeile, CPUs, Speicher, `/proc/iomem`
- `/proc/interrupts` (zeigt, ob UART-TX/RX-Interrupts kommen)
- `clk_summary` (gelesene PLL-Raten, u. a. `apb_pclk`)
- Zustand der GPIO-Pins (`/sys/kernel/debug/gpio`)
- Wurzel des Device Trees und `model`
- Kernel-Log-Zeilen zu SDP, UART-Takt, PSCI, GIC, Timer, MMC

Danach gibt es eine Mini-Shell (`help`, `diag`, `cat`, `ls`, `write`, `dmesg`,
`reboot`, `poweroff`). Das Programm schreibt nie auf einen Datenträger. Ohne
eingebettetes init bauen: `DIAG_INITRAMFS=0`.

## Selbst bauen (z. B. auf dem Debian-VServer)

```bash
sudo apt-get install -y clang lld llvm flex bison bc libssl-dev libelf-dev make patch python3
git clone --depth 1 --branch v6.6.162 https://github.com/gregkh/linux.git ~/linux-6.6.162-b059
bash porting/build059/kernel/build.sh ~/linux-6.6.162-b059 arm64 tiny ~/b059-out
bash porting/build059/kernel/build.sh ~/linux-6.6.162-b059 arm   tiny ~/b059-out
```

Profil `android`: zusätzlich die offiziellen Android-15-Kernelanforderungen
(AOSP `kernel/configs`, `android-6.6/android-base.config`) einmischen –
`ANDROID_BASE_CONFIG=/pfad/android-base.config` setzen. Das Ergebnis enthält
`android-coverage.txt`: wie viele Anforderungen erfüllt sind und welche nicht.

Der Kernelbaum wird beim ersten Lauf gepatcht – dafür einen eigenen Baum
verwenden. Ergebnis je Lauf in `~/b059-out/artifacts-<arch>-<profil>/`:
`Image`/`zImage`, die zwei Q60T-DTBs (plus dekompilierte DTS),
`config`, `System.map`, `SHA256SUMS`, `BUILD_INFO.txt`.

## Korrekturen gegenüber früheren Annahmen

- `arch/arm64/configs/Nike.M-Tizen_debug_defconfig` aus Samsungs GPL-Paket
  ist **keine** arm64-Konfiguration: Kopfzeile `Linux/arm 4.1.10`,
  `CONFIG_ARM=y`, `CONFIG_CPU_V7=y`, `CONFIG_ARM_LPAE=y`. Sie liegt nur im
  falschen Ordner. Samsungs einziges echtes arm64-Material für die SDP-Familie
  sind die FPGA-Device-Trees `arch/arm64/boot/dts/sdp/sdp1600*` (SDP1600,
  Spin-Table über `0x4003E0 + 4·cpu`).
- Ob der Q60T einen AArch64-Kernel starten kann, ist damit **weiterhin offen**.
  Der Original-Kernel startet in AArch32-HYP. Ein Wechsel nach AArch64 geht
  nur, wenn die EL3-Firmware (Secure World) selbst AArch64 ist und den Wechsel
  erlaubt. Deshalb baut Build 059 **beide** Architekturen aus denselben Quellen.

## Bootweg: Stand der Fakten

| Frage | Befund (Quelle) |
|---|---|
| kexec aus dem laufenden Tizen | **nicht möglich**: `# CONFIG_KEXEC is not set` (Samsung `Nike.M-Tizen_release_defconfig`) |
| `/dev/mem` | aus: `# CONFIG_DEVMEM is not set` |
| eigene Kernelmodule | `CONFIG_MODULES=y`, aber Samsungs UEP prüft Module (`CONFIG_SECURITY_SFD_UEP_CHECK_MODULE=y`) |
| Kernel-Image-Format | U-Boot-Legacy-`uImage`, ARM, unkomprimiert, Load/Entry `0x80008000`; daneben `sign.bin` (1040 Byte) |
| Speicherbelegung | `0x80008000` liegt in **keiner** Speicherbank der Firmware-DTBs → der Bootloader schreibt `/memory` vermutlich zur Laufzeit um. Die echte Belegung zeigt erst ein laufendes System (`/proc/iomem`, das Diagnose-init gibt sie aus). |

Folge: Ein Start ohne Flashen über Standardwege gibt es nicht; die signierte
Bootkette (`sign.bin`, `seret`, `secos`) ist das eigentliche Nadelöhr. Dieser
Build bereitet alles vor, was dafür **nicht** nötig ist, damit der erste Test –
sobald ein Bootweg existiert – möglichst viel Information liefert.

## Offen / nächste Stufen

1. **Bootkette** (entscheidet arm64 vs. arm32): `secos.bin`, `seret.bin`,
   `ddr.init`, `sign.bin` analysieren – läuft EL3 in AArch64? Wie prüft der
   Bootloader `uImage` (Signatur, Architektur-Feld)? Die Dateien liegen
   bisher nur offline vor.
2. **Serielle Konsole am TV**: Anschluss und Freischaltung (Bootargs
   `rs232=0`; im Firmware-DT gibt es Bootmodi mit Taste „S“ → `init=/bin/sh`).
   Spur: Im Firmware-DT trägt der USB-Controller `ohci@4a8000` die Einträge
   `uart_sel_port = <1>` und `reg_chk_uart_sel = <0x9c0954>` – dieser USB-Port
   lässt sich offenbar auf eine UART umschalten (Service-Adapter?). Klären,
   welcher physische USB-Anschluss das ist und wie die Umschaltung ausgelöst wird.
3. **Clock-Treiber** erweitern: Gates und Software-Resets (`0x7xx`/`0x8xx`)
   als Reset-Controller, sobald die gelesenen PLL-Raten am Gerät bestätigt sind.
4. **eMMC am Gerät testen**: Samsungs `sdp_mmc.c` trägt
   `MODULE_LICENSE("Proprietary")` und wird deshalb **nicht** portiert. Laut
   seinen Registerdefinitionen ist der Controller ein Synopsys DesignWare MMC
   in Samsungs Exynos-Ausführung (`CLKSEL` 0xA8, HS400 0x180–0x188,
   `ENABLE_SHIFT` 0x110) – identisch mit `dw_mmc-exynos` „exynos7“. Der
   Knoten ist beschrieben, aber deaktiviert; erst nach einem Test mit
   Shell auf dem TV einschalten, dann HS200/HS400-Tuning ergänzen.
   Danach Pinctrl, USB (EHCI/OHCI), Ethernet.
5. Display/GPU: Fortsetzung der Arbeiten aus Build 050–058 auf dieser Basis.

## Grenzen

Nichts davon wurde auf dem Fernseher ausgeführt. Ein grüner CI-Lauf beweist
nur: Patches passen auf 6.6.162, die Konfiguration enthält alle
Pflicht-Symbole, der UART-Treiber baut mit `W=1` ohne Warnung, Image und
DTBs entstehen. Er beweist nicht, dass der Kernel auf dem Q60T startet.
