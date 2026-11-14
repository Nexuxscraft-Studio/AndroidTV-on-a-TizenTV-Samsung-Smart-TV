// SPDX-License-Identifier: GPL-2.0-only
/*
 * Build 058: dedicated Nike CPUFreq API skeleton (Linux 6.6.162).
 * Samsung 4.1.10's table and voltage groups are evidence only, NOT OPPs.
 * This module is hard-blocked before cpufreq registration and all hardware.
 */
#include <linux/cpufreq.h>
#include <linux/err.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

#define NIKEL_CPU_BUILD058_OFFLINE_ONLY 1

/* Intentionally no cpufreq_frequency_table / operating-points table.
 * Nike-M/L source: L4 table says 100 MHz, divider yields 125 MHz.
 * Old firmware cannot transition L1<->L2/L3/L4 directly (no temp clock).
 * The ASV bin, regulator named CPU_PW and voltage ordering remain unverified.
 */
/* Linux 6.6 uses cpufreq_policy_data for ->verify, not cpufreq_policy. */
static int nikel_cpu_verify(struct cpufreq_policy_data *policy)
{
	(void)policy;
	return -EOPNOTSUPP;
}

static int nikel_cpu_policy_init(struct cpufreq_policy *policy)
{
	(void)policy;
	return -EOPNOTSUPP;
}

static unsigned int nikel_cpu_get(unsigned int cpu)
{
	(void)cpu;
	return 0; /* No fabricating a CPU clock rate. */
}

static int nikel_cpu_target_index(struct cpufreq_policy *policy,
				  unsigned int index)
{
	/* No direct non-L0 -> non-L0 transition; no unverified voltage writes.
	 * Future implementation must use an explicit, validated state machine.
	 */
	(void)policy;
	(void)index;
	return -EOPNOTSUPP;
}

static struct cpufreq_driver nikel_cpu_freq_driver = {
	/* CPUFREQ_NAME_LEN is 16 bytes, including the terminating NUL. */
	.name = "sdp-nikel-off",
	.verify = nikel_cpu_verify,
	.init = nikel_cpu_policy_init,
	.get = nikel_cpu_get,
	.target_index = nikel_cpu_target_index,
};

static int nikel_cpufreq_probe(struct platform_device *pdev)
{
#if NIKEL_CPU_BUILD058_OFFLINE_ONLY
	return dev_err_probe(&pdev->dev, -EOPNOTSUPP,
			     "CPUFreq Build 058 has no validated OPPs\n");
#endif
	return cpufreq_register_driver(&nikel_cpu_freq_driver);
}

static int nikel_cpufreq_remove(struct platform_device *pdev)
{
	(void)pdev;
	cpufreq_unregister_driver(&nikel_cpu_freq_driver);
	return 0;
}

static const struct of_device_id nikel_cpufreq_of_match[] = {
	{ .compatible = "nover,nikel-cpufreq-offline" },
	{ }
};
MODULE_DEVICE_TABLE(of, nikel_cpufreq_of_match);

static struct platform_driver nikel_cpufreq_platform_driver = {
	.probe = nikel_cpufreq_probe,
	.remove = nikel_cpufreq_remove,
	.driver = {
		.name = "sdp-nikel-cpufreq-offline",
		.of_match_table = nikel_cpufreq_of_match,
	},
};
module_platform_driver(nikel_cpufreq_platform_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Fail-closed Nike-L CPUFreq API prototype for Linux 6.6.162");
