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
shutil.copyfile(here / "pattern.h", sdp / "build107_pattern.h")
