/* Build 018: standalone ARM32 initramfs /init for QEMU only.
 *
 * It checks the old Samsung 4.1.10 Binder ABI via BINDER_VERSION. It does
 * not issue Binder transactions, start Android, or access a real television.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <unistd.h>

struct binder_version {
    int protocol_version;
};
#define BINDER_VERSION _IOWR('b', 9, struct binder_version)

static void try_mount(const char *device, const char *target, const char *type)
{
    if (mount(device, target, type, 0, NULL) && errno != EBUSY)
        dprintf(STDOUT_FILENO, "Q60T_GUEST_MOUNT_FAIL target=%s errno=%d\n",
                target, errno);
}

static void probe_binder(const char *name)
{
    char path[64];
    struct binder_version version = { -1 };
    int fd;

    snprintf(path, sizeof(path), "/dev/%s", name);
    fd = open(path, O_RDWR | O_CLOEXEC);
    if (fd < 0) {
        dprintf(STDOUT_FILENO, "Q60T_BINDER_DEVICE_MISSING name=%s errno=%d\n",
                name, errno);
        return;
    }
    if (ioctl(fd, BINDER_VERSION, &version) < 0) {
        dprintf(STDOUT_FILENO, "Q60T_BINDER_VERSION_IOCTL_FAIL name=%s errno=%d\n",
                name, errno);
    } else if (version.protocol_version == 8) {
        dprintf(STDOUT_FILENO,
                "Q60T_BINDER_VERSION_IOCTL_PASS name=%s protocol=%d\n",
                name, version.protocol_version);
    } else {
        dprintf(STDOUT_FILENO,
                "Q60T_BINDER_VERSION_IOCTL_MISMATCH name=%s protocol=%d expected=8\n",
                name, version.protocol_version);
    }
    close(fd);
}

int main(void)
{
    int console = open("/dev/console", O_RDWR | O_NOCTTY);
    if (console >= 0) {
        dup2(console, STDIN_FILENO);
        dup2(console, STDOUT_FILENO);
        dup2(console, STDERR_FILENO);
        if (console > STDERR_FILENO)
            close(console);
    }

    dprintf(STDOUT_FILENO, "Q60T_GUEST_INIT_STARTED host_only=1 no_flash=1\n");
    try_mount("devtmpfs", "/dev", "devtmpfs");
    try_mount("proc", "/proc", "proc");
    try_mount("sysfs", "/sys", "sysfs");

    probe_binder("binder");
    probe_binder("hwbinder");
    probe_binder("vndbinder");

    dprintf(STDOUT_FILENO, "Q60T_BINDER_ABI_PROBE_FINISHED transaction_tested=0\n");
    for (;;)
        pause();
}
