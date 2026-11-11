# Build 069 M2: board for the QEMU 'virt' ARM32 TV device (emulation only).
TARGET_ARCH := arm
TARGET_ARCH_VARIANT := armv7-a-neon
TARGET_CPU_VARIANT := generic
TARGET_CPU_ABI := armeabi-v7a
TARGET_CPU_ABI2 := armeabi

TARGET_BOARD_PLATFORM := qemuarm
TARGET_BOOTLOADER_BOARD_NAME := qemu_arm_tv
TARGET_NO_BOOTLOADER := true
TARGET_NO_KERNEL := true
TARGET_NO_RECOVERY := true

# Plain (non-dynamic) partitions on separate virtio disks:
# vda = system, vdb = vendor, vdc = userdata (see fstab.qemuarm).
TARGET_USERIMAGES_USE_EXT4 := true
TARGET_USERIMAGES_SPARSE_EXT_DISABLED := true
BOARD_FLASH_BLOCK_SIZE := 4096
BOARD_SYSTEMIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_SYSTEMIMAGE_PARTITION_SIZE := 3221225472
TARGET_COPY_OUT_VENDOR := vendor
BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_VENDORIMAGE_PARTITION_SIZE := 536870912
TARGET_COPY_OUT_PRODUCT := system/product
TARGET_COPY_OUT_SYSTEM_EXT := system/system_ext

DEVICE_MANIFEST_FILE := device/nexuxscraft/qemu_arm_tv/manifest.xml

# minigbm gralloc SELinux types (as in Cuttlefish); the boot runs permissive.
BOARD_VENDOR_SEPOLICY_DIRS += external/minigbm/cros_gralloc/sepolicy
