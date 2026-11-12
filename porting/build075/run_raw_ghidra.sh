#!/usr/bin/env bash
# Build075: verified raw ARM32 import in an ephemeral Ghidra project.
# Never loads firmware modules, touches the TV, or requires root.
set -euo pipefail

payload="${1:-/opt/samsung-atv-lab/analysis/payload.bin}"
out_dir="${2:-/opt/samsung-atv-lab/analysis/build075}"
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ghidra="${GHIDRA_INSTALL_DIR:-/opt/ghidra_12.1.4_PUBLIC}"
java_home="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"

test -x "$ghidra/support/analyzeHeadless" || {
  echo "Ghidra 12.x analyzeHeadless unavailable; set GHIDRA_INSTALL_DIR." >&2
  exit 2
}
test -x "$java_home/bin/java" || {
  echo "Full JDK not available; set JAVA_HOME." >&2
  exit 2
}
export GHIDRA_INSTALL_DIR="$ghidra" JAVA_HOME="$java_home"

mkdir -p "$out_dir"
chmod 700 "$out_dir"
test ! -e "$out_dir/raw-payload-preflight.json" || {
  echo "Report exists; select a fresh report directory." >&2
  exit 2
}
test ! -e "$out_dir/ghidra-headless.log" || {
  echo "Log exists; select a fresh report directory." >&2
  exit 2
}
python3 "$repo_dir/porting/build075/raw_payload_probe.py" \
  --payload "$payload" --output "$out_dir/raw-payload-preflight.json"

tmp="$(mktemp -d "${TMPDIR:-/tmp}/q60t-build075.XXXXXXXX")"
trap 'rm -rf -- "$tmp"' EXIT

# Ghidra BinaryLoader base addresses use a hex address in the default space.
# The 0x80008000 value comes solely from the uImage header; it is not a
# verified kernel runtime mapping. Read-only project discarded after analysis.
# "-noanalysis" intentionally keeps this first pass narrow: an ARM zImage
# often embeds compressed kernel contents that are NOT ARM instructions.
timeout 480 "$ghidra/support/analyzeHeadless" "$tmp" q60t_raw_arm32 \
  -import "$payload" \
  -loader BinaryLoader \
  -loader-baseAddr 80008000 \
  -loader-blockName samsung_kernel_payload \
  -processor ARM:LE:32:v7 \
  -cspec default \
  -scriptPath "$repo_dir/porting/build075/ghidra" \
  -preScript RawKernelSeed.java \
  -postScript RawKernelAudit.java \
  -max-cpu 2 \
  -readOnly \
  -noanalysis \
  > "$out_dir/ghidra-headless.log" 2>&1

grep -q 'BUILD075_ZIMAGE_MAGIC_AT_OFFSET_0x24:' "$out_dir/ghidra-headless.log" || {
  echo "Ghidra output lacks audit marker; check LOCAL log for import/script errors." >&2
  exit 2
}
echo "Build075 local Ghidra audit complete; original payload unchanged."
echo "Reports remain on this Linux server: $out_dir"
