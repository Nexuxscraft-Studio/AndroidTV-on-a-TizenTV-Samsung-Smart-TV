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


## Review of the original Linux 4.1.10 runner export

Source: BUILD106 Actions run 43629072878, private artifact
14127491741, including the DRM candidate list and the hashed source
manifest. The exported DRM candidates are `drm_tztv_helper.c` and
`panel/panel-sdp.c`. The export contains no matching GP, Mixer or OSDP
driver and no matching `samsung,sdp-{gp,mixer,osdp}` compatible in its
source files. This finding applies to the exported set.

| Area | Finding and remaining dependency |
| --- | --- |
| GP | BUILD087 records source and destination geometry and the existence of separate low/high A1 operations. The 4.1.10 export does not supply the format field, address encoding, memory selection or enable/latch sequence. |
| Mixer and OSDP | BUILD087 records Mixer mask and clear offsets. The 4.1.10 export does not establish layer select values, output route, update sequencing or OSDP programming. |
| Clocks and reset | The similarly named gates in `drivers/clk/clk-sdp.c:888–911` use SDP1406 mask registers. They are unsuitable evidence for SDP1804. The Q60T clock names alone do not establish SDP1804 gate mappings or reset ordering. |
| VSync | No original handler for this display path in the export. Status bit, mask polarity, clear semantics, and event ordering still need verification. |
| Panel | `drivers/gpu/drm/panel/panel-sdp.c:34–48` explicitly labels its mode dummy data and gives zero-width sync intervals. Its compatible is `samsung,sdp1202-panel` (line 200). Native Q60T pixel clock, blanking, sync polarity and panel routing remain open. |

The next source dependency is the matching Nike-L display package with
its GP, Mixer and OSDP implementation, paired with SDP1804 clock and
Q60T panel evidence. Keep the unconditional probe gate and disabled DT
nodes while these prerequisites and reversible boot are unresolved.
