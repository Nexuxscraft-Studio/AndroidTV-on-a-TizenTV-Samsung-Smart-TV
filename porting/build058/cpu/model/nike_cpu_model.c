// SPDX-License-Identifier: GPL-2.0-only
/* Portable offline evidence model. It has no I/O and cannot control a CPU. */
#include "nike_cpu_model.h"
#include <errno.h>
#include <stddef.h>

static const unsigned int samsung_table_khz[NIKE_LEVELS] = {
	1700000, 1000000, 500000, 250000, 100000,
};

unsigned int nike_legacy_table_khz(unsigned int level)
{
	return level < NIKE_LEVELS ? samsung_table_khz[level] : 0;
}

unsigned int nike_divider_khz(unsigned int level)
{
	/* Samsung source: 1-GHz DVFS parent / 2^(level - 1). */
	if (level < 1 || level >= NIKE_LEVELS)
		return 0;
	return 1000000U >> (level - 1U);
}

int nike_transition_plan(unsigned int old_level, unsigned int new_level,
			 struct nike_plan *plan)
{
	if (plan == NULL || old_level >= NIKE_LEVELS || new_level >= NIKE_LEVELS)
		return -EINVAL;
	plan->step_count = 0;
	if (old_level == new_level)
		return 0;

	/* L4 table 100 MHz != actual divider result 125 MHz. */
	if (old_level == 4 || new_level == 4)
		return -ERANGE;

	/* Samsung original does nothing for non-L0 -> non-L0 changes.
	 * A jump through L0 could overclock at an unsafe voltage. Refuse.
	 */
	if (old_level != 0 && new_level != 0)
		return -EOPNOTSUPP;

	if (old_level == 0) {
		plan->actions[0] = NIKE_WRITE_DIVIDER;
		plan->actions[1] = NIKE_SELECT_DVFS;
		plan->step_count = 2;
	} else {
		plan->actions[0] = NIKE_SELECT_PLL;
		plan->step_count = 1;
	}
	/* This is a read-only PLAN; regulator and MMIO operations not provided. */
	return 0;
}

int nike_legacy_sensor_millicelsius(unsigned int raw, unsigned int fuse,
				    int *millicelsius)
{
	int temp_c;

	if (millicelsius == NULL || raw > 255 || fuse > 255)
		return -EINVAL;
	/* Samsung TSC_DEGREE_25 == 46; fused 0 triggers fallback 46. */
	if (fuse == 0)
		fuse = 46;
	temp_c = (int)raw + 25 - (int)fuse;
	if (temp_c < 0)
		temp_c = 0;
	*millicelsius = temp_c * 1000;
	return 0;
}
