#!/usr/bin/env bash
# Build 070: build the shared Q60T kernel (Linux 6.6.162 ARM32, Build-059
# profile "android" = Android fixes + nikel-drivers.config + patches
# 0001..0012) on the self-hosted runner, then check the Q60T device trees with
# extra dtc warnings (W=1).
#
# Usage: kernel_build.sh <work-dir> <lineageos-dir>
#   <work-dir>       own kernel tree + output (never shared with Build 069)
#   <lineageos-dir>  only for the LLVM prebuilt (clang/ld.lld), no install
#
# Compile/static checks only. Nothing is flashed, booted on a TV or loaded.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
WORK="${1:?work dir}"
LOS_DIR="${2:?LineageOS dir}"
LINUX_TAG=v6.6.162
LINUX_COMMIT=5139929c698c273e07cb0635732f6a918a7b8e78

log() { printf 'build070 [%s] %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

mkdir -p "$WORK"
WORK="$(cd "$WORK" && pwd)"
KSRC="$WORK/linux"
KOUT="$WORK/kernel"
ABC="$WORK/android-base.config"

# 1. clean v6.6.162 tree every run, so changed patches are applied fresh ------
if [ ! -f "$KSRC/Makefile" ]; then
  log "cloning $LINUX_TAG"
  git clone -q --depth 1 --branch "$LINUX_TAG" https://github.com/gregkh/linux.git "$KSRC"
fi
[ "$(git -C "$KSRC" rev-parse HEAD)" = "$LINUX_COMMIT" ] || die "kernel tree is not $LINUX_TAG"
git -C "$KSRC" reset -q --hard "$LINUX_COMMIT"
git -C "$KSRC" clean -q -fdx
rm -rf "$KOUT"

# 2. AOSP android-base.config (same source as Build 069) ----------------------
if [ ! -s "$ABC" ]; then
  for p in v/android-6.6 android-6.6; do
    url="https://android.googlesource.com/kernel/configs/+/refs/heads/main/$p/android-base.config?format=TEXT"
    if curl -fsSL "$url" | base64 -d > "$ABC" 2>/dev/null && grep -q '^CONFIG_' "$ABC"; then
      log "android-base.config from $url"; break
    fi
    rm -f "$ABC"
  done
  [ -s "$ABC" ] || die "could not fetch android-base.config"
fi
sha256sum "$ABC" >&2

# 3. toolchain: LLVM prebuilt of the LineageOS tree ---------------------------
clangdir="$(ls -d "$LOS_DIR"/prebuilts/clang/host/linux-x86/clang-r*/bin 2>/dev/null \
            | while read -r d; do [ -x "$d/ld.lld" ] && echo "$d"; done | sort -V | tail -1)"
[ -n "$clangdir" ] || die "no LLVM prebuilt with ld.lld under $LOS_DIR/prebuilts/clang"
export PATH="$clangdir:$PATH"
log "toolchain $clangdir ($(clang --version | head -1))"

# 4. the shared kernel (fragment survival + W=1 -Werror gate live in build.sh)
set +e
TOOLCHAIN=llvm DIAG_INITRAMFS=0 ANDROID_BASE_CONFIG="$ABC" JOBS="$(nproc)" \
  bash "$REPO/porting/build059/kernel/build.sh" "$KSRC" arm android "$KOUT" \
  > "$WORK/kernel-build.log" 2>&1
krc=$?
set -e
grep -E '^build059|error:|Error [0-9]|warning:|fragment value lost|required symbol' \
  "$WORK/kernel-build.log" | head -200 >&2 || true
[ "$krc" = 0 ] || die "kernel build failed (exit $krc, see kernel-build.log)"
ART="$KOUT/artifacts-arm-android"

# 5. device trees with extra dtc warnings ------------------------------------
DTC="$KOUT/kbuild-arm-android/scripts/dtc/dtc"
[ -x "$DTC" ] || die "kernel dtc not built"
dtc_warn=0
for d in sdp-nikel-q60t-1g5 sdp-nikel-q60t-2g; do
  rm -f "$KOUT/kbuild-arm-android/arch/arm/boot/dts/sdp/$d.dtb"   # force a rebuild
  make -s -C "$KSRC" O="$KOUT/kbuild-arm-android" ARCH=arm LLVM=1 W=1 \
       "sdp/$d.dtb" > "$WORK/dtc-$d.log" 2>&1 || die "dtc W=1 failed for $d"
  n="$(grep -c -i 'warning' "$WORK/dtc-$d.log" || true)"
  dtc_warn=$((dtc_warn + n))
  log "dtc W=1 $d.dtb: $n warning(s)"
  sed 's/^/  /' "$WORK/dtc-$d.log" >&2
done

[ "$dtc_warn" = 0 ] || die "dtc W=1 produced $dtc_warn warnings"

# 6. summary into the log ---------------------------------------------------
{
  echo "===== BUILD_INFO"; cat "$ART/BUILD_INFO.txt"
  echo "===== android-coverage (head 40)"; head -40 "$ART/android-coverage.txt"
  echo "===== driver symbols in .config"
  grep -E '^CONFIG_(ARCH_SDP|DRM|DRM_SDP|DRM_SIMPLEDRM|DRM_PANFROST|DRM_FBDEV_EMULATION|CPUFREQ_DT|THERMAL_OF|CPU_THERMAL|RC_CORE|LIRC|SND|SND_SOC|MEDIA_SUPPORT|MEDIA_CEC_SUPPORT|VIDEO_DEV|V4L_MEM2MEM_DRIVERS|ETHERNET|SECURITY_SELINUX|LSM|ASHMEM|ANDROID_BINDER_IPC|BPF_JIT)=' "$ART/config" || true
  echo "===== patches applied"; cat "$KSRC/.build059-patches-applied"
  echo "===== dtc W=1 warnings total: $dtc_warn"
} | tee "$WORK/summary.txt"
log "done: $ART"
