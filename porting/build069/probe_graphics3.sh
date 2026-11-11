#!/usr/bin/env bash
# Build 069 M3: read-only probe 3b - where Treble gets disabled for qemu_arm_tv.
set -uo pipefail
L="${1:?los dir}"; P="${2:-qemu_arm_tv}"; cd "$L" || exit 1
sec() { printf '\n######## %s\n' "$*"; }
sec "config.mk treble logic"; grep -n -B4 -A4 -E 'FULL_TREBLE|Treble enabled|treble' build/make/core/config.mk | head -80
sec "product var defaults"; grep -rn -E 'FULL_TREBLE' build/make/core/product.mk build/make/core/product_config.mk build/make/core/board_config.mk 2>/dev/null | head -20
sec "who sets PRODUCT_FULL_TREBLE*"; grep -rn --include='*.mk' -E 'PRODUCT_FULL_TREBLE' build/make/target device/google/atv vendor/lineage device/nexuxscraft 2>/dev/null | head -30
sec "ro.treble.enabled writer"; grep -rn -E 'ro.treble.enabled' build/make/core build/make/tools build/soong/android 2>/dev/null | head -10
sec "dumpvars"; ( source build/envsetup.sh >/dev/null 2>&1; lunch lineage_${P}-bp1a-userdebug >/dev/null 2>&1; get_build_var PRODUCT_FULL_TREBLE; get_build_var PRODUCT_FULL_TREBLE_OVERRIDE; get_build_var PRODUCT_SHIPPING_API_LEVEL; get_build_var BOARD_VNDK_VERSION ) 2>&1 | tail -6
echo "(done)"
