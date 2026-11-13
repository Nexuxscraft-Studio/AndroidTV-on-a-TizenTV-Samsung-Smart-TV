# Build 085 — SDP1804 Clock Controller Research

**Status:** Research only / hardware configuration not validated  
**Target under investigation:** Samsung Q60T, model GQ50Q60TGUXZG, firmware 2743.0  
**Research scope:** Samsung SDP clock-controller source and the Q60T firmware Device Tree  
**No hardware register writes or TV modifications were performed as part of this documentation.**

## Executive summary

The firmware Device Tree contains a clock-controller node compatible with `samsung,sdp1804-clock`. The inspected clock source contains an SDP1804 clock table explicitly labelled `for Muse-L ES`. That table defines one fixed-rate root, 13 PLL descriptors, five fixed dividers and seven gate/reset descriptors in the inspected excerpt.

The same source search found the Nike-L clock initializer and its table assignments commented out. This is the central limitation: the existence of an SDP1804-compatible DT node does **not** prove that the Muse-L ES clock table is correct for the Q60T/Nike-L board.

**No clock rates, gate states, reset sequences, or register programming values are asserted as validated for the Q60T.**

## Documents

- [Clock controller and Device Tree evidence](device-tree-analysis.md)
- [PLL table](pll-analysis.md)
- [Fixed-rate and fixed-divider table](clock-controller.md)
- [Observed gate/reset descriptors](clock-gates.md)
- [Nike-L vs. Muse-L ES assessment](nike-l-vs-muse-l.md)
- [Register offset map](register-map.md)

## Key findings

1. The Q60T firmware DTB was reported with `compatible = "samsung,sdp1804-clock"`.
2. The clock resource was reported as `reg = <0x00f50000 0x3000>`.
3. The inspected SDP1804 source table is explicitly marked `/* for Muse-L ES */`.
4. The SDP1804 table contains 13 PLL descriptors, a `fin_pll` root, five fixed dividers and seven gate/reset descriptors in the inspected source excerpt.
5. The Nike-L-specific initializer/table assignments found by source search were commented out.
6. Therefore the source does not currently provide a validated Nike-L clock configuration.

## Evidence boundaries

This release records source and DTB findings from the Build 085 investigation. It does not include Samsung firmware binaries, proprietary source archives, extracted modules, or copied Samsung source files. The tables below are a concise factual transcription of names and offsets observed during analysis, not a redistribution of implementation code.

The current report does not establish:
- the actual input oscillator frequency;
- PLL output frequencies or lock behavior;
- the correct Nike-L mux/divider/gate configuration;
- which gates are required for the Q60T display pipeline;
- safe runtime values for any clock/reset register;
- successful clock initialization on the television.

## Safety

Do not apply the Muse-L ES descriptors to the Q60T simply because the DTB advertises `samsung,sdp1804-clock`. Do not write to the clock/reset MMIO region based on this research note. First obtain and verify the exact Nike-L clock implementation, register semantics, parent relationships, and board-specific requirements.

## Next work

1. Recover/inspect the complete Nike-L clock source and any matching firmware evidence.
2. Resolve whether the DT clock provider actually binds to the SDP1804 initializer in the target kernel.
3. Validate clock IDs and consumer references from the complete Q60T DTB.
4. Derive register semantics from source and corroborating evidence.
5. Only then design a Linux 6.6 clock-controller port and host-side tests.
