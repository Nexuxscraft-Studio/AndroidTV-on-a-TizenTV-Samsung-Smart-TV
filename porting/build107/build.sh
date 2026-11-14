#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
root=${1:?absolute work directory}
tarball=${2:?verified kernel archive}
report=${3:?absolute report directory}
mkdir -p "$report"
# Keep the BUILD106 scripts unchanged; add the hook before Kbuild runs.
python3 - "$root" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
def generate(src, dest, old, new):
    text = Path(src).read_text()
    if text.count(old) != 1:
        raise SystemExit(f"{src}: BUILD106 integration point changed")
    (root / dest).write_text(text.replace(old, new))
generate("porting/build106/build-modules.sh", "build.sh",
         'src="$work/linux-nikel"',
         'src="$work/linux-nikel"\npython3 porting/build107/prepare-pattern.py "$src/drivers/gpu/drm/sdp"')
generate("porting/build106/init.c", "init.c", "int main(void)",
         '#include "guest-pattern.h"\n\nint main(void)')
init = root / "init.c"
text = init.read_text()
anchor = '\tout("BUILD106 /proc/modules:\\n");'
if text.count(anchor) != 1:
    raise SystemExit("BUILD106 guest integration point changed")
init.write_text(text.replace(anchor, "\tfails += build107_pattern_test();\n" + anchor))
generate("porting/build106/qemu-modules.sh", "qemu.sh", "porting/build106/init.c",
         '-I porting/build107/guest-include -I "$work/linux-nikel/drivers/gpu/drm/sdp" -I porting/build107 "$(dirname "$0")/init.c"')
PY
for build in a b; do
  mkdir -p "$root/$build/report"
  bash "$root/build.sh" "$root/$build/work" "$tarball" "$root/$build/report" \
    2>&1 | tee "$report/build-$build.log"
  cp "$root/$build/report/SHA256SUMS" "$report/build-$build.sha256"
  (
    cd "$root/$build/work/samsung-out"
    sha256sum -- *.dtb
  ) >> "$report/build-$build.sha256"
  if [[ "$build" == a ]]; then
    cp -r "$root/a/report/." "$report/"
    mkdir -p "$report/dtb"
    cp "$root"/a/work/samsung-out/*.dtb "$report/dtb/"
    cp "$root"/a/work/samsung-out/{dt-status.txt,patches-applied.txt} "$report/"
  fi
done
# Compare independent trees on the same runner and toolchain.
diff -u "$report/build-a.sha256" "$report/build-b.sha256" > "$report/reproducibility.diff" \
  && echo 'Byte-identical zImage, 17 modules and 4 DTBs' | tee "$report/reproducibility.txt" \
  || compare_failed=1
bash "$root/qemu.sh" "$root/a/work" "$report" 2>&1 | tee "$report/qemu.log"
python3 porting/build107/preview.py "$report" | tee "$report/pattern-result.txt"
test "${compare_failed:-0}" -eq 0
