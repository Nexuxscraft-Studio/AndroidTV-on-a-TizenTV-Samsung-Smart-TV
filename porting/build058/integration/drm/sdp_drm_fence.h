/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Samsung Electronics Co., Ltd. (2013) sdp_drm_fence.h interface,
 * migrated from struct fence to Linux 6.6 struct dma_fence.
 * API migration only: does not imply a functioning Samsung DRM driver.
 */
#ifndef _Q60T_SDP_DRM_FENCE_LINUX66_H
#define _Q60T_SDP_DRM_FENCE_LINUX66_H

#include <linux/atomic.h>
#include <linux/dma-fence.h>
#include <linux/kref.h>
#include <linux/spinlock.h>

struct sdp_fence_context {
	u64 context;
	char *name;
	atomic_t seqno;
	atomic_t fence_count;
	struct kref refs;
};

struct sdp_fence {
	struct sdp_fence_context *fence_context;
	struct dma_fence base;
	spinlock_t lock;
};

struct sdp_fence_context *sdp_fence_context_create(const char *name);
/* Caller must stop producing new fences before destroying the owner ref. */
void sdp_fence_context_destroy(struct sdp_fence_context *ctx);
struct dma_fence *sdp_fence_create(struct sdp_fence_context *ctx);

#endif
