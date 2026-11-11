#!/usr/bin/env bash
# Build 069: boot the Build-068 LineageOS 22.2 ARM32 ATV GSI on the
# Build-059 Linux 6.6.162 ARM32 kernel under qemu-system-arm -M virt.
#
# Emulation only. Nothing touches the TV, firmware or signatures. Inputs are
# read-only: system.img is attached with snapshot=on, the ramdisk is extended
# in a copy.
#
# Stages: kernel -> images -> boot -> analyse   (kernel/images are cached)
#
# Usage: run_android_qemu.sh --los-dir DIR --work-dir DIR [options]
#   --product-out DIR   default <los>/out/target/product/generic (GSI);
#                       out/target/product/qemu_arm_tv = M2 device (vendor.img)
#   --timeout SEC       QEMU wall-clock cap (default 1200; TCG is slow)
#   --smp N / --mem MB  default 4 / 3072
#   --hardware NAME     androidboot.hardware (default qemuarm)
#   --rebuild-kernel    force a kernel rebuild
#   --extra-cmdline S   appended to the kernel command line
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
LINUX_TAG=v6.6.162
LINUX_COMMIT=5139929c698c273e07cb0635732f6a918a7b8e78

LOS_DIR=""; WORK=""; PRODUCT_OUT=""; TIMEOUT=1200; SMP=4; MEM=3072
HW=qemuarm; REBUILD=0; EXTRA_CMDLINE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --los-dir) LOS_DIR="$2"; shift 2 ;;
    --work-dir) WORK="$2"; shift 2 ;;
    --product-out) PRODUCT_OUT="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --smp) SMP="$2"; shift 2 ;;
    --mem) MEM="$2"; shift 2 ;;
    --hardware) HW="$2"; shift 2 ;;
    --rebuild-kernel) REBUILD=1; shift ;;
    --extra-cmdline) EXTRA_CMDLINE="$2"; shift 2 ;;
    *) echo "build069: unknown option $1" >&2; exit 64 ;;
  esac
done
[ -n "$LOS_DIR" ] && [ -n "$WORK" ] || { echo "build069: --los-dir and --work-dir required" >&2; exit 64; }
[[ "$TIMEOUT$SMP$MEM" =~ ^[0-9]+$ ]] || { echo "build069: numeric options expected" >&2; exit 64; }
[[ "$HW" =~ ^[a-z0-9_]+$ ]] || { echo "build069: bad --hardware" >&2; exit 64; }
LOS_DIR="$(realpath -m "$LOS_DIR")"; WORK="$(realpath -m "$WORK")"
: "${PRODUCT_OUT:=$LOS_DIR/out/target/product/generic}"
mkdir -p "$WORK"
log() { printf 'build069 [%s] %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

# ------------------------------------------------------------------ kernel
KOUT="$WORK/kernel"
ZIMAGE="$KOUT/artifacts-arm-android/zImage"
stage_kernel() {
  if [ -f "$ZIMAGE" ] && [ "$REBUILD" = 0 ]; then log "kernel: cached $ZIMAGE"; return; fi
  local ksrc="$WORK/linux" clangdir abc="$WORK/android-base.config"
  if [ ! -f "$ksrc/Makefile" ]; then
    log "kernel: cloning $LINUX_TAG"
    git clone -q --depth 1 --branch "$LINUX_TAG" https://github.com/gregkh/linux.git "$ksrc"
  fi
  [ "$(git -C "$ksrc" rev-parse HEAD)" = "$LINUX_COMMIT" ] || die "kernel tree is not $LINUX_TAG ($LINUX_COMMIT)"
  if [ ! -s "$abc" ]; then
    local p url
    for p in v/android-6.6 android-6.6; do
      url="https://android.googlesource.com/kernel/configs/+/refs/heads/main/$p/android-base.config?format=TEXT"
      if curl -fsSL "$url" | base64 -d > "$abc" 2>/dev/null && grep -q '^CONFIG_' "$abc"; then
        log "kernel: android-base.config from $url"; break
      fi
      rm -f "$abc"
    done
    [ -s "$abc" ] || die "could not fetch android-base.config"
  fi
  sha256sum "$abc" >&2
  # Toolchain: the LLVM prebuilt that ships with the LineageOS tree (no install).
  clangdir="$(ls -d "$LOS_DIR"/prebuilts/clang/host/linux-x86/clang-r*/bin 2>/dev/null \
              | while read -r d; do [ -x "$d/ld.lld" ] && echo "$d"; done | sort -V | tail -1)"
  [ -n "$clangdir" ] || die "no LLVM prebuilt with ld.lld under $LOS_DIR/prebuilts/clang"
  log "kernel: toolchain $clangdir ($("$clangdir/clang" --version | head -1))"
  set +e
  PATH="$clangdir:$PATH" TOOLCHAIN=llvm DIAG_INITRAMFS=0 \
    ANDROID_BASE_CONFIG="$abc" EXTRA_FRAGMENTS="$HERE/qemu-virt.config" \
    JOBS="$(nproc)" \
    bash "$REPO/porting/build059/kernel/build.sh" "$ksrc" arm android "$KOUT" 2>&1 \
    | tee "$WORK/kernel-build.log" | grep -E '^build059|error|Error|coverage' >&2
  local krc="${PIPESTATUS[0]}"
  set -e
  [ "$krc" = 0 ] || die "kernel build failed (see $WORK/kernel-build.log)"
  [ -f "$ZIMAGE" ] || die "zImage missing"
  head -1 "$KOUT/artifacts-arm-android/android-coverage.txt" >&2 || true
}

# ------------------------------------------------------------------ images
SYS_IMG="$WORK/system.raw"
RAMDISK="$WORK/ramdisk-$HW.img"
VENDOR_IMG=""
USERDATA_IMG="$WORK/userdata.img"
stage_images() {
  local src="$PRODUCT_OUT/system.img" magic fstype fstab="$WORK/fstab.$HW"
  [ -f "$src" ] || die "$src missing (run Build 068 first)"
  [ -f "$PRODUCT_OUT/ramdisk.img" ] || die "$PRODUCT_OUT/ramdisk.img missing"
  magic="$(head -c4 "$src" | od -An -tx1 | tr -d ' \n')"
  if [ "$magic" = "3aff26ed" ]; then
    local s2i="$LOS_DIR/out/host/linux-x86/bin/simg2img"
    [ -x "$s2i" ] || die "system.img is sparse and simg2img is missing"
    if [ ! -f "$SYS_IMG" ] || [ "$src" -nt "$SYS_IMG" ]; then
      log "images: unsparsing system.img"; "$s2i" "$src" "$SYS_IMG"
    fi
  else
    ln -sf "$src" "$SYS_IMG"
  fi
  if [ "$(dd if="$SYS_IMG" bs=1 skip=1080 count=2 2>/dev/null | od -An -tx1 | tr -d ' \n')" = "53ef" ]; then
    fstype=ext4
  elif [ "$(dd if="$SYS_IMG" bs=1 skip=1024 count=4 2>/dev/null | od -An -tx1 | tr -d ' \n')" = "e2e1f5e0" ]; then
    fstype=erofs
  else
    die "system image is neither ext4 nor erofs"
  fi
  log "images: system.img = $fstype ($(stat -Lc %s "$SYS_IMG") bytes)"
  # Minimal first-stage fstab: system on the first virtio-blk disk (/dev/block/vda).
  if [ "$fstype" = ext4 ]; then
    printf '/dev/block/vda  /system  ext4  ro,barrier=1  wait,first_stage_mount\n' > "$fstab"
  else
    printf '/dev/block/vda  /system  erofs  ro  wait,first_stage_mount\n' > "$fstab"
  fi
  python3 "$HERE/ramdisk_tool.py" list "$PRODUCT_OUT/ramdisk.img" > "$WORK/ramdisk-listing.txt"
  head -1 "$WORK/ramdisk-listing.txt" >&2
  if [ -f "$PRODUCT_OUT/vendor.img" ]; then
    # M2 device mode: the device build ships its own fstab in ramdisk+vendor.
    VENDOR_IMG="$PRODUCT_OUT/vendor.img"
    grep -q " fstab.$HW\$" "$WORK/ramdisk-listing.txt" \
      || die "device ramdisk has no fstab.$HW (check PRODUCT_COPY_FILES)"
    cp "$PRODUCT_OUT/ramdisk.img" "$RAMDISK"
    rm -f "$USERDATA_IMG"; truncate -s 4G "$USERDATA_IMG"   # empty -> fs_mgr formats it
    log "images: device mode - vendor.img $(stat -Lc %s "$VENDOR_IMG") bytes, fresh 4G userdata"
  else
    python3 "$HERE/ramdisk_tool.py" add "$PRODUCT_OUT/ramdisk.img" "$RAMDISK" \
      --file "fstab.$HW=$fstab" \
      --file-if-dir "first_stage_ramdisk:first_stage_ramdisk/fstab.$HW=$fstab" >&2
  fi
}

# ------------------------------------------------------------------ boot
QLOG="$WORK/qemu-android.log"
stage_boot() {
  local cmdline="console=ttyAMA0 earlycon panic=-1 loglevel=8 printk.devkmsg=on"
  cmdline+=" androidboot.hardware=$HW androidboot.selinux=permissive androidboot.console=ttyAMA0"
  [ -n "$EXTRA_CMDLINE" ] && cmdline+=" $EXTRA_CMDLINE"
  log "boot: qemu-system-arm virt, smp=$SMP mem=${MEM}M, cap ${TIMEOUT}s"
  log "boot: cmdline: $cmdline"
  set +e
  # virtio-blk-pci: probe order = command-line order -> vda, vdb, vdc.
  local disks=(-drive "if=none,id=system,file=$SYS_IMG,format=raw,snapshot=on"
               -device virtio-blk-pci,drive=system)
  if [ -n "$VENDOR_IMG" ]; then
    disks+=(-drive "if=none,id=vendor,file=$VENDOR_IMG,format=raw,snapshot=on"
            -device virtio-blk-pci,drive=vendor
            -drive "if=none,id=userdata,file=$USERDATA_IMG,format=raw"
            -device virtio-blk-pci,drive=userdata)
  fi
  timeout "$TIMEOUT" qemu-system-arm -M virt -cpu cortex-a15 -smp "$SMP" -m "$MEM" \
    -nographic -no-reboot -nic none \
    -kernel "$ZIMAGE" -initrd "$RAMDISK" "${disks[@]}" \
    -append "$cmdline" > "$QLOG" 2>&1
  local rc=$?
  set -e
  log "boot: qemu exit $rc (124 = time cap reached, guest still running)"
  echo "$rc" > "$WORK/qemu-exit.txt"
}

stage_analyse() {
  local rc=0
  python3 "$HERE/boot_milestones.py" "$QLOG" --json "$WORK/milestones.json" || rc=$?
  return "$rc"
}

stage_kernel
stage_images
stage_boot
stage_analyse
