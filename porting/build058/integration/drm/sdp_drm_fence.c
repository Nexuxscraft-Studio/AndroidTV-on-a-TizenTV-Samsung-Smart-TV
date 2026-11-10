// SPDX-License-Identifier: GPL-2.0-only
/*
 * Samsung Electronics Co., Ltd. (2013) sdp_drm_fence.c (GPLv2).
 * Build 058 Linux 6.6 port: modern DMA fences with a safe context lifetime.
 * No GPU jobs, interrupts, or actual fence signal path are implemented.
 */
#include <linux/atomic.h>
#include <linux/dma-fence.h>
#include <linux/errno.h>
#include <linux/kref.h>
#include <linux/module.h>
#include <linux/slab.h>
#include <linux/spinlock.h>

#include "sdp_drm_fence.h"

#define to_sdp_fence(fence) container_of(fence, struct sdp_fence, base)

static void sdp_fence_context_release(struct kref *ref)
{
	struct sdp_fence_context *ctx =
		container_of(ref, struct sdp_fence_context, refs);

	kfree(ctx->name);
	kfree(ctx);
}

struct sdp_fence_context *sdp_fence_context_create(const char *name)
{
	struct sdp_fence_context *ctx;

	ctx = kzalloc(sizeof(*ctx), GFP_KERNEL);
	if (!ctx)
		return NULL;
	ctx->name = kstrdup(name ? name : "sdp.gfx", GFP_KERNEL);
	if (!ctx->name) {
		kfree(ctx);
		return NULL;
	}
	ctx->context = dma_fence_context_alloc(1);
	atomic_set(&ctx->seqno, 0);
	atomic_set(&ctx->fence_count, 0);
	kref_init(&ctx->refs);
	return ctx;
}
EXPORT_SYMBOL_GPL(sdp_fence_context_create);

void sdp_fence_context_destroy(struct sdp_fence_context *ctx)
{
	if (!ctx)
		return;
	/* Unlike Samsung's original, live fences keep the context allocated. */
	WARN_ON(atomic_read(&ctx->fence_count));
	kref_put(&ctx->refs, sdp_fence_context_release);
}
EXPORT_SYMBOL_GPL(sdp_fence_context_destroy);

static const char *sdp_fence_get_driver_name(struct dma_fence *fence)
{
	(void)fence;
	return "sdp.gfx";
}

static const char *sdp_fence_get_timeline_name(struct dma_fence *fence)
{
	return to_sdp_fence(fence)->fence_context->name;
}

static bool sdp_fence_enable_signaling(struct dma_fence *fence)
{
	(void)fence;
	/* No IRQ/worker signal integration; this returns the Samsung default. */
	return true;
}

static void sdp_fence_release(struct dma_fence *fence)
{
	struct sdp_fence *sf = to_sdp_fence(fence);
	struct sdp_fence_context *ctx = sf->fence_context;

	atomic_dec(&ctx->fence_count);
	kfree(sf);
	kref_put(&ctx->refs, sdp_fence_context_release);
}

static const struct dma_fence_ops sdp_fence_ops = {
	.get_driver_name = sdp_fence_get_driver_name,
	.get_timeline_name = sdp_fence_get_timeline_name,
	.enable_signaling = sdp_fence_enable_signaling,
	.wait = dma_fence_default_wait,
	.release = sdp_fence_release,
};

struct dma_fence *sdp_fence_create(struct sdp_fence_context *ctx)
{
	struct sdp_fence *sf;
	u32 seqno;

	if (!ctx)
		return NULL;
	/* Caller must hold an owner reference while creating new fences. */
	sf = kzalloc(sizeof(*sf), GFP_KERNEL);
	if (!sf)
		return NULL;

	spin_lock_init(&sf->lock);
	sf->fence_context = ctx;
	kref_get(&ctx->refs);
	seqno = (u32)atomic_inc_return(&ctx->seqno) - 1;
	atomic_inc(&ctx->fence_count);
	dma_fence_init(&sf->base, &sdp_fence_ops, &sf->lock,
		       ctx->context, seqno);
	return &sf->base;
}
EXPORT_SYMBOL_GPL(sdp_fence_create);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Compile-only Samsung SDP DRM DMA fence API port");
