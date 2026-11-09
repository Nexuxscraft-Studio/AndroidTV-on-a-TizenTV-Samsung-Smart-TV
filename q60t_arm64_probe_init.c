/* Build 023: static AArch64 PID1, QEMU-virt-only kernel API smoke test.
 * No Android userspace, policy loading, device flashing or Samsung access.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/android/binder.h>
#include <linux/android/binderfs.h>
#include <linux/dma-heap.h>
#include <linux/memfd.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <unistd.h>

static void serial_console(void) {
    int console = open("/dev/console", O_RDWR | O_CLOEXEC);
    if (console >= 0) {
        (void)dup2(console, STDIN_FILENO);
        (void)dup2(console, STDOUT_FILENO);
        (void)dup2(console, STDERR_FILENO);
        if (console > STDERR_FILENO) (void)close(console);
    }
    (void)setvbuf(stdout, NULL, _IONBF, 0);
}

static void mount_fs(const char *name, const char *path, const char *type) {
    int status = mount(name, path, type, 0, NULL);
    if (status == 0 || errno == EBUSY) {
        printf("Q60T_ARM64_MOUNT name=%s status=pass\n", name);
    } else {
        printf("Q60T_ARM64_MOUNT name=%s status=fail errno=%d\n", name, errno);
    }
}

static void binderfs_setup(void) {
    static const char *const devices[] = {"binder", "hwbinder", "vndbinder"};
    if (mkdir("/dev/binderfs", 0755) != 0 && errno != EEXIST) {
        printf("Q60T_ARM64_BINDERFS status=fail phase=mkdir errno=%d\n", errno);
        return;
    }
    if (mount("binder", "/dev/binderfs", "binder", 0, NULL) != 0 && errno != EBUSY) {
        printf("Q60T_ARM64_BINDERFS status=fail phase=mount errno=%d\n", errno);
        return;
    }
    int ctl = open("/dev/binderfs/binder-control", O_RDWR | O_CLOEXEC);
    if (ctl < 0) {
        printf("Q60T_ARM64_BINDERFS status=fail phase=control errno=%d\n", errno);
        return;
    }
    for (size_t i = 0; i < sizeof(devices) / sizeof(devices[0]); i++) {
        struct binderfs_device request = {0};
        (void)snprintf(request.name, sizeof(request.name), "%s", devices[i]);
        if (ioctl(ctl, BINDER_CTL_ADD, &request) == 0) {
            printf("Q60T_ARM64_BINDERFS_DEVICE name=%s status=pass\n", devices[i]);
        } else {
            printf("Q60T_ARM64_BINDERFS_DEVICE name=%s status=fail errno=%d\n",
                   devices[i], errno);
        }
    }
    (void)close(ctl);
}

static void binder_probe(const char *name) {
    char path[128];
    struct binder_version version = {0};
    int n = snprintf(path, sizeof(path), "/dev/%s", name);
    if (n < 0 || (size_t)n >= sizeof(path)) return;
    int fd = open(path, O_RDWR | O_CLOEXEC);
    if (fd < 0 && errno == ENOENT) {
        n = snprintf(path, sizeof(path), "/dev/binderfs/%s", name);
        if (n > 0 && (size_t)n < sizeof(path))
            fd = open(path, O_RDWR | O_CLOEXEC);
    }
    if (fd < 0) {
        printf("Q60T_ARM64_BINDER name=%s status=fail phase=open errno=%d\n", name, errno);
        return;
    }
    if (ioctl(fd, BINDER_VERSION, &version) == 0 && version.protocol_version > 0) {
        printf("Q60T_ARM64_BINDER name=%s status=pass protocol=%d\n", name,
               version.protocol_version);
    } else {
        printf("Q60T_ARM64_BINDER name=%s status=fail phase=ioctl errno=%d\n", name, errno);
    }
    (void)close(fd);
}

static void selinux_probe(void) {
    (void)mkdir("/sys/fs/selinux", 0755);
    if (mount("selinuxfs", "/sys/fs/selinux", "selinuxfs", 0, NULL) != 0 &&
        errno != EBUSY) {
        printf("Q60T_ARM64_SELINUX status=fail phase=mount errno=%d policy_loaded=unverified\n", errno);
        return;
    }
    int fd = open("/sys/fs/selinux/enforce", O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        printf("Q60T_ARM64_SELINUX status=fail phase=open errno=%d policy_loaded=unverified\n", errno);
        return;
    }
    char state = '?';
    ssize_t bytes = read(fd, &state, 1);
    (void)close(fd);
    if (bytes == 1 && (state == '0' || state == '1')) {
        printf("Q60T_ARM64_SELINUX status=pass enforce=%c policy_loaded=unverified\n", state);
    } else {
        printf("Q60T_ARM64_SELINUX status=fail phase=read policy_loaded=unverified\n");
    }
}

static void memfd_probe(void) {
    const size_t size = 4096;
    int fd = memfd_create("q60t-arm64-memory-test", MFD_CLOEXEC);
    if (fd < 0 || ftruncate(fd, (off_t)size) != 0) {
        printf("Q60T_ARM64_MEMFD status=fail phase=create errno=%d\n", errno);
        if (fd >= 0) (void)close(fd);
        return;
    }
    unsigned char *p = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (p == MAP_FAILED) {
        printf("Q60T_ARM64_MEMFD status=fail phase=mmap errno=%d\n", errno);
    } else {
        memset(p, 0x5a, size);
        printf("Q60T_ARM64_MEMFD status=%s bytes=4096\n",
               (p[0] == 0x5a && p[size - 1] == 0x5a) ? "pass" : "fail");
        (void)munmap(p, size);
    }
    (void)close(fd);
}

static void dma_heap_probe(void) {
    int fd = open("/dev/dma_heap/system", O_RDWR | O_CLOEXEC);
    if (fd < 0) {
        printf("Q60T_ARM64_DMA_HEAP status=fail phase=open errno=%d\n", errno);
        return;
    }
    struct dma_heap_allocation_data allocation = {0};
    allocation.len = 4096;
    allocation.fd_flags = O_RDWR | O_CLOEXEC;
    if (ioctl(fd, DMA_HEAP_IOCTL_ALLOC, &allocation) == 0) {
        printf("Q60T_ARM64_DMA_HEAP status=pass bytes=4096\n");
        (void)close((int)allocation.fd);
    } else {
        printf("Q60T_ARM64_DMA_HEAP status=fail phase=ioctl errno=%d\n", errno);
    }
    (void)close(fd);
}

int main(void) {
    serial_console();
    struct utsname sys = {0};
    printf("Q60T_ARM64_GUEST_INIT_STARTED version=023 qemu_only=1 no_flash=1\n");
    if (uname(&sys) == 0) {
        printf("Q60T_ARM64_UNAME machine=%s release=%s\n", sys.machine, sys.release);
    } else {
        printf("Q60T_ARM64_UNAME status=fail errno=%d\n", errno);
    }
    mount_fs("devtmpfs", "/dev", "devtmpfs");
    mount_fs("proc", "/proc", "proc");
    mount_fs("sysfs", "/sys", "sysfs");
    binderfs_setup();
    binder_probe("binder");
    binder_probe("hwbinder");
    binder_probe("vndbinder");
    selinux_probe();
    memfd_probe();
    dma_heap_probe();
    printf("Q60T_ARM64_GUEST_PROBE_FINISHED version=023\n");
    /* PID 1 must not exit: QEMU runner terminates after its fixed timeout. */
    for (;;) pause();
}
