// SPDX-License-Identifier: GPL-2.0-only
/*
 * Build 058: Samsung SDP thermal sensor API prototype (Linux 6.6.162).
 * This model derives its formula from Samsung sdp_thermal.c, but has no
 * validated Nike-L calibration/initialization. probe() always refuses bind.
 */
#include <linux/err.h>
#include <linux/io.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/slab.h>
#include <linux/thermal.h>

#define NIKEL_CPU_BUILD058_OFFLINE_ONLY 1

#define NIKEL_TMU_TEMP_OFFSET         0x000c
#define NIKEL_TMU_TEMP_SHIFT          12
#define NIKEL_TMU_TEMP_MASK           0x000000ff
#define NIKEL_TMU_CHIPID_OFFSET       0x0010
#define NIKEL_TMU_FUSE_SHIFT          17
#define NIKEL_TMU_FUSE_MASK           0x000000ff
#define NIKEL_TMU_FUSE_DEFAULT        46

struct nikel_tmu {
	void __iomem *tmu_base;
	void __iomem *chipid_base;
};

static int nikel_tmu_get_temp(struct thermal_zone_device *zone, int *temp)
{
	struct nikel_tmu *tmu = thermal_zone_device_priv(zone);
	u32 raw, fused;
	int temp_c;

	raw = (readl(tmu->tmu_base + NIKEL_TMU_TEMP_OFFSET) >>
	       NIKEL_TMU_TEMP_SHIFT) & NIKEL_TMU_TEMP_MASK;
	fused = (readl(tmu->chipid_base + NIKEL_TMU_CHIPID_OFFSET) >>
		 NIKEL_TMU_FUSE_SHIFT) & NIKEL_TMU_FUSE_MASK;
	if (!fused)
		fused = NIKEL_TMU_FUSE_DEFAULT;

	/* Samsung: diff=46-fused; temp=raw+diff-(46-25). */
	temp_c = (int)raw + 25 - (int)fused;
	*temp = max(temp_c, 0) * 1000; /* Linux thermal API: millidegrees C */
	return 0;
}

static const struct thermal_zone_device_ops nikel_tmu_ops = {
	.get_temp = nikel_tmu_get_temp,
};

static int nikel_tmu_probe(struct platform_device *pdev)
{
	struct nikel_tmu *tmu;
	struct thermal_zone_device *zone;

#if NIKEL_CPU_BUILD058_OFFLINE_ONLY
	return dev_err_probe(&pdev->dev, -EOPNOTSUPP,
			     "SDP TMU Build 058 not calibrated for Nike-L\n");
#endif
	tmu = devm_kzalloc(&pdev->dev, sizeof(*tmu), GFP_KERNEL);
	if (!tmu)
		return -ENOMEM;
	tmu->tmu_base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(tmu->tmu_base))
		return PTR_ERR(tmu->tmu_base);
	tmu->chipid_base = devm_platform_ioremap_resource(pdev, 1);
	if (IS_ERR(tmu->chipid_base))
		return PTR_ERR(tmu->chipid_base);

	/* Does not initialize the TMU hardware or enable active cooling. */
	zone = devm_thermal_of_zone_register(&pdev->dev, 0, tmu, &nikel_tmu_ops);
	return PTR_ERR_OR_ZERO(zone);
}

static const struct of_device_id nikel_tmu_of_match[] = {
	{ .compatible = "nover,nikel-thermal-offline" },
	{ }
};
MODULE_DEVICE_TABLE(of, nikel_tmu_of_match);

static struct platform_driver nikel_tmu_platform_driver = {
	.probe = nikel_tmu_probe,
	.driver = {
		.name = "sdp-nikel-thermal-offline",
		.of_match_table = nikel_tmu_of_match,
	},
};
module_platform_driver(nikel_tmu_platform_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Fail-closed SDP TMU thermal-of prototype for Linux 6.6.162");
