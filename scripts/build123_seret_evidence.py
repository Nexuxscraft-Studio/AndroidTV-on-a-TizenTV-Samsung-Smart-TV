"""Collect static boot-chain evidence from regular firmware files."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

ROOT = Path("/opt/samsung-atv-lab/samsung/firmware-2743")
REQUIRED = ("decrypted/seret.bin", "rootfs-extracted/root/etc/include/partition.txt")
LIMIT = 64 * 1024 * 1024
PATTERN = re.compile(
    r"flash_partition_map|(?:seret|kernel|dtb|sign|platform)[_-]?[01]\b|"
    r"mmcblk0p(?:[3-9]|10|18|19)\b|boot[_ -]?(?:slot|count|limit|status|success|part)|"
    r"active[_ -]?slot|slot[_ -]?(?:suffix|select|status)|"
    r"upgrade_available|upgrade[_ -]?status|update[_ -]?(?:status|flag|state|result)|"
    r"fallback|roll[_ -]?back|bootfail|bootretry|altbootcmd|"
    r"(?:verify|check)[_ -]?(?:signature|image|kernel|hash)|signature[_ -]?(?:fail|verify)",
    re.I,
)
STRINGS = (("ascii", re.compile(rb"[\x20-\x7e]{4,}"), "ascii"),
           ("utf16le", re.compile(rb"(?:[\x20-\x7e]\x00){4,}"), "utf-16-le"))
PARTITION_IMAGE = re.compile(r"^(sign|seret|kernel|dtb|platform)[_-]?[01](?:\.[^.]+)?$", re.I)


def read_regular(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("not a regular file")
        if info.st_size > LIMIT:
            raise ValueError("file exceeds scan limit")
        data = stream.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError("file exceeded scan limit while reading")
        return data


def candidates():
    seen = set()
    for name in REQUIRED:
        path = ROOT / name
        seen.add(path)
        yield path
    for subtree in ("decrypted", "rootfs-extracted/root"):
        for base, dirs, files in os.walk(ROOT / subtree, followlinks=False):
            dirs.sort()
            for name in sorted(files):
                path = Path(base) / name
                if path not in seen and not path.is_symlink() and path.is_file():
                    yield path


def inspect(path, data):
    row = {"file": str(path.relative_to(ROOT)), "bytes": len(data),
           "sha256": hashlib.sha256(data).hexdigest(), "hits": [], "omitted_hits": 0}
    for label, regex, codec in STRINGS:
        for run in regex.finditer(data):
            decoded = run.group().decode(codec)
            for match in PATTERN.finditer(decoded):
                if len(row["hits"]) >= 100:
                    row["omitted_hits"] += 1
                    continue
                row["hits"].append({
                    "offset": hex(run.start() + match.start() * (2 if label == "utf16le" else 1)),
                    "encoding": label, "match": match.group(),
                    "context": decoded[max(0, match.start()-36):match.end()+36],
                })
    if data.startswith(b"\x7fELF") and row["hits"] and shutil.which("readelf"):
        elf = subprocess.run(["readelf", "-W", "-l", "-s", str(path)],
                             capture_output=True, timeout=15, check=False)
        # readelf needs a seekable file. Use the already validated path if stdin is rejected.
        if elf.returncode:
            elf = subprocess.run(["readelf", "-W", "-l", "-s", str(path)],
                                 capture_output=True, timeout=15, check=False)
        lines = elf.stdout.decode(errors="replace").splitlines()
        row["elf"] = {"exit_code": elf.returncode, "load_segments": [
            line.strip() for line in lines if line.lstrip().startswith("LOAD ")
        ], "matching_symbols": [line.strip() for line in lines if PATTERN.search(line)][:100]}
    return row


def main():
    report = {"build": 123, "root": str(ROOT), "scan_limit_bytes": LIMIT,
              "files_scanned": 0, "files_skipped": 0, "required_errors": {},
              "skip_examples": [], "evidence": [],
              "assessment": {
                  "slot_selection": "unresolved pending selector and branch data flow",
                  "boot_update_flags": "unresolved pending flag source and consumer",
                  "sign_verification": "unresolved pending verifier inputs and result branch",
                  "fallback": "unresolved pending a failure edge that selects the alternate slot",
              }}
    root = ROOT.resolve(strict=True)
    for path in candidates():
        name = str(path.relative_to(ROOT))
        try:
            if not path.resolve(strict=True).is_relative_to(root):
                raise ValueError("path escapes firmware root")
            data = read_regular(path)
        except (OSError, ValueError) as exc:
            report["files_skipped"] += 1
            if name in REQUIRED:
                report["required_errors"][name] = str(exc)
            if len(report["skip_examples"]) < 100:
                report["skip_examples"].append({"file": name, "reason": str(exc)})
            continue
        report["files_scanned"] += 1
        row = inspect(path, data)
        if row["hits"] or name in REQUIRED or PARTITION_IMAGE.fullmatch(path.name):
            report["evidence"].append(row)
    out = Path(sys.argv[1])
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Scanned {report['files_scanned']} files; {len(report['evidence'])} evidence entries")
    return bool(report["required_errors"])


if __name__ == "__main__":
    sys.exit(main())
