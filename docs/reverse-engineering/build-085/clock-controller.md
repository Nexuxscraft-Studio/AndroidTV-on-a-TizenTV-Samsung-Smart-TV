# Build 085 — Fixed-rate and fixed-divider descriptors

## Fixed-rate root

The inspected SDP1804 table declares one fixed-rate root:

| Name | Flags |
|---|---|
| `fin_pll` | `CLK_IS_ROOT` |

No numeric input frequency was established in the captured evidence.

## Fixed dividers

| Clock | Parent | Multiplier | Divider | Alias |
|---|---|---:|---:|---|
| `arm_clk` | `CPUPLL` | 1 | 1 | `arm0_clk` |
| `apb_pclk` | `COREPLL0` | 1 | 8 | `apb_pclk` |
| `ddr2_clk` | `DDRPLL2` | 1 | 2 | `ddr2_clk` |
| `ddr3_clk` | `DDRPLL3` | 1 | 2 | `ddr3_clk` |
| `emmc_clk` | `COREPLL2` | 1 | 2 | `emmc_clk` |

These are descriptors from the section marked **“for Muse-L ES”**. They must not be treated as verified Q60T/Nike-L operating frequencies or settings.

## Unresolved

- The numeric rate of `fin_pll`.
- Whether these divider relationships are valid on the Q60T.
- The exact clock IDs exposed to Device Tree consumers.
- Runtime binding and successful operation on the target.
