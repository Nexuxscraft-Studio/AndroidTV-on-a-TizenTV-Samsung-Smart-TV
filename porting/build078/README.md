# Build 078 — Q60T Firmware Authentication Evidence

**Date:** 2026-11-13  
**Target:** Samsung Q60T GQ50Q60TGUXZG; existing offline reference firmware T-NKLDEUC 2743.0.  
**Scope:** Public-source review and read-only comparison of the owner's already-extracted firmware components. **Not a TV boot or signature verification.**

## Most important finding: common 16-byte tail is retained CBC plaintext padding

The source of the upstream Q60T decryptor resolves a major ambiguity from
Build 077:

1. [Synacktiv, `firmware/decrypt.py`](https://github.com/synacktiv/samsung-q60t-exploit/blob/main/firmware/decrypt.py#L223-L243)
   calls `AES.new(..., AES.MODE_CBC, ...)`, decrypts the *entire* encrypted
   partition, and writes the decrypted bytes directly with `f.write(dec)`.
   There is **no PKCS#7-unpadding step**.
2. In the separate public [msddecrypt implementation by bugficks/SamyGO](https://github.com/bugficks/msddecrypt/blob/main/src/msddecrypt.py#L210-L232),
   the writer explicitly truncates the decrypted output using the final
   padding-length byte. This shows that extraction tools can differ in
   whether padding is retained.
3. The owner's six local extracted files all end in exactly **16 × `0x10`**,
   consistent with the *full-block* PKCS#7 padding of AES-CBC plaintext.
   If these files were produced by the no-unpadding extraction path,
   the 16-byte suffix is explained by the tool. It is **not by itself
   evidence of a Samsung-specific authentication trailer**.

The actual on-device update/decrypt implementation has not been verified.
The common `0x10` suffix applies to **these extracted files**, not to the
encrypted bytes stored in the original `upgrade.msd`.

## Additional strong clue: a real RSA descriptor in the MSD metadata

The public [Synacktiv parser](https://github.com/synacktiv/samsung-q60t-exploit/blob/main/firmware/decrypt.py#L168-L185)
handles **TLV tag `0x10`** as `OURSAValidationDesc`. It reads a
**public-key identifier**, a **2-byte signature length** and the corresponding
**signature bytes** from the decrypted **MSD metadata**.

This is direct **source evidence that the update's metadata includes a
signature-validation descriptor**. The script does not cryptographically
verify it. That metadata descriptor is **not the same object** as the
256-byte end window in each decrypted partition. We have **not established**
whether those trailing 256 bytes are per-component RSA signatures or other
signed-image data, nor the deployed verification routine/trust anchor.

In particular, distinguish:

- **Update package parsing / verification** (metadata TLV and updater code)
- **Partition-image end fields** (the measured last 256 bytes of extracted files)
- **BootROM / early boot image validation** (actual Q60T acceptance of images)

Evidence for the first does **not** establish the third. Knowing how a
package is decrypted does not make a modified image authorized or bootable.

## Owner-observed six-component footer pattern

The final 272 decrypted bytes consist of a **256-byte candidate region**
followed by **16 bytes `0x10`**:

| Component | Extracted bytes | Candidate 256-byte start | Entropy (bits/byte) | Candidate zero bytes | 256-byte SHA-256 (prefix) |
| --- | ---: | --- | ---: | ---: | --- |
| `seret.bin` | 3,137,552 | `0x2fdf00` | 7.146 | 1 | `3c02a9c0` |
| `uImage` | 7,041,296 | `0x6b7000` | 7.228 | 1 | `29b4bdfe` |
| `sign.bin` | 1,040 | `0x300` | **0.000** | **256** | `5341e6b2` |
| `secos.bin` | 4,186,128 | `0x3fdf00` | 7.274 | 2 | `add0b88c` |
| `ddr.init` | 311,312 | `0x4bf00` | 7.161 | 0 | `201171e7` |
| `dtb.bin` | 1,564,688 | `0x17df00` | 7.252 | 1 | `b30b7147` |

All six 16-byte suffixes match exactly. **`sign.bin` has 256 zero bytes
instead of a varying 256-byte window.** This is a striking structural
difference, not proof that signature verification is disabled.

The `uImage` candidate begins precisely after the **declared uImage
payload** (64-byte legacy header + 7,040,960-byte payload = `0x6b7000`).
This establishes a container boundary, **not** that the following 256 bytes
constitute an authenticated signature.

The original Build 061 `sign.bin` analysis observed `Salted__` at
offset `0x108`; marker recognition alone cannot identify the effective
key store, validation rule, or whether a second-level inner container
is involved. We do not infer a hardware-held key just from the marker.

## Source-code review: what's proven, and what's missing

| Evidence / code | Finding | Limit |
| --- | --- | --- |
| Synacktiv Q60T `decrypt.py` | Parses `OURSAValidationDesc` in MSD metadata; performs AES-CBC extraction | **Does not execute RSA verification** |
| SamyGO `msddecrypt.py` | Explicitly discards the terminal padding bytes from extracted partitions | Is a separate tool, not proof of actual Samsung TV implementation |
| Build 077 local SERET disassembly | ARM wrapper, zImage entry, FDT/bootargs alterations and `0x2020` block | **No proven auth-verify call**, no early `onboot.bin` |
| TV's proprietary early loader / TrustZone | **Not yet acquired / inspected** | No verified on-device signature policy or authorized boot path |

A source tree containing `RSA_verify` or `OURSAValidationDesc` text is
not sufficient without resolving its **callers**, data dependencies and
reachability. Generic Samsung GPL kernel code is not automatically the
firmware updater or immutable BootROM verifier.

## Repeat the offline footer check

The script reads **only** the existing reference files; it emits summary JSON
to stdout (no binary data, salts, keys or signatures):

```bash
cd /opt/samsung-atv-lab/repo
git fetch origin
git switch --track origin/feature/build078-firmware-auth-evidence

python3 -m unittest discover -s porting/build078/tests -v
python3 porting/build078/footer_auth_audit.py \
    --components-dir /opt/samsung-atv-lab/samsung/firmware-2743/decrypted \
    --strict
```

The six SHA-256 reference windows in `footer_auth_audit.py` are based on
the owner's output. The seven unit tests are synthetic and never require
Samsung files. The new tests are **not yet reported as run on the owner
server or by GitHub Actions**.

## Follow-on evidence to pursue

1. Identify the **actual update verification routine** that consumes the
   metadata `OURSAValidationDesc`. Prefer official/authorized source,
   rather than guessing from static strings.
2. Determine if the decrypted metadata supplies a **256-byte signature
   length** for each of the six image items; do not conflate metadata
   signature bytes with file tails.
3. If the owner has trusted static disassembly or saved logs from
   verification code, correlate their callers and trust-anchor handling.
4. Confirm whether the 256-byte trailer of each *extracted* image is part
   of a signed plaintext file or simply an unused reserved slot.
5. Keep all hardware boot, flash, recovery and signing-bypass claims
   **UNVERIFIED / BLOCKED** until independently established.

**No firmware binaries, signatures, passwords or keys have been
committed. The Q60T and its storage were not accessed.**
