/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <stdint.h>

#include "sdp_drm_hw.h"

/* The GEM and test-pattern paths share this aperture check. */
int main(void)
{
	const u64 boundary = UINT64_C(0x100000000);

	assert(sdp_scanout_check_dma_span(0, boundary) == 0);
	assert(sdp_scanout_check_dma_span(boundary - 4, 4) == 0);
	assert(sdp_scanout_check_dma_span(boundary - 4, 5) == -ERANGE);
	assert(sdp_scanout_check_dma_span(boundary, 1) == -ERANGE);
	assert(sdp_scanout_check_dma_span(0, 0) == -ERANGE);
	assert(sdp_scanout_check_dma_span(4, UINT64_MAX) == -ERANGE);
	assert(sdp_scanout_check_dma_span(1, 4) == -EINVAL);
	return 0;
}
