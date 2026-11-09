/* Build 020: minimal ARM32 Linux /init, never an Android system image.
 *
 * Compile with the repository's q60t_initramfs_lab.py (static ARM32 ELF).
 * This program only runs inside the isolated QEMU virt guest. It does not
 * contact the Samsung television or access host disks/network interfaces.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/futex.h>
#include <poll.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/epoll.h>
#include <sys/eventfd.h>
#include <sys/inotify.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

/* The BINDER_VERSION layout is stable across the older protocol variants.
 * Avoid a host-specific linux/android/binder.h dependency: our userspace
 * cross-compiler may not package the vendor UAPI header.
 */
struct q60t_binder_version { int protocol_version; };
#define BINDER_VERSION _IOWR('b', 9, struct q60t_binder_version)

static void result(const char *name, const char *state)
{
    dprintf(STDOUT_FILENO, "Q60T_ANDROID_PROBE_FEATURE name=%s result=%s\n",
            name, state);
}

static int mount_fs(const char *name, const char *where, const char *type)
{
    return mount(name, where, type, 0, NULL) == 0 || errno == EBUSY;
}

static int proc_file_exists(const char *path)
{
    return access(path, R_OK) == 0;
}

static void check_binder(const char *name)
{
    char path[48];
    struct q60t_binder_version version = { .protocol_version = -1 };
    snprintf(path, sizeof(path), "/dev/%s", name);
    int fd = open(path, O_RDWR | O_CLOEXEC);
    if (fd < 0) {
        result(name, "fail");
        return;
    }
    int ok = ioctl(fd, BINDER_VERSION, &version) == 0 &&
             version.protocol_version == 8;
    close(fd);
    result(name, ok ? "pass" : "fail");
}

static void check_device(const char *name, const char *path)
{
    int fd = open(path, O_RDWR | O_CLOEXEC);
    result(name, fd >= 0 ? "pass" : "fail");
    if (fd >= 0)
        close(fd);
}

static void check_fork(void)
{
    pid_t child = fork();
    if (child == 0)
        _exit(0);
    if (child < 0) {
        result("fork_wait", "fail");
        return;
    }
    int status = 0;
    pid_t waited;
    do {
        waited = waitpid(child, &status, 0);
    } while (waited < 0 && errno == EINTR);
    result("fork_wait", waited == child && WIFEXITED(status) &&
           WEXITSTATUS(status) == 0 ? "pass" : "fail");
}

static void check_futex(void)
{
    int word = 0;
    long rc = syscall(SYS_futex, &word, FUTEX_WAKE, 1, NULL, NULL, 0);
    result("futex", rc == 0 ? "pass" : "fail");
}

static void check_epoll(void)
{
    int fd = epoll_create1(EPOLL_CLOEXEC);
    result("epoll", fd >= 0 ? "pass" : "fail");
    if (fd >= 0)
        close(fd);
}

static void check_eventfd(void)
{
    int fd = eventfd(0, EFD_CLOEXEC);
    result("eventfd", fd >= 0 ? "pass" : "fail");
    if (fd >= 0)
        close(fd);
}

static void check_inotify(void)
{
    int fd = inotify_init1(IN_CLOEXEC);
    result("inotify", fd >= 0 ? "pass" : "fail");
    if (fd >= 0)
        close(fd);
}


/* Legacy Android ION UAPI used with 4.1.x (pre-dma-buf-fd-only ABI).
 * Keep the structure in sync with the vendor's include/uapi/linux/ion.h.
 * This test must not be used for newer ION implementations.
 */
struct q60t_ion_allocation_data {
    size_t len;
    size_t align;
    unsigned int heap_id_mask;
    unsigned int flags;
    int handle;
};
struct q60t_ion_handle_data { int handle; };
#define Q60T_ION_IOC_ALLOC _IOWR('I', 0, struct q60t_ion_allocation_data)
#define Q60T_ION_IOC_FREE _IOWR('I', 1, struct q60t_ion_handle_data)

static void check_ion_allocation(void)
{
    int fd = open("/dev/ion", O_RDWR | O_CLOEXEC);
    if (fd < 0) {
        dprintf(STDOUT_FILENO, "Q60T_ION_TEST stage=open result=fail errno=%d\n", errno);
        result("ion", "fail");
        return;
    }
    dprintf(STDOUT_FILENO, "Q60T_ION_TEST stage=open result=pass\n");
    struct q60t_ion_allocation_data request = {
        .len = 4096, .align = 4096,
        .heap_id_mask = 1u, /* ION_HEAP_TYPE_SYSTEM = 0 */
        .flags = 0, .handle = 0,
    };
    if (ioctl(fd, Q60T_ION_IOC_ALLOC, &request) != 0 || request.handle <= 0) {
        dprintf(STDOUT_FILENO, "Q60T_ION_TEST stage=alloc result=fail errno=%d\n", errno);
        result("ion", "fail");
        close(fd);
        return;
    }
    dprintf(STDOUT_FILENO, "Q60T_ION_TEST stage=alloc result=pass bytes=4096\n");
    struct q60t_ion_handle_data release = { .handle = request.handle };
    int freed = ioctl(fd, Q60T_ION_IOC_FREE, &release) == 0;
    dprintf(STDOUT_FILENO, "Q60T_ION_TEST stage=free result=%s\n",
            freed ? "pass" : "fail");
    result("ion", freed ? "pass" : "fail");
    close(fd);
}

static void check_cgroups(void)
{
    FILE *input = fopen("/proc/filesystems", "r");
    if (!input) {
        result("cgroups", "unknown");
        return;
    }
    char line[256];
    int available = 0;
    while (fgets(line, sizeof(line), input)) {
        if (strstr(line, "\tcgroup\n") || strstr(line, "\tcgroup2\n")) {
            available = 1;
            break;
        }
    }
    fclose(input);
    /* Filesystem registration != Android cgroup controller layout. */
    result("cgroups", available ? "pass" : "fail");
}

static void check_selinux(void)
{
    /* This mounts only inside our throwaway guest. A missing policy is not
     * evidence that an Android SELinux setup is working.
     */
    (void)mkdir("/sys/fs/selinux", 0755);
    (void)mount_fs("selinuxfs", "/sys/fs/selinux", "selinuxfs");
    int fd = open("/sys/fs/selinux/enforce", O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        result("selinux_enforcing", "unknown");
        return;
    }
    char mode = '\0';
    ssize_t size = read(fd, &mode, 1);
    close(fd);
    result("selinux_enforcing", size == 1 && mode == '1' ? "pass" :
           size == 1 && mode == '0' ? "fail" : "unknown");
}

int main(void)
{
    int console = open("/dev/console", O_RDWR | O_NOCTTY);
    if (console >= 0) {
        (void)dup2(console, STDIN_FILENO);
        (void)dup2(console, STDOUT_FILENO);
        (void)dup2(console, STDERR_FILENO);
        if (console > STDERR_FILENO)
            close(console);
    }

    dprintf(STDOUT_FILENO,
            "Q60T_ANDROID_PROBE_BEGIN version=020 host_only=1 no_flash=1\n");
    int dev_ok = mount_fs("devtmpfs", "/dev", "devtmpfs");
    int proc_ok = mount_fs("proc", "/proc", "proc");
    int sys_ok = mount_fs("sysfs", "/sys", "sysfs");
    result("devtmpfs", dev_ok && proc_file_exists("/dev/console") ?
           "pass" : "fail");
    result("procfs", proc_ok && proc_file_exists("/proc/self/status") ?
           "pass" : "fail");
    result("sysfs", sys_ok && proc_file_exists("/sys/kernel") ?
           "pass" : "fail");
    check_fork();
    check_futex();
    check_epoll();
    check_eventfd();
    check_inotify();
    check_binder("binder");
    check_binder("hwbinder");
    check_binder("vndbinder");
    check_device("ashmem", "/dev/ashmem");
    check_ion_allocation();
    check_cgroups();
    check_selinux();
    dprintf(STDOUT_FILENO, "Q60T_ANDROID_PROBE_END version=020\n");
    for (;;)
        pause();
}
