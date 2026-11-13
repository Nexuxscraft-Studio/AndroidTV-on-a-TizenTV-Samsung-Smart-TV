# Build 085 — SDP1804 clock-controller register offsets

The source defines the following offsets relative to the clock-controller MMIO resource. The Q60T DTB resource was recorded as base `0x00F50000`, size `0x3000`.

## Software reset registers

| Register | Offset |
|---|---:|
| SW_RESET00–SW_RESET24 | `0x7D0` through `0x830`, step `0x4` |
| SW_RESET25 | `0x870` |
| SW_RESET26 | `0x874` |

## Clock mask registers

| Register | Offset |
|---|---:|
| CLK_MASK00–CLK_MASK10 | `0x878` through `0x8A0`, step `0x4` |
| CLK_MASK11 | `0x8F4` |
| CLK_MASK12 | `0x8F8` |

The gaps between the numbered register groups are preserved exactly as found in the source; do not assume a continuous register bank.

## PLL descriptor offsets

See [pll-analysis.md](pll-analysis.md) for the individual AMS/K register pairs.

## Physical addresses vs. offsets

`0x00F50000` is the DTB resource base. Values such as `0x894` are offsets inside that resource. A derived physical address would be base plus offset, but this document intentionally does not prescribe MMIO access or register writes.

## Safety

The presence of a register definition does not establish the register's bitfield semantics, access permissions, clock/reset polarity, or safe programming sequence. No write values are recommended here.
