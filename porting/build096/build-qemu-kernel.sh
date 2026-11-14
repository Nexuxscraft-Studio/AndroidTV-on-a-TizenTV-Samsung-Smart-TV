#!/usr/bin/env bash
# Build 096: build a minimal, reproducible Linux 6.6.162 ARM32 zImage and a
# separate initramfs for the QEMU "virt" boot test.
#
# Usage: build-qemu-kernel.sh <work-dir>
#
# Environment:
#   LINUX_TARBALL   use this linux-6.6.162.tar.xz instead of downloading it
#   BUILD096_CACHE  directory that may hold (and receives) the verified tarball
#   LINUX_SRC       use an existing clean 6.6.162 tree instead of the tarball
#   JOBS            parallel jobs (default: nproc)
#
# The kernel is vanilla upstream 6.6.162 (pinned SHA-256) configured from
# allnoconfig plus qemu-virt-arm32.config. No Samsung patch, driver, DT or
# MMIO address is involved. Results land in <work-dir>/out. Nothing is
# installed, flashed or booted here.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
WORK="${1:?work directory}"
JOBS="${JOBS:-$(nproc)}"
VERSION=6.6.162
TARBALL_NAME="linux-$VERSION.tar.xz"
TARBALL_URL="https://cdn.kernel.org/pub/linux/kernel/v6.x/$TARBALL_NAME"
TARBALL_SHA256=4aa89f3652fc131e5d39990f3bcd4b9e131028af3f315dbe83f3a8557dc06f06
FRAGMENT="$HERE/qemu-virt-arm32.config"

# Fixed build identity so two runs with the same toolchain give the same bytes.
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1767225600}"   # 2026-01-01 UTC
export KBUILD_BUILD_TIMESTAMP="@$SOURCE_DATE_EPOCH"
export KBUILD_BUILD_USER=build096
export KBUILD_BUILD_HOST=qemu-virt
export KBUILD_BUILD_VERSION=1

die() { echo "build096: ERROR: $*" >&2; exit 1; }
log() { echo "build096: $*"; }

mkdir -p "$WORK"
WORK="$(cd "$WORK" && pwd)"
OUT="$WORK/out"
KOUT="$WORK/kbuild-qemu-arm32"
IRD="$WORK/initramfs"
rm -rf "$OUT" "$KOUT" "$IRD"
mkdir -p "$OUT" "$KOUT" "$IRD"

# shellcheck source=/dev/null
source "$REPO/porting/ci/selfhosted-llvm.sh"
for tool in gzip sha256sum llvm-readelf; do
  command -v "$tool" >/dev/null || die "missing host tool $tool"
done

# 1. pinned kernel source ------------------------------------------------------
if [ -n "${LINUX_SRC:-}" ]; then
  KSRC="$(cd "$LINUX_SRC" && pwd)"
  SOURCE_DESC="existing tree $KSRC"
else
  tarball="${LINUX_TARBALL:-}"
  if [ -z "$tarball" ] && [ -n "${BUILD096_CACHE:-}" ] && [ -f "$BUILD096_CACHE/$TARBALL_NAME" ]; then
    tarball="$BUILD096_CACHE/$TARBALL_NAME"
  fi
  if [ -z "$tarball" ]; then
    tarball="$WORK/$TARBALL_NAME"
    log "downloading $TARBALL_URL"
    curl --fail --location --retry 3 --silent --show-error -o "$tarball" "$TARBALL_URL"
  fi
  echo "$TARBALL_SHA256  $tarball" | sha256sum -c - || die "tarball checksum mismatch"
  if [ -n "${BUILD096_CACHE:-}" ] && [ ! -f "$BUILD096_CACHE/$TARBALL_NAME" ]; then
    mkdir -p "$BUILD096_CACHE" && cp "$tarball" "$BUILD096_CACHE/$TARBALL_NAME"
  fi
  rm -rf "$WORK/linux-$VERSION"
  tar -xf "$tarball" -C "$WORK"
  KSRC="$WORK/linux-$VERSION"
  SOURCE_DESC="$TARBALL_URL sha256 $TARBALL_SHA256"
fi
[ "$(make -s -C "$KSRC" kernelversion)" = "$VERSION" ] || die "kernel tree is not $VERSION"
[ ! -e "$KSRC/arch/arm/mach-sdp" ] && [ ! -e "$KSRC/drivers/tty/serial/sdp_uart.c" ] \
  || die "kernel tree carries Samsung patches; Build 096 QEMU needs vanilla $VERSION"

MAKEARGS=(-C "$KSRC" O="$KOUT" ARCH=arm LLVM=1 -j"$JOBS")

# 2. minimal configuration -------------------------------------------------------
log "configuring allnoconfig + $(basename "$FRAGMENT")"
make "${MAKEARGS[@]}" KCONFIG_ALLCONFIG="$FRAGMENT" allnoconfig
make "${MAKEARGS[@]}" olddefconfig
lost=0
while IFS= read -r line; do
  case "$line" in
    '# CONFIG_'*' is not set')
      sym="${line#\# }"; sym="${sym%% *}"
      if grep -q "^$sym=" "$KOUT/.config"; then
        echo "build096: fragment wants $sym off but it is set" >&2; lost=1
      fi ;;
    ''|'#'*) ;;
    *) grep -qxF "$line" "$KOUT/.config" || { echo "build096: fragment value lost: $line" >&2; lost=1; } ;;
  esac
done < "$FRAGMENT"
if grep -E '^CONFIG_(ARCH_SDP|SERIAL_SDP|COMMON_CLK_SDP1804|DRM_SDP)[A-Z_0-9]*=' "$KOUT/.config"; then
  echo "build096: Samsung symbol present in the QEMU configuration" >&2; lost=1
fi
[ "$lost" = 0 ] || die "configuration incomplete"
cp "$KOUT/.config" "$OUT/kernel.config"

# 3. kernel --------------------------------------------------------------------------
log "building zImage"
make "${MAKEARGS[@]}" zImage 2>&1 | tee "$OUT/kernel-build.log"
cp "$KOUT/arch/arm/boot/zImage" "$OUT/zImage"
llvm-readelf -h "$KOUT/vmlinux" > "$OUT/vmlinux-elf.txt"
grep -Eq 'Class:[[:space:]]+ELF32$' "$OUT/vmlinux-elf.txt" || die "vmlinux is not ELF32"
grep -Eq 'Machine:[[:space:]]+ARM$' "$OUT/vmlinux-elf.txt" || die "vmlinux is not ARM"
# ARM zImage magic 0x016f2818 at offset 0x24 (little endian)
magic="$(od -An -tx4 -j36 -N4 "$OUT/zImage" | tr -d ' ')"
[ "$magic" = 016f2818 ] || die "zImage magic is $magic, expected 016f2818"
grep -aom1 "Linux version $VERSION [[:print:]]*" "$KOUT/vmlinux" > "$OUT/linux-banner.txt" \
  || die "vmlinux banner does not name $VERSION"

# 4. /init (nolibc, static, soft-float ARMv7) ----------------------------------------
log "building /init against nolibc"
make "${MAKEARGS[@]}" headers
cp -r "$KSRC/tools/include/nolibc" "$IRD/nolibc"
# nolibc 6.6 uses GCC-only "%r0" operands in its ARM start code (as in Build 059)
sed -i 's/%r0/r0/g' "$IRD/nolibc/arch-arm.h"
clang --target=armv7a-linux-gnueabi -march=armv7-a -mfloat-abi=soft -marm \
  -nostdinc -isystem "$(clang -print-resource-dir)/include" \
  -isystem "$KOUT/usr/include" -include "$IRD/nolibc/nolibc.h" \
  -nostdlib -static -Os -fno-stack-protector -Wall -Wextra -Werror \
  -Wno-unknown-attributes -fuse-ld=lld -Wl,--build-id=none \
  -o "$IRD/init" "$HERE/init.c"
llvm-readelf -h "$IRD/init" > "$OUT/init-elf.txt"
grep -Eq 'Class:[[:space:]]+ELF32$' "$OUT/init-elf.txt" || die "/init is not ELF32"
grep -Eq 'Machine:[[:space:]]+ARM$' "$OUT/init-elf.txt" || die "/init is not ARM"
grep -Eq 'Type:[[:space:]]+EXEC' "$OUT/init-elf.txt" || die "/init is not a static executable"
if grep -aq "BUILD096_ARM32_QEMU_BOOT_OK" "$IRD/init" "$OUT/zImage" "$KOUT/vmlinux"; then
  die "success marker must only be assembled at runtime"
fi
cp "$IRD/init" "$OUT/init"

# 5. initramfs -------------------------------------------------------------------------
cat > "$IRD/initramfs.list" <<EOL
dir /dev 0755 0 0
nod /dev/console 0600 0 0 c 5 1
dir /proc 0755 0 0
dir /sys 0755 0 0
file /init $IRD/init 0755 0 0
EOL
[ -x "$KOUT/usr/gen_init_cpio" ] || make "${MAKEARGS[@]}" usr/gen_init_cpio
# gen_init_cpio -t only covers dirs and device nodes; regular files keep their
# own mtime, so pin /init as well to get identical bytes on every build.
touch -h -d "@$SOURCE_DATE_EPOCH" "$IRD/init"
"$KOUT/usr/gen_init_cpio" -t "$SOURCE_DATE_EPOCH" "$IRD/initramfs.list" > "$IRD/initramfs.cpio"
gzip -n -9 -c "$IRD/initramfs.cpio" > "$OUT/initramfs.cpio.gz"
cp "$IRD/initramfs.list" "$OUT/initramfs.list"
sed -i "s|$IRD/init|init|" "$OUT/initramfs.list"

# 6. provenance ----------------------------------------------------------------------------
{
  echo "kernel: Linux $VERSION (vanilla upstream)"
  echo "source: $SOURCE_DESC"
  echo "config: allnoconfig + porting/build096/qemu-virt-arm32.config"
  echo "toolchain: $(clang --version | head -1)"
  echo "linker: $(ld.lld --version | head -1)"
  echo "SOURCE_DATE_EPOCH: $SOURCE_DATE_EPOCH"
  echo "banner: $(cat "$OUT/linux-banner.txt")"
} > "$OUT/build-info.txt"
(cd "$OUT" && sha256sum zImage initramfs.cpio.gz init kernel.config > SHA256SUMS)
cat "$OUT/build-info.txt" "$OUT/SHA256SUMS"
log "done: $OUT/zImage $OUT/initramfs.cpio.gz"
