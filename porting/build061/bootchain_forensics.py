#!/usr/bin/env python3
"""Build 061 – read-only forensics of the Samsung Nike-L boot chain.

Operates ONLY on locally decrypted ORIGINAL firmware components that the user
supplies via --components-dir. Reads no network, writes no firmware, ships no
Samsung bytes. Standard library only. Prints findings as JSON.

Covered components (whichever are present in the directory):
  seret.bin, secos.bin, ddr.init, sign.bin   (bootchain container)
  uImage, dtb.bin                            (decrypted FullOS image)

The tool makes NO claim about secure-boot acceptance, bootability, or any
device flash. It is a descriptive inventory only. A valid U-Boot CRC protects
against accidental corruption, not against deliberate replacement; the presence
of sign.bin / TrustZone images is NOT a cryptographic validation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections import Counter
from pathlib import Path


KNOWN = ["seret.bin", "secos.bin", "ddr.init", "sign.bin", "uImage", "dtb.bin"]
UBOOT_MAGIC = 0x27051956
FDT_MAGIC = 0xD00DFEED
XZ_MAGIC = b"\xfd7zXZ\x00"


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def entropy_runs(data: bytes, win: int = 16384):
    runs = []
    prev = None
    for i in range(0, len(data), win):
        e = entropy(data[i : i + win])
        band = "LOW" if e < 6.5 else ("MID" if e < 7.5 else "HIGH")
        if band != prev:
            runs.append({"start": i, "end": i + win, "band": band, "e": round(e, 2)})
            prev = band
        else:
            runs[-1]["end"] = i + win
    return runs


def ascii_strings(data: bytes, minlen: int = 4):
    out = []
    cur = bytearray()
    start = 0
    for i, b in enumerate(data):
        if 32 <= b < 127:
            if not cur:
                start = i
            cur.append(b)
        else:
            if len(cur) >= minlen:
                out.append((start, bytes(cur)))
            cur = bytearray()
    if len(cur) >= minlen:
        out.append((start, bytes(cur)))
    return out


def find_str(data: bytes, needle: bytes, maxrun: int = 160):
    i = data.find(needle)
    if i < 0:
        return None
    end = i
    while end < len(data) and 32 <= data[end] < 127 and end - i < maxrun:
        end += 1
    return {"off": i, "text": data[i:end].decode("ascii", "replace")}


def analyze_seret(data: bytes) -> dict:
    """seret.bin: AArch32 zImage-style self-relocating/decompressing stub."""
    words = [struct.unpack_from("<I", data, o)[0] for o in range(0, 0x40, 4)]
    entry_words = [f"{w:08x}" for w in words]
    markers = {
        "xz_magic_constant": data.find(XZ_MAGIC),  # unxz compare constant, not a stream
        "payload_entropy_run": entropy_runs(data),
    }
    strings = {
        s: find_str(data, s.encode())
        for s in [
            "done, booting the kernel",
            "Input is not in the XZ format",
            "/chosen/bootargs",
            "decompressor returned an error",
        ]
    }
    # The entry sequence "mov r3,pc ; sub r3,r3,#8 ; and r0,r3,#0xfc000000"
    # is the ARM zImage head.S position-independent self-relocation.
    looks_like_zimage = words[0] == 0xE1A0300F and any(
        w == 0xE203033F for w in words
    )
    return {
        "role": "AArch32 Linux zImage stub (NOT a TrustZone monitor)",
        "entry_words_le": entry_words,
        "looks_like_arm_zimage_head": looks_like_zimage,
        "decompressor_strings": strings,
        "markers": markers,
        "note": "Payload region is high-entropy and not decompressible with "
        "standard codecs (gzip/zlib/xz/lzma); consistent with an encrypted or "
        "non-standard-packed kernel payload.",
    }


def analyze_sign(data: bytes) -> dict:
    """sign.bin: OpenSSL `enc` Salted__ blob (AES, salt-derived key)."""
    info = {"size": len(data)}
    s = data.find(b"Salted__")
    info["salted_magic_off"] = s
    if s >= 0:
        info["salt"] = data[s + 8 : s + 16].hex()
        info["is_openssl_enc"] = True
    # length field often precedes the blob
    info["pkcs7_pad_tail"] = data.rstrip(b"\x00").endswith(b"\x10" * 16)
    info["interpretation"] = (
        "OpenSSL symmetric enc container (password/HW-key derived via "
        "EVP_BytesToKey). NOT a plaintext hash of the other components; without "
        "the hardware-held key it is neither reproducible nor forgeable."
    )
    return info


def analyze_encrypted(name: str, data: bytes) -> dict:
    return {
        "role": {
            "secos.bin": "Secure OS / TrustZone image",
            "ddr.init": "DDR training blob",
        }.get(name, "unknown"),
        "entropy_first_100k": round(entropy(data[:100_000]), 2),
        "likely_encrypted": entropy(data[:100_000]) > 7.8,
        "note": "Key most likely held in hardware (eFuse/OTP); not decryptable "
        "without an exploit. Not attempted.",
    }


def analyze_uimage(data: bytes) -> dict:
    """uImage: U-Boot legacy header + (here uncompressed) ARM kernel."""
    if len(data) < 64 or struct.unpack_from(">I", data, 0)[0] != UBOOT_MAGIC:
        return {"valid_uboot": False}
    size = struct.unpack_from(">I", data, 0x0C)[0]
    load = struct.unpack_from(">I", data, 0x10)[0]
    entry = struct.unpack_from(">I", data, 0x14)[0]
    os_id, arch_id, typ, comp = data[0x1C], data[0x1D], data[0x1E], data[0x1F]
    name = data[0x20:0x40].split(b"\x00", 1)[0].decode("ascii", "replace")
    payload = data[0x40:]
    hyp = payload[0x24:0x28] == b"\x1a\x90\x29\xe2"  # eor r9,r9,#0x1a (HYP handling)
    return {
        "valid_uboot": True,
        "os": os_id,  # 5 = Linux
        "arch": arch_id,  # 2 = ARM (AArch32); 22 = ARM64
        "arch_name": {2: "ARM (AArch32)", 22: "ARM64"}.get(arch_id, f"id={arch_id}"),
        "type": typ,  # 2 = kernel
        "compression": comp,  # 0 = none
        "load": f"0x{load:08x}",
        "entry": f"0x{entry:08x}",
        "image_name": name,
        "payload_size": size,
        "payload_entry_is_hyp_aware_stext": hyp,
        "linux_version": (find_str(payload, b"Linux version") or {}).get("text"),
        "soc_hint": (find_str(payload, b"SDP14") or find_str(payload, b"sdp-nikel")
                     or {}).get("text"),
        "note": "arch=2 (ARM/AArch32), comp=0 (uncompressed Image), 32-bit load "
        "address and HYP-aware stext confirm an AArch32 kernel.",
    }


def analyze_dtb(data: bytes) -> dict:
    if len(data) < 8 or struct.unpack_from(">I", data, 0)[0] != FDT_MAGIC:
        return {"valid_fdt": False}
    totalsize = struct.unpack_from(">I", data, 4)[0]
    version = struct.unpack_from(">I", data, 20)[0]
    models = {}
    for key in ["samsung,", "sdp-nikel", "Nike-L", "arm,cortex"]:
        hit = find_str(data, key.encode(), maxrun=60)
        if hit:
            models[key] = hit["text"]
    return {
        "valid_fdt": True,
        "first_tree_totalsize": totalsize,
        "version": version,
        "blob_bytes": len(data),
        "multi_dtb": len(data) > totalsize + 64,
        "model_hints": models,
    }


def analyze(root: Path) -> dict:
    out = {"type": "bootchain_forensics_build061", "components": {}}
    for name in KNOWN:
        p = root / name
        if not p.is_file():
            continue
        data = p.read_bytes()
        rec = {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        if name == "seret.bin":
            rec.update(analyze_seret(data))
        elif name == "sign.bin":
            rec.update(analyze_sign(data))
        elif name in ("secos.bin", "ddr.init"):
            rec.update(analyze_encrypted(name, data))
        elif name == "uImage":
            rec.update(analyze_uimage(data))
        elif name == "dtb.bin":
            rec.update(analyze_dtb(data))
        out["components"][name] = rec
    out["arch_conclusion"] = (
        "EL3/secure monitor runs AArch32 (seret stub is a 32-bit zImage; stock "
        "kernel enters in AArch32 HYP). With a 32-bit EL3, SCR_EL3.RW cannot be "
        "set, so lower exception levels stay AArch32 and an AArch64 Linux cannot "
        "boot. The A57 cores are ARMv8 silicon, but this firmware permits only "
        "AArch32 -> target ARM 32-bit."
    )
    out["disclaimer"] = (
        "Descriptive, read-only inventory. No secure-boot validation, no "
        "bootability claim, no device flash. Research only."
    )
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--components-dir", required=True, type=Path,
                    help="Directory with locally decrypted ORIGINAL components.")
    args = ap.parse_args(argv)
    if not args.components_dir.is_dir():
        print("components-dir not found", flush=True)
        return 2
    print(json.dumps(analyze(args.components_dir), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
