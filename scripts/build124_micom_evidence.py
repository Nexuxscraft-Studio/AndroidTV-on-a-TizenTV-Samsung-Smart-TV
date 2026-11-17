import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path("/opt/samsung-atv-lab/samsung/firmware-2743")
TARGETS = {
    "usr/bin/SWUCoreTV": "2213a6d4c477f993519634ce5f0b8bd0fa4ff3974c9af65896ec7212a6a3d79e",
    "usr/bin/SWUVerifierTV": "0af2d2b00d96b8eff32032dd1001b7b688b124e9cf0b9bdf5862e55eea183149",
    "usr/lib/libmicom.so.0.1": "aaff2560b637c9ba5d5e23d77818d188a4297806685f30e62dde9305fa3a3e75",
}
PATTERNS = {
    "upgrade_flag": r"UpgradeStatusFlag",
    "update_outcome": r"(?:updat\w*|upgrad\w*).{0,65}(?:success|fail(?:ed|ure)?|error)|(?:success|fail(?:ed|ure)?|error).{0,35}(?:updat\w*|upgrad\w*)",
    "micom_status": r"micom[_ :].{0,70}(?:status|result|version|boot|upgrade|update)",
    "recovery": r"recover(?:y|ing)|rollback|roll back|fallback|fall back",
}
LIMIT = 60
EXCLUDED = re.compile(r"signature|secure.?boot|certificate|public.?key|private.?key", re.I)


def run_tool(command):
    return subprocess.run(command, check=True, capture_output=True, text=True,
                          errors="replace", timeout=45)


def rea_exports(path, output):
    rea = shutil.which("rea")
    npx = shutil.which("npx")
    if not (rea or npx):
        return {"status": "unavailable", "reason": "rea and npx missing"}
    prefix = [rea] if rea else [npx, "--yes", "rea-agents@6.9.0"]
    try:
        result = run_tool(prefix + ["inspect-native-exports", str(path), "--json"])
        evidence = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"status": "unavailable", "reason": type(exc).__name__,
                "detail": getattr(exc, "stderr", "")[:400]}
    return {"status": "collected", "evidence_file": output.name,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest()} if write_rea(output, evidence) else {
                "status": "unavailable", "reason": "REA reported an error"}


def write_rea(output, evidence):
    if isinstance(evidence, dict) and (evidence.get("error") or evidence.get("ok") is False):
        return False
    # Preserve the native-export Evidence for the MICOM library only.
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return True


def inspect(root, name, expected):
    relative = Path("rootfs-extracted/root") / name
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size > 8_000_000:
        raise ValueError(f"Unexpected input: {relative}")
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != expected or not content.startswith(b"\x7fELF"):
        raise ValueError(f"Input differs from BUILD 123: {relative}")
    findings = {}
    for category, pattern in PATTERNS.items():
        regex = re.compile(pattern, re.I)
        count = 0
        records = []
        for match in re.finditer(rb"[ -~]{5,}", content):
            value = match.group().decode("ascii")
            if len(value) <= 300 and regex.search(value) and not EXCLUDED.search(value):
                count += 1
                if len(records) < LIMIT:
                    records.append({"offset": match.start(), "text": value})
        findings[category] = {"count": count, "records": records}
    symbols = []
    for line in run_tool(["readelf", "--dyn-syms", "--wide", str(path)]).stdout.splitlines():
        if any(re.search(pattern, line, re.I) for pattern in PATTERNS.values()) and not EXCLUDED.search(line):
            symbols.append(line.strip())
    return {"path": str(relative), "sha256": digest, "bytes": len(content),
            "dynamic_symbols": symbols, "strings": findings}


def markdown(report):
    lines = [
        "# BUILD 124 – Samsung Q60T MICOM & Recovery Analysis",
        "",
        "Firmware 2743.0. Drei ELF-Dateien anhand der SHA-256-Werte aus BUILD 123 abgeglichen.",
        "",
        "Dynamische Symbole dokumentieren Definitionen oder Importe (Index UND). "
        "String-Offsets sind Dateioffsets. Texte sind statische Diagnose- oder Recovery-Hinweise. "
        "Die Reihenfolge von Zustandsübergängen und die Bedingungen für Recovery bleiben offen.",
        "",
        "**Automatischer Boot-Fallback bleibt offen.** Die in BUILD 123 belegten Slot-APIs "
        "und doppelten Partitionen belegen keine automatische Umschaltung nach einem Bootfehler.",
        "",
        f"REA-Native-Exports für libmicom: {report['rea']['status']}. Details stehen im JSON.",
    ]
    for row in report["files"]:
        lines += ["", f"## {Path(row['path']).name}", "", f"Pfad `{row['path']}`",
                  "", f"SHA-256 `{row['sha256']}`", "", "### Dynamische Symbole", "", "```text"]
        lines += row["dynamic_symbols"] or ["Keine Treffer im definierten Filter."]
        lines += ["```"]
        for category, evidence in row["strings"].items():
            lines += ["", f"### {category} ({evidence['count']} Treffer, bis zu {LIMIT} angezeigt)",
                      "", "````text"]
            lines += [f"0x{record['offset']:x}  {record['text']}" for record in evidence["records"]]
            lines += ["````"]
    return "\n".join(lines) + "\n"


def main():
    output = Path(sys.argv[1])
    output.mkdir()
    root = ROOT.resolve(strict=True)
    report = {
        "build": 124, "firmware": "2743.0", "baseline_run": 44077634400,
        "run_id": os.environ.get("GITHUB_RUN_ID"), "commit": os.environ.get("GITHUB_SHA"),
        "automatic_boot_fallback": "open",
        "files": [inspect(root, name, digest) for name, digest in TARGETS.items()],
    }
    report["rea"] = rea_exports(root / "rootfs-extracted/root/usr/lib/libmicom.so.0.1",
                                output / "rea-micom-exports.json")
    (output / "evidence.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "report.md").write_text(markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
