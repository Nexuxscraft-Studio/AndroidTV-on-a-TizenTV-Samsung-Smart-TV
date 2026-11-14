// SPDX-License-Identifier: GPL-2.0-only
/* Build 087: inert register/resource and GEM-DMA preparation layer for 6.6. */
#include <linux/errno.h>
#include <linux/io.h>
#include <linux/overflow.h>
#include <linux/platform_device.h>
#include <drm/drm_crtc.h>
#include <drm/drm_fourcc.h>
#include <drm/drm_fb_dma_helper.h>
#include <drm/drm_framebuffer.h>
#include <drm/drm_gem_dma_helper.h>
#include <drm/drm_gem_framebuffer_helper.h>
#include <drm/drm_plane.h>
#include "sdp_drm_hw.h"

/* Deliberately no DT/module-parameter override in Build 087. */
bool sdp_hw_access_allowed(void)
{
	return false;
}

/* Named resources prevent confusing OSDP with GP, as positional maps did. */
int sdp_hw_map_resources(struct platform_device *pdev, struct sdp_hw *hw)
{
	static const char * const names[] = { "osdp", "gp", "mixer" };
	static const resource_size_t bases[] = {
		SDP_OSDP_BASE, SDP_GP_BASE, SDP_MIXER_BASE,
	};
	struct resource *res;
	unsigned int i;

	/* Validate all banks before reserving any of them. Never perform IO. */
	for (i = 0; i < SDP_BANK_COUNT; i++) {
		res = platform_get_resource_byname(pdev, IORESOURCE_MEM, names[i]);
		if (!res || res->start != bases[i] ||
		    res->end < res->start ||
		    resource_size(res) != SDP_REG_WINDOW_SIZE)
			return -EINVAL;
	}
	for (i = 0; i < SDP_BANK_COUNT; i++) {
		hw->bank[i] = devm_platform_ioremap_resource_byname(pdev, names[i]);
		if (IS_ERR(hw->bank[i]))
			return PTR_ERR(hw->bank[i]);
	}
	return 0;
}

/*
 * A deliberately narrow linear, uncropped, unscaled software contract.
 * Keep DMA addresses wide until the complete span has passed the 32-bit gate.
 * No register encoding is inferred from the old boot-logo implementation.
 */
int sdp_hw_prepare_plane(const struct drm_plane_state *state,
			 const struct drm_crtc_state *crtc_state,
			 struct sdp_scanout *scanout)
{
	struct drm_framebuffer *fb = state->fb;
	struct drm_gem_dma_object *gem;
	u64 bytes, end, address;
	struct sdp_scanout next = { };

	if (!fb || !state->crtc || !crtc_state || !crtc_state->enable)
		return -EINVAL;
	if (fb->format->num_planes != 1 ||
	    (fb->format->format != DRM_FORMAT_XRGB8888 &&
	     fb->format->format != DRM_FORMAT_ARGB8888) ||
	    fb->modifier != DRM_FORMAT_MOD_LINEAR)
		return -EINVAL;
	if (!fb->width || !fb->height || fb->width > 65535 || fb->height > 65535 ||
	    fb->pitches[0] != fb->width * 4 || state->src_x || state->src_y ||
	    state->src_w != fb->width << 16 ||
	    state->src_h != fb->height << 16 ||
	    state->crtc_x || state->crtc_y ||
	    state->crtc_w != fb->width || state->crtc_h != fb->height ||
	    crtc_state->adjusted_mode.hdisplay != fb->width ||
	    crtc_state->adjusted_mode.vdisplay != fb->height ||
	    crtc_state->adjusted_mode.flags &
		(DRM_MODE_FLAG_INTERLACE | DRM_MODE_FLAG_DBLSCAN) ||
	    state->rotation != DRM_MODE_ROTATE_0)
		return -EINVAL;
	gem = drm_fb_dma_get_gem_obj(fb, 0);
	if (!gem)
		return -EINVAL;
	bytes = (u64)fb->pitches[0] * fb->height;
	if (check_add_overflow((u64)fb->offsets[0], bytes, &end) ||
	    end > gem->base.size)
		return -EINVAL;
	if (check_add_overflow((u64)gem->dma_addr, (u64)fb->offsets[0], &address) ||
	    check_add_overflow(address, bytes - 1, &end) || end > U32_MAX)
		return -ERANGE;
	/* Only natural pixel alignment is known; hardware alignment is still open. */
	if (address & 3)
		return -EINVAL;
	next.dma_addr = (dma_addr_t)address;
	next.width = fb->width;
	next.height = fb->height;
	next.pitch = fb->pitches[0];
	next.format = fb->format->format;
	*scanout = next;
	return 0;
}

/* No IRQ requested, no status reads, no mask/ack writes, no fake vblank. */
int sdp_hw_enable_vblank(void)
{
	return -EOPNOTSUPP;
}

void sdp_hw_disable_vblank(void)
{
}
