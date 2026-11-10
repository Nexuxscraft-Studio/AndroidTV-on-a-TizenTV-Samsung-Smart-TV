// SPDX-License-Identifier: GPL-2.0-only
#include "nike_cpu_model.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>

int main(void)
{
	struct nike_plan plan;
	int millidegrees = -1;
	unsigned int i;

	assert(nike_legacy_table_khz(0) == 1700000);
	assert(nike_legacy_table_khz(4) == 100000);
	assert(nike_divider_khz(4) == 125000);
	assert(nike_divider_khz(4) != nike_legacy_table_khz(4));
	assert(nike_divider_khz(0) == 0);
	assert(nike_divider_khz(1) == 1000000);
	assert(nike_divider_khz(2) == 500000);
	assert(nike_divider_khz(3) == 250000);
	for (i = 0; i < NIKE_LEVELS; i++) {
		assert(nike_transition_plan(i, i, &plan) == 0);
		assert(plan.step_count == 0);
	}
	assert(nike_transition_plan(0, 2, &plan) == 0);
	assert(plan.step_count == 2);
	assert(plan.actions[0] == NIKE_WRITE_DIVIDER);
	assert(plan.actions[1] == NIKE_SELECT_DVFS);
	assert(nike_transition_plan(2, 0, &plan) == 0);
	assert(plan.step_count == 1);
	assert(plan.actions[0] == NIKE_SELECT_PLL);
	assert(nike_transition_plan(2, 3, &plan) == -EOPNOTSUPP);
	assert(nike_transition_plan(0, 4, &plan) == -ERANGE);
	assert(nike_transition_plan(4, 0, &plan) == -ERANGE);
	assert(nike_transition_plan(1, 99, &plan) == -EINVAL);

	assert(nike_legacy_sensor_millicelsius(46, 46, &millidegrees) == 0);
	assert(millidegrees == 25000);
	assert(nike_legacy_sensor_millicelsius(46, 0, &millidegrees) == 0);
	assert(millidegrees == 25000);
	assert(nike_legacy_sensor_millicelsius(0, 46, &millidegrees) == 0);
	assert(millidegrees == 0);
	assert(nike_legacy_sensor_millicelsius(256, 46, &millidegrees) == -EINVAL);

	puts("PASS: offline Nike CPU/DVFS/TMU model (no hardware I/O)");
	return 0;
}
