# Build 085 — Device Tree analysis

## Q60T firmware evidence

The Build 085 investigation recorded the following properties for the clock-controller node in the firmware Device Tree:

| Property | Observed value |
|---|---|
| Compatible | `samsung,sdp1804-clock` |
| Register resource | `0x00F50000` |
| Resource size | `0x3000` |
| Clock cells | `1` |

These are Device Tree declarations. They establish the advertised compatible string and resource description in the examined DTB; they do not independently prove silicon identity, clock functionality, or that every source table associated with the compatible is appropriate for this board.

## Source-code cross-check

The source search located the Nike-L initializer symbol and table assignments, but the matching `sdp_nikel_clk_init` block was commented out. The same source contains an SDP1804 table section explicitly labelled `for Muse-L ES`.

This creates an unresolved mismatch between:
- the Q60T DTB's `samsung,sdp1804-clock` compatible; and
- the source table's explicit Muse-L ES scope, with Nike-L initialization commented out.

## Required follow-up

- Inspect the complete node and its clock-provider registration in the exact source revision.
- Resolve every consumer clock phandle and numeric clock ID against the provider's published clock indices.
- Confirm whether the running kernel actually binds this provider on the target hardware.
- Compare both original firmware DTB profiles, while keeping their RAM/profile differences separate.
- Do not infer a physical clock frequency from a phandle or a register offset.
