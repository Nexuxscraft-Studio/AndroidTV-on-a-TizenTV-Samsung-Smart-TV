# Build 059 — First Display Probe

This external platform driver follows the Build 058 compile-only layout.
Its OF match table covers the Nike-L mixer and OSDP. It validates resources
before reserving and mapping one MMIO window with
`devm_platform_ioremap_resource()`. It performs no register access and
requests no clocks, resets, power transitions or IRQ handlers. An enabled
bootlogo node blocks both probes. An enabled cursor node also blocks the
mixer probe. The mapping API rejects an already reserved window.

## Firmware resource evidence

Both decompiled Samsung firmware DTs in the Build 070 artifact
`build070-kernel-43192182923.zip`, `gpl/firmware/dtb0.dts` and
`dtb1.dts`, declare the same resources. The accompanying DTB manifest
records source offsets `0x0` and `0x15000` and matches both to Build 004.
The `/soc` ranges translate these addresses 1:1.

| Node | Physical window | IRQ declaration | DTS compatible line (dtb0 / dtb1) |
| --- | --- | --- | --- |
| `samsung,sdp-osdp` | `0x5d0000–0x5d3fff` | GIC cells `<0 0x2f 0>` | 1472 / 1477 |
| `samsung,sdp-mixer` | `0x5d8000–0x5dbfff` | No IRQ property | 1485 / 1490 |

OSDP uses SPI index 47 (GIC INTID 79). The final cell is zero in both
DTs. The driver checks the raw cells and GIC compatible without creating
a Linux IRQ mapping or interpreting the trigger. The bootlogo node lists
both windows and additionally lists SPI `0x66` alongside `0x2f`.
The cursor node lists the mixer window. The evidence is from firmware DTs
and leaves the running target's DT and ownership to be checked separately.

## Offline verification

Use a Linux host with a clean Linux 6.6.162 source tree, host kernel build
dependencies (including flex, bison and libssl-dev), ARM32 cross GCC and
binutils, and device-tree-compiler (`dtc` and `fdtget`).

```bash
CROSS_COMPILE=arm-linux-gnueabihf- bash \
  porting/build059/run-arm32-compile-only.sh \
  /opt/samsung-atv-lab/linux-6.6.162 \
  /opt/samsung-atv-lab/build059-run001
```

The script checks the compiled fixture, effective ARM32/OF Kconfig
prerequisites and the ELF32 ARM object. The external Makefile needs no
in-tree Kconfig entry. A linked module would require a separately built
matching kernel and its `Module.symvers`. The DTS fixture is standalone
and disabled, and the lab check ends at the build artifacts. Keep the
firmware DT and bootlogo path intact. A hardware probe requires a proven
reversible lab boot and confirmed exclusive ownership of each window.
TV runtime and display output are unverified.

## Results

Both firmware DTS variants were inspected offline and the Bash runner was
syntax-checked. This Windows workspace had no Linux build environment
or ARM32 cross compiler. The [initial GitHub Actions run](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/actions/runs/43441465992)
failed before a runner or any build step was reported. ARM32 compilation,
effective Kconfig and compiled DT validation are pending. Run the command
above on the Debian lab to obtain those results.
