# Nike-L (SDP1412) – reale SoC-Peripherie-Adressen

Eigene Referenztabelle, abgeleitet aus der öffentlichen GPL-DTS `sdp1412.dtsi`
(Fakten/Hardware-Adressen, **kein** übernommener Quellcode). Diese ersetzen die
Platzhalter in den Build-059/063-Scaffolds. **Achtung:** Die GPL-Basis-DTS ist
eine generische Mehrvarianten-Vorlage; Display/GPU-Knoten fehlen dort und müssen
aus der Firmware-`dtb.bin` kommen. CPU-Angaben der GPL-DTS (a7×2) weichen vom
Serienboard (a57×4) ab.

| Block | Compatible | Basis-Adresse | IRQ | Hinweise |
|---|---|---|---|---|
| GIC | `arm,cortex-a15-gic` | `0x10fa1000`, `0x10fa2000` | – | dist+cpu; deckt DTB-Fund |
| Clock-Controller | `samsung,sdp1412-clock` | `0x10DF0000` (0x200) | – | `#clock-cells=1` |
| Chip-ID | `samsung,sdp-chipid` | `0x10080000` (0x20) | – | |
| Timer | `samsung,sdp-timer` | `0x10090400` (0x100) | 16–19 | 4 Timer |
| UART0 | `samsung,sdp-uart` | `0x10090A00` (0x40) | 65 | Konsole |
| UART1 | `samsung,sdp-uart` | `0x10090A40` (0x40) | 66 | irq-affinity 2 |
| I2C0–4 | `samsung,sdp-i2c` | `0x10090100`…`0x10090180` | 80–84 | |
| **eMMC** | `samsung,sdp-mmc` | `0x10000000` (0x1000) | **43** | 8-bit, non-removable, ddr50, hw-reset; Tuning via `0x100000A8`/`0x10000110` |
| Ethernet | `samsung,sdp-mac` | `0x10020000` (+4 Regionen) | (41) | pad `0x10030000`, phy-sel `0x10040000`, 32-bit |
| USB EHCI | `samsung,sdp-ehci` | `0x30210000`, `0x30230000` | 37, 38 | |
| USB OHCI | `samsung,sdp-ohci` | `0x30218000`, `0x30238000` | 39, 40 | |
| USB xHCI | `samsung,xhci-hcd` | `0x30100000` (0xC700) | 36 | |
| GA-DMA | `samsung,sdp-gadma` | `0x30070000` (0x80) | 42 | |
| G-DMA0 | `samsung,sdp-gdma` | `0x30081000` (0x1000) | 44 | |
| SPI/SSP | `samsung,sdp-spi` | `0x10090200` (0x20) | 73 | max 25 MHz |
| MISC/SMP | (board) | `0x00400000` | – | CPU-Powerup `+0xC`, Boot-Entry `+0x3E0` |
| Micom-GPR | (board) | `0x009C12C0` | – | Boot-Progress-SRAM `0x9c12d8` |

## Clock-Namen (aus `sdp1412-clocks.dtsi`)

`apb_pclk`, `ahb_clk`, `emmc_clk`, `dma_clk`, `rstn_i2c`, `rstn_uart` – alle unter
dem Controller `@0x10DF0000` (`samsung,sdp-clock`-Schema).

## Nicht in der GPL-Basis-DTS (→ aus Firmware-`dtb.bin`)

Display-Controller (VD, proprietär), GPU (Mali), MFC, Audio, HDMI/CEC, TMU,
die A57-CPU-Knoten und die realen RAM-/CMA-Bereiche (nikel-1.5G/2G). Für diese
bleibt die Firmware-DTB maßgeblich (Build 004/050).

## Nächste konkrete Nutzung

- eMMC-Knoten in Build 059 mit **dieser** realen Config auf `okay` bringen
  (P0 für Partitionen/Daten) – Clocks/Tuning sind jetzt bekannt.
- UART/USB/I2C-Adressen für die 6.6-ARM32-DTS verifizieren.
