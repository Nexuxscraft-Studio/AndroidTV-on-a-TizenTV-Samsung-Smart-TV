# Build 069 M2: placeholder for the "android.hardware.wifi" entry that
# device/google/atv/products/atv_generic_system.mk puts into PRODUCT_PACKAGES.
# For AOSP TV it is resolved by the goldfish emulator vendor (not usable on
# ARM32); the product enforces that every PRODUCT_PACKAGES entry exists.
# QEMU has no Wi-Fi, so an empty phony package is enough.
LOCAL_PATH := $(call my-dir)

ifeq ($(TARGET_DEVICE),qemu_arm_tv)
include $(CLEAR_VARS)
LOCAL_MODULE := android.hardware.wifi
LOCAL_MODULE_TAGS := optional
include $(BUILD_PHONY_PACKAGE)
endif
