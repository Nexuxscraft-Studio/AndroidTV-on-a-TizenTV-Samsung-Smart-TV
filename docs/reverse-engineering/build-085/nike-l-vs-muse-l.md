# Build 085 — Nike-L vs. Muse-L ES: evidence assessment

## What is directly observed

- The firmware DTB for the investigated Q60T reports the model string `Samsung DTV based on Nike-L SoC` and includes `samsung,sdp-nikel` in its compatible list (see the repository's existing firmware inventory report).
- The same DTB inventory includes `samsung,sdp1804-clock`.
- The inspected clock source's SDP1804 table section is explicitly commented `for Muse-L ES`.
- The source search found `sdp_nikel_clk_init` and its assignments to Nike-L clock tables commented out.

## What this does and does not prove

The Device Tree compatible string indicates which provider compatible the firmware describes. It does not prove that every table in the source file is suitable for the Q60T.

Likewise, a source comment identifying a table as Muse-L ES is meaningful scope evidence, but does not by itself establish whether the same register layout is shared by another silicon revision.

The current evidence therefore does **not** justify copying the Muse-L ES table into a new Nike-L clock driver or enabling it on the Q60T.

## Required resolution

1. Obtain the complete exact-version Nike-L clock source and its build configuration.
2. Trace the DT compatible to the actual registered `CLK_OF_DECLARE` initializer in the matching kernel.
3. Resolve all clock IDs and consumer references from the complete DTB.
4. Compare register layouts and semantics using independent Nike-L evidence.
5. Validate only in a controlled host/emulator environment until a safe hardware test method exists.

## Release status

**Unresolved / research only.** No Q60T clock initialization success is claimed.
