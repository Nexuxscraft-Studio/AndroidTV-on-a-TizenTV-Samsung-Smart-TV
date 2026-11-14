# BUILD 107 — FIRST DISPLAY TEST

The gated SDP DRM coherent DMA framebuffer fill uses a 1920×1080
little-endian XRGB8888 pattern: four 480-pixel bars (red, green, blue,
white), 7680 bytes per row, 8294400 bytes per frame. The Samsung probe
interlock and disabled DT nodes are preserved. No register programming
or hardware enable is added. BUILD 106's 17 modules and checks are inherited.

QEMU virt boots the paired ARM32 kernel and checks all 19 module
load/unload results plus every byte of the shared pixel generator in
guest RAM. The CI comparison checks the reported digest against an independent
host reference. The PPM and raw file are reference images. QEMU does not
exercise Samsung KMS registration, connector routing, real DMA or scanout.
Independent builds on the same runner compare the kernel, modules and four
DTBs byte for byte; a mismatch fails CI and leaves a diff.

| Required before real display | Evidence / gap |
| --- | --- |
| Register map and resource ownership | Stock DT identifies OSDP 0x005d0000, GP 0x005d4000 and mixer 0x005d8000, each 0x4000 bytes, via its identity bus range. Cursor1 shares the mixer range. Confirm offsets, masks, field widths, latch semantics and ownership against original source. |
| Clocks and resets | Stock DT names two clocks per block. Resolve parent, rate, gating, reset and teardown sequencing from bindings and original code. |
| DMA | Stock gfx0 / gfx1 carveouts vary by memory configuration. Verify scanout bus translation, addressability, alignment, pitch units, coherency and reserved memory ownership. |
| VSync | Stock OSDP interrupt tuple is <0 0x2f 0>, with no explicit trigger flags. Resolve controller, polarity, status, mask and acknowledgement from original driver and routing. |
| Panel and mixer timing | A 1080p buffer is not a panel mode. Establish native timings, polarities, GP routing, output link, initial state and layer commit handshake. |
| Boot and recovery | Document a proven reversible RAM boot and recovery procedure for GQ50Q60TGUXZG and obtain explicit approval before any real TV test. No Tizen firmware, flash, partition, bootloader or persistent setting changes. |

The source index generated on the Debian runner supplies paths, line
numbers and source hashes for review. Search hits do not verify hardware
semantics or authorize enabling the probe.

The geometry word (0x07800438) and vendor source offset (480) now run
through the same helpers in the guest and the inert register plan.
Provenance: BUILD087 vendor archive evidence, sdp_gfx.c:464–466 and
sdp_gp.c:97–104. This is separate from verifying the runner's Linux
4.1.10 tree. The runner exports focused numbered excerpts for the GP,
Mixer, OSDP and device-tree analysis. This still does not establish
the format, address high bits, latch, IRQ or initial bring-up order.

## BUILD108 — isolate the GP-only plan

The BUILD107 artifact (run 43638868332, artifact 14131244232) contains
17 ARM32 modules, identical kernel/module/DTB checksums from two builds,
and 19 successful QEMU load/unload pairs. Its runner evidence has an empty
display-candidate list and includes legacy SDP1501 DT excerpts; those do
not establish the Nike-L programming sequence.

The inert plan now lists GP byte offsets 0x10/0x14 with 0x07800438 and
0x18 with 480, using the existing BUILD087/089 evidence. The DMA address
is software metadata. OSDP geometry and mixer active size are excluded
from the plan: framebuffer dimensions alone cannot establish routing or
panel timing. DT resource descriptions and the unconditional probe gate
are unchanged.

QEMU compiles the generated driver headers with freestanding types and
exercises the same post-validation helper as DRM atomic check. It checks
the exact GP tuples, the last aligned 32-bit span, overflow/misalignment,
and rejection of unsupported dimensions, pitch and FourCC. This does
not invoke the DRM callback or cover GEM, mode state, or commit handling.

Next evidence needed: matching Nike-L vendor display code or a
version-matched register trace that establishes register ownership,
FourCC-to-hardware encoding, address translation and stride, routing and
latching, clocks and resets, VSync acknowledgement, and output timings.
No actual scanout, MMIO access, or hardware test is introduced.
