#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
src=/opt/samsung-atv-lab/samsung/build018-original/linux-4.1.10
out=${1:?absolute output directory}
mkdir -p "$out"
cd "$src"
# Report locations and hashes, without copying the vendor source tree.
for topic in registers address clocks reset dma irq timing; do
  case "$topic" in
    registers) pattern='sdp[_,-](gp|osdp|mixer|drm)|GP_(SRC|DST)|MIXER_' ;;
    address) pattern='(005[dD][048]000|0x5[dD][048]000|ioremap|of_address_to_resource|ranges[[:space:]]*=)' ;;
    clocks) pattern='(gp_clk|gfxp_clk|osdp_clk|clk_(set_rate|prepare_enable))' ;;
    reset) pattern='(reset_control|resets[[:space:]]*=|soft_?reset)' ;;
    dma) pattern='(dma_(alloc|map|set_mask)|phys_to_dma|dma-ranges|samsung,gfx[01]|smem-region)' ;;
    irq) pattern='(vsync|vblank|IRQF_TRIGGER|request(_threaded)?_irq|interrupts[[:space:]]*=)' ;;
    timing) pattern='(display-timings|pixelclock|hsync-len|vsync-len|1080[pP]|drm_display_mode)' ;;
  esac
  rc=0
  grep -rinE --include='*.c' --include='*.h' --include='*.dts' --include='*.dtsi' \
    "$pattern" drivers/gpu/drm drivers/video arch/arm/boot/dts > "$out/$topic.matches" || rc=$?
  test "$rc" -le 1
  # Preserve source path and line numbers; no assertions about semantic equivalence.
  cut -d: -f1,2 "$out/$topic.matches" > "$out/$topic.locations"
  rm "$out/$topic.matches"
done
cut -d: -f1 "$out"/*.locations | sort -u | xargs -r -d '\n' sha256sum > "$out/source.sha256"
wc -l "$out"/*.locations | tee "$out/counts.txt"
