#!/usr/bin/env bash
# Build 068: reproducible LineageOS 22.2 ARM32 Android-TV userspace pipeline.
#
# Runs on the x86_64 build host (Proxmox VM), NOT on GitHub runners and NOT on
# the TV. Stages (each writes <work>/state/<stage>.done; reruns skip finished
# stages unless --force):
#
#   deps          check (and with --install-deps: apt-install) host packages
#   preflight     Build-060 host gate (RAM/disk/tools), JSON into <work>
#   init          repo init LineageOS lineage-22.2 (reuses an existing .repo)
#   sync          repo sync (+ pinned manifest snapshot for reproducibility)
#   check-target  verify the lunch target exists in THIS tree (no assumptions)
#   build         breakfast <target> <variant>; assert TARGET_ARCH=arm; mka
#   verify        offline artifact check (verify_userspace_artifacts.py)
#   emulator      only with --run-emulator AND an ARM32 emulator kernel present
#   handback      small tar.gz with all results, to hand back for review
#
# Nothing here touches the TV, firmware, signatures or flashing. A skipped or
# missing step is reported as SKIPPED/MISSING, never as success.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
STAGES=(deps preflight init sync check-target build verify emulator handback)

LOS_DIR="/opt/lineage-22.2"
WORK_DIR="${HOME}/build068-run"
TARGET="sdk_tv_arm"
VARIANT=""
JOBS="$(nproc 2>/dev/null || echo 4)"
SYNC_JOBS=4
SHALLOW=0
ALLOW_UNDERSIZED=0
INSTALL_DEPS=0
RUN_EMULATOR=0
DRY_RUN=0
FORCE=0
FROM_STAGE=""
ONLY_STAGE=""
PIN_MANIFEST=""
NO_CCACHE=0
CCACHE_DIR_PATH=""

usage() {
  cat <<'EOF'
Usage: userspace_pipeline.sh [options]

  --los-dir DIR        LineageOS source tree (default /opt/lineage-22.2).
                       An existing tree (e.g. an old lineage-22.1 checkout) is
                       re-initialised to lineage-22.2 and reuses its objects.
  --work-dir DIR       logs/state/results (default ~/build068-run)
  --target T           sdk_tv_arm (default) | gsi_tv_arm  (both ARM32 TV)
  --variant V          eng | userdebug (default: eng for sdk_tv_arm,
                       userdebug for gsi_tv_arm)
  --jobs N             mka parallelism (default: nproc). Lower it on small RAM.
  --sync-jobs N        repo sync parallelism (default 4)
  --shallow            repo init --depth=1 (saves disk, no git history)
  --pin FILE           sync exactly the revisions in a manifest snapshot
                       (as written by a previous run: <work>/manifest-pinned.xml)
  --install-deps       apt-get install missing packages (uses sudo)
  --ccache-dir DIR     ccache directory (default: <work-dir>/ccache)
  --no-ccache          build without ccache
  --allow-undersized   continue although the host gate says NOT READY
  --run-emulator       try the emulator stage (only if an ARM32 kernel exists)
  --from STAGE         start at STAGE      --only STAGE   run only STAGE
  --force              ignore .done markers
  --dry-run            print what would run, change nothing
  -h, --help

Stages: deps preflight init sync check-target build verify emulator handback
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --los-dir) LOS_DIR="$2"; shift 2 ;;
    --work-dir) WORK_DIR="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --variant) VARIANT="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    --sync-jobs) SYNC_JOBS="$2"; shift 2 ;;
    --shallow) SHALLOW=1; shift ;;
    --pin) PIN_MANIFEST="$2"; shift 2 ;;
    --install-deps) INSTALL_DEPS=1; shift ;;
    --no-ccache) NO_CCACHE=1; shift ;;
    --ccache-dir) CCACHE_DIR_PATH="$2"; shift 2 ;;
    --allow-undersized) ALLOW_UNDERSIZED=1; shift ;;
    --run-emulator) RUN_EMULATOR=1; shift ;;
    --from) FROM_STAGE="$2"; shift 2 ;;
    --only) ONLY_STAGE="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "build068: unknown option: $1" >&2; usage >&2; exit 64 ;;
  esac
done

case "$TARGET" in
  sdk_tv_arm) : "${VARIANT:=eng}" ;;
  gsi_tv_arm) : "${VARIANT:=userdebug}" ;;
  *) echo "build068: --target must be sdk_tv_arm or gsi_tv_arm (ARM32 TV only)" >&2; exit 64 ;;
esac
case "$VARIANT" in eng|userdebug) ;; *) echo "build068: bad --variant" >&2; exit 64 ;; esac
[[ "$JOBS" =~ ^[0-9]+$ && "$JOBS" -ge 1 ]] || { echo "build068: bad --jobs" >&2; exit 64; }
[[ "$SYNC_JOBS" =~ ^[0-9]+$ && "$SYNC_JOBS" -ge 1 ]] || { echo "build068: bad --sync-jobs" >&2; exit 64; }
for s in "$FROM_STAGE" "$ONLY_STAGE"; do
  if [ -n "$s" ] && [[ ! " ${STAGES[*]} " =~ \ $s\  ]]; then
    echo "build068: unknown stage: $s" >&2; exit 64
  fi
done

# Absolute paths: the check-target stage cd's into the source tree.
LOS_DIR="$(realpath -m "$LOS_DIR")"
WORK_DIR="$(realpath -m "$WORK_DIR")"
[ -z "$PIN_MANIFEST" ] || PIN_MANIFEST="$(realpath -m "$PIN_MANIFEST")"
[ -n "$CCACHE_DIR_PATH" ] || CCACHE_DIR_PATH="$WORK_DIR/ccache"
CCACHE_DIR_PATH="$(realpath -m "$CCACHE_DIR_PATH")"
STATE_DIR="$WORK_DIR/state"
LOG_DIR="$WORK_DIR/logs"
if [ "$DRY_RUN" -eq 0 ]; then mkdir -p "$STATE_DIR" "$LOG_DIR"; fi

log() { printf 'build068 [%s] %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

# run CMD...: execute (or print in --dry-run)
run() {
  if [ "$DRY_RUN" -eq 1 ]; then printf '  DRY-RUN: %q' "$1" >&2; shift; printf ' %q' "$@" >&2; echo >&2; return 0; fi
  "$@"
}

write_file() {  # write_file PATH (content on stdin); no-op in dry-run
  if [ "$DRY_RUN" -eq 1 ]; then cat >/dev/null; log "DRY-RUN: would write $1"; return 0; fi
  cat >"$1"
}

# ---------------------------------------------------------------- deps
DEPS=(bc bison build-essential ccache curl erofs-utils flex g++-multilib
      gcc-multilib git git-lfs gnupg gperf imagemagick kmod protobuf-compiler
      python3-protobuf lib32readline-dev lib32z1-dev libdw-dev libelf-dev
      libgnutls28-dev lz4 libsdl1.2-dev libssl-dev libxml2 libxml2-utils lzop
      pngcrush rsync schedtool squashfs-tools xsltproc xxd zip zlib1g-dev
      repo python3 file binutils)

stage_deps() {
  local missing=()
  if command -v dpkg-query >/dev/null 2>&1; then
    for p in "${DEPS[@]}"; do
      # Tools may come from outside dpkg (e.g. repo in /usr/local/bin).
      case "$p" in repo|git|git-lfs|python3|curl|rsync|zip|file)
        command -v "$p" >/dev/null 2>&1 && continue ;; esac
      dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || missing+=("$p")
    done
  else
    log "dpkg-query not found (not Debian/Ubuntu?) - checking only git/git-lfs/repo/python3"
    for t in git git-lfs repo python3; do command -v "$t" >/dev/null || missing+=("$t"); done
  fi
  if [ ${#missing[@]} -eq 0 ]; then log "deps: all packages present"; return 0; fi
  log "deps: missing: ${missing[*]}"
  if [ "$INSTALL_DEPS" -eq 1 ] || [ "$DRY_RUN" -eq 1 ]; then
    run sudo -n apt-get update
    run sudo -n apt-get install -y "${missing[@]}"
    run git lfs install
  else
    die "missing packages; rerun with --install-deps or install them manually"
  fi
}

# ---------------------------------------------------------------- preflight
stage_preflight() {
  local probe="$LOS_DIR" rc=0
  while [ ! -d "$probe" ]; do probe="$(dirname "$probe")"; done
  log "preflight: Build-060 host gate on filesystem of $probe"
  if [ "$DRY_RUN" -eq 1 ]; then
    run python3 "$REPO_ROOT/porting/build060/host_preflight.py" --build-dir "$probe" --json; return 0
  fi
  python3 "$REPO_ROOT/porting/build060/host_preflight.py" --build-dir "$probe" --json \
    >"$WORK_DIR/preflight.json" || rc=$?
  { echo "--- /proc/meminfo (Mem/Swap)"; grep -E '^(MemTotal|SwapTotal|SwapFree):' /proc/meminfo
    echo "--- nproc: $(nproc)"; echo "--- df"; df -h "$probe"
    echo "--- zram"; compgen -G '/sys/block/zram*' || echo none
  } >"$WORK_DIR/host.txt" 2>&1 || true
  cat "$WORK_DIR/preflight.json" >&2
  if [ "$rc" -ne 0 ]; then
    if [ "$ALLOW_UNDERSIZED" -eq 1 ]; then
      log "preflight: NOT READY - continuing because of --allow-undersized (see host.txt)"
      log "preflight: expect OOM kills / disk-full; use small --jobs and large swap"
    else
      die "host gate NOT READY (see $WORK_DIR/preflight.json); fix host or use --allow-undersized"
    fi
  fi
}

# ---------------------------------------------------------------- init
stage_init() {
  if ! { git config --global user.email && git config --global user.name; } >/dev/null 2>&1; then
    [ "$DRY_RUN" -eq 1 ] && log "WARN: git user.name/user.email not set (needed for repo init)" \
      || die "git user.name/user.email not set (repo init needs them; set them on your account)"
  fi
  run mkdir -p "$LOS_DIR"
  local args=(-u https://github.com/LineageOS/android.git -b lineage-22.2 --git-lfs --no-clone-bundle)
  [ "$SHALLOW" -eq 1 ] && args+=(--depth=1)
  if [ -d "$LOS_DIR/.repo" ]; then
    log "init: existing .repo found - re-initialising to lineage-22.2 (objects are reused)"
  fi
  (cd "$LOS_DIR" 2>/dev/null || cd / || exit 1; run repo init "${args[@]}")
}

# ---------------------------------------------------------------- sync
stage_sync() {
  local args=(-c "-j$SYNC_JOBS" --no-tags --no-clone-bundle --optimized-fetch --prune)
  if [ -n "$PIN_MANIFEST" ]; then
    [ -f "$PIN_MANIFEST" ] || die "--pin file not found: $PIN_MANIFEST"
    args+=(-m "$PIN_MANIFEST")
    log "sync: pinned to $PIN_MANIFEST"
  fi
  local try
  for try in 1 2 3; do
    log "sync: attempt $try"
    if (cd "$LOS_DIR" 2>/dev/null || cd / || exit 1; run repo sync "${args[@]}") 2>&1 \
         | { if [ "$DRY_RUN" -eq 1 ]; then cat; else tee -a "$LOG_DIR/sync.log"; fi; }; then
      break
    fi
    [ "$try" -eq 3 ] && die "repo sync failed 3x (see $LOG_DIR/sync.log)"
    sleep 30
  done
  if [ "$DRY_RUN" -eq 0 ]; then
    (cd "$LOS_DIR" && repo manifest -r -o "$WORK_DIR/manifest-pinned.xml")
    log "sync: pinned snapshot -> $WORK_DIR/manifest-pinned.xml (reuse with --pin)"
  fi
}

# ---------------------------------------------------------------- check-target
stage_check_target() {
  local prod="vendor/lineage/build/target/product"
  local atv_mk release emu_kernel qemu_arm
  case "$TARGET" in
    sdk_tv_arm) atv_mk="device/google/atv/products/sdk_atv_armv7.mk" ;;
    gsi_tv_arm) atv_mk="device/google/atv/products/aosp_tv_arm.mk" ;;
  esac
  if [ "$DRY_RUN" -eq 1 ]; then log "DRY-RUN: would check $prod/lineage_$TARGET.mk, $atv_mk"; return 0; fi
  cd "$LOS_DIR" || die "cannot cd to $LOS_DIR"
  grep -q "lineage_${TARGET}\.mk" "$prod/AndroidProducts.mk" \
    || die "lineage_${TARGET} is NOT in $prod/AndroidProducts.mk of this tree"
  [ -f "$prod/lineage_${TARGET}.mk" ] || die "$prod/lineage_${TARGET}.mk missing"
  [ -f "$atv_mk" ] || die "$atv_mk missing (ATV ARM32 base product)"
  release="$(sed -n 's/^aosp_target_release=//p' vendor/lineage/vars/aosp_target_release 2>/dev/null || true)"
  [ -n "$release" ] || die "vendor/lineage/vars/aosp_target_release unreadable"
  # Android 15 goldfish ships emulator kernels/boards for arm64/x86_64 only.
  emu_kernel="absent"; [ -e device/generic/goldfish/board/kernel/arm.mk ] && emu_kernel="present"
  qemu_arm="absent"
  compgen -G "prebuilts/android-emulator/linux-x86_64/qemu/linux-x86_64/qemu-system-arm*" >/dev/null \
    && qemu_arm="present"
  cat >"$WORK_DIR/check-target.json" <<EOF
{
  "target": "lineage_${TARGET}",
  "lunch": "lineage_${TARGET}-${release}-${VARIANT}",
  "aosp_target_release": "${release}",
  "atv_base_product": "${atv_mk}",
  "goldfish_arm32_kernel_board": "${emu_kernel}",
  "emulator_qemu_system_arm_binary": "${qemu_arm}",
  "vendor_lineage_head": "$(git -C vendor/lineage rev-parse HEAD 2>/dev/null || echo unknown)",
  "device_google_atv_head": "$(git -C device/google/atv rev-parse HEAD 2>/dev/null || echo unknown)"
}
EOF
  cat "$WORK_DIR/check-target.json" >&2
}

# ---------------------------------------------------------------- build
inner_build_script() {  # runs in a clean bash: envsetup is not set -eu safe
  cat <<EOF
cd "$LOS_DIR" || exit 90
export USE_CCACHE=1 CCACHE_EXEC="\$(command -v ccache || true)"
if [ -n "\$CCACHE_EXEC" ] && [ "$NO_CCACHE" -eq 0 ]; then
  # Explicit cache dir on the build filesystem; the runner's HOME layout is
  # not usable for ccache ("Not a directory", Build-068 run 2).
  export CCACHE_DIR="$CCACHE_DIR_PATH"
  mkdir -p "\$CCACHE_DIR" || exit 96
  "\$CCACHE_EXEC" -M 50G >/dev/null || exit 96
  echo "ccache: \$CCACHE_DIR"
else
  unset USE_CCACHE CCACHE_EXEC
  echo "ccache: off"
fi
source build/envsetup.sh >/dev/null || exit 91
breakfast "$TARGET" "$VARIANT" || exit 92
vars="\$(get_build_var TARGET_PRODUCT); \$(get_build_var TARGET_RELEASE); \$(get_build_var TARGET_BUILD_VARIANT)"
arch="\$(get_build_var TARGET_ARCH)"; arch2="\$(get_build_var TARGET_2ND_ARCH)"
{
  echo "TARGET_PRODUCT/RELEASE/VARIANT=\$vars"
  echo "TARGET_ARCH=\$arch"
  echo "TARGET_2ND_ARCH=\$arch2"
  echo "TARGET_ARCH_VARIANT=\$(get_build_var TARGET_ARCH_VARIANT)"
  echo "TARGET_CPU_ABI=\$(get_build_var TARGET_CPU_ABI)"
  echo "PRODUCT_OUT=\$(get_build_var PRODUCT_OUT)"
} > "$WORK_DIR/build-vars.txt"
cat "$WORK_DIR/build-vars.txt"
[ "\$arch" = "arm" ] || { echo "TARGET_ARCH=\$arch is not arm - abort"; exit 93; }
[ -z "\$arch2" ] || { echo "TARGET_2ND_ARCH=\$arch2 set - not pure 32-bit - abort"; exit 94; }
mka -j$JOBS || exit 95
EOF
}

stage_build() {
  if [ "$DRY_RUN" -eq 1 ]; then log "DRY-RUN: inner build script:"; inner_build_script >&2; return 0; fi
  local start rc
  start="$(date -u +%s)"
  set +e
  inner_build_script | bash --noprofile --norc 2>&1 | tee "$LOG_DIR/build.log"
  rc="${PIPESTATUS[1]}"
  set -e
  echo "build_seconds=$(( $(date -u +%s) - start )) exit=$rc" >>"$WORK_DIR/build-vars.txt"
  [ "$rc" -eq 0 ] || die "build failed (exit $rc, 9x = pipeline guard; see $LOG_DIR/build.log)"
}

product_out() {
  local p
  p="$(sed -n 's/^PRODUCT_OUT=//p' "$WORK_DIR/build-vars.txt" 2>/dev/null | tail -1)"
  [ -n "$p" ] || die "PRODUCT_OUT unknown - run the build stage first"
  case "$p" in /*) echo "$p" ;; *) echo "$LOS_DIR/$p" ;; esac
}

# ---------------------------------------------------------------- verify
stage_verify() {
  if [ "$DRY_RUN" -eq 1 ]; then run python3 "$HERE/verify_userspace_artifacts.py" '<PRODUCT_OUT>' --json; return 0; fi
  local out rc=0
  out="$(product_out)"
  python3 "$HERE/verify_userspace_artifacts.py" "$out" --json >"$WORK_DIR/verify.json" || rc=$?
  python3 "$HERE/verify_userspace_artifacts.py" "$out" >&2 || true
  case "$rc" in
    0) log "verify: PASS (static; no boot proven)" ;;
    2) log "verify: INCOMPLETE - some inputs missing (see verify.json)" ;;
    *) die "verify: FAIL (see $WORK_DIR/verify.json)" ;;
  esac
}

# ---------------------------------------------------------------- emulator
stage_emulator() {
  local note="$WORK_DIR/emulator.txt" out
  if [ "$RUN_EMULATOR" -eq 0 ]; then
    echo "SKIPPED: --run-emulator not given" | write_file "$note"; log "emulator: SKIPPED (not requested)"; return 0
  fi
  [ "$DRY_RUN" -eq 1 ] && { log "DRY-RUN: would try emulator if an ARM32 kernel exists"; return 0; }
  out="$(product_out)"
  if [ ! -e "$out/kernel-ranchu" ] && ! grep -q '"goldfish_arm32_kernel_board": "present"' "$WORK_DIR/check-target.json" 2>/dev/null; then
    echo "SKIPPED: no ARM32 emulator kernel (no \$PRODUCT_OUT/kernel-ranchu, no goldfish arm board). Next: boot system image with the Build-059 6.6.162 ARM32 kernel under qemu-system-arm (Build 069)." \
      | write_file "$note"
    log "emulator: SKIPPED - no ARM32 emulator kernel in this tree"; return 0
  fi
  log "emulator: starting headless (TCG, ARM on x86 is slow; 30 min cap)"
  ( cd "$LOS_DIR" && bash --noprofile --norc -c "source build/envsetup.sh >/dev/null; breakfast $TARGET $VARIANT >/dev/null; \
      timeout 1800 emulator -no-window -no-audio -no-snapshot -show-kernel" >"$LOG_DIR/emulator.log" 2>&1 & )
  local adb="$LOS_DIR/out/host/linux-x86/bin/adb"; command -v adb >/dev/null && adb="$(command -v adb)"
  if timeout 1500 "$adb" wait-for-device shell 'while [ "$(getprop sys.boot_completed)" != 1 ]; do sleep 5; done' 2>/dev/null; then
    { echo "BOOT_COMPLETED"
      for p in ro.build.version.release ro.product.cpu.abi ro.zygote ro.product.cpu.abilist64; do
        echo "$p=$("$adb" shell getprop "$p" | tr -d '\r')"; done
      echo "uname -m=$("$adb" shell uname -m | tr -d '\r')"
    } | write_file "$note"
  else
    echo "NOT BOOTED within 25 min (see logs/emulator.log)" | write_file "$note"
  fi
  "$adb" emu kill >/dev/null 2>&1 || true
  cat "$note" >&2
}

# ---------------------------------------------------------------- handback
stage_handback() {
  [ "$DRY_RUN" -eq 1 ] && { log "DRY-RUN: would pack $WORK_DIR/handback-*.tar.gz"; return 0; }
  local hb="$WORK_DIR/handback" out ts
  rm -rf "$hb"; mkdir -p "$hb"
  for f in preflight.json host.txt check-target.json build-vars.txt verify.json emulator.txt manifest-pinned.xml; do
    [ -f "$WORK_DIR/$f" ] && cp "$WORK_DIR/$f" "$hb/"
  done
  [ -f "$LOG_DIR/build.log" ] && tail -n 400 "$LOG_DIR/build.log" >"$hb/build.log.tail"
  [ -f "$LOG_DIR/sync.log" ] && tail -n 100 "$LOG_DIR/sync.log" >"$hb/sync.log.tail"
  [ -f "$LOG_DIR/emulator.log" ] && tail -n 300 "$LOG_DIR/emulator.log" >"$hb/emulator.log.tail"
  if out="$(product_out 2>/dev/null)"; then
    for f in system/build.prop vendor/build.prop product/etc/build.prop system_ext/etc/build.prop; do
      [ -f "$out/$f" ] && cp "$out/$f" "$hb/${f//\//_}"
    done
    ls -la "$out" >"$hb/product_out_listing.txt" 2>&1 || true
  fi
  (cd "$REPO_ROOT" && git rev-parse HEAD >"$hb/pipeline_repo_commit.txt" 2>/dev/null) || true
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  tar -C "$WORK_DIR" -czf "$WORK_DIR/handback-$ts.tar.gz" handback
  log "handback: $WORK_DIR/handback-$ts.tar.gz  (attach this file in the chat for review)"
}

# ---------------------------------------------------------------- driver
started=0
[ -z "$FROM_STAGE" ] && [ -z "$ONLY_STAGE" ] && started=1
log "target=lineage_$TARGET variant=$VARIANT los=$LOS_DIR work=$WORK_DIR jobs=$JOBS dry_run=$DRY_RUN"
for stage in "${STAGES[@]}"; do
  if [ -n "$ONLY_STAGE" ]; then [ "$stage" = "$ONLY_STAGE" ] || continue
  else
    [ "$stage" = "$FROM_STAGE" ] && started=1
    [ "$started" -eq 1 ] || continue
  fi
  marker="$STATE_DIR/$stage.done"
  if [ "$FORCE" -eq 0 ] && [ -f "$marker" ] && [ "$stage" != handback ]; then
    log "== $stage: already done ($(cat "$marker")) - skip (use --force)"; continue
  fi
  log "== $stage"
  "stage_${stage//-/_}"
  [ "$DRY_RUN" -eq 1 ] || date -u +%FT%TZ >"$marker"
done
log "finished"
