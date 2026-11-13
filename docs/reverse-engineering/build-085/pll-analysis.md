# Build 085 — SDP1804 PLL descriptor inventory

The following PLL names and AMS/K register offsets were transcribed from the inspected SDP1804 source table. The source section is explicitly labelled **“for Muse-L ES”**.

| PLL | AMS offset | K offset |
|---|---:|---:|
| COREPLL0 | `0x000` | `0x004` |
| CPUPLL | `0x01C` | `0x020` |
| PULLPLL0 | `0x038` | `0x03C` |
| PULLPLL1 | `0x054` | `0x058` |
| FRCPLL | `0x070` | `0x074` |
| COREPLL1 | `0x08C` | `0x090` |
| COREPLL2 | `0x0A8` | `0x0AC` |
| USITPLL | `0x0C4` | `0x0C8` |
| DPPLL | `0x0E0` | `0x0E4` |
| AUDPLL0 | `0x0FC` | `0x100` |
| AUDPLL1 | `0x118` | `0x11C` |
| DDRPLL2 | `0x134` | `0x138` |
| DDRPLL3 | `0x150` | `0x154` |

All entries use `fin_pll` as their declared parent in the inspected table.

## Interpretation limits

These are register offsets in the clock-controller register space, not physical addresses. The table does not provide enough evidence to calculate valid PLL frequencies: input rate, field encodings, divider/multiplier semantics, lock bits, and board-specific programming requirements must be independently verified.

**Do not program these PLLs on the Q60T based on this inventory.**
