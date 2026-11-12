#!/usr/bin/env bash
# Build 069 M3: read-only probe 3e - why the AOSP example audio core HAL never
# registers IModule/default (boot 8: "Invalid XML config file").
set -uo pipefail
L="${1:?los dir}"; cd "$L" || exit 1
O=out/target/product/qemu_arm_tv
sec() { printf '\n######## %s\n' "$*"; }
C=device/google/cuttlefish/shared/config/audio/policy
sec "cuttlefish audio_policy_configuration.xml"; cat $C/audio_policy_configuration.xml
sec "xi:include targets vs installed vendor/etc"; grep -o 'href="[^"]*"' $C/*.xml | sort -u; ls $O/vendor/etc | grep -i -E 'audio|volume' 
sec "cuttlefish device.mk audio copy block"; sed -n 295,325p device/google/cuttlefish/shared/device.mk
sec "example HAL main.cpp module registration"; grep -n -E 'IModule|getModuleConfig|registerService|AServiceManager|createInstance|primary|default' hardware/interfaces/audio/aidl/default/main.cpp | head -40
sec "AHAL_Config invalid xml"; grep -rn -B3 -A3 'Invalid XML config file' hardware/interfaces/audio/aidl/default/*.cpp | head -40
echo "(done)"
