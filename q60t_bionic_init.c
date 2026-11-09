/* Build 021: statically linked ARM32 PID 1 for the disposable QEMU guest.
 *
 * Only execs a local, dynamically linked Bionic test application after
 * setting up proc, sysfs and devtmpfs. Never boots Samsung hardware.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

static void mount_local(const char *device, const char *target, const char *type)
{
    if (mount(device, target, type, 0, NULL) != 0 && errno != EBUSY)
        dprintf(STDOUT_FILENO, "Q60T_BIONIC_MOUNT_WARN target=%s errno=%d\n",
                target, errno);
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

    dprintf(STDOUT_FILENO, "Q60T_GUEST_INIT_STARTED host_only=1 no_flash=1\n");
    mount_local("devtmpfs", "/dev", "devtmpfs");
    mount_local("proc", "/proc", "proc");
    mount_local("sysfs", "/sys", "sysfs");
    dprintf(STDOUT_FILENO, "Q60T_BIONIC_EXEC_BEGIN version=021\n");

    pid_t child = fork();
    if (child == 0) {
        char *const argv[] = {"/system/bin/q60t_bionic_hello", NULL};
        char *const envp[] = {"PATH=/system/bin", "LD_LIBRARY_PATH=/system/lib", NULL};
        execve(argv[0], argv, envp);
        dprintf(STDERR_FILENO, "Q60T_BIONIC_EXECVE_FAILED errno=%d\n", errno);
        _exit(127);
    }
    if (child < 0) {
        dprintf(STDOUT_FILENO, "Q60T_BIONIC_EXEC_RESULT status=fail reason=fork\n");
    } else {
        int status = 0;
        pid_t waited;
        do {
            waited = waitpid(child, &status, 0);
        } while (waited < 0 && errno == EINTR);
        if (waited == child && WIFEXITED(status)) {
            dprintf(STDOUT_FILENO, "Q60T_BIONIC_EXEC_RESULT status=%s exit=%d\n",
                    WEXITSTATUS(status) == 0 ? "pass" : "fail", WEXITSTATUS(status));
        } else {
            dprintf(STDOUT_FILENO, "Q60T_BIONIC_EXEC_RESULT status=fail reason=signal_or_wait\n");
        }
    }

    /* PID 1 stays alive until the bounded QEMU runner stops the guest. */
    for (;;)
        pause();
}
