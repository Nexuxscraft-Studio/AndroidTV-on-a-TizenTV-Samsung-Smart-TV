# BUILD112 — Samsung seret.bin static handoff evidence

**Strictly offline/read-only.** No eMMC writes, SDB actions, flashing or boot experiments.

This continues the BUILD076/098–111 bootchain work. It does **not** claim that
file offsets equal executable memory addresses or that static ARM branch
candidates are reachable bootloader instructions.

## On the Debian analysis machine

```bash
python3 porting/build112/seret_handoff_scan.py --self-test
python3 porting/build112/seret_handoff_scan.py \
  --seret /absolute/path/to/seret.bin \
  --uimage /absolute/path/to/uImage \
  --output /tmp/build112-seret-handoff.json
```

Only pass paths to **already extracted** stock artifacts. Omit `--uimage` if unavailable.

## Report interpretation

- SHA-256 hashes record exactly which input files were examined.
- zImage magic is checked at candidate image start + 0x24; presence is **not** proof of execution.
- ARM B/BL candidates are decoded PC-relatively across the first 0x8000 bytes. The reported target offsets assume a contiguous runtime mapping. They may be false positives in data or unreachable code.
- ARM CMP r2,#0 and text occurrences are **candidate evidence only**, not a register-flow proof.
- FDT header candidates include big-endian totalsize bounds checks.
- Legacy uImage fields are reported if supplied; the load/entry values are **header claims**, not measured runtime addresses.

## Next gated phase

Use the JSON offsets to inspect only relevant disassembly windows, trace
instructions leading to the handoff, and identify the origin of r2. Validate
the memory map and signature gate from independent runtime evidence before
considering any reversible hardware RAM boot. **Hardware boot remains NO-GO.**
