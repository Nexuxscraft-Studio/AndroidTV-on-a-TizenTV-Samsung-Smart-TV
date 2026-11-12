#!/system/bin/sh
# Build 069 M3: one-shot display diagnostics into the kernel log ("D> " lines),
# because the QEMU console is the only output we can read (boot 9: SurfaceFlinger
# and HWC up, but DisplayManager "Can't find display mode with id -1").
sleep 60
k() { while IFS= read -r l; do echo "D> $1: $l" > /dev/kmsg; done; }
mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null
for f in /sys/kernel/debug/dri/*/state /sys/kernel/debug/dri/*/name; do
  [ -f "$f" ] && cat "$f" 2>&1 | head -80 | k "$f"
done
ls -l /dev/dri 2>&1 | k devdri
for c in /sys/class/drm/card*-*; do
  [ -d "$c" ] && echo "$(cat $c/status 2>/dev/null) $(cat $c/enabled 2>/dev/null) modes=$(tr '\n' ' ' < $c/modes 2>/dev/null)" | k "${c##*/}"
done
/system/bin/dumpsys SurfaceFlinger --displays 2>&1 | head -60 | k sf-displays
/system/bin/dumpsys SurfaceFlinger 2>&1 | grep -i -E -A3 'display|mode|hwc|vsync' | head -120 | k sf
/system/bin/dumpsys display 2>&1 | head -120 | k display
/system/bin/dumpsys android.hardware.graphics.composer3.IComposer/default 2>&1 | head -60 | k hwc
