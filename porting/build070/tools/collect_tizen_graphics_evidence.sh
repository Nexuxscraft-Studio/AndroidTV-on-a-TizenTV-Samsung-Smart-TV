#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
#
# Collect graphics evidence from the stock Q60T Tizen system through SDB.
# This tool is intentionally read-only: it never runs su, writes sysfs,
# loads modules, changes clocks, or changes the target's filesystem.

set -euo pipefail

: "${SDB_BIN:=sdb}"
: "${SDB_SERIAL:?Set SDB_SERIAL to the already connected SDB device (host:port or serial).}"
: "${OUT_DIR:=./tizen-graphics-evidence-$(date -u +%Y%m%dT%H%M%SZ)}"

if ! command -v "$SDB_BIN" >/dev/null 2>&1; then
	echo "SDB binary not found: $SDB_BIN" >&2
	exit 127
fi

mkdir -p "$OUT_DIR"

collect() {
	local name=$1
	local command=$2

	printf 'Collecting %s\n' "$name"
	"$SDB_BIN" -s "$SDB_SERIAL" shell "$command" >"$OUT_DIR/$name" 2>&1 || true
}

# Connection identity and the stock kernel's messages provide provenance.
collect identity.txt 'id; uname -a; cat /proc/version'
collect dmesg-gpu-clock-display.txt \
	'dmesg | grep -i -E "mali|panfrost|gpu|sdp.*(clk|drm|gfx)|clock|regulator|vblank|vsync"'
collect interrupts.txt 'cat /proc/interrupts'
collect cmdline.txt 'cat /proc/cmdline'

# The live DT is authoritative for the running stock system.  DT values are
# binary, so record a stable textual listing and preserve any readable blobs.
collect live-dt-gpu.txt \
	'find /proc/device-tree -iname "*gpu*" -o -iname "*mali*" -o -iname "*clock*" 2>/dev/null'
collect live-dt-sdpgpu.txt \
	'for f in compatible reg interrupts interrupt-names clocks clock-names power-domains mali-supply status; do p=/proc/device-tree/soc/sdpgpu@00500000/$f; if [ -r "$p" ]; then printf "== %s ==\\n" "$p"; od -An -tx1 "$p"; fi; done'
collect live-dt-clock-controller.txt \
	'find /proc/device-tree/soc/clock-controller@00F50000 -maxdepth 2 -type f -print 2>/dev/null'

# Debugfs files are optional and may be inaccessible on production Tizen.
# Missing files are captured as command output, never treated as a failure.
collect clk-summary.txt 'cat /sys/kernel/debug/clk/clk_summary 2>/dev/null'
collect regulator-summary.txt 'cat /sys/kernel/debug/regulator/regulator_summary 2>/dev/null'
collect dri.txt 'find /sys/kernel/debug/dri /sys/class/drm -maxdepth 3 -type f -print 2>/dev/null'
collect gpu-sysfs.txt \
	'find /sys/devices -ipath "*gpu*" -o -ipath "*mali*" 2>/dev/null | head -n 500'

printf '%s\n' \
	'This collection uses read-only SDB shell commands only.' \
	'No GPU driver was loaded and no MMIO or sysfs value was written.' \
	>"$OUT_DIR/README.txt"

printf 'Evidence written to %s\n' "$OUT_DIR"
