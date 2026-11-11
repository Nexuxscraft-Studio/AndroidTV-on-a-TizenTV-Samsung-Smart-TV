#!/usr/bin/env bash
# Build 069 M3: read-only probe 3d - installable AOSP default audio HAL for an
# ARM32 vendor (audioserver SIGSEGV without IModule/IFactory).
set -uo pipefail
L="${1:?los dir}"; cd "$L" || exit 1
sec() { printf '\n######## %s\n' "$*"; }
D=hardware/interfaces/audio/aidl/default
sec "$D/Android.bp: module names, namespace, enabled, vendor"; grep -n -E '^[a-z_]+ \{|name: "|soong_namespace|enabled:|vendor:|installable:|relative_install_path|apex_available|compile_multilib' $D/Android.bp | head -120
sec "$D/apex"; ls -R $D/apex 2>/dev/null | head -30; for f in $(find $D/apex -name Android.bp 2>/dev/null); do echo "--- $f"; sed -n 1,140p "$f"; done
sec "cuttlefish audio product config"; grep -rn -E 'audio' device/google/cuttlefish/shared/device.mk device/google/cuttlefish/shared/config/*.mk 2>/dev/null | grep -v '^\s*#' | head -40
sec "cuttlefish audio mk files"; ls device/google/cuttlefish/shared/*/ 2>/dev/null | head -0; find device/google/cuttlefish -name '*audio*' -maxdepth 4 | head -20
sec "goldfish/emulator audio product"; grep -rn -E 'audio.service|com.android.hardware.audio|audio.effect' device/generic/goldfish/product/*.mk device/generic/goldfish/*.mk 2>/dev/null | head -20
sec "module-info for audio example (if built)"; grep -o -E '"android.hardware.audio[^"]*example[^"]*"' out/target/product/qemu_arm_tv/module-info.json 2>/dev/null | sort -u | head -20; grep -o -E '"com.android.hardware.audio[^"]*"' out/target/product/qemu_arm_tv/module-info.json 2>/dev/null | sort -u | head
echo "(done)"
