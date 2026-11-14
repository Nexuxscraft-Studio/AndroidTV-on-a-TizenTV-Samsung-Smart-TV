/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef BUILD107_PATTERN_H
#define BUILD107_PATTERN_H

#define BUILD107_WIDTH 1920U
#define BUILD107_HEIGHT 1080U
#define BUILD107_PITCH (BUILD107_WIDTH * 4U)
#define BUILD107_BYTES (BUILD107_PITCH * BUILD107_HEIGHT)

/* DRM_FORMAT_XRGB8888, serialized little endian; four 480 px bars. */
static inline unsigned int build107_pixel(unsigned int x)
{
	static const unsigned int colors[] = {
		0x00ff0000, 0x0000ff00, 0x000000ff, 0x00ffffff,
	};

	return colors[x / (BUILD107_WIDTH / 4U)];
}

#endif
