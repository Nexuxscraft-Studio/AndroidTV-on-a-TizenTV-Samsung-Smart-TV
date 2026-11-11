# Build 069 M2: minimal ARM32 Android-TV device for QEMU 'virt'.
# Same ATV system as lineage_gsi_tv_arm, plus a real vendor partition
# (split SELinux policy, fstab, init, VINTF manifest). Emulation only;
# template for device/samsung/nikel. Never flash this to a TV.

LOCAL_PATH := device/nexuxscraft/qemu_arm_tv

PRODUCT_SHIPPING_API_LEVEL := 35
# Boot 4 / probe 3: PRODUCT_ENFORCE_VINTF_MANIFEST_OVERRIDE := false (M2)
# silently turned PRODUCT_FULL_TREBLE off (build/make/core/config.mk:790),
# giving ro.treble.enabled=false. linkerconfig then generated the legacy layout
# without the exported "sphal" namespace, the Vulkan loader could not dlopen
# /vendor/lib/hw/vulkan.pastel.so, ANGLE init failed and SurfaceFlinger aborted
# with "no suitable EGLConfig found". Keep VINTF enforcement on (full Treble).

$(call inherit-product, device/google/atv/products/atv_generic_system.mk)
$(call inherit-product, device/google/atv/products/atv_system_ext.mk)
$(call inherit-product, device/google/atv/products/atv_product.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/base_vendor.mk)
$(call inherit-product, device/google/atv/products/atv_vendor.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/generic_ramdisk.mk)
include vendor/lineage/build/target/product/lineage_generic_tv_target.mk

PRODUCT_PACKAGES += \
    LeanbackIME \
    TvSampleLeanbackLauncher \
    TvProvision

# Software KeyMint (AOSP reference, in-process TA - emulation only, NOT secure).
# Without any KeyMint HAL keystore2 aborts ("mandatory security level TEE")
# and vold blocks on android.security.maintenance (Build 069 M2-Boot 2).
PRODUCT_PACKAGES += \
    android.hardware.security.keymint-service

# Graphics (Build 069 M3), same architecture as AOSP Cuttlefish:
# virtio-gpu (KMS) -> drm_hwcomposer (HWC3), minigbm (allocator + stable-C
# mapper), SwiftShader Vulkan ("pastel") + ANGLE for GLES. Software
# rendering, emulation only. On the TV: drm_hwcomposer + gbm with Mesa/Panfrost.
PRODUCT_PACKAGES += \
    android.hardware.composer.hwc3-service.drm \
    android.hardware.graphics.allocator-service.minigbm \
    mapper.minigbm \
    vulkan.pastel \
    libEGL_angle \
    libGLESv1_CM_angle \
    libGLESv2_angle

PRODUCT_VENDOR_PROPERTIES += \
    ro.hardware.egl=angle \
    ro.hardware.vulkan=pastel \
    ro.hardware.gralloc=minigbm \
    ro.opengles.version=196608

# Audio: TODO - the AOSP example AIDL audio HAL modules are not installable
# for this product ("non-existent modules", M3 build 3); audioserver crashes
# without an audio HAL but does not trigger a reboot. Revisit after graphics.

# Minimal platform HALs system_server expects (AOSP examples).
PRODUCT_PACKAGES += \
    android.hardware.health-service.example \
    android.hardware.power-service.example

# 32-bit only product: no default zygote is set by core_64_bit*.mk.
PRODUCT_VENDOR_PROPERTIES += \
    ro.zygote=zygote32 \
    debug.sf.nobootanimation=1 \
    ro.sf.lcd_density=320

PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/fstab.qemuarm:$(TARGET_COPY_OUT_VENDOR)/etc/fstab.qemuarm \
    $(LOCAL_PATH)/fstab.qemuarm:$(TARGET_COPY_OUT_RAMDISK)/fstab.qemuarm \
    $(LOCAL_PATH)/init.qemuarm.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.qemuarm.rc \
    $(LOCAL_PATH)/qemu_logcat_kmsg.sh:$(TARGET_COPY_OUT_VENDOR)/bin/qemu_logcat_kmsg.sh

# atv_generic_system.mk lists "android.hardware.wifi"; see Android.mk here
# (empty phony package, QEMU has no Wi-Fi).

TARGET_NO_KERNEL_OVERRIDE := true
PRODUCT_ENFORCE_ARTIFACT_PATH_REQUIREMENTS := false
PRODUCT_CHARACTERISTICS := tv

PRODUCT_NAME := lineage_qemu_arm_tv
PRODUCT_DEVICE := qemu_arm_tv
PRODUCT_BRAND := Nexuxscraft
PRODUCT_MANUFACTURER := Nexuxscraft
PRODUCT_MODEL := Q60T-Port QEMU ARM32 TV (emulation)
