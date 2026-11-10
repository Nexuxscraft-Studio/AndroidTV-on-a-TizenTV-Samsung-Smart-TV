// SPDX-License-Identifier: GPL-2.0-only
/*
 * Build 058: Nike CPU clock provider API prototype for Linux 6.6.162.
 * Register meanings are REFERENCED from Samsung Linux 4.1.10, not validated
 * for the Nike-L Q60T silicon. This driver cannot bind or touch hardware.
 */
#include <linux/bitops.h>
#include <linux/clk-provider.h>
#include <linux/err.h>
#include <linux/io.h>
#include <linux/kernel.h>
#include <linux/math64.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/slab.h>

#define NIKEL_CPU_BUILD058_OFFLINE_ONLY 1

#define NIKEL_CPU_PLL_PMS_OFFSET       0x001c
#define NIKEL_CPU_PLL_K_OFFSET         0x0020 /* not decoded in original get_speed */
#define NIKEL_CPU_DVFS_CTRL_OFFSET     0x0008
#define NIKEL_CPU_SEL_ARM_VS_DVFS      BIT(8)
#define NIKEL_CPU_DVFS_SHIFT           12
#define NIKEL_CPU_DVFS_MASK            GENMASK(13, 12)
#define NIKEL_CPU_PLL_M_SHIFT          8
#define NIKEL_CPU_PLL_M_MASK           GENMASK(17, 8)
#define NIKEL_CPU_PLL_P_SHIFT          20
#define NIKEL_CPU_PLL_P_MASK           GENMASK(25, 20)
#define NIKEL_CPU_PLL_S_MASK           GENMASK(2, 0)
#define NIKEL_CPU_DVFS_BASE_HZ         1000000000UL

struct nikel_cpu_clk {
	struct clk_hw hw;
	void __iomem *clock_base;
	void __iomem *pmu_base;
};

static unsigned long nikel_cpu_recalc_rate(struct clk_hw *hw,
					   unsigned long parent_rate)
{
	struct nikel_cpu_clk *cpu_clk = container_of(hw, struct nikel_cpu_clk, hw);
	u32 ctrl = readl(cpu_clk->pmu_base + NIKEL_CPU_DVFS_CTRL_OFFSET);
	u32 div = (ctrl & NIKEL_CPU_DVFS_MASK) >> NIKEL_CPU_DVFS_SHIFT;
	u32 pms, m, p, s;
	u64 hz;

	if (!(ctrl & NIKEL_CPU_SEL_ARM_VS_DVFS))
		return NIKEL_CPU_DVFS_BASE_HZ >> div;

	if (!parent_rate)
		return 0; /* Do not invent a 24.576-MHz parent clock. */
	pms = readl(cpu_clk->clock_base + NIKEL_CPU_PLL_PMS_OFFSET);
	m = (pms & NIKEL_CPU_PLL_M_MASK) >> NIKEL_CPU_PLL_M_SHIFT;
	p = (pms & NIKEL_CPU_PLL_P_MASK) >> NIKEL_CPU_PLL_P_SHIFT;
	s = pms & NIKEL_CPU_PLL_S_MASK;
	if (!p || !m)
		return 0;

	/* Reproduces Samsung's integer-PMS/100-MHz rounding as an estimate.
	 * Fractional PLL-K and hardware-specific timings are NOT validated.
	 */
	hz = (((u64)parent_rate >> s) / p) * m;
	return div64_u64(hz + 50000000ULL, 100000000ULL) * 100000000ULL;
}

static int nikel_cpu_set_rate(struct clk_hw *hw, unsigned long rate,
			      unsigned long parent_rate)
{
	/* No PLL, PMU or regulator writes before Nike-L validation. */
	(void)hw;
	(void)rate;
	(void)parent_rate;
	return -EOPNOTSUPP;
}

static const struct clk_ops nikel_cpu_clk_ops = {
	.recalc_rate = nikel_cpu_recalc_rate,
	.set_rate = nikel_cpu_set_rate,
};

static struct clk_hw *nikel_cpu_clk_of_get(struct of_phandle_args *args,
					   void *data)
{
	struct nikel_cpu_clk *cpu_clk = data;

	if (args->args_count != 1 || args->args[0] != 0)
		return ERR_PTR(-EINVAL);
	return &cpu_clk->hw;
}

static int nikel_cpu_clk_probe(struct platform_device *pdev)
{
	struct nikel_cpu_clk *cpu_clk;
	struct clk_init_data init = {
		.name = "nikel-cpu-clock-unverified",
		.ops = &nikel_cpu_clk_ops,
		.num_parents = 0, /* exact Nike-L parent not established */
	};
	int ret;

#if NIKEL_CPU_BUILD058_OFFLINE_ONLY
	return dev_err_probe(&pdev->dev, -EOPNOTSUPP,
			     "CPU clock Build 058 is offline-only\n");
#endif

	cpu_clk = devm_kzalloc(&pdev->dev, sizeof(*cpu_clk), GFP_KERNEL);
	if (!cpu_clk)
		return -ENOMEM;
	cpu_clk->clock_base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(cpu_clk->clock_base))
		return PTR_ERR(cpu_clk->clock_base);
	cpu_clk->pmu_base = devm_platform_ioremap_resource(pdev, 1);
	if (IS_ERR(cpu_clk->pmu_base))
		return PTR_ERR(cpu_clk->pmu_base);
	cpu_clk->hw.init = &init;
	ret = devm_clk_hw_register(&pdev->dev, &cpu_clk->hw);
	if (ret)
		return ret;
	return devm_of_clk_add_hw_provider(&pdev->dev, nikel_cpu_clk_of_get, cpu_clk);
}

static const struct of_device_id nikel_cpu_clk_of_match[] = {
	{ .compatible = "nover,nikel-cpu-clock-offline" },
	{ }
};
MODULE_DEVICE_TABLE(of, nikel_cpu_clk_of_match);

static struct platform_driver nikel_cpu_clk_driver = {
	.probe = nikel_cpu_clk_probe,
	.driver = {
		.name = "nikel-cpu-clk-offline",
		.of_match_table = nikel_cpu_clk_of_match,
	},
};
module_platform_driver(nikel_cpu_clk_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Fail-closed Nike-L CPU clock reference for Linux 6.6.162");
