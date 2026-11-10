// SPDX-License-Identifier: GPL-2.0-only
/*
 * Samsung Nike-L GPU clock/reset experiment for Linux 6.6.
 *
 * BUILD 058 IS FAIL-CLOSED. probe() unconditionally refuses to bind before
 * ioremap, provider registration or any register access. This is an API and
 * compilation prototype only. It is NOT approved for Samsung hardware.
 *
 * Register locations/active bit values are reconstructed from Samsung's
 * original mali_kbase_platform_sdp.c and mali_kbase_config_platform.h.
 * The complete board clock tree, PM domains and IRQ polarity are unknown.
 */

#include <linux/bitops.h>
#include <linux/clk-provider.h>
#include <linux/err.h>
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/reset-controller.h>
#include <linux/slab.h>
#include <linux/spinlock.h>

/* Offsets from original Nike-L clkrst base 0x00f50000, size 0x3000. */
#define SDP_NIKEL_GPU_RESET_OFFSET      0x07f8
#define SDP_NIKEL_GPU_CLOCK_OFFSET      0x088c
#define SDP_NIKEL_GPU_IDLE_REQ_OFFSET   0x0a10
#define SDP_NIKEL_GPU_IDLE_ACK_OFFSET   0x0a14

#define SDP_NIKEL_GPU_BUS_RESET         BIT(24)
#define SDP_NIKEL_GPU_CORE_RESET        BIT(28)
#define SDP_NIKEL_GPU_CLOCK_GATE        BIT(12)
#define SDP_NIKEL_GPU_IDLE_BIT          BIT(0)

#define SDP_NIKEL_GPU_RESET_BUS_ID      0
#define SDP_NIKEL_GPU_RESET_CORE_ID     1
#define SDP_NIKEL_GPU_RESET_COUNT       2
#define SDP_NIKEL_GPU_CLOCK_ID          0
#define SDP_NIKEL_GPU_IDLE_TIMEOUT_US   2000

/* Intentionally hard-coded. Never replace with a module parameter. */
#define SDP_NIKEL_BUILD058_HARDWARE_DISABLED 1

struct sdp_nikel_gpu_clkrst {
	void __iomem *base;
	spinlock_t lock;
	struct clk_hw gpu_hw;
	struct reset_controller_dev rcdev;
	struct device *dev;
};

static inline struct sdp_nikel_gpu_clkrst *to_nikel_gpu_clk(struct clk_hw *hw)
{
	return container_of(hw, struct sdp_nikel_gpu_clkrst, gpu_hw);
}

static inline struct sdp_nikel_gpu_clkrst *to_nikel_gpu_reset(struct reset_controller_dev *rcdev)
{
	return container_of(rcdev, struct sdp_nikel_gpu_clkrst, rcdev);
}

/* All shared register updates must preserve unrelated bits. */
static void nikel_gpu_update_bits(struct sdp_nikel_gpu_clkrst *ctl,
				 u32 offset, u32 mask, bool set)
{
	unsigned long flags;
	u32 value;

	spin_lock_irqsave(&ctl->lock, flags);
	value = readl(ctl->base + offset);
	if (set)
		value |= mask;
	else
		value &= ~mask;
	writel(value, ctl->base + offset);
	spin_unlock_irqrestore(&ctl->lock, flags);
}

/* Samsung's on sequence: clock -> bus reset release -> core release -> idle clear. */
static int nikel_gpu_clock_enable(struct clk_hw *hw)
{
	struct sdp_nikel_gpu_clkrst *ctl = to_nikel_gpu_clk(hw);

	nikel_gpu_update_bits(ctl, SDP_NIKEL_GPU_CLOCK_OFFSET,
			      SDP_NIKEL_GPU_CLOCK_GATE, true);
	nikel_gpu_update_bits(ctl, SDP_NIKEL_GPU_RESET_OFFSET,
			      SDP_NIKEL_GPU_BUS_RESET, true);
	nikel_gpu_update_bits(ctl, SDP_NIKEL_GPU_RESET_OFFSET,
			      SDP_NIKEL_GPU_CORE_RESET, true);
	nikel_gpu_update_bits(ctl, SDP_NIKEL_GPU_IDLE_REQ_OFFSET,
			      SDP_NIKEL_GPU_IDLE_BIT, false);
	return 0;
}

/*
 * Samsung's off sequence: request idle -> wait -> bus/core reset -> clock off.
 * Unlike original firmware, this polls a MASKED bit with a finite timeout.
 * clk_ops.disable has no error return. On timeout, leave the clock running
 * and abort resets; the CCF status may then be out of sync (unresolved).
 */
static void nikel_gpu_clock_disable(struct clk_hw *hw)
{
	struct sdp_nikel_gpu_clkrst *ctl = to_nikel_gpu_clk(hw);
	u32 value;
	int ret;

	nikel_gpu_update_bits(ctl, SDP_NIKEL_GPU_IDLE_REQ_OFFSET,
			      SDP_NIKEL_GPU_IDLE_BIT, true);
	ret = readl_poll_timeout_atomic(ctl->base + SDP_NIKEL_GPU_IDLE_ACK_OFFSET,
					value, value & SDP_NIKEL_GPU_IDLE_BIT,
					1, SDP_NIKEL_GPU_IDLE_TIMEOUT_US);
	if (ret) {
		nikel_gpu_update_bits(ctl, SDP_NIKEL_GPU_IDLE_REQ_OFFSET,
					      SDP_NIKEL_GPU_IDLE_BIT, false);
		dev_warn_ratelimited(ctl->dev,
			"GPU idle timed out; left clock enabled; CCF state may differ\n");
		return;
	}

	nikel_gpu_update_bits(ctl, SDP_NIKEL_GPU_RESET_OFFSET,
			      SDP_NIKEL_GPU_BUS_RESET, false);
	nikel_gpu_update_bits(ctl, SDP_NIKEL_GPU_RESET_OFFSET,
			      SDP_NIKEL_GPU_CORE_RESET, false);
	nikel_gpu_update_bits(ctl, SDP_NIKEL_GPU_CLOCK_OFFSET,
			      SDP_NIKEL_GPU_CLOCK_GATE, false);
}

static int nikel_gpu_clock_is_enabled(struct clk_hw *hw)
{
	struct sdp_nikel_gpu_clkrst *ctl = to_nikel_gpu_clk(hw);

	return !!(readl(ctl->base + SDP_NIKEL_GPU_CLOCK_OFFSET) &
		  SDP_NIKEL_GPU_CLOCK_GATE);
}

static const struct clk_ops nikel_gpu_clock_ops = {
	.enable = nikel_gpu_clock_enable,
	.disable = nikel_gpu_clock_disable,
	.is_enabled = nikel_gpu_clock_is_enabled,
};

static int nikel_gpu_reset_modify(struct reset_controller_dev *rcdev,
				  unsigned long id, bool deassert)
{
	struct sdp_nikel_gpu_clkrst *ctl = to_nikel_gpu_reset(rcdev);
	u32 mask;

	switch (id) {
	case SDP_NIKEL_GPU_RESET_BUS_ID:
		mask = SDP_NIKEL_GPU_BUS_RESET;
		break;
	case SDP_NIKEL_GPU_RESET_CORE_ID:
		mask = SDP_NIKEL_GPU_CORE_RESET;
		break;
	default:
		return -EINVAL;
	}

	/* Samsung original: 1 = deassert reset, 0 = assert reset. */
	nikel_gpu_update_bits(ctl, SDP_NIKEL_GPU_RESET_OFFSET, mask, deassert);
	return 0;
}

static int nikel_gpu_reset_assert(struct reset_controller_dev *rcdev,
				 unsigned long id)
{
	return nikel_gpu_reset_modify(rcdev, id, false);
}

static int nikel_gpu_reset_deassert(struct reset_controller_dev *rcdev,
				   unsigned long id)
{
	return nikel_gpu_reset_modify(rcdev, id, true);
}

static int nikel_gpu_reset_status(struct reset_controller_dev *rcdev,
				  unsigned long id)
{
	struct sdp_nikel_gpu_clkrst *ctl = to_nikel_gpu_reset(rcdev);
	u32 mask;

	if (id == SDP_NIKEL_GPU_RESET_BUS_ID)
		mask = SDP_NIKEL_GPU_BUS_RESET;
	else if (id == SDP_NIKEL_GPU_RESET_CORE_ID)
		mask = SDP_NIKEL_GPU_CORE_RESET;
	else
		return -EINVAL;

	return !(readl(ctl->base + SDP_NIKEL_GPU_RESET_OFFSET) & mask);
}

static const struct reset_control_ops nikel_gpu_reset_ops = {
	.assert = nikel_gpu_reset_assert,
	.deassert = nikel_gpu_reset_deassert,
	.status = nikel_gpu_reset_status,
};

static struct clk_hw *nikel_gpu_of_get_clk(struct of_phandle_args *spec,
					  void *data)
{
	struct sdp_nikel_gpu_clkrst *ctl = data;

	if (spec->args_count != 1 || spec->args[0] != SDP_NIKEL_GPU_CLOCK_ID)
		return ERR_PTR(-EINVAL);
	return &ctl->gpu_hw;
}

static int nikel_gpu_clkrst_probe(struct platform_device *pdev)
{
	struct sdp_nikel_gpu_clkrst *ctl;
	struct clk_init_data init = {
		.name = "sdp-nikel-gpu-gate-unverified",
		.ops = &nikel_gpu_clock_ops,
		.num_parents = 0, /* parent frequency/source NOT verified */
	};
	int ret;

	/* FAIL CLOSED: no ioremap, clock/reset registration, or MMIO. */
#if SDP_NIKEL_BUILD058_HARDWARE_DISABLED
	return dev_err_probe(&pdev->dev, -EOPNOTSUPP,
			     "Build 058 compile-only; Nike-L hardware access blocked\n");
#endif

	ctl = devm_kzalloc(&pdev->dev, sizeof(*ctl), GFP_KERNEL);
	if (!ctl)
		return -ENOMEM;
	ctl->dev = &pdev->dev;
	spin_lock_init(&ctl->lock);
	ctl->base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(ctl->base))
		return PTR_ERR(ctl->base);

	ctl->gpu_hw.init = &init;
	ret = devm_clk_hw_register(&pdev->dev, &ctl->gpu_hw);
	if (ret)
		return ret;

	ctl->rcdev.owner = THIS_MODULE;
	ctl->rcdev.ops = &nikel_gpu_reset_ops;
	ctl->rcdev.of_node = pdev->dev.of_node;
	ctl->rcdev.of_reset_n_cells = 1;
	ctl->rcdev.nr_resets = SDP_NIKEL_GPU_RESET_COUNT;
	ret = devm_reset_controller_register(&pdev->dev, &ctl->rcdev);
	if (ret)
		return ret;

	return devm_of_clk_add_hw_provider(&pdev->dev, nikel_gpu_of_get_clk, ctl);
}

/* Deliberately NOT compatible with the original samsung,sdp1804-clock node. */
static const struct of_device_id nikel_gpu_clkrst_of_match[] = {
	{ .compatible = "nover,sdp-nikel-gpu-clkrst-experimental" },
	{ }
};
MODULE_DEVICE_TABLE(of, nikel_gpu_clkrst_of_match);

static struct platform_driver nikel_gpu_clkrst_driver = {
	.probe = nikel_gpu_clkrst_probe,
	.driver = {
		.name = "sdp-nikel-gpu-clkrst-experimental",
		.of_match_table = nikel_gpu_clkrst_of_match,
	},
};
module_platform_driver(nikel_gpu_clkrst_driver);

MODULE_DESCRIPTION("Fail-closed Samsung Nike-L GPU CCF/reset prototype (Build 058)");
MODULE_LICENSE("GPL");
