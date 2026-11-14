/* SPDX-License-Identifier: GPL-2.0-only */
/* Freestanding guest stand-ins; never on the Kbuild include path. */
typedef unsigned int u32;
typedef unsigned long long u64;
typedef u32 dma_addr_t;
typedef _Bool bool;
#define __iomem
