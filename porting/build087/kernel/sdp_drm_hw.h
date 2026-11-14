/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef SDP_DRM_HW_H
#define SDP_DRM_HW_H

#include <linux/types.h>

struct platform_device;
struct drm_plane_state;
struct drm_crtc_state;

/* Byte offsets, not vendor 32-bit register indices. */
#define SDP_OSDP_BASE                 0x005d0000
#define SDP_GP_BASE                   0x005d4000
#define SDP_MIXER_BASE                0x005d8000
#define SDP_REG_WINDOW_SIZE           0x4000
#define SDP_GP_PLANE_ENABLE           0x00
#define SDP_GP_SOURCE_SIZE            0x10
#define SDP_GP_DESTINATION_SIZE       0x14
#define SDP_GP_SOURCE_OFFSET          0x18
#define SDP_GP_FRAMEBUFFER_A1         0x30
#define SDP_GP_REGISTER_UPDATE        0x54
#define SDP_MIXER_IRQ_CLEAR           0x08
#define SDP_MIXER_IRQ_MASK            0x0c

enum sdp_register_bank { SDP_OSDP, SDP_GP, SDP_MIXER, SDP_BANK_COUNT };

struct sdp_hw {
	void __iomem *bank[SDP_BANK_COUNT];
};

/* Software description only: no enable, format or latch bitfields inferred. */
struct sdp_scanout {
	dma_addr_t dma_addr;
	u32 width, height, pitch, format;
};

bool sdp_hw_access_allowed(void);
int sdp_hw_map_resources(struct platform_device *pdev, struct sdp_hw *hw);
int sdp_hw_prepare_plane(const struct drm_plane_state *state,
			 const struct drm_crtc_state *crtc_state,
			 struct sdp_scanout *scanout);
int sdp_hw_enable_vblank(void);
void sdp_hw_disable_vblank(void);
#endif
