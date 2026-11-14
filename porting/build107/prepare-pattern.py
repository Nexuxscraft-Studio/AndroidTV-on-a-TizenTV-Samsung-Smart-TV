"""Install the shared pixel generator without changing the hardware gate."""
from pathlib import Path
import shutil
import sys

here = Path(__file__).resolve().parent
sdp = Path(sys.argv[1])
header = sdp / "sdp_drm_test_pattern.h"
content = header.read_text()
start = content.index("static inline u32 sdp_test_pixel(")
end = content.index("\n/*", start)
header.write_text(
    content[:start]
    + '#include "build107_pattern.h"\n\n'
    + 'static inline u32 sdp_test_pixel(unsigned int x, unsigned int y)\n'
    + '{\n\treturn build107_pixel(x);\n}\n'
    + content[end:]
)
# Route the already documented geometry through the same code as the guest.
content = header.read_text()
for old, new in (
    ("SDP_TEST_WIDTH << 16 | SDP_TEST_HEIGHT", "build107_size_word()"),
    ("SDP_TEST_WIDTH / 4;", "build107_source_offset();"),
):
    if content.count(old) != 1:
        raise SystemExit(f"SDP geometry integration point changed: {old}")
    content = content.replace(old, new)
header.write_text(content)
shutil.copyfile(here / "pattern.h", sdp / "build107_pattern.h")
