/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "sdp_drm_test_pattern.h"

int main(void)
{
	static const u32 colors[] = {
		0xffffff, 0xffff00, 0x00ffff, 0x00ff00,
		0xff00ff, 0xff0000, 0x0000ff, 0x000000,
	};
	static const struct sdp_test_register expected[] = {
		{ SDP_GP, 0x10, 0x07800438 },
		{ SDP_GP, 0x14, 0x07800438 },
		{ SDP_GP, 0x18, 480 },
		{ SDP_OSDP, 0x10, 0x07800438 },
		{ SDP_OSDP, 0x14, 0x07800438 },
		{ SDP_OSDP, 0x18, 480 },
		{ SDP_MIXER, 0x20, 0x07800438 },
	};
	const u64 last_base = UINT64_C(0x100000000) - 8294400;
	struct sdp_test_plan plan;
	unsigned char snapshot[sizeof(plan)];
	unsigned int x, y, i;

	assert(SDP_TEST_PITCH == 7680 && SDP_TEST_BYTES == 8294400);
	for (y = 0; y < 1080; y++) {
		for (x = 0; x < 1920; x++) {
			u32 pixel = colors[x / 240];

			if (!x || x == 1919 || !y || y == 1079)
				pixel = 0x808080;
			assert(sdp_test_pixel(x, y) == pixel);
		}
	}
	assert(sdp_test_prepare_plan(0, &plan) == 0);
	assert(sdp_test_prepare_plan(last_base, &plan) == 0);
	assert(plan.gp_dma_address == last_base);
	for (i = 0; i < sizeof(expected) / sizeof(expected[0]); i++) {
		assert(plan.geometry[i].bank == expected[i].bank);
		assert(plan.geometry[i].offset == expected[i].offset);
		assert(plan.geometry[i].value == expected[i].value);
	}
	memcpy(snapshot, &plan, sizeof(plan));
	assert(sdp_test_prepare_plan(last_base + 4, &plan) == -ERANGE);
	assert(sdp_test_prepare_plan(1, &plan) == -ERANGE);
	assert(sdp_test_prepare_plan(UINT64_C(0x100000000), &plan) == -ERANGE);
	assert(sdp_test_prepare_plan(UINT64_MAX, &plan) == -ERANGE);
	assert(memcmp(snapshot, &plan, sizeof(plan)) == 0);

	puts("1080p pixel, geometry and DMA boundary tests passed");
	return 0;
}
