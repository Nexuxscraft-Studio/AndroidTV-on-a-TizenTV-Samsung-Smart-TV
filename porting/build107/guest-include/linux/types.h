/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef BUILD108_GUEST_LINUX_TYPES_H
#define BUILD108_GUEST_LINUX_TYPES_H

/* Preserve the ARM UAPI types used by nolibc and its Linux headers. */
#include_next <linux/types.h>

typedef __u32 u32;
typedef __u64 u64;
typedef u32 dma_addr_t;
#ifndef bool
typedef _Bool bool;
#endif
#define __iomem

#endif
