/* Build 018: standalone ARM32 initramfs /init for QEMU only.
 *
 * It checks Samsung 4.1.10 Binder ABI via BINDER_VERSION and then attempts
 * a bounded two-process context-manager roundtrip. No Android/TV access.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

struct binder_version {
    int protocol_version;
};
#define BINDER_VERSION _IOWR('b', 9, struct binder_version)

/* Minimal UAPI subset from Samsung Linux 4.1.10 include/uapi/linux/android/
 * binder.h, configured with BINDER_IPC_32BIT=n. Do not replace these u64
 * pointer-sized fields with 32-bit C pointers: protocol version is 8.
 */
typedef uint64_t binder_size_t;
typedef uint64_t binder_uintptr_t;

struct binder_write_read {
    binder_size_t write_size;
    binder_size_t write_consumed;
    binder_uintptr_t write_buffer;
    binder_size_t read_size;
    binder_size_t read_consumed;
    binder_uintptr_t read_buffer;
};

struct binder_transaction_data {
    union {
        uint32_t handle;
        binder_uintptr_t ptr;
    } target;
    binder_uintptr_t cookie;
    uint32_t code;
    uint32_t flags;
    pid_t sender_pid;
    uid_t sender_euid;
    binder_size_t data_size;
    binder_size_t offsets_size;
    union {
        struct {
            binder_uintptr_t buffer;
            binder_uintptr_t offsets;
        } ptr;
        uint8_t buf[8];
    } data;
};

_Static_assert(sizeof(struct binder_write_read) == 48, "wrong Binder write/read ABI");
_Static_assert(sizeof(struct binder_transaction_data) == 64, "wrong Binder transaction ABI");

#define BINDER_WRITE_READ _IOWR('b', 1, struct binder_write_read)
#define BINDER_SET_CONTEXT_MGR _IOW('b', 7, int32_t)
#define BC_TRANSACTION _IOW('c', 0, struct binder_transaction_data)
#define BC_REPLY _IOW('c', 1, struct binder_transaction_data)
#define BC_FREE_BUFFER _IOW('c', 3, binder_uintptr_t)
#define BC_ENTER_LOOPER _IO('c', 12)
#define BR_ERROR _IOR('r', 0, int32_t)
#define BR_OK _IO('r', 1)
#define BR_TRANSACTION _IOR('r', 2, struct binder_transaction_data)
#define BR_REPLY _IOR('r', 3, struct binder_transaction_data)
#define BR_ACQUIRE_RESULT _IOR('r', 4, int32_t)
#define BR_DEAD_REPLY _IO('r', 5)
#define BR_TRANSACTION_COMPLETE _IO('r', 6)
#define BR_INCREFS _IOR('r', 7, struct binder_ptr_cookie)
#define BR_ACQUIRE _IOR('r', 8, struct binder_ptr_cookie)
#define BR_RELEASE _IOR('r', 9, struct binder_ptr_cookie)
#define BR_DECREFS _IOR('r', 10, struct binder_ptr_cookie)
#define BR_NOOP _IO('r', 12)
#define BR_SPAWN_LOOPER _IO('r', 13)
#define BR_FAILED_REPLY _IO('r', 17)

struct binder_ptr_cookie {
    binder_uintptr_t ptr;
    binder_uintptr_t cookie;
};

#define Q60T_BINDER_MAPPING_SIZE (128U * 1024U)
#define Q60T_BINDER_READ_SIZE 4096U
#define Q60T_BINDER_TRANSACTION_CODE 0x51313842U

static const char q60t_request[] = "Q60T_BINDER_PING_018";
static const char q60t_reply[] = "Q60T_BINDER_PONG_018";

static int binder_write_bytes(int fd, const void *bytes, size_t size)
{
    struct binder_write_read io = { 0 };
    io.write_size = size;
    io.write_buffer = (binder_uintptr_t)(uintptr_t)bytes;
    if (ioctl(fd, BINDER_WRITE_READ, &io) < 0) {
        dprintf(STDOUT_FILENO, "Q60T_BINDER_WRITE_IOCTL_FAIL errno=%d\n", errno);
        return -1;
    }
    if (io.write_consumed != size) {
        dprintf(STDOUT_FILENO, "Q60T_BINDER_SHORT_WRITE consumed=%llu expected=%zu\n",
                (unsigned long long)io.write_consumed, size);
        return -1;
    }
    return 0;
}

static int binder_write_command(int fd, uint32_t command)
{
    return binder_write_bytes(fd, &command, sizeof(command));
}

static int binder_write_transaction(int fd, uint32_t command,
                                    const struct binder_transaction_data *tr)
{
    uint8_t packet[sizeof(uint32_t) + sizeof(*tr)];
    memcpy(packet, &command, sizeof(command));
    memcpy(packet + sizeof(command), tr, sizeof(*tr));
    return binder_write_bytes(fd, packet, sizeof(packet));
}

static int binder_free_buffer(int fd, binder_uintptr_t ptr)
{
    uint32_t cmd = BC_FREE_BUFFER;
    uint8_t packet[sizeof(cmd) + sizeof(ptr)];
    memcpy(packet, &cmd, sizeof(cmd));
    memcpy(packet + sizeof(cmd), &ptr, sizeof(ptr));
    return binder_write_bytes(fd, packet, sizeof(packet));
}

static int binder_open_mapped(void **mapped)
{
    int fd = open("/dev/binder", O_RDWR | O_CLOEXEC | O_NONBLOCK);
    if (fd < 0)
        return -1;
    *mapped = mmap(NULL, Q60T_BINDER_MAPPING_SIZE, PROT_READ,
                   MAP_PRIVATE, fd, 0);
    if (*mapped == MAP_FAILED) {
        int saved_errno = errno;
        close(fd);
        errno = saved_errno;
        return -1;
    }
    return fd;
}

static int binder_read_event(int fd, uint32_t *event,
                             struct binder_transaction_data *transaction)
{
    /* poll() bounds the guest experiment; the descriptor is non-blocking. */
    for (int attempt = 0; attempt < 50; ++attempt) {
        struct pollfd ready = { .fd = fd, .events = POLLIN };
        int polled = poll(&ready, 1, 100);
        if (polled < 0 && errno == EINTR)
            continue;
        if (polled < 0 || (ready.revents & (POLLERR | POLLHUP | POLLNVAL)))
            return -1;
        if (polled == 0)
            continue;

        uint8_t buffer[Q60T_BINDER_READ_SIZE];
        struct binder_write_read io = { 0 };
        io.read_size = sizeof(buffer);
        io.read_buffer = (binder_uintptr_t)(uintptr_t)buffer;
        if (ioctl(fd, BINDER_WRITE_READ, &io) < 0) {
            if (errno == EINTR || errno == EAGAIN)
                continue;
            dprintf(STDOUT_FILENO, "Q60T_BINDER_READ_IOCTL_FAIL errno=%d\n", errno);
            return -1;
        }
        if (io.read_consumed > sizeof(buffer))
            return -1;
        for (size_t at = 0; at + sizeof(uint32_t) <= io.read_consumed;) {
            uint32_t cmd;
            memcpy(&cmd, buffer + at, sizeof(cmd));
            at += sizeof(cmd);
            if (cmd == BR_NOOP || cmd == BR_OK || cmd == BR_TRANSACTION_COMPLETE ||
                cmd == BR_SPAWN_LOOPER)
                continue;
            if (cmd == BR_TRANSACTION || cmd == BR_REPLY) {
                if (at + sizeof(*transaction) > io.read_consumed)
                    return -1;
                memcpy(transaction, buffer + at, sizeof(*transaction));
                *event = cmd;
                return 0;
            }
            if (cmd == BR_INCREFS || cmd == BR_ACQUIRE ||
                cmd == BR_RELEASE || cmd == BR_DECREFS) {
                if (at + sizeof(struct binder_ptr_cookie) > io.read_consumed)
                    return -1;
                at += sizeof(struct binder_ptr_cookie);
                continue;
            }
            if (cmd == BR_ERROR || cmd == BR_ACQUIRE_RESULT) {
                int32_t error;
                if (at + sizeof(error) > io.read_consumed)
                    return -1;
                memcpy(&error, buffer + at, sizeof(error));
                dprintf(STDOUT_FILENO, "Q60T_BINDER_DRIVER_ERROR cmd=%u value=%d\n",
                        cmd, error);
                return -1;
            }
            dprintf(STDOUT_FILENO, "Q60T_BINDER_UNEXPECTED_EVENT cmd=%u\n", cmd);
            return -1;
        }
    }
    dprintf(STDOUT_FILENO, "Q60T_BINDER_EVENT_TIMEOUT\n");
    return -1;
}

static int binder_match_payload(const struct binder_transaction_data *tr,
                                const void *mapping, const char *expected,
                                size_t expected_size)
{
    uintptr_t ptr = (uintptr_t)tr->data.ptr.buffer;
    uintptr_t base = (uintptr_t)mapping;
    if (tr->data.ptr.buffer != (binder_uintptr_t)ptr ||
        tr->data_size != expected_size ||
        ptr < base || ptr - base > Q60T_BINDER_MAPPING_SIZE ||
        expected_size > Q60T_BINDER_MAPPING_SIZE - (ptr - base))
        return -1;
    return memcmp((const void *)ptr, expected, expected_size) == 0 ? 0 : -1;
}

static int binder_client(void)
{
    void *mapping = NULL;
    int fd = binder_open_mapped(&mapping);
    if (fd < 0) {
        dprintf(STDOUT_FILENO, "Q60T_BINDER_CLIENT_OPEN_FAIL errno=%d\n", errno);
        return 1;
    }
    struct binder_transaction_data tr = { 0 };
    tr.target.handle = 0; /* context manager */
    tr.code = Q60T_BINDER_TRANSACTION_CODE;
    tr.data_size = sizeof(q60t_request);
    tr.data.ptr.buffer = (binder_uintptr_t)(uintptr_t)q60t_request;
    if (binder_write_transaction(fd, BC_TRANSACTION, &tr) < 0)
        goto fail;
    for (int attempt = 0; attempt < 5; ++attempt) {
        uint32_t event;
        struct binder_transaction_data response = { 0 };
        if (binder_read_event(fd, &event, &response) < 0)
            goto fail;
        if (event != BR_REPLY)
            continue;
        int valid = binder_match_payload(&response, mapping, q60t_reply,
                                         sizeof(q60t_reply));
        if (binder_free_buffer(fd, response.data.ptr.buffer) < 0 || valid != 0)
            goto fail;
        dprintf(STDOUT_FILENO, "Q60T_BINDER_CLIENT_REPLY_OK\n");
        munmap(mapping, Q60T_BINDER_MAPPING_SIZE);
        close(fd);
        return 0;
    }
fail:
    dprintf(STDOUT_FILENO, "Q60T_BINDER_CLIENT_REPLY_FAIL\n");
    munmap(mapping, Q60T_BINDER_MAPPING_SIZE);
    close(fd);
    return 1;
}

static int binder_server(int start_pipe, pid_t child)
{
    void *mapping = NULL;
    int fd = binder_open_mapped(&mapping);
    char start_signal = 'N';
    if (fd < 0) {
        dprintf(STDOUT_FILENO, "Q60T_BINDER_SERVER_OPEN_FAIL errno=%d\n", errno);
        goto fail;
    }
    int context_mgr = 0;
    if (ioctl(fd, BINDER_SET_CONTEXT_MGR, &context_mgr) < 0) {
        dprintf(STDOUT_FILENO, "Q60T_BINDER_CONTEXT_MGR_FAIL errno=%d\n", errno);
        goto fail;
    }
    if (binder_write_command(fd, BC_ENTER_LOOPER) < 0)
        goto fail;
    start_signal = 'Y';
    if (write(start_pipe, &start_signal, 1) != 1)
        goto fail;
    close(start_pipe);
    start_pipe = -1;
    uint32_t event;
    struct binder_transaction_data request = { 0 };
    if (binder_read_event(fd, &event, &request) < 0 || event != BR_TRANSACTION)
        goto fail;
    int valid = (request.code == Q60T_BINDER_TRANSACTION_CODE &&
                 request.flags == 0 &&
                 binder_match_payload(&request, mapping, q60t_request,
                                      sizeof(q60t_request)) == 0);
    if (!valid) {
        binder_free_buffer(fd, request.data.ptr.buffer);
        goto fail;
    }
    dprintf(STDOUT_FILENO, "Q60T_BINDER_SERVICE_REQUEST_OK\n");

    struct binder_transaction_data reply = { 0 };
    reply.data_size = sizeof(q60t_reply);
    reply.data.ptr.buffer = (binder_uintptr_t)(uintptr_t)q60t_reply;
    if (binder_write_transaction(fd, BC_REPLY, &reply) < 0 ||
        binder_free_buffer(fd, request.data.ptr.buffer) < 0)
        goto fail;
    /* Keep the context manager alive until the client has received the
     * reply; closing /dev/binder here would tear down its Binder process.
     */
    int child_status = 0;
    pid_t waited;
    do {
        waited = waitpid(child, &child_status, 0);
    } while (waited < 0 && errno == EINTR);
    if (waited != child || !WIFEXITED(child_status) || WEXITSTATUS(child_status))
        goto fail;
    munmap(mapping, Q60T_BINDER_MAPPING_SIZE);
    close(fd);
    return 0;
fail:
    dprintf(STDOUT_FILENO, "Q60T_BINDER_SERVICE_REPLY_FAIL\n");
    if (start_pipe >= 0) {
        (void)write(start_pipe, &start_signal, 1);
        close(start_pipe);
    }
    if (fd >= 0) {
        munmap(mapping, Q60T_BINDER_MAPPING_SIZE);
        close(fd);
    }
    return 1;
}

static void binder_roundtrip(void)
{
    int channel[2];
    if (pipe(channel) < 0) {
        dprintf(STDOUT_FILENO, "Q60T_BINDER_TRANSACTION_FAIL reason=pipe\n");
        return;
    }
    pid_t child = fork();
    if (child < 0) {
        dprintf(STDOUT_FILENO, "Q60T_BINDER_TRANSACTION_FAIL reason=fork\n");
        close(channel[0]);
        close(channel[1]);
        return;
    }
    if (child == 0) {
        close(channel[1]);
        char signal_byte = 'N';
        ssize_t got = read(channel[0], &signal_byte, 1);
        close(channel[0]);
        _exit(got == 1 && signal_byte == 'Y' ? binder_client() : 1);
    }

    close(channel[0]);
    int server_result = binder_server(channel[1], child);
    if (server_result != 0) {
        int status = 0;
        (void)waitpid(child, &status, 0);
    }
    if (server_result == 0)
        dprintf(STDOUT_FILENO,
                "Q60T_BINDER_TRANSACTION_PASS protocol=8 request=PING reply=PONG\n");
    else
        dprintf(STDOUT_FILENO, "Q60T_BINDER_TRANSACTION_FAIL reason=roundtrip\n");
}

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
    binder_roundtrip();
    for (;;)
        pause();
}
