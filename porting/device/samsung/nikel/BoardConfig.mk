# SPDX-License-Identifier: Apache-2.0
# Research-only configuration. Build must be blocked until a recoverable boot
# experiment and compatible kernel + graphics HAL have been validated.

DEVICE_PATH := device/samsung/nikel
TARGET_BOARD_PLATFORM := nikel

# Never invent TARGET_ARCH, memory layout, boot image size, DTB, partition
# locations, AVB keys, kernel source, fstab or vendor HALs.
$(error Q60T Nike-L is a research target only; no verified boot path/graphics HAL/kernel build. DO NOT BUILD OR FLASH)
