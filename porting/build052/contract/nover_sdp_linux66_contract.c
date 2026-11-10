// SPDX-License-Identifier: GPL-2.0-only
/*
 * Build 052 - compile-only DRM/GEM API contract for Linux 6.6.
 *
 * This is NOT the Samsung display driver. The real Samsung KMS, GEM,
 * clocks, DMA, connectors, panel, and boot-chain are not yet ported.
 *
 * There is intentionally no platform driver, device-tree match or
 * DRM registration on the live device. Module init always fails.
 */

#include <linux/err.h>
#include <linux/init.h>
#include <linux/module.h>
#include <linux/slab.h>

#include <drm/drm_device.h>
#include <drm/drm_drv.h>
#include <drm/drm_gem.h>

static void nover_sdp52_gem_free(struct drm_gem_object *object)
{
	drm_gem_object_release(object);
	kfree(object);
}

static const struct drm_gem_object_funcs nover_sdp52_gem_ops = {
	.free = nover_sdp52_gem_free,
};

static struct drm_gem_object *
nover_sdp52_gem_create(struct drm_device *drm, size_t size)
{
	struct drm_gem_object *object;
	int error;

	object = kzalloc(sizeof(*object), GFP_KERNEL);
	if (!object)
		return ERR_PTR(-ENOMEM);

	object->funcs = &nover_sdp52_gem_ops;
	error = drm_gem_object_init(drm, object, size);
	if (error) {
		kfree(object);
		return ERR_PTR(error);
	}

	return object;
}

DEFINE_DRM_GEM_FOPS(nover_sdp52_file_ops);

static const struct drm_driver nover_sdp52_driver = {
	.driver_features = DRIVER_GEM,
	.gem_create_object = nover_sdp52_gem_create,
	.fops = &nover_sdp52_file_ops,
	.name = "nover-sdp52-contract",
	.desc = "Samsung Nike-L Linux 6.6 API compile contract only",
	.date = "20261110",
	.major = 0,
	.minor = 52,
};

/*
 * Compiler-checked API migration sketch, never called by module_init.
 * A real driver must initialize the hardware, GEM, KMS and connectors
 * before drm_dev_register() and tear them down in reverse order.
 */
static int __maybe_unused nover_sdp52_registration_contract(struct device *parent)
{
	struct drm_device *drm;
	int error;

	drm = drm_dev_alloc(&nover_sdp52_driver, parent);
	if (IS_ERR(drm))
		return PTR_ERR(drm);

	error = drm_dev_register(drm, 0);
	if (!error)
		drm_dev_unregister(drm);
	drm_dev_put(drm);

	return error;
}

static int __init nover_sdp52_contract_init(void)
{
	/* Deliberate hard stop: never load or probe Samsung hardware. */
	return -ENODEV;
}

module_init(nover_sdp52_contract_init);

MODULE_DESCRIPTION("Nover Samsung Build 052 API compile contract - never load");
MODULE_LICENSE("GPL");
