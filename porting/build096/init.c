// SPDX-License-Identifier: GPL-2.0
/*
 * Build 096 - minimal /init for the ARM32 QEMU "virt" boot test.
 *
 * Built against the kernel's own nolibc (tools/include/nolibc) and packed
 * into a separate initramfs (-initrd). It runs as PID 1 on the generic QEMU
 * virt machine, never on Samsung hardware, and touches no storage:
 *
 *   1. checks that it really is PID 1,
 *   2. mounts proc, sysfs and devtmpfs,
 *   3. checks from userspace that the running kernel is 6.6.162 on ARMv7 and
 *      that the device tree is QEMU's virtual one ("linux,dummy-virt"),
 *   4. prints the Build 096 success marker only if every check passed,
 *      otherwise BUILD096_ARM32_QEMU_INIT_FAIL with the failed check,
 *   5. powers the virtual machine off through PSCI SYSTEM_OFF.
 *
 * The success marker is assembled at runtime from two halves so that the
 * literal string never appears in the binary or in the kernel image. The
 * harness therefore cannot be satisfied by the marker merely being echoed
 * from a file or a command line.
 */

#define EXPECTED_RELEASE	"6.6.162"
#define EXPECTED_DT		"linux,dummy-virt"

static int failures;

static void out(const char *s)
{
	write(1, s, strlen(s));
}

static void line(const char *a, const char *b)
{
	out(a);
	if (b)
		out(b);
	out("\n");
}

static void fail(const char *what, const char *detail)
{
	failures++;
	out("BUILD096_ARM32_QEMU_INIT_FAIL: ");
	line(what, detail);
}

/* Read up to size-1 bytes of a file; returns the length or -1. */
static int slurp(const char *path, char *buf, int size)
{
	int fd, n, total = 0;

	fd = open(path, O_RDONLY, 0);
	if (fd < 0)
		return -1;
	while (total < size - 1 && (n = read(fd, buf + total, size - 1 - total)) > 0)
		total += n;
	close(fd);
	buf[total] = '\0';
	return total;
}

static int starts_with(const char *s, const char *prefix)
{
	return !strncmp(s, prefix, strlen(prefix));
}

static int contains(const char *hay, const char *needle)
{
	size_t n = strlen(needle);

	for (; *hay; hay++)
		if (!strncmp(hay, needle, n))
			return 1;
	return 0;
}

static int append(char *dst, int pos, const char *src)
{
	while (*src)
		dst[pos++] = *src++;
	return pos;
}

static void strip_newline(char *s)
{
	for (; *s; s++)
		if (*s == '\n') {
			*s = '\0';
			return;
		}
}

static void try_mount(const char *src, const char *dst, const char *type)
{
	mkdir(dst, 0755);
	if (mount(src, dst, type, 0, 0) < 0 && errno != EBUSY)
		fail("mount ", dst);
}

static void check_kernel(void)
{
	char buf[512];

	if (slurp("/proc/sys/kernel/osrelease", buf, sizeof(buf)) <= 0) {
		fail("cannot read ", "/proc/sys/kernel/osrelease");
	} else {
		strip_newline(buf);
		line("build096-init: kernel release ", buf);
		if (!starts_with(buf, EXPECTED_RELEASE))
			fail("unexpected kernel release ", buf);
	}

	if (slurp("/proc/cpuinfo", buf, sizeof(buf)) <= 0)
		fail("cannot read ", "/proc/cpuinfo");
	else if (!contains(buf, "ARMv7"))
		fail("CPU is not reported as ARMv7", 0);
	else
		line("build096-init: cpu ARMv7 (32-bit)", 0);

	/* The DT must be QEMU's generated virtual tree, never a Samsung one. */
	if (slurp("/proc/device-tree/compatible", buf, sizeof(buf)) <= 0) {
		fail("cannot read ", "/proc/device-tree/compatible");
	} else {
		line("build096-init: dt compatible ", buf);
		if (strcmp(buf, EXPECTED_DT))
			fail("device tree is not ", EXPECTED_DT);
		if (contains(buf, "samsung"))
			fail("unexpected Samsung device tree", 0);
	}
}

int main(void)
{
	char pid[16];
	int p = getpid();

	line("build096-init: started", 0);
	if (p != 1) {
		/* Never mount or power off when run outside the guest. */
		pid[0] = '0' + (p % 10);
		pid[1] = '\0';
		fail("not running as PID 1, pid mod 10 = ", pid);
		return 1;
	}

	try_mount("proc", "/proc", "proc");
	try_mount("sysfs", "/sys", "sysfs");
	try_mount("devtmpfs", "/dev", "devtmpfs");
	check_kernel();

	if (!failures) {
		/*
		 * Assembled at runtime (see the header comment) and written with
		 * a single write() so kernel messages cannot split the line.
		 */
		char marker[48];
		int n = append(marker, 0, "BUILD096_ARM32_");

		n = append(marker, n, "QEMU_BOOT_OK\n");
		write(1, marker, n);
	}

	line("build096-init: requesting power off", 0);
	reboot(LINUX_REBOOT_CMD_POWER_OFF);
	fail("power off returned", 0);
	for (;;)
		sleep(60);
	return 0;
}
