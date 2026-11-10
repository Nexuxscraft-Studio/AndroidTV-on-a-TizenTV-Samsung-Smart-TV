// SPDX-License-Identifier: GPL-2.0
/*
 * q60t-diag-init - tiny diagnostic init for the first Build 059 boots
 *
 * Built against the kernel's own nolibc (tools/include/nolibc), so it needs
 * no C library and no root filesystem: it is embedded into the kernel as
 * initramfs. On the serial console it
 *
 *   1. mounts /proc, /sys, /dev (devtmpfs) and debugfs,
 *   2. prints a fixed set of diagnostics (CPU, IRQs, memory map, clocks,
 *      device tree root, kernel log of the SDP drivers),
 *   3. offers a minimal shell: help, diag, cat, ls, write, dmesg, reboot,
 *      poweroff.
 *
 * It never writes to any storage device. Writes happen only on explicit
 * "write FILE VALUE" commands (meant for sysfs/debugfs knobs).
 *
 * Build (example):
 *   clang --target=aarch64-linux-gnu -nostdlib -static -Os -fno-stack-protector \
 *         -fuse-ld=lld -include <linux>/tools/include/nolibc/nolibc.h \
 *         -o init q60t-diag-init.c
 * Host test (no mounts, no reboot when not running as PID 1):
 *   clang -nostdlib -static -include .../nolibc.h -o t q60t-diag-init.c
 */

#ifndef NOLIBC
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#endif

#define LINE_MAX_LEN	256
#define VERSION		"build059-diag-2"

/* reboot(2) magic values, as in <linux/reboot.h> */
#define Q_RB_RESTART	0x01234567
#define Q_RB_POWER_OFF	0x4321FEDC

static int is_init;

/* nolibc has no strstr() */
static const char *find_str(const char *hay, const char *needle)
{
	size_t n = strlen(needle);

	for (; *hay; hay++)
		if (!strncmp(hay, needle, n))
			return hay;
	return NULL;
}

static void out(const char *s)
{
	write(1, s, strlen(s));
}

static void out_line(const char *a, const char *b)
{
	out(a);
	if (b)
		out(b);
	out("\n");
}

static void cat_file(const char *path, int max_lines)
{
	char buf[512];
	int fd, lines = 0;
	ssize_t n, i;

	fd = open(path, O_RDONLY, 0);
	if (fd < 0) {
		out_line("  (cannot open) ", path);
		return;
	}
	while ((n = read(fd, buf, sizeof(buf))) > 0) {
		if (max_lines > 0) {
			for (i = 0; i < n; i++) {
				if (buf[i] == '\n' && ++lines >= max_lines) {
					write(1, buf, i + 1);
					out("  ...\n");
					close(fd);
					return;
				}
			}
		}
		write(1, buf, n);
	}
	close(fd);
}

static void list_dir(const char *path)
{
	char buf[1024];
	int fd, n, pos;

	fd = open(path, O_RDONLY | O_DIRECTORY, 0);
	if (fd < 0) {
		out_line("  (cannot open) ", path);
		return;
	}
	while ((n = getdents64(fd, (void *)buf, sizeof(buf))) > 0) {
		for (pos = 0; pos < n;) {
			struct linux_dirent64 *d = (void *)(buf + pos);

			if (strcmp(d->d_name, ".") && strcmp(d->d_name, "..")) {
				out("  ");
				out(d->d_name);
				out(d->d_type == 4 ? "/\n" : "\n");
			}
			pos += d->d_reclen;
		}
	}
	close(fd);
}

/* kernel log lines containing one of the given words */
static void dmesg_grep(const char *const *words)
{
	char buf[1024];
	int fd;
	ssize_t n;

	fd = open("/dev/kmsg", O_RDONLY | O_NONBLOCK, 0);
	if (fd < 0) {
		out_line("  (cannot open /dev/kmsg)", NULL);
		return;
	}
	/* every read returns exactly one record */
	while ((n = read(fd, buf, sizeof(buf) - 1)) > 0) {
		const char *msg;
		int i, hit = !words;

		buf[n] = 0;
		msg = strchr(buf, ';');
		msg = msg ? msg + 1 : buf;
		for (i = 0; words && words[i]; i++)
			if (find_str(msg, words[i]))
				hit = 1;
		if (hit)
			out(msg);
	}
	close(fd);
}

static void section(const char *title)
{
	out("\n===== ");
	out(title);
	out(" =====\n");
}

static const char *const sdp_words[] = {
	"sdp", "SDP", "ttySDP", "uartclk", "psci", "GIC", "arch_timer",
	"Memory", "CPU", "dw_mmc", "mmc", NULL
};

static void diag(void)
{
	section("kernel");
	cat_file("/proc/version", 0);
	cat_file("/proc/cmdline", 0);
	section("cpus");
	cat_file("/proc/cpuinfo", 40);
	section("memory");
	cat_file("/proc/meminfo", 6);
	cat_file("/proc/iomem", 40);
	section("interrupts");
	cat_file("/proc/interrupts", 30);
	section("clocks (debugfs)");
	cat_file("/sys/kernel/debug/clk/clk_summary", 40);
	section("gpio (debugfs)");
	cat_file("/sys/kernel/debug/gpio", 40);
	section("device tree /");
	list_dir("/proc/device-tree");
	section("model");
	cat_file("/proc/device-tree/model", 0);
	out("\n");
	section("kernel log (SDP related)");
	dmesg_grep(sdp_words);
	section("end of diagnostics");
}

static void setup_mounts(void)
{
	mkdir("/proc", 0755);
	mkdir("/sys", 0755);
	mkdir("/dev", 0755);
	mount("proc", "/proc", "proc", 0, NULL);
	mount("sysfs", "/sys", "sysfs", 0, NULL);
	mount("devtmpfs", "/dev", "devtmpfs", 0, NULL);
	mount("debugfs", "/sys/kernel/debug", "debugfs", 0, NULL);
}

static void help(void)
{
	out("commands:\n"
	    "  help              this text\n"
	    "  diag              print all diagnostics again\n"
	    "  cat FILE          print a file\n"
	    "  ls [DIR]          list a directory (default /)\n"
	    "  write FILE VALUE  write VALUE to FILE (sysfs/debugfs knobs)\n"
	    "  dmesg             print the whole kernel log\n"
	    "  reboot | poweroff\n");
}

static char *next_word(char **p)
{
	char *s = *p, *w;

	while (*s == ' ' || *s == '\t')
		s++;
	if (!*s)
		return NULL;
	w = s;
	while (*s && *s != ' ' && *s != '\t')
		s++;
	if (*s)
		*s++ = 0;
	*p = s;
	return w;
}

static int read_line(char *buf, int len)
{
	int n = 0;
	char c;

	while (n < len - 1) {
		if (read(0, &c, 1) != 1)
			return n ? n : -1;
		if (c == '\r' || c == '\n')
			break;
		buf[n++] = c;
	}
	buf[n] = 0;
	return n;
}

static int run_command(char *line)
{
	char *p = line, *cmd, *a, *b;

	cmd = next_word(&p);
	if (!cmd)
		return 0;
	a = next_word(&p);
	b = p;
	while (*b == ' ')
		b++;

	if (!strcmp(cmd, "help")) {
		help();
	} else if (!strcmp(cmd, "diag")) {
		diag();
	} else if (!strcmp(cmd, "cat")) {
		if (a)
			cat_file(a, 0);
		else
			out("usage: cat FILE\n");
	} else if (!strcmp(cmd, "ls")) {
		list_dir(a ? a : "/");
	} else if (!strcmp(cmd, "write")) {
		int fd;

		if (!a || !*b) {
			out("usage: write FILE VALUE\n");
			return 0;
		}
		fd = open(a, O_WRONLY, 0);
		if (fd < 0 || write(fd, b, strlen(b)) < 0)
			out("write failed\n");
		if (fd >= 0)
			close(fd);
	} else if (!strcmp(cmd, "dmesg")) {
		dmesg_grep(NULL);
	} else if (!strcmp(cmd, "reboot") || !strcmp(cmd, "poweroff")) {
		if (!is_init) {
			out("(not PID 1, ignoring)\n");
			return 0;
		}
		/* nothing to sync: this init never writes to storage */
		reboot(cmd[0] == 'r' ? Q_RB_RESTART : Q_RB_POWER_OFF);
	} else if (!strcmp(cmd, "exit") && !is_init) {
		return 1;
	} else {
		out("unknown command, try 'help'\n");
	}
	return 0;
}

int main(void)
{
	char line[LINE_MAX_LEN];

	is_init = getpid() == 1;
	if (is_init)
		setup_mounts();

	out("\nq60t-diag-init " VERSION " - Samsung Q60T / Nike-L, Build 059\n");
	if (is_init)
		diag();
	help();

	for (;;) {
		out("q60t# ");
		if (read_line(line, sizeof(line)) < 0) {
			if (!is_init)
				return 0;
			continue;
		}
		if (run_command(line))
			return 0;
	}
}
