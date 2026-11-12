#!/usr/bin/env bash
# Build 069 M3 / Boot 10: read-only probe - why audioserver waits forever for
# android.hardware.audio.core.IModule/bluetooth (system_server main thread
# then blocks in AudioManager.isVolumeFixed -> watchdog kill after ~60 s).
# Questions: who declares IModule/bluetooth (VINTF), who registers which
# IModule instances (example HAL main.cpp), and does Android 15 audioserver
# take the module list from the AIDL HAL instead of audio_policy_configuration.xml?
set -uo pipefail
L="${1:?los dir}"; cd "$L" || exit 1
O=out/target/product/qemu_arm_tv
sec() { printf '\n######## %s\n' "$*"; }
A=hardware/interfaces/audio/aidl/default
sec "example HAL: apex files"; find $A/apex -type f | sort
sec "example HAL: VINTF fragments declaring audio.core"; for f in $(grep -rl "audio.core" $A --include='*.xml' | sort); do echo "--- $f"; cat "$f"; done
sec "example HAL main.cpp"; cat -n $A/main.cpp
sec "Module::createInstance / BLUETOOTH"; grep -n -E 'createInstance|Type::BLUETOOTH|ModuleBluetooth|typeFromString' $A/Module.cpp | head -30
sec "Configuration: per-module config sources"; grep -n -E 'getConfiguration|BLUETOOTH|bluetooth|r_submix|getPrimaryConfiguration' $A/Configuration.cpp | head -40
sec "libaudiohal: how module names are found"; grep -n -E 'forEachDeclaredInstance|getDeclaredInstances|waitForService|checkService|getDeviceNames|IModule::descriptor|getHalModules|getAudioPolicyConfig' frameworks/av/media/libaudiohal/impl/DevicesFactoryHalAidl.cpp | head -40
sec "audiopolicy: XML vs AIDL config"; grep -rn -E 'loadFromApmAidlConfigWithFallback|loadFromApmXmlConfigWithFallback|loadFromCustomXml|getAudioPolicyConfig' frameworks/av/services/audiopolicy/service/*.cpp frameworks/av/services/audiopolicy/common/managerdefinitions/src/AudioPolicyConfig.cpp | head -30
sec "audiopolicy: AudioPolicyService::loadAudioPolicyManager / createAudioPolicyManager"; grep -n -B2 -A25 'AudioPolicyConfig::load' frameworks/av/services/audiopolicy/service/AudioPolicyService.cpp | head -80
sec "installed: VINTF fragments with audio.core in PRODUCT_OUT"; grep -rl "audio.core" $O/vendor/etc/vintf $O/system/etc/vintf $O/apex 2>/dev/null | sort; for f in $(grep -rl "audio.core" $O/vendor/etc/vintf $O/system/etc/vintf 2>/dev/null); do echo "--- $f"; cat "$f"; done
sec "installed: apexes with audio"; find $O -name '*hardware.audio*apex*' -o -name 'com.android.hardware.audio*' 2>/dev/null | head; ls $O/vendor/apex $O/system/apex 2>/dev/null | grep -i audio
sec "installed: bluetooth audio HAL present?"; find $O/vendor $O/system -iname '*bluetooth.audio*' 2>/dev/null | head -20
sec "cuttlefish: bluetooth audio / audio HAL packages"; grep -rn -E 'bluetooth.audio|hardware.audio|IModule' device/google/cuttlefish/shared/device.mk device/google/cuttlefish/shared/bluetooth/*.mk 2>/dev/null | head -30
sec "2: bluetooth policy XML (module name, halVersion)"; f=frameworks/av/services/audiopolicy/config/bluetooth_audio_policy_configuration_7_0.xml; ls -l $f; cat $f
sec "2: HAL Configuration for BLUETOOTH"; sed -n 680,730p $A/Configuration.cpp
sec "2: XML converter: module name -> type"; sed -n 125,165p $A/Module.cpp
sec "2: ModuleBluetooth: what it needs at construction/start"; grep -n -E 'ModuleBluetooth::|IBluetoothAudioProviderFactory|BluetoothAudioSession|waitForService|getService|checkService' $A/bluetooth/ModuleBluetooth.cpp $A/ModuleBluetooth.cpp 2>/dev/null | head -40
sec "2: cuttlefish policy XML + where the BT XML gets installed"; grep -n -i 'include\|bluetooth' device/google/cuttlefish/shared/config/audio/policy/audio_policy_configuration.xml; grep -rn 'bluetooth_audio_policy_configuration' device/google/cuttlefish frameworks/av/services/audiopolicy/config/Android.bp 2>/dev/null | head
sec "2: our installed policy XMLs"; ls -l $O/vendor/etc/*.xml | grep -i -E 'audio|volume'
echo "(done)"
