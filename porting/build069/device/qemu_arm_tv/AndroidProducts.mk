# Build 069 M2: minimal ARM32 Android-TV device for QEMU 'virt' (emulation only).
PRODUCT_MAKEFILES := \
    $(LOCAL_DIR)/lineage_qemu_arm_tv.mk

COMMON_LUNCH_CHOICES := \
    lineage_qemu_arm_tv-bp1a-userdebug
