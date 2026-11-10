/*
 * Build 054 ARM32 compiler probe. Never touches the Samsung display.
 * This is an object-only diagnostic; the source is not a TV driver.
 */
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>

#ifndef CONFIG_ARM
#error "Build 054 ARM32 probe requires ARCH=arm and CONFIG_ARM"
#endif

#ifndef CONFIG_CPU_V7
#error "Build 054 expects the audited Nike.M ARMv7 defconfig"
#endif

static int __init nover_arm32_probe_init(void)
{
	/* Compile-only; if built as a module by mistake, refuse loading. */
	return -ENODEV;
}

static void __exit nover_arm32_probe_exit(void)
{
}

module_init(nover_arm32_probe_init);
module_exit(nover_arm32_probe_exit);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Build 054 ARMv7 Linux 4.1 compile-only probe");
