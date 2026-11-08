# SPDX-License-Identifier: Apache-2.0
# Research-only target; BoardConfig intentionally prevents a ROM build.

PRODUCT_MAKEFILES := \
    $(LOCAL_DIR)/lineage_nikel.mk

COMMON_LUNCH_CHOICES := \
    lineage_nikel-userdebug
