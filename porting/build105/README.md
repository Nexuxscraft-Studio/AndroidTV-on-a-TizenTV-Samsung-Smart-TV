# Build 105 MICOM source and integration audit

## Base

Use `feature/build097-module-artifacts` at `dee0f6306417eff23d5821856998de03e0851b67`. GitHub branch enumeration returned 54 branches across two cursor requests. The repository's recent PR listing returned #1–#28, all open and unmerged at the time of review. Build 097 (#27) builds Linux 6.6.162 ARM32 module artifacts and inherits the Build 094 driver integration and the Build 096 ARM32 validation. Compared with main, Build 058 hardware integration is 217 commits ahead, Build 095 is 380 ahead, and Build 097 is 387 ahead. Build 098 (#28) adds a RAM-boot readiness audit above Build 097. Build 097 gives this work the ARM32 build harness without requiring the RAM-boot audit.

The workspace had no checkout, and direct Git authentication to the private repository was unavailable. The source checks used the authenticated GitHub connector against the pinned commit.

## Original source availability

GitHub returned HTTP 404 at the pinned commit for all five requested paths:

- `drivers/misc/micom-msg/msg-wt61p807.c`
- `include/uapi/linux/micom-msg.h`
- `drivers/mfd/sdp_micom_messagebox.c`
- `drivers/mfd/sdp_micom_uart.c`
- `include/linux/mfd/sdp_micom.h`

The repository carries a derivative of the Nike-L GPL code in [patch 0013](../build059/kernel/patches/0013-soc-sdp-add-Micom-message-box-protocol-core-and-remote.patch). Its provenance notes name the original `drivers/mailbox/sdp_micom_msgbox.c` and a `tztv-micom/sdp_micom_messagebox.c`. Obtain and verify the Nike-L Samsung Linux 4.1.10 source package, including its actual file layout, before implementing the legacy ioctl client or reproducing the vendor retry behavior.

## Transport and existing integration

The locally archived stock Nike-L DTS contains `samsung,sdp-messagebox` at offset `0x9c0400` and a separate `samsung,tztv-micom` endpoint. Patch 0013 pairs these compatibles through the messagebox receive callback. The DTS also describes SDP UART controllers. The MICOM endpoint has no UART association in the inspected DTS.

Patch 0013 serializes commands that await ACKs, completes the waiter for the expected ACK or `SDP_MICOM_ACK_UNKNOWN`, and uses a caller-supplied timeout with `-ETIMEDOUT` on expiry. Handling of the unknown-command reply needs comparison with the original ioctl client's error semantics. The mailbox send path polls for a free slot with a bounded wait. The ACK path sends once per call and has no protocol retransmission loop. The patch wires `SDP_MSGBOX` and `SDP_MICOM` through Kconfig and Kbuild, with the core depending on the messagebox. This audit adds no ioctl client or Kbuild entry.

## Verification

A local freestanding Clang syntax check targeting `arm-linux-gnueabihf` confirmed 32-bit pointers and that the ARM ioctl encoding for read/write, size 12, type `0xB3`, number 1 is `0xC00CB301`. The actual `struct sdp_micom_usr_msg` layout and macro remain unverified pending the original UAPI header.

The Build 097 workflow declares `[self-hosted, debian]` and checks that `RUNNER_NAME` equals `debian`. The inherited host-only workflow runs synthetic checks independently of the kernel build.

## Build on Debian

Build 105 uses the existing Build 097 workflow and its two clean Linux
6.6.162 ARM32 builds. The same nine modules are verified. The build checks
that Kconfig retained the built-in messagebox and MICOM core before compiling
the IR modules that use them.

The [14 November 2026 PR job](https://github.com/Nexuxscraft-Studio/AndroidTV-on-a-TizenTV-Samsung-Smart-TV/actions/runs/43620406106/job/132524608395)
ran on runner and machine `debian`, in group `Default`. That job ran the
synthetic checks. It records the runner assignment for that job. Current
availability and label uniqueness require separate evidence.

## Compare the original files on the existing Debian host

The original tree can stay under `/opt/samsung-atv-lab`. From the existing
Debian checkout, check the following paths before comparing them with patch
0013 in the Build 105 branch. If any path differs, locate the matching
basename within the same Linux 4.1.10 tree and record the actual relative path.

```bash
src=/opt/samsung-atv-lab/samsung/build018-original/linux-4.1.10
for file in \
  drivers/misc/micom-msg/msg-wt61p807.c \
  include/uapi/linux/micom-msg.h \
  drivers/mfd/sdp_micom_messagebox.c \
  drivers/mfd/sdp_micom_uart.c \
  include/linux/mfd/sdp_micom.h
do
  if test -r "$src/$file"; then
    sha256sum "$src/$file"
  else
    find "$src" -type f -name "${file##*/}"
  fi
done
```

Use the header to verify the ioctl declaration and ARM32 struct layout,
then compare the command and ACK paths against the original client and
messagebox transport. Commit the resulting kernel patch to
`feature/build105-micom` and use the existing ARM32 workflow. The CI build
takes the patch from Git so it does not need access to the original source
tree.
