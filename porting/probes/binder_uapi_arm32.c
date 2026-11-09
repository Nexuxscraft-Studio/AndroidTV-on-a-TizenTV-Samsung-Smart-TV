/*
 * Compile-only ARM32 Binder UAPI layout check for the Samsung 4.1 header.
 *
 * Deliberately no main(), file operations, ioctl(), networking or device I/O.
 * Run only with a separate cross compiler on a development machine.
 */

#include <sys/types.h>
#include <stddef.h>
#include <linux/android/binder.h>
#include <linux/ioctl.h>

_Static_assert(sizeof(binder_size_t) == 8,
               "Binder size fields must use 64-bit IPC layout");
_Static_assert(sizeof(binder_uintptr_t) == 8,
               "Binder addresses must use 64-bit IPC layout");
_Static_assert(BINDER_CURRENT_PROTOCOL_VERSION == 8,
               "Old 32-bit Binder protocol is unsuitable for this experiment");
_Static_assert(sizeof(struct binder_write_read) == 48,
               "Unexpected ARM32 Binder write-read wire layout");
_Static_assert(sizeof(struct flat_binder_object) == 24,
               "Unexpected flat Binder object wire layout");
_Static_assert(sizeof(struct binder_transaction_data) == 64,
               "Unexpected Binder transaction data wire layout");
_Static_assert(_IOC_NR(BINDER_WRITE_READ) == 1, "Binder IPC ioctl number changed");
_Static_assert(_IOC_NR(BINDER_VERSION) == 9, "Binder version ioctl number changed");

int q60t_binder_uapi_compile_only(void)
{
    return (int)(sizeof(struct binder_write_read) +
                 sizeof(struct binder_transaction_data) +
                 sizeof(struct flat_binder_object));
}
