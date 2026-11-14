"""Emit an independent reference image and check the guest's framebuffer digest."""
from pathlib import Path
import re
import sys

report = Path(sys.argv[1])
colors = ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255))
rgb = b"".join(bytes(c) * 480 for c in colors)
row = b"".join(bytes((b, g, r, 0)) * 480 for r, g, b in colors)
frame = row * 1080
(report / "reference-1920x1080.ppm").write_bytes(b"P6\n1920 1080\n255\n" + rgb * 1080)
(report / "reference-xrgb8888.bin").write_bytes(frame)
digest = 2166136261
for v in frame:
    digest = ((digest ^ v) * 16777619) & 0xFFFFFFFF
serial = (report / "qemu/serial.log").read_text(errors="replace")
pattern = f"BUILD107_PATTERN_OK width=1920 height=1080 pitch=7680 fnv1a={digest >> 16}:{digest & 65535}"
summary = "BUILD106_QEMU_SUMMARY modules=19 loaded=19 unloaded=19 failures=0"
plan = "BUILD108_GP_PLAN_OK cases=9"
for line in (pattern, summary, plan):
    if len(re.findall(r"^" + re.escape(line) + r"$", serial, re.M)) != 1:
        raise SystemExit(f"Missing unique guest result: {line}")
print(pattern)
print(summary)
print(plan)
print("QEMU virt: CPU RAM only; Samsung scanout and KMS commits untested")
