"""Verify that experimental nodes in the compiled fixtures stay disabled."""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build070/tools"))
from dt_nodes import parse

DISPLAY = {b"samsung,nikel-drm-hw-preparation"}
CPU = {b"nover,nikel-cpu-clock-offline", b"nover,nikel-cpufreq-offline", b"nover,nikel-thermal-offline"}
BOARD = {
    b"samsung,sdp-drm", b"arm,mali-bifrost", b"samsung,sdp-messagebox",
    b"samsung,tztv-micom", b"samsung,sdp-mc-cecif", b"samsung,sdp-mac",
    b"samsung,sdp-hdmi", b"samsung,sdp-mc-irb", b"samsung,sdp-mc-irs",
    b"samsung,sdp1804-dw-mshc", b"samsung,sdp-ehci", b"samsung,sdp-ohci",
}


def check(filename, required):
    seen = set()
    for path, props in parse(Path(filename).read_bytes()).items():
        if "samsung,enable-experimental-kms" in props:
            raise SystemExit(f"{filename}: {path} opts into experimental KMS")
        if path.endswith("/gpu-power-domain") and props.get("status") != b"disabled\0":
            raise SystemExit(f"{filename}: {path} must remain disabled")
        matches = required.intersection(props.get("compatible", b"").split(b"\0"))
        if matches:
            if props.get("status") != b"disabled\0":
                raise SystemExit(f"{filename}: {path} must remain disabled")
            seen.update(matches)
    if missing := required - seen:
        raise SystemExit(f"{filename}: missing guarded nodes {sorted(missing)}")
    print(f"{filename}: all {len(required)} guarded compatibles are disabled")


def check_probe(source):
    probe = (source / "sdp_drm.c").read_text().split("static int sdp_drm_probe(", 1)[1]
    hw = (source / "sdp_drm_hw.c").read_text()
    if not re.search(r"bool sdp_hw_access_allowed\(void\)\s*\{\s*return false;\s*\}", hw):
        raise SystemExit("SDP DRM hardware interlock must always return false")
    probe_start = re.compile(
        r"[^{}]*\{(?:[^;{}()]+;)*\s*(?:/\*[^{}]*?\*/\s*)?"
        r"if\s*\(!sdp_hw_access_allowed\(\)\)\s*"
        r"return dev_err_probe\(&pdev->dev, -EOPNOTSUPP,"
    )
    if not probe_start.match(probe):
        raise SystemExit("SDP DRM probe must reject before calling hardware helpers")
    print("SDP DRM probe interlock preserved")


if sys.argv[1] == "--probe":
    check_probe(Path(sys.argv[2]))
else:
    check(sys.argv[1], DISPLAY)
    check(sys.argv[2], CPU)
    for filename in sys.argv[3:]:
        check(filename, BOARD)
