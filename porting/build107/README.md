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
