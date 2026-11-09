/* Build 020: compile with an Android NDK clang, not GNU glibc.
 * This is a minimal Bionic link/ELF-preparation sample. It has NOT run on QEMU.
 */
#include <unistd.h>

int main(void)
{
    static const char message[] = "Q60T_BIONIC_HELLO version=020 host_only=1\n";
    return write(STDOUT_FILENO, message, sizeof(message) - 1) ==
        (ssize_t)(sizeof(message) - 1) ? 0 : 1;
}
