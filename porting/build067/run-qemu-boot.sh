#!/usr/bin/env bash
# Build 067: boot the Build 059 Nike-L kernel (Linux 6.6.162 ARM32) under
# qemu-system-arm -M virt and verify it reaches the userspace diag init.
#
# Usage: run-qemu-boot.sh <linux-6.6.162-tree> <output-dir>
#
# Reuses the (CI-green) Build 059 "full" ARM build, which produces a
# multi_v7 zImage with the q60t-diag-init embedded as /init. We then boot that
# zImage on the generic QEMU 'virt' machine (NOT Samsung hardware) and grep the
# serial console for the init's banner. A pass proves the 6.6.162 ARM32 kernel
# boots to userspace IN EMULATION. It proves nothing about the real TV.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
KSRC="${1:?kernel tree}"
OUT="${2:?output dir}"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"

echo "build067: building Build 059 arm/full kernel (reuses tested path)..."
bash "$REPO/porting/build059/kernel/build.sh" "$KSRC" arm full "$OUT"

ZIMAGE="$OUT/artifacts-arm-full/zImage"
[ -f "$ZIMAGE" ] || { echo "build067: ERROR: zImage not found at $ZIMAGE" >&2; exit 1; }

LOG="$OUT/qemu-boot.log"
echo "build067: booting zImage under qemu-system-arm -M virt (90s cap)..."
set +e
# -nic none: the 'virt' machine otherwise auto-adds a virtio-net device that
# needs efi-virtio.rom (not shipped with qemu-system-arm on the runner), which
# makes qemu fail to start. We do not need networking for the boot smoke test.
timeout 90 qemu-system-arm -M virt -cpu cortex-a15 -m 512 -nographic -no-reboot \
  -nic none \
  -kernel "$ZIMAGE" -append "console=ttyAMA0 earlycon panic=-1" > "$LOG" 2>&1
rc=$?
set -e
echo "build067: qemu exit code $rc (124 = planned timeout at the diag shell)"
echo "---- qemu serial log (tail) ----"
tail -n 50 "$LOG" || true
echo "--------------------------------"

if grep -q "q60t-diag-init" "$LOG"; then
  echo "build067: BOOT OK - reached userspace init (6.6.162 ARM32 on QEMU virt)"
  exit 0
fi
echo "build067: BOOT FAIL - userspace init banner not seen" >&2
exit 1
