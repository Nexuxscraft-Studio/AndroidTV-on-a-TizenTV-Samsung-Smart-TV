/* SPDX-License-Identifier: GPL-2.0-only */
#include "sdp_drm_test_pattern.h"

static int build108_plan_test(void)
{
	const u32 xrgb = 0x34325258U; /* Linux FourCC XR24 */
	const u32 last = 0xffffffffU - (1920U * 1080U * 4U - 1U);
	const struct {
		u32 address, width, height, pitch, format;
		int result;
	} cases[] = {
		{ 0x10000000, 1920, 1080, 7680, xrgb, 0 },
		{ last,       1920, 1080, 7680, xrgb, 0 },
		{ last + 4,   1920, 1080, 7680, xrgb, -ERANGE },
		{ last - 1,   1920, 1080, 7680, xrgb, -ERANGE },
		{ last,       1919, 1080, 7680, xrgb, -EINVAL },
		{ last,       1920, 1081, 7680, xrgb, -EINVAL },
		{ last,       1920, 1080, 7684, xrgb, -EINVAL },
		{ last,       1920, 1080, 7680, 0x34325241U, -EINVAL },
	};
	unsigned int i;

	for (i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
		struct sdp_scanout scanout = {
			.dma_addr = cases[i].address, .width = cases[i].width,
			.height = cases[i].height, .pitch = cases[i].pitch,
			.format = cases[i].format,
		};
		struct sdp_test_plan plan = { .dma_address = 0xdeadbeef };
		int ret = sdp_test_prepare_scanout(&scanout, xrgb, &plan);

		if (ret != cases[i].result)
			return 1;
		if (ret) {
			if (plan.dma_address != 0xdeadbeef)
				return 1;
			continue;
		}
		if (plan.dma_address != cases[i].address ||
		    sizeof(plan.geometry) / sizeof(plan.geometry[0]) != 3 ||
		    plan.geometry[0].bank != SDP_GP ||
		    plan.geometry[1].bank != SDP_GP ||
		    plan.geometry[2].bank != SDP_GP ||
		    plan.geometry[0].offset != 0x10 ||
		    plan.geometry[1].offset != 0x14 ||
		    plan.geometry[2].offset != 0x18 ||
		    plan.geometry[0].value != 0x07800438 ||
		    plan.geometry[1].value != 0x07800438 ||
		    plan.geometry[2].value != 480)
			return 1;
	}
	if (sdp_test_prepare_plan(0x100000000ULL, &(struct sdp_test_plan){}) != -ERANGE)
		return 1;
	out("BUILD108_GP_PLAN_OK cases=9\n");
	return 0;
}
