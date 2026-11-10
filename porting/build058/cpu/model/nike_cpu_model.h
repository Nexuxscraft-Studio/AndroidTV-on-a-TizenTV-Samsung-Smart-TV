/* SPDX-License-Identifier: GPL-2.0-only */
/* Pure CPU transition model derived from Samsung 4.1.10; never accesses HW. */
#ifndef NIKE_CPU_MODEL_H
#define NIKE_CPU_MODEL_H

#define NIKE_LEVELS 5
#define NIKE_MAX_STEPS 2

enum nike_action {
	NIKE_WRITE_DIVIDER,
	NIKE_SELECT_DVFS,
	NIKE_SELECT_PLL,
};

struct nike_plan {
	unsigned int step_count;
	enum nike_action actions[NIKE_MAX_STEPS];
};

unsigned int nike_legacy_table_khz(unsigned int level);
unsigned int nike_divider_khz(unsigned int level);
int nike_transition_plan(unsigned int old_level, unsigned int new_level,
			 struct nike_plan *plan);
int nike_legacy_sensor_millicelsius(unsigned int raw, unsigned int fuse,
				    int *millicelsius);

#endif
