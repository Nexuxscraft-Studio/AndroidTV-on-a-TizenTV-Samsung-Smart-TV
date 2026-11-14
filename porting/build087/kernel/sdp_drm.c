// SPDX-License-Identifier: GPL-2.0-only
/* Build 087: compile-only KMS integration. Probe is unconditionally blocked. */
#include <linux/dma-mapping.h>
#include "sdp_drm_hw.h"
#include <linux/mod_devicetable.h>
#include <linux/module.h>
#include <linux/platform_device.h>

#include <drm/drm_atomic_helper.h>
#include <drm/drm_connector.h>
#include <drm/drm_drv.h>
#include <drm/drm_edid.h>
#include <drm/drm_fbdev_dma.h>
#include <drm/drm_fourcc.h>
#include <drm/drm_gem_dma_helper.h>
#include <drm/drm_gem_framebuffer_helper.h>
#include <drm/drm_managed.h>
#include <drm/drm_mode_config.h>
#include <drm/drm_modeset_helper_vtables.h>
#include <drm/drm_probe_helper.h>
#include <drm/drm_simple_kms_helper.h>
#include <drm/drm_vblank.h>

#define SDP_DRM_DEFAULT_WIDTH	1920
#define SDP_DRM_DEFAULT_HEIGHT	1080

struct sdp_drm_device {
	struct drm_device drm;
	struct sdp_hw hw;
	struct drm_simple_display_pipe pipe;
	struct drm_connector connector;
};

static const u32 sdp_drm_formats[] = {
	DRM_FORMAT_XRGB8888,
	DRM_FORMAT_ARGB8888,
};

/* Connector: expose one fixed mode. TODO: read real Nike-L panel timing. */
static int sdp_drm_conn_get_modes(struct drm_connector *connector)
{
	int count;

	count = drm_add_modes_noedid(connector, SDP_DRM_DEFAULT_WIDTH,
				     SDP_DRM_DEFAULT_HEIGHT);
	drm_set_preferred_mode(connector, SDP_DRM_DEFAULT_WIDTH,
			       SDP_DRM_DEFAULT_HEIGHT);
	return count;
}

static const struct drm_connector_helper_funcs sdp_drm_conn_helper_funcs = {
	.get_modes = sdp_drm_conn_get_modes,
};

static const struct drm_connector_funcs sdp_drm_conn_funcs = {
	.fill_modes = drm_helper_probe_single_connector_modes,
	.destroy = drm_connector_cleanup,
	.reset = drm_atomic_helper_connector_reset,
	.atomic_duplicate_state = drm_atomic_helper_connector_duplicate_state,
	.atomic_destroy_state = drm_atomic_helper_connector_destroy_state,
};

/* Simple display pipe: all hardware steps are TODO for a real bring-up. */
static void sdp_drm_pipe_enable(struct drm_simple_display_pipe *pipe,
				struct drm_crtc_state *crtc_state,
				struct drm_plane_state *plane_state)
{
	/* TODO: program the Nike-L display controller and enable the output. */
}

static void sdp_drm_pipe_disable(struct drm_simple_display_pipe *pipe)
{
	/* TODO: blank the Nike-L display controller. */
}

static void sdp_drm_pipe_update(struct drm_simple_display_pipe *pipe,
				struct drm_plane_state *old_state)
{
	/* TODO: flip to the new framebuffer and signal VSync/vblank. */
}

static int sdp_drm_pipe_check(struct drm_simple_display_pipe *pipe,
			      struct drm_plane_state *state,
			      struct drm_crtc_state *crtc_state)
{
	struct sdp_scanout prepared;

	if (!state->fb)
		return 0;
	return sdp_hw_prepare_plane(state, crtc_state, &prepared);
}

static int sdp_drm_enable_vblank(struct drm_simple_display_pipe *pipe)
{
	return sdp_hw_enable_vblank();
}

static void sdp_drm_disable_vblank(struct drm_simple_display_pipe *pipe)
{
	sdp_hw_disable_vblank();
}

static const u64 sdp_drm_modifiers[] = {
	DRM_FORMAT_MOD_LINEAR,
	DRM_FORMAT_MOD_INVALID,
};

static const struct drm_simple_display_pipe_funcs sdp_drm_pipe_funcs = {
	.check = sdp_drm_pipe_check,
	.enable_vblank = sdp_drm_enable_vblank,
	.disable_vblank = sdp_drm_disable_vblank,
	.enable = sdp_drm_pipe_enable,
	.disable = sdp_drm_pipe_disable,
	.update = sdp_drm_pipe_update,
};

static const struct drm_mode_config_funcs sdp_drm_mode_config_funcs = {
	.fb_create = drm_gem_fb_create,
	.atomic_check = drm_atomic_helper_check,
	.atomic_commit = drm_atomic_helper_commit,
};

DEFINE_DRM_GEM_DMA_FOPS(sdp_drm_fops);

static const struct drm_driver sdp_drm_driver = {
	.driver_features = DRIVER_GEM | DRIVER_MODESET | DRIVER_ATOMIC,
	.fops = &sdp_drm_fops,
	DRM_GEM_DMA_DRIVER_OPS,
	.name = "sdp-drm",
	.desc = "Samsung SDP Nike-L display (skeleton)",
	.date = "20261114",
	.major = 0,
	.minor = 1,
};

static int sdp_drm_probe(struct platform_device *pdev)
{
	struct sdp_drm_device *sdp;
	struct drm_device *drm;
	int ret;

	/* No DT property or module parameter may bypass this Build 087 gate. */
	if (!sdp_hw_access_allowed())
		return dev_err_probe(&pdev->dev, -EOPNOTSUPP,
			"Build 087 hardware access disabled pending register/IRQ validation\n");

	/* Future integration order, compiled for API coverage only. */
	sdp = devm_drm_dev_alloc(&pdev->dev, &sdp_drm_driver,
				 struct sdp_drm_device, drm);
	if (IS_ERR(sdp))
		return PTR_ERR(sdp);
	drm = &sdp->drm;
	platform_set_drvdata(pdev, drm);

	ret = dma_set_mask_and_coherent(&pdev->dev, DMA_BIT_MASK(32));
	if (ret)
		return ret;
	ret = sdp_hw_map_resources(pdev, &sdp->hw);
	if (ret)
		return ret;

	ret = drmm_mode_config_init(drm);
	if (ret)
		return ret;
	drm->mode_config.min_width = SDP_DRM_DEFAULT_WIDTH;
	drm->mode_config.max_width = SDP_DRM_DEFAULT_WIDTH;
	drm->mode_config.min_height = SDP_DRM_DEFAULT_HEIGHT;
	drm->mode_config.max_height = SDP_DRM_DEFAULT_HEIGHT;
	drm->mode_config.funcs = &sdp_drm_mode_config_funcs;

	drm_connector_helper_add(&sdp->connector, &sdp_drm_conn_helper_funcs);
	ret = drm_connector_init(drm, &sdp->connector, &sdp_drm_conn_funcs,
				 DRM_MODE_CONNECTOR_Unknown);
	if (ret)
		return ret;

	ret = drm_simple_display_pipe_init(drm, &sdp->pipe, &sdp_drm_pipe_funcs,
					   sdp_drm_formats,
					   ARRAY_SIZE(sdp_drm_formats), sdp_drm_modifiers,
					   &sdp->connector);
	if (ret)
		return ret;

	ret = drm_vblank_init(drm, 1);
	if (ret)
		return ret;

	drm_mode_config_reset(drm);

	ret = drm_dev_register(drm, 0);
	if (ret)
		return ret;

	drm_fbdev_dma_setup(drm, 32);
	return 0;
}

static int sdp_drm_remove(struct platform_device *pdev)
{
	struct drm_device *drm = platform_get_drvdata(pdev);

	drm_dev_unregister(drm);
	drm_atomic_helper_shutdown(drm);
	return 0;
}

static const struct of_device_id sdp_drm_of_match[] = {
	{ .compatible = "samsung,nikel-drm-hw-preparation" },
	{ }
};
MODULE_DEVICE_TABLE(of, sdp_drm_of_match);

static struct platform_driver sdp_drm_platform_driver = {
	.probe = sdp_drm_probe,
	.remove = sdp_drm_remove,
	.driver = {
		.name = "sdp-drm",
		.of_match_table = sdp_drm_of_match,
	},
};
module_platform_driver(sdp_drm_platform_driver);

MODULE_DESCRIPTION("Samsung SDP Nike-L display DRM/KMS skeleton (compile-only)");
MODULE_LICENSE("GPL");
