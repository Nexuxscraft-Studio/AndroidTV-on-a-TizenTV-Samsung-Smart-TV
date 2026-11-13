# Build 076 — Samsung Nike-L SERET Bootchain (ARM32, read-only)

**Target research:** Samsung Q60T GQ50Q60TGUXZG, firmware generation T-NKLDEUC 2743.0.  
**Evidence dated:** 2026-11-13.  
**Status:** \`STATIC_WRAPPER_FDT_ZIMAGE_EVIDENCE\` — **no TV boot, no bootloader unlock, no flash authorization**.

This records the owner's reproducible, read-only disassembly and hex dumps of the
already-extracted Samsung file \`seret.bin\`. The original firmware **is not stored
in this repository**, and the relationship between this reference firmware and
the exact retail 50-inch board/boot stage remains unverified.

## Input identity

| Item | Observation |
| --- | --- |
| Original file | \`seret.bin\` (decrypted reference components) |
| File size | **3,137,552 bytes** |
| SHA-256 | \`c97ae1b4db73c2981b13fa9b7121930d77702e8705641225c3a1506064bec728\` |
| Other available reference | \`ddr.init\`, **311,312 bytes**, SHA-256 \`128cb3a48977cd063fb26b33794f5180e2403260b956250e2b198db565b03708\` |
| Missing from server file search | \`onboot.bin\` — **not found**, not proof that it is absent from the actual TV |
| Source | Owner-provided \`sha256sum\`, \`xxd\`, \`arm-linux-gnueabihf-objdump\` output |
| Execution | **Offline only**; neither code was run on the Q60T nor its eMMC accessed |

\`file seret.bin\` reporting \`data\` is consistent with a raw binary lacking an
ELF/uImage wrapper. The entropy-like prefix of \`ddr.init\` does not establish
encryption or a cipher.

## Proven file layout and code/data boundary

All positions in this report are **file offsets** in the extracted \`seret.bin\`
unless clearly stated otherwise; **none are proven physical TV addresses**.

| File offset | Evidence | Interpretation |
| --- | --- | --- |
| \`0x000000\` | \`e1a0300f\` (\`mov r3, pc\`) | AArch32 startup wrapper |
| \`0x000034\` | \`b 0x4b8\` | Entry flow into wrapper |
| \`0x0004f0\` | \`add r4, pc, r4\` | PC-relative appended-header pointer |
| \`0x0006f8\` | \`bl 0x8000\` | **Internal call** to embedded image at file offset \`0x8000\` |
| \`0x008000\` | ARM NOPs; branch at \`0x8020\` | ARM zImage-style entry |
| \`0x008024\` | little-endian \`0x016f2818\` | ARM zImage magic |
| \`0x008028\` | \`0x00000000\` | zImage header start word |
| \`0x00802c\` | \`0x00198cd8\` | zImage header end word |
| \`0x1a0cd8\` | \`0x00002020\` | Appended block header; wrapper specifically compares this value |
| \`0x1a0cdc\` | \`0x0017e010\` | Unknown header field (do not call it a filesize) |
| \`0x1a0ce0\` | \`0x00006178\` | Unknown header field |

The embedded image begins at \`0x8000\`; its reported zImage end
\`0x198cd8\` relative to that start yields an **absolute appended-block file
offset \`0x1a0cd8\`**. The remainder is **1,430,328 bytes**:

\`\`\`text
0x00008000 + 0x00198cd8 = 0x001a0cd8
3137552 - 0x001a0cd8 = 1430328
\`\`\`

The original \`objdump -D -b binary\` output displays literal-pool words as if
they were instructions. Do **not** label \`0x7b0\`, \`0x958\` or the zImage magic
word as executable instructions.

### The appended \`0x2020\` header is genuinely referenced

Confirmed by three *independent supplied outputs* (objdump, literal-pool
hexdump, and block hexdump):

\`\`\`asm
0x4e8  ldr   r4, [pc, #704]   ; literal at file offset 0x7b0 = 0x001a07e0
0x4f0  add   r4, pc, r4       ; ARM PC value here: 0x4f8
                              ; r4 = 0x4f8 + 0x001a07e0 = 0x001a0cd8
0x534  ldr   r3, [r4]
0x544  movw  r1, #0x2020
0x548  cmp   r3, r1
\`\`\`

Hex at \`0x1a0cd8\` is \`20 20 00 00\` (little-endian \`0x00002020\`).
The branch at \`0x54c\` distinguishes that header from the \`0x101\` case.
This proves a wrapper **reference to the appended block and a comparison
against its first word**, not that an unmodified or modified image is
accepted by the hardware bootloader.

## Flattened Device Tree and command-line evidence

| File offset | Concrete evidence | What it supports |
| --- | --- | --- |
| \`0x958\` | literal \`0xd00dfeed\` compared by function \`0x808\` | FDT header recognition |
| \`0x24e0\` | \`/memory/reg\\0\` | Search target for function \`0x354\` |
| \`0x24f6\` | \`/chosen/bootargs\\0\` | Boot-arguments lookup |
| \`0x354\` | FDT property lookup then big-endian writes to property cells | **Conditional** alteration of \`/memory/reg\` |
| \`0x6c8–0x6d4\` | passes \`r2 = 0x02000000\` to \`0x354\` | A **32 MiB parameter** on this call path, **not total installed RAM** |
| \`0x3e0\` | calls \`0xfc\`, formatting helpers and \`0x1cc\` | Memory-related command-line editing |
| \`0xfc\` | compares sought text and overwrites matched token bytes with \`0x20\` | Token removal by replacing bytes with spaces |
| \`0x1cc\` | trims trailing spaces and copies a string | Text appending into a space-padded buffer |
| \`0x23c\` | scans and compacts repeated spaces | Command-line normalization |
| \`0x2b8\` | parses decimal characters into a number | \`atoi\`-like helper |
| \`0x2ec\` | scanning with \`0x95c\` comparisons | \`strstr\`-like helper |

The code explicitly contains \`mem=\`, \`M@\`, \`root=\`, \`vmalloc=\`,
\`rootfstype=\`, \`rootwait\`, \`crashkernel=\`, and \`loglevel=3\`.
These are **possible operations supported by the wrapper**; the *actual live
boot command line* remains unknown.

At \`0x6ec–0x6f8\` the wrapper places \`r0=0\`, \`r1=0\`, \`r2=r4\` before
calling the image entry at \`0x8000\`. This matches conventional ARM Linux
boot-register usage and is evidence for **the internal handoff**. The actual
CPU state, DRAM address, pre-boot verification, and retail device handoff
are **not verified**.

## Hypotheses requiring confirmation

- Whether the embedded image is a dedicated early/recovery Linux and
  exactly what code is decompressed/entered.
- Meaning of the \`0x2020\` container format and \`0x17e010\`/\`0x6178\` fields;
  their names and semantics remain **unknown**.
- Whether \`seret.bin\` runs directly before the normal \`uImage\`, and which
  component loads or authenticates it.
- The early \`onboot.bin\` binary and its acceptance/signature policy.
- The full 50-inch board memory map; do not transplant the declared
  \`0x80008000\` from \`uImage\` as a known-safe RAM address.
- A **nonpersistent, authorized boot path plus tested recovery**; still absent.

## Offline reproducibility

The checker only *reads* an existing reference file and prints JSON;
it does not install firmware, touch the TV or write a report unless the
operator redirects standard output.

\`\`\`bash
python3 porting/build076/seret_audit.py \
  --seret /opt/samsung-atv-lab/samsung/firmware-2743/decrypted/seret.bin

python3 -m unittest discover -s porting/build076/tests -v
\`\`\`

Use Ghidra to expand function-level control-flow evidence, with separate
file offsets vs. mapped addresses. Do not treat disassembling arbitrary
compressed bytes as code, or count an interrupted Ghidra export as evidence.

Related reports: [Build 061 bootchain](../../reports/bootchain_forensics_build061.json),
[Build 071 bootloader research](../build071/README.md),
[Build 072 boot feasibility](../build072/README.md),
and [boot/recovery gates](../boot-evidence.json).

**No binary extracts, device secrets, console log identifiers, or Samsung
firmware files were uploaded to GitHub in this build.**
