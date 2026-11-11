#!/usr/bin/env bash
# Build 069: read crash evidence from the guest userdata image left by the last
# QEMU boot (read-only; debugfs -c = catastrophic/read-only mode).
# Usage: extract_tombstones.sh <work-dir>
set -uo pipefail
W="${1:?work dir}"; IMG="$W/userdata.img"
DFS="$(command -v debugfs || ls /usr/sbin/debugfs /sbin/debugfs 2>/dev/null | head -1)"
[ -n "$DFS" ] || { echo "debugfs not found (e2fsprogs)"; exit 0; }
[ -s "$IMG" ] || { echo "no userdata image at $IMG"; exit 0; }
d() { "$DFS" -c -R "$1" "$IMG" 2>/dev/null; }
echo "######## /tombstones"; d "ls -l /tombstones"
for f in $(d "ls /tombstones" | tr -s ' \t' '\n' | grep -E '^tombstone_[0-9]+$' | sort -u); do
  echo; echo "######## $f"
  d "cat /tombstones/$f" | grep -v -E '^ +(r[0-9]+|ip|sp|lr|pc|d[0-9]+|scr|fp) ' | head -90
done
echo; echo "######## /misc/logd (persisted logs, if any)"; d "ls -l /misc/logd"
echo "######## /system/dropbox"; d "ls -l /system/dropbox" | tail -20
echo "(done)"
