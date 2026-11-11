# Build 069 M2: minimal ARM32 Android-TV device for QEMU 'virt'.
# Same ATV system as lineage_gsi_tv_arm, plus a real vendor partition
# (split SELinux policy, fstab, init, VINTF manifest). Emulation only;
# template for device/samsung/nikel. Never flash this to a TV.

LOCAL_PATH := device/nexuxscraft/qemu_arm_tv

PRODUCT_SHIPPING_API_LEVEL := 35
# Skip the build-time VINTF compatibility check: the emulator provides no HALs.
PRODUCT_ENFORCE_VINTF_MANIFEST_OVERRIDE := false

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

# 32-bit only product: no default zygote is set by core_64_bit*.mk.
PRODUCT_VENDOR_PROPERTIES += \
    ro.zygote=zygote32 \
    debug.sf.nobootanimation=1

PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/fstab.qemuarm:$(TARGET_COPY_OUT_VENDOR)/etc/fstab.qemuarm \
    $(LOCAL_PATH)/fstab.qemuarm:$(TARGET_COPY_OUT_RAMDISK)/fstab.qemuarm \
    $(LOCAL_PATH)/init.qemuarm.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.qemuarm.rc

TARGET_NO_KERNEL_OVERRIDE := true
PRODUCT_ENFORCE_ARTIFACT_PATH_REQUIREMENTS := false
PRODUCT_CHARACTERISTICS := tv

PRODUCT_NAME := lineage_qemu_arm_tv
PRODUCT_DEVICE := qemu_arm_tv
PRODUCT_BRAND := Nexuxscraft
PRODUCT_MANUFACTURER := Nexuxscraft
PRODUCT_MODEL := Q60T-Port QEMU ARM32 TV (emulation)
