/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Samsung Electronics Co., Ltd. (2013) sdp_drm_util.h interface,
 * adapted for Linux 6.6.162 by the Q60T offline porting project.
 * This is a compile-only migration, not an integrated Samsung DRM stack.
 */
#ifndef _Q60T_SDP_DRM_UTIL_LINUX66_H
#define _Q60T_SDP_DRM_UTIL_LINUX66_H

#include <linux/compiler_types.h>
#include <linux/types.h>

int sdp_drm_copy_from_user(void *to, const void __user *from,
			   unsigned long count);
int sdp_drm_copy_to_user(void __user *to, const void *from,
			 unsigned long count);
void sdp_drm_wait(int msecs);
int sdp_drm_curr_pid(void);
const char *sdp_drm_curr_comm(void);

/* 32-bit hardware register helpers: register ownership still unverified. */
void writel_mask(u32 value, void __iomem *addr, u64 mask);
u32 readl_mask(void __iomem *addr, u64 mask);
u32 readl_mask2(void __iomem *addr, u64 mask);

#endif
