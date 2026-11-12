# SPDX-License-Identifier: Apache-2.0
# Research target: no proprietary firmware, HALs, fstab or keylayout installed.
# Do NOT add unknown vendor paths or fabricate partition geometry.

# Deliberately empty until verified Android-compatible components exist.

# Build 070: kernel-side Android fixes shared with the QEMU device (Build 069).
# memfd instead of ashmem (Linux 6.6 has no CONFIG_ASHMEM).
PRODUCT_COPY_FILES += \
    device/samsung/nikel/init.nikel.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.nikel.rc
