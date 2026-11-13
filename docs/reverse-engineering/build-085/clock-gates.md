# Build 085 — Observed clock-gate and reset descriptors

The following seven descriptors were present in the inspected SDP1804 source excerpt, whose surrounding section is labelled **“for Muse-L ES”**.

| Name | Parent | Register macro | Offset | Bit |
|---|---|---|---:|---:|
| `mfd_pclk` | `COREPLL0` | `SDP1804_CLK_MASK07` | `0x894` | 28 |
| `jpeg0_clk` | `FRCPLL` | `SDP1804_CLK_MASK08` | `0x898` | 4 |
| `hen_pclk` | `FRCPLL` | `SDP1804_CLK_MASK08` | `0x898` | 8 |
| `dvde_hclk` | `FRCPLL` | `SDP1804_CLK_MASK05` | `0x88C` | 24 |
| `gzip_clk` | `apb_pclk` | `SDP1804_CLK_MASK08` | `0x898` | 16 |
| `gzip_rst` | `apb_pclk` | `SDP1804_SW_RESET16` | `0x810` | 16 |
| `sdp_spi` | `apb_pclk` | `SDP1804_SW_RESET15` | `0x80C` | 28 |

The source descriptors carry `CLK_SET_PARENT_GATE | CLK_IGNORE_UNUSED`.

## Important distinction

The names ending in `_rst` or using a `SW_RESET` register are reset descriptors, not ordinary clock-mask gates. The table above preserves the source's descriptor names and register references; it does not assert the polarity or write semantics of the bits.

## Completeness

This is the set of seven entries visible in the captured source excerpt. It should not be treated as proof that the full SoC has only seven gates or resets.
