// SPDX-License-Identifier: GPL-2.0-only
#include <linux/device.h>
#include <linux/err.h>
#include <linux/io.h>
#include <linux/ioport.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_irq.h>
#include <linux/platform_device.h>

struct nikel_display_resources {
	resource_size_t base;
	bool has_irq;
};

static const struct nikel_display_resources mixer = {
	.base = 0x5d8000,
};

static const struct nikel_display_resources osdp = {
	.base = 0x5d0000,
	.has_irq = true,
};

static bool nikel_has_enabled_node(const char *compatible)
{
	struct device_node *node;

	for_each_compatible_node(node, NULL, compatible) {
		if (of_device_is_available(node)) {
			of_node_put(node);
			return true;
		}
	}

	return false;
}

static int nikel_display_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	const struct nikel_display_resources *expected;
	struct of_phandle_args irq;
	struct resource *mem;
	void __iomem *base;
	bool valid_irq;
	int ret;

	expected = of_device_get_match_data(dev);
	if (!expected || !of_machine_is_compatible("samsung,sdp-nikel"))
		return -ENODEV;

	if (nikel_has_enabled_node("samsung,sdp-bootlogo") ||
	    (expected == &mixer && nikel_has_enabled_node("samsung,sdp-cursor1")))
		return dev_err_probe(dev, -EBUSY, "shared display DT node is enabled\n");

	mem = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	if (!mem || mem->start != expected->base || resource_size(mem) != 0x4000 ||
	    platform_get_resource(pdev, IORESOURCE_MEM, 1))
		return dev_err_probe(dev, -EINVAL, "unexpected MMIO resources\n");

	if (expected->has_irq) {
		if (of_property_present(dev->of_node, "interrupts-extended") ||
		    of_property_count_u32_elems(dev->of_node, "interrupts") != 3)
			return dev_err_probe(dev, -EINVAL, "expected one legacy OSDP IRQ specifier\n");

		/* Parse the firmware specifier without mapping a Linux IRQ. */
		ret = of_irq_parse_one(dev->of_node, 0, &irq);
		if (ret)
			return dev_err_probe(dev, ret, "missing OSDP IRQ specifier\n");

		valid_irq = of_device_is_compatible(irq.np, "arm,gic-400") &&
			    irq.args_count == 3 && irq.args[0] == 0 &&
			    irq.args[1] == 0x2f && irq.args[2] == 0;
		of_node_put(irq.np);
		if (!valid_irq)
			return dev_err_probe(dev, -EINVAL, "unexpected OSDP IRQ specifier\n");
	} else if (of_property_present(dev->of_node, "interrupts") ||
		   of_property_present(dev->of_node, "interrupts-extended")) {
		return dev_err_probe(dev, -EINVAL, "unexpected mixer IRQ property\n");
	}

	base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(base))
		return dev_err_probe(dev, PTR_ERR(base), "cannot reserve and map MMIO\n");

	if (expected->has_irq)
		dev_info(dev, "MMIO mapped %pR; DT GIC SPI 47, flags 0, no handler\n", mem);
	else
		dev_info(dev, "MMIO mapped %pR; no DT IRQ\n", mem);

	return 0;
}

static const struct of_device_id nikel_display_of_match[] = {
	{ .compatible = "samsung,sdp-mixer", .data = &mixer },
	{ .compatible = "samsung,sdp-osdp", .data = &osdp },
	{ }
};
MODULE_DEVICE_TABLE(of, nikel_display_of_match);

static struct platform_driver nikel_display_driver = {
	.probe = nikel_display_probe,
	.driver = {
		.name = "sdp-nikel-display-probe",
		.of_match_table = nikel_display_of_match,
	},
};
module_platform_driver(nikel_display_driver);

MODULE_DESCRIPTION("Samsung Nike-L display resource probe");
MODULE_LICENSE("GPL");
