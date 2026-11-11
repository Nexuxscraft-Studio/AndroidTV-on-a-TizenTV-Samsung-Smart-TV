#!/system/bin/sh
# Build 069 (emulation only): copy logcat warnings/errors + crash buffer to the
# kernel log (QEMU serial console), one kmsg record per line.
/system/bin/logcat -b crash -b main -b system -v brief '*:W' | while IFS= read -r l; do
  echo "L> $l" > /dev/kmsg
done
