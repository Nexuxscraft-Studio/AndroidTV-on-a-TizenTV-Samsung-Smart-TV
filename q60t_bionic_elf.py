#!/usr/bin/env python3
"""Small bounded ELF32/ARM dynamic-dependency reader for QEMU Bionic research.

No executing, library loading, or network access. Does not infer ABI
compatibility merely because a binary is an ARM ELF.
"""

from __future__ import annotations

from pathlib import Path
import struct


MAX_ELF_BYTES = 64 * 1024 * 1024
ANDROID_LINKER = "/system/bin/linker"


def parse_elf32_arm(blob: bytes, *, require_interpreter: bool = False) -> dict:
    if not 52 <= len(blob) <= MAX_ELF_BYTES or blob[:7] != b"\x7fELF\x01\x01\x01":
        raise ValueError("Kein ELF32/ARM Little-Endian-Systembinary")
    kind, machine = struct.unpack_from("<HH", blob, 16)
    if machine != 40 or kind not in (2, 3):
        raise ValueError("ELF ist nicht ARM32 ET_EXEC/ET_DYN")
    phoff = struct.unpack_from("<I", blob, 28)[0]
    entsize, count = struct.unpack_from("<HH", blob, 42)
    if entsize < 32 or count < 1 or count > 256 or phoff + entsize * count > len(blob):
        raise ValueError("ELF32-Programmheader ungültig")

    segments = []
    interpreter = None
    dynamic = None
    for idx in range(count):
        off = phoff + idx * entsize
        ph_type, p_offset, p_vaddr, _p_paddr, p_size, p_memsz, _flags, _align = struct.unpack_from(
            "<IIIIIIII", blob, off)
        if p_size and p_offset + p_size > len(blob):
            raise ValueError("ELF-Segment überschreitet Dateigröße")
        if ph_type == 1:
            segments.append((p_offset, p_vaddr, p_size, p_memsz))
        if ph_type == 2:
            if dynamic is not None or p_size > 256 * 1024:
                raise ValueError("Ungültiges PT_DYNAMIC")
            dynamic = (p_offset, p_size)
        if ph_type == 3:
            if interpreter is not None or p_size < 2 or p_size > 256:
                raise ValueError("Ungültiger PT_INTERP")
            raw_path = blob[p_offset:p_offset + p_size]
            if not raw_path.endswith(b"\0"):
                raise ValueError("PT_INTERP nicht nullterminiert")
            interpreter = raw_path[:-1].decode("ascii")

    if require_interpreter and (kind != 3 or interpreter != ANDROID_LINKER):
        raise ValueError("Bionic-Testprogramm braucht ET_DYN und /system/bin/linker")

    needs: list[str] = []
    soname = None
    has_symbol_versions = False
    if dynamic:
        d_off, d_size = dynamic
        if d_size % 8:
            raise ValueError("PT_DYNAMIC ist nicht 8-byte-aligned")
        entries: dict[int, list[int]] = {}
        for offset in range(d_off, d_off + d_size, 8):
            tag, value = struct.unpack_from("<II", blob, offset)
            if tag == 0:
                break
            entries.setdefault(tag, []).append(value)
        strtab_addr = entries.get(5, [None])[0]  # DT_STRTAB
        strsz = entries.get(10, [None])[0]        # DT_STRSZ
        if strtab_addr is not None and strsz is not None:
            if strsz == 0 or strsz > 4 * 1024 * 1024:
                raise ValueError("DT_STRTAB hat ungültige Größe")
            candidates = [file_off + (strtab_addr - vaddr)
                          for file_off, vaddr, size, _memsz in segments
                          if vaddr <= strtab_addr < vaddr + size and
                          strtab_addr + strsz <= vaddr + size]
            if not candidates:
                raise ValueError("DT_STRTAB ist nicht als PT_LOAD abgebildet")
            start = candidates[0]
            table = blob[start:start + strsz]

            def dynamic_string(number: int) -> str:
                if number >= len(table):
                    raise ValueError("Dynamischer Stringoffset außerhalb der Tabelle")
                ending = table.find(b"\0", number)
                if ending < 0:
                    raise ValueError("Unterminierter dynamischer String")
                return table[number:ending].decode("ascii")

            needs = [dynamic_string(item) for item in entries.get(1, [])]
            if entries.get(14):
                soname = dynamic_string(entries[14][0])
        elif entries.get(1) or entries.get(14):
            raise ValueError("DT_NEEDED ohne validen Stringtable")
        has_symbol_versions = bool(entries.get(0x6ffffffe) or entries.get(0x6ffffff0))

    return {
        "elf_class": "ELF32", "endian": "little", "machine": "ARM",
        "type": "ET_DYN" if kind == 3 else "ET_EXEC",
        "interpreter": interpreter, "needed": needs, "soname": soname,
        "symbol_versions_present": has_symbol_versions,
    }


def read_elf32_arm(path: Path, *, require_interpreter: bool = False) -> dict:
    if (not path.is_file() or path.is_symlink() or
            not 52 <= path.stat().st_size <= MAX_ELF_BYTES):
        raise ValueError("Fehlendes oder ungültiges reguläres ELF32")
    return parse_elf32_arm(path.read_bytes(), require_interpreter=require_interpreter)
