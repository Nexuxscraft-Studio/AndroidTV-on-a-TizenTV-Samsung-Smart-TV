/* SPDX-License-Identifier: GPL-2.0-only */
#include "pattern.h"

/* RAM only: the same pixel function as the gated SDP DRM DMA fill. */
static int build107_pattern_test(void)
{
	static unsigned char frame[BUILD107_BYTES];
	static const unsigned char expected[][4] = {
		{0, 0, 255, 0}, {0, 255, 0, 0},
		{255, 0, 0, 0}, {255, 255, 255, 0},
	};
	unsigned int x, y, b, hash = 2166136261U;

	for (y = 0; y < BUILD107_HEIGHT; y++)
		for (x = 0; x < BUILD107_WIDTH; x++) {
			unsigned int pixel = build107_pixel(x);
			unsigned char *p = frame + y * BUILD107_PITCH + x * 4U;

			for (b = 0; b < 4; b++)
				p[b] = pixel >> (8U * b);
		}

	for (y = 0; y < 1080; y++)
		for (x = 0; x < 1920; x++)
			for (b = 0; b < 4; b++) {
				unsigned char v = frame[y * 7680 + x * 4 + b];

				if (v != expected[x / 480][b])
					return 1;
				hash = (hash ^ v) * 16777619U;
			}

	out("BUILD107_PATTERN_OK width=1920 height=1080 pitch=7680 fnv1a=");
	num(hash >> 16);
	out(":");
	num(hash & 65535U);
	out("\n");
	return 0;
}
