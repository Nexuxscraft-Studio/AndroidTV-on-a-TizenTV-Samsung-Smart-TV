# SPDX-License-Identifier: Apache-2.0
# EXPERIMENTAL / NON-BOOTABLE: Samsung Q60T Nike-L research target.

PRODUCT_IS_ATV := true

# Android TV foundations, following the official LineageOS ADT-2 pattern.
$(call inherit-product, device/google/atv/products/atv_base.mk)
$(call inherit-product, vendor/lineage/config/common_full_tv.mk)

# Only placeholders, not a vendor implementation.
$(call inherit-product, device/samsung/nikel/device.mk)

PRODUCT_BRAND := samsung
PRODUCT_DEVICE := nikel
PRODUCT_MANUFACTURER := Samsung
PRODUCT_MODEL := Q60T-Research-Only
PRODUCT_NAME := lineage_nikel
