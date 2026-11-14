#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
export KBUILD_BUILD_USER=build097 KBUILD_BUILD_HOST=ci KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP='2025-01-01 00:00:00 UTC'
export SOURCE_DATE_EPOCH=1735689600

work=${1:?absolute work directory}
tarball=${2:?absolute Linux tarball path}
report=${3:?absolute report directory}
mkdir -p "$report"
source porting/ci/selfhosted-llvm.sh
for tool in llvm-readelf modinfo; do
  command -v "$tool" || { echo "Missing runner prerequisite: $tool" >&2; exit 1; }
done
clang --version > "$report/clang.txt"
modinfo --version > "$report/modinfo-version.txt"
bash porting/build096/samsung-config-dtb.sh "$work" "$tarball" 2>&1 | tee "$report/config.log"
cp "$work/samsung-out/"{kernel.config,patches-applied.txt} "$report/"
src="$work/linux-nikel"
out="$work/nikel-arm"
cpu="$work/cpu"
cp -R porting/build058/cpu/kernel "$cpu"

printf '%s\n' 'module,kconfig,path' > "$report/module-mapping.csv"
modules=()
bad=0
while read -r symbol root path; do
  case "$root" in kernel) base="$out";; external) base="$cpu";; esac
  modules+=("$base/$path")
  printf '%s,%s,%s/%s\n' "${path##*/}" "$symbol" "$root" "$path" >> "$report/module-mapping.csv"
  if [[ "$root" == kernel ]]; then
    obj=${path##*/}
    obj=${obj%.ko}.o
    if ! grep -qE "^[[:space:]]*(menu)?config[[:space:]]+$symbol[[:space:]]*$" "$src/${path%/*}/Kconfig" ||
       ! grep -qx "CONFIG_$symbol=m" "$out/.config" ||
       ! awk -v symbol='obj-$('"CONFIG_$symbol"')' -v obj="$obj" '
           $1 == symbol { for (i = 2; i <= NF; i++) if ($i == obj) found = 1 }
           END { exit !found }
         ' "$src/${path%/*}/Makefile"; then
      echo "Invalid Kconfig/Makefile mapping: CONFIG_$symbol=m -> $path" >&2
      bad=1
    fi
  fi
done <<'EOF'
DRM_SDP kernel drivers/gpu/drm/sdp/sdp_display.ko
DRM_PANFROST kernel drivers/gpu/drm/panfrost/panfrost.ko
DRM_SDP_HDMI kernel drivers/gpu/drm/sdp-hdmi/sdp_hdmi.ko
SDP_MAC kernel drivers/net/ethernet/sdp/sdp_mac.ko
SDP_MICOM_IRB kernel drivers/misc/sdp-micom/sdp_micom_irb.ko
SDP_MICOM_IRS kernel drivers/misc/sdp-micom/sdp_micom_irs.ko
none external sdp_nikel_cpu_clk.ko
none external sdp_nikel_cpufreq.ko
none external sdp_nikel_thermal.ko
EOF
test "$bad" -eq 0

make_args=(-C "$src" O="$out" ARCH=arm LLVM=1 -j"$(nproc)")
export KCFLAGS="-ffile-prefix-map=$work=/build097"
make "${make_args[@]}" zImage modules 2>&1 | tee "$report/kernel-build.log"
test -s "$out/Module.symvers"
make "${make_args[@]}" M="$cpu" W=1 KCFLAGS="$KCFLAGS -Werror" modules 2>&1 | tee "$report/external-build.log"
release=$(cat "$out/include/config/kernel.release")
printf '%s\n' "$release" > "$report/kernel-release.txt"
[[ "$release" == 6.6.162 || "$release" == 6.6.162-* ]]

mkdir -p "$report/modules" "$report/metadata"
printf 'module\tdepends\n' > "$report/dependencies.tsv"
for ko in "${modules[@]}"; do
  name=${ko##*/}
  if [[ ! -s "$ko" ]]; then
    echo "Missing module: $ko" >&2
    bad=1
    continue
  fi
  header="$report/metadata/$name.elf.txt"
  if ! llvm-readelf -h "$ko" > "$header" ||
     ! grep -Eq 'Class:[[:space:]]+ELF32$' "$header" ||
     ! grep -Eq 'Machine:[[:space:]]+ARM$' "$header" ||
     ! grep -Eq 'Type:[[:space:]]+REL([[:space:]]|$)' "$header" ||
     ! modinfo "$ko" > "$report/metadata/$name.modinfo.txt" ||
     ! vermagic=$(modinfo -F vermagic "$ko") ||
     [[ "${vermagic%% *}" != "$release" ]] ||
     ! deps=$(modinfo -F depends "$ko"); then
    echo "Invalid ELF or module metadata: $ko" >&2
    bad=1
    continue
  fi
  printf '%s\t%s\n' "$name" "$deps" >> "$report/dependencies.tsv"
  cp "$ko" "$report/modules/"
done
test "$bad" -eq 0
(cd "$report" && sha256sum modules/*.ko > SHA256SUMS && sha256sum -c SHA256SUMS)
