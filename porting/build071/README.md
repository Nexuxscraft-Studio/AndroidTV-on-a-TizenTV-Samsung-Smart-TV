# Build 071 – Samsung Q60T Bootloader Research

**Target:** GQ50Q60TGUXZG, Nike-L / T-NKLDEUC 2743.0.
**Scope:** Firmware/bootchain analysis on a development host only. No bootloader
installation, no partition writes, no signing bypass, no TV access or boot test.

## Current findings and evidence quality

| Question | Finding | Limit |
| --- | --- | --- |
| Original kernel image format | Legacy U-Boot uImage, ARM32 Linux 4.1.10, recorded load/entry 0x80008000 | A uImage header **does not** prove U-Boot executes on the TV |
| Early bootloader implementation | **Unknown** | No trustworthy early-boot capture from the 50-inch target |
| Signature/secure-world components | sign.bin, secos.bin, seret.bin inventoried in Build 061 | Existence is not verification of signing rules or bootrom acceptance |
| Alternate OS / GRUB / U-Boot execution | **Not demonstrated** | Unknown UEFI availability, authorization and entry point |
| Recovery / Tizen fallback | **Not demonstrated** | No nonpersistent boot or proven rollback on equivalent hardware |
| Exact target board revision | **Not verified** | Previous reference evidence includes 55-inch firmware |

Source-derived information:
- [Bootchain inventory](../BOOTCHAIN.md)
- [Build 061 forensics](../../reports/bootchain_forensics_build061.json)
- [Build 066 boot access](../build066/docs/BOOT_ACCESS.md)
- [Eight recovery/boot gates](../boot-evidence.json)

Do **not** equate the AArch32 zImage-style seret.bin with a verified
U-Boot loader. The Linux image header and CRCs provide format/integrity
evidence, not proof of installed first-stage/second-stage bootloaders.

## Reproduce, offline

From a repository checkout:

```bash
python3 porting/build071/bootloader_research.py
python3 -m unittest discover -s porting/build071/tests -v
```

If **original files already exist on the development host**, optionally
include the original extracted kernel and a saved, passively obtained UART
capture (not a live serial device):

```bash
python3 porting/build071/bootloader_research.py \
    --uimage /path/to/original/decrypted/uImage \
    --uart-log /path/to/saved/passive-uart-capture.txt \
    --output /tmp/q60t-build071-bootchain.json
```

The analyzer reuses the repository's CRC-checked, bounded `inspect_uimage`
implementation, reads only local files and writes only a new JSON report when
requested. It excludes raw serial text, which may contain serial numbers or
other sensitive data. A matching bootloader **banner is only a candidate**:
it must be corroborated with the provenance and timing of the capture.
Never publish or commit the raw UART capture or firmware binaries.

## Hardware next steps (no modification)

1. Identify the **exact** PCB, flash and RAM revision for the 50-inch target.
2. Establish the genuine early bootloader stage through trustworthy passive
   observation or vendor documentation. If authorized to inspect a serial
   console, confirm electrical levels and isolation first; never connect
   RS-232 voltage directly to TTL pins. Do not issue bootloader commands.
3. Characterize the real authentication/signature gates independently;
   neither filename conventions nor U-Boot CRCs are signature proofs.
4. Demonstrate a *nonpersistent* and recoverable boot path on equivalent
   hardware before even considering a change to the stock boot path.
5. Independently prove verified backups, recovery, rollback, watchdog fallback
   and power-loss recovery. These are fail-closed checks in boot-evidence.json.

## Boot manager decision

- **Now:** Leave Samsung's stock boot chain untouched and continue offline
  ARM32 porting / independent QEMU tests.
- **Simulation concept:** Experiment with a U-Boot `extlinux.conf` Tizen /
  LineageOS *mock* boot menu on a separate QEMU virtual machine. This does
  not demonstrate compatibility with Samsung's BootROM or firmware.
- **Not ready:** Replacing the bootloader or installing GRUB on the retail TV.
  No demonstrated EFI/UEFI environment, signature authorization, reversible
  test boot or recovery path exists.

General references, **not Samsung device-specific evidence**:
- U-Boot extlinux: https://docs.u-boot.org/en/stable/develop/bootstd/extlinux.html
- U-Boot Standard Boot: https://docs.u-boot.org/en/stable/develop/bootstd/overview.html
- GNU GRUB UEFI security: https://www.gnu.org/software/grub/manual/grub/html_node/UEFI-secure-boot-and-shim.html

## Explicit outcome

Build 071 may confirm the identity of **a file format** and summarize
candidates from passive early-boot text. It cannot prove the exact bootloader
or enable GRUB, replace Secure Boot, authorize flashing, or establish a
recoverable Tizen/LineageOS dual boot. All such status fields remain
UNVERIFIED / NOT_DEMONSTRATED until independent evidence exists.
