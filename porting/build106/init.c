// SPDX-License-Identifier: GPL-2.0
/*
 * Build 106 - /init for the ARM32 QEMU "virt" module load test.
 *
 * Built against the kernel's nolibc. Runs as PID 1 on QEMU virt with the
 * Build 106 modular Nike-L kernel. Reads /modules.list (one path per line,
 * dependencies first), loads each module with finit_module(2), prints
 * /proc/modules, unloads everything in reverse order with delete_module(2)
 * and powers off. QEMU has no Nike-L hardware: drivers register, but none of
 * them can probe a Samsung device, so this proves linking, relocation,
 * symbol resolution, module_init and module_exit only.
 */
#include <asm/unistd.h>

#define MAXMODS 128

static char list[8192];
static char *mods[MAXMODS];
static char names[MAXMODS][64];
static int loaded[MAXMODS];

static void out(const char *s) { write(1, s, strlen(s)); }

static void num(long v)
{
	char b[24];
	int i = sizeof(b);

	b[--i] = 0;
	if (v < 0) { out("-"); v = -v; }
	do { b[--i] = '0' + v % 10; v /= 10; } while (v);
	out(b + i);
}

static int slurp(const char *path, char *buf, int size)
{
	int fd = open(path, O_RDONLY, 0), n, total = 0;

	if (fd < 0)
		return -1;
	while (total < size - 1 && (n = read(fd, buf + total, size - 1 - total)) > 0)
		total += n;
	close(fd);
	buf[total] = 0;
	return total;
}

/* module name as the kernel sees it: basename, no .ko, '-' -> '_' */
static void modname(const char *path, char *dst)
{
	const char *b = path, *p;
	int i = 0;

	for (p = path; *p; p++)
		if (*p == '/')
			b = p + 1;
	for (; *b && i < 63; b++) {
		if (b[0] == '.' && b[1] == 'k' && b[2] == 'o' && !b[3])
			break;
		dst[i++] = *b == '-' ? '_' : *b;
	}
	dst[i] = 0;
}

int main(void)
{
	static char buf[16384];
	int n = 0, i, fails = 0, ok = 0, unloaded = 0;
	char *p;

	mount("proc", "/proc", "proc", 0, 0);
	mount("sysfs", "/sys", "sysfs", 0, 0);
	mount("devtmpfs", "/dev", "devtmpfs", 0, 0);
	if (slurp("/proc/sys/kernel/osrelease", buf, sizeof(buf)) > 0) {
		out("BUILD106 kernel release: ");
		out(buf);
	}
	if (slurp("/modules.list", list, sizeof(list)) <= 0) {
		out("BUILD106_QEMU_FAIL no /modules.list\n");
		goto off;
	}
	for (p = list; *p && n < MAXMODS;) {
		mods[n] = p;
		while (*p && *p != '\n')
			p++;
		if (*p)
			*p++ = 0;
		if (*mods[n])
			modname(mods[n], names[n]), n++;
	}
	for (i = 0; i < n; i++) {
		int fd = open(mods[i], O_RDONLY, 0);
		long rc = fd < 0 ? fd : my_syscall3(__NR_finit_module, fd, "", 0);

		if (fd >= 0)
			close(fd);
		out(rc == 0 ? "BUILD106_LOAD_OK " : "BUILD106_LOAD_FAIL ");
		out(names[i]);
		out(" rc=");
		num(rc);
		out("\n");
		loaded[i] = rc == 0;
		if (rc == 0)
			ok++;
		else
			fails++;
	}
	out("BUILD106 /proc/modules:\n");
	if (slurp("/proc/modules", buf, sizeof(buf)) > 0)
		out(buf);
	for (i = n - 1; i >= 0; i--) {
		long rc;

		if (!loaded[i])
			continue;
		rc = my_syscall2(__NR_delete_module, names[i], O_NONBLOCK);
		out(rc == 0 ? "BUILD106_UNLOAD_OK " : "BUILD106_UNLOAD_FAIL ");
		out(names[i]);
		out(" rc=");
		num(rc);
		out("\n");
		if (rc == 0)
			unloaded++;
		else
			fails++;
	}
	out("BUILD106_QEMU_SUMMARY modules=");
	num(n);
	out(" loaded=");
	num(ok);
	out(" unloaded=");
	num(unloaded);
	out(" failures=");
	num(fails);
	out("\n");
off:
	my_syscall0(__NR_sync);
	reboot(LINUX_REBOOT_CMD_POWER_OFF);
	return 0;
}
