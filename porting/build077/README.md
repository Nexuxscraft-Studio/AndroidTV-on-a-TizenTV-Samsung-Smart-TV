# Build 077 — SERET AArch32 Wrapper Deep Analysis (offline only)

**Target:** Samsung Q60T GQ50Q60TGUXZG; reference components from firmware T-NKLDEUC 2743.0.  
**Date:** 2026-11-13.  
**Status:** `OFFLINE_STATIC_CONTROL_FLOW_CORROBORATED` if and only if the owner's original `seret.bin` matches the pinned SHA and code bytes. **No hardware boot authorization**.

## Why this exists

Build 076 establishes:

- `seret.bin` (3,137,552 bytes; SHA-256 pinned in `porting/build076/seret_audit.py`)
- ARM32 wrapper, ARM-zImage signature at file offset `0x8024`, embedded image entry at `0x8000`
- Header beginning at `0x1a0cd8` immediately after zImage end, with word0 `0x2020`
- Wrapper FDT/property editing routines and Linux AArch32-style register handoff
- No evidence of `onboot.bin` behavior, working secure-boot bypass, safe RAM boot or TV recovery

This build adds a **machine-checkable static A32 instruction and branch audit**.
It does not disassemble decompressed code, identify the `0x2020` format,
emulate boot firmware or patch a Samsung binary.

## More specific verified A32 chain

These are **file offsets**, not physical/virtual addresses on the actual TV.

| File offset | A32 instruction | Static observation |
| --- | --- | --- |
| `0x4e8` | `ldr r4, [pc, #704]` | Fetches little-endian literal word at file offset `0x7b0` |
| `0x7b0` | literal `0x001a07e0` | Data pool; not an instruction |
| `0x4f0` | `add r4, pc, r4` | `0x4f8 + 0x1a07e0 = 0x1a0cd8` |
| `0x534` | `ldr r3, [r4]` | Reads the header's first word |
| `0x544` | `movw r1, #0x2020` | Loads the header tag |
| `0x548` | `cmp r3, r1` | Compares it against the appended tag |
| `0x6ec` | `mov r1, #0` | Part of AArch32 boot-register setup |
| `0x6f0` | `mov r2, r4` | Loads likely FDT pointer into r2 |
| `0x6f4` | `mov r0, r1` | Sets r0 to zero |
| `0x6f8` | `bl 0x8000` | Calls embedded zImage **inside the file's ARM32 code** |

**Important:** The source also has conditional dispatch and branching;
the table does not establish that *all these instructions were executed* on
the user's TV. A static `bl` target does not prove that the installed
bootloader executes `seret.bin`, accepts modified images or reaches Linux.

The analysis of `0x4b8..0x7ac` scans only B/BL immediate encodings. It deliberately
excludes the literal pool beginning at `0x7ac` and does not pretend to
perform complete ARM decoding. A branch instruction present in this range is
not necessarily runtime-reachable.

### Current data block hypothesis

At `0x1a0cd8` the first three 32-bit words are:

```text
0x00002020
0x0017e010
0x00006178
```

The first is directly compared by the wrapper. The following fields
**remain uninterpreted**. The trailing block is 1,430,328 bytes; an
unrecognized high-entropy header cannot by itself prove encrypted or
compressed data. Build 077 reports Shannon entropy for the first 64 KiB
after the 12-byte header for comparison only.

## Run on the Debian development server

The original `seret.bin` must remain **outside Git**. From the checked-out
`feature/build077-seret-deep-analysis` branch:

```bash
python3 -m unittest discover -s porting/build076/tests -v
python3 -m unittest discover -s porting/build077/tests -v

python3 porting/build076/seret_audit.py \
  --seret /opt/samsung-atv-lab/samsung/firmware-2743/decrypted/seret.bin

python3 porting/build077/seret_deep_audit.py \
  --seret /opt/samsung-atv-lab/samsung/firmware-2743/decrypted/seret.bin
```

The Build 077 tool fails closed when the input SHA, size, zImage/header
evidence, or recorded instruction words differ; it reads only the named
file and prints JSON to standard output. All tests use synthetic bytes.

## Research questions next

1. Recover the complete control flow and data-flow around `0x4b8`, including
   the conditional `0x2020` vs. `0x101` paths; confirm exact dispatch and
   pointer use with Ghidra and original raw A32 file offsets.
2. Identify `0x17e010` and `0x6178` using *source-derived evidence*, not field
   names invented from sizes.
3. Identify the image decompressed by the embedded `zImage` and its
   exact intended RAM region, without equating file offsets with RAM.
4. Locate/identify the early `onboot.bin` stage using publicly released
   sources, available static reference components or a **passive** and
   explicitly authorized capture.
5. Keep Linux 6.6.162 first-hardware-boot blocked until a demonstrated,
   recoverable, authorized handoff exists.

## CI limitation observed on PR #18

At 2026-11-13 the general `host-only-tests.yml` workflow failed **before
any job step began** (job steps empty, runner IDs 0, zero billed Ubuntu
milliseconds). Thus there is *no evidence of a Python test failure from
that GitHub run*. The specific reason that hosted runners could not start
(billing/limits/account/availability/etc.) has not been established.
Do **not** move untrusted PR-triggered test jobs to the self-hosted runner.
The owner's local Build 076 SHA checker and all five unit tests passed;
those are local, not GitHub-hosted CI, results.

**No extracted firmware files, patched binaries, signing keys, bootloader
bypasses, TV flash actions, or elevated permissions are part of Build 077.**
