"""Verify that experimental nodes in the compiled fixtures stay disabled."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build070/tools"))
from dt_nodes import parse

DISPLAY = {b"samsung,sdp-drm", b"samsung,nikel-drm-hw-preparation"}
BOARD = {
    b"samsung,sdp-drm", b"arm,mali-bifrost", b"samsung,sdp-messagebox",
    b"samsung,tztv-micom", b"samsung,sdp-mc-cecif", b"samsung,sdp-mac",
    b"samsung,sdp-hdmi", b"samsung,sdp-mc-irb", b"samsung,sdp-mc-irs",
    b"samsung,sdp1804-dw-mshc", b"samsung,sdp-ehci", b"samsung,sdp-ohci",
}


def check(filename, required):
    seen = set()
    for path, props in parse(Path(filename).read_bytes()).items():
        matches = required.intersection(props.get("compatible", b"").split(b"\0"))
        if matches:
            if props.get("status") != b"disabled\0":
                raise SystemExit(f"{filename}: {path} must remain disabled")
            seen.update(matches)
    if missing := required - seen:
        raise SystemExit(f"{filename}: missing guarded nodes {sorted(missing)}")
    print(f"{filename}: all {len(required)} guarded compatibles are disabled")


check(sys.argv[1], DISPLAY - {b"samsung,sdp-drm"})
for filename in sys.argv[2:]:
    check(filename, BOARD)
