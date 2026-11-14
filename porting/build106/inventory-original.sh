#!/usr/bin/env bash
# Build 106: inventory the Samsung Linux 4.1.10 (Nike-L, T-NKLDEUC) GPL source
# tree that lives on the self-hosted Debian runner. Runs only inside a GitHub
# Actions job on that runner; nothing here reaches the tree from elsewhere.
#
# Usage: inventory-original.sh <output-dir>
#
# Writes:
#   samsung-dirs.txt        Samsung/SDP specific directories and files
#   compatibles.tsv         DT compatible strings -> source file
#   manifest.tsv            path, bytes, sha256 of every exported file
#   exported-sources.tar.xz driver sources needed for the Linux 6.6 port
#                           (.c/.h/Kconfig/Makefile/Kbuild/.dts/.dtsi only)
set -euo pipefail
export LC_ALL=C

src=${SAMSUNG_ORIGINAL_TREE:-/opt/samsung-atv-lab/samsung/build018-original/linux-4.1.10}
out=${1:?output directory}
mkdir -p "$out"
test -d "$src" || { echo "::error::Original kernel tree unavailable at $src"; exit 1; }
cd "$src"

head -n 5 Makefile > "$out/kernel-makefile-head.txt"

# Directories whose name marks them as Samsung SoC / TV specific.
find drivers include sound arch/arm -type d \
  \( -iname '*sdp*' -o -iname '*tztv*' -o -iname '*micom*' -o -iname '*nike*' \
     -o -iname '*samsung*' -o -iname 'mali*' -o -iname '*vdfs*' -o -iname 'mach-sdp*' \) \
  -print | sort > "$out/samsung-dirs.txt"
# Individual Samsung files outside those directories.
find drivers include arch/arm -type f \
  \( -iname '*sdp*' -o -iname '*tztv*' -o -iname '*micom*' -o -iname '*nike*' \) \
  -print | sort > "$out/samsung-files.txt"

# Which driver implements which compatible string.
grep -rEo --include='*.c' '"samsung,(sdp|tztv|nike)[^"]*"' drivers arch/arm 2>/dev/null \
  | sed -E 's/:"/\t"/' | sort -u > "$out/compatibles.tsv" || true

# Export set: Samsung directories (minus vendor binaries) plus single files.
: > "$out/export.list"
while IFS= read -r d; do
  find "$d" -type f \( -name '*.c' -o -name '*.h' -o -name 'Kconfig*' -o -name 'Makefile' \
       -o -name 'Kbuild' -o -name '*.dts' -o -name '*.dtsi' \) -print >> "$out/export.list"
done < "$out/samsung-dirs.txt"
grep -E '\.(c|h|dts|dtsi)$' "$out/samsung-files.txt" >> "$out/export.list" || true
for f in include/uapi/linux/micom-msg.h include/linux/mfd/sdp_micom.h \
         drivers/gpu/drm/Kconfig drivers/gpu/drm/Makefile \
         drivers/video/Kconfig drivers/video/Makefile \
         drivers/mfd/Kconfig drivers/mfd/Makefile drivers/misc/Kconfig drivers/misc/Makefile; do
  [[ -f "$f" ]] && echo "$f" >> "$out/export.list"
done
sort -u -o "$out/export.list" "$out/export.list"

printf 'path\tbytes\tsha256\n' > "$out/manifest.tsv"
while IFS= read -r f; do
  printf '%s\t%s\t%s\n' "$f" "$(stat -c %s -- "$f")" "$(sha256sum -- "$f" | cut -d' ' -f1)"
done < "$out/export.list" >> "$out/manifest.tsv"

tar --sort=name --owner=0 --group=0 --numeric-owner --mtime='2020-01-01 00:00Z' \
  -cJf "$out/exported-sources.tar.xz" -T "$out/export.list"
(cd "$out" && sha256sum exported-sources.tar.xz > exported-sources.sha256)

echo "Samsung directories: $(wc -l < "$out/samsung-dirs.txt")"
echo "Exported files:      $(wc -l < "$out/export.list")"
echo "Archive bytes:       $(stat -c %s "$out/exported-sources.tar.xz")"
cat "$out/samsung-dirs.txt"
