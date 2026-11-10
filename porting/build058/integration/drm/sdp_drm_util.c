// SPDX-License-Identifier: GPL-2.0-only
/*
 * Samsung Electronics Co., Ltd. (2013) sdp_drm_util.c, Linux 4.1.10.
 * Build 058: a limited, reworked Linux 6.6.162 port of the real Samsung
 * utility functions. DO NOT load on hardware or treat this as working DRM.
 *
 * Differences: removed drmP.h; bounded user copies; msleep instead of the
 * old schedule_timeout state sequence; portable shift instead of ARM asm;
 * explicit validation of empty 32-bit register masks.
 *
 * Samsung's proprietary high-mask flag (bit 32) has not been validated.
 * The register helper here only implements the low 32-bit masked RMW form.
 */
#include <linux/bitops.h>
#include <linux/delay.h>
#include <linux/errno.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/printk.h>
#include <linux/sched.h>
#include <linux/sched/task.h>
#include <linux/uaccess.h>

#include "sdp_drm_util.h"

int sdp_drm_copy_from_user(void *to, const void __user *from,
			   unsigned long count)
{
	/* The Samsung retry loop could spin forever on an invalid address. */
	return copy_from_user(to, from, count) ? -EFAULT : 0;
}
EXPORT_SYMBOL_GPL(sdp_drm_copy_from_user);

int sdp_drm_copy_to_user(void __user *to, const void *from,
			 unsigned long count)
{
	return copy_to_user(to, from, count) ? -EFAULT : 0;
}
EXPORT_SYMBOL_GPL(sdp_drm_copy_to_user);

void sdp_drm_wait(int msecs)
{
	if (msecs > 0)
		msleep(msecs);
}
EXPORT_SYMBOL_GPL(sdp_drm_wait);

int sdp_drm_curr_pid(void)
{
	return task_pid_nr(current);
}
EXPORT_SYMBOL_GPL(sdp_drm_curr_pid);

const char *sdp_drm_curr_comm(void)
{
	return current->comm;
}
EXPORT_SYMBOL_GPL(sdp_drm_curr_comm);

void writel_mask(u32 value, void __iomem *addr, u64 mask)
{
	u32 mask32 = (u32)mask;
	u32 regval;

	/* Only low-32-bit masks are implemented in this offline helper. */
	if (WARN_ON_ONCE(!addr || !mask32 || (mask >> 32)))
		return;

	regval = readl(addr);
	regval &= ~mask32;
	regval |= (value << __ffs(mask32)) & mask32;
	writel(regval, addr);
}
EXPORT_SYMBOL_GPL(writel_mask);

u32 readl_mask(void __iomem *addr, u64 mask)
{
	u32 mask32 = (u32)mask;

	if (WARN_ON_ONCE(!addr || !mask32 || (mask >> 32)))
		return 0;
	return (readl(addr) & mask32) >> __ffs(mask32);
}
EXPORT_SYMBOL_GPL(readl_mask);

u32 readl_mask2(void __iomem *addr, u64 mask)
{
	/* Replaces the architecture-specific ARM CLZ inline assembler. */
	return readl_mask(addr, mask);
}
EXPORT_SYMBOL_GPL(readl_mask2);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Compile-only Samsung SDP DRM utility port for Linux 6.6");
