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

# The atomic check must validate the same GP geometry that the test pattern
# would use. The source evidence covers full-screen, unscaled geometry only.
driver = sdp / "sdp_drm.c"
content = driver.read_text()
old = """	struct sdp_scanout prepared;

	if (!state->fb)
		return 0;
	return sdp_hw_prepare_plane(state, crtc_state, &prepared);"""
new = """	struct sdp_scanout prepared;
	struct sdp_test_plan plan;
	int ret;

	if (!state->fb)
		return 0;

	ret = sdp_hw_prepare_plane(state, crtc_state, &prepared);
	if (ret)
		return ret;

	/*
	 * Reuse the documented unscaled GP geometry and DMA span check.
	 * A Linux FourCC is not the vendor register encoding.
	 */
	if (prepared.width != SDP_TEST_WIDTH ||
	    prepared.height != SDP_TEST_HEIGHT ||
	    prepared.pitch != SDP_TEST_PITCH ||
	    prepared.format != DRM_FORMAT_XRGB8888)
		return -EINVAL;

	return sdp_test_prepare_plan(prepared.dma_addr, &plan);"""
if content.count(old) != 1:
    raise SystemExit("SDP atomic plane integration point changed")
content = content.replace(old, new)
old = "\tDRM_FORMAT_ARGB8888,\n"
if content.count(old) != 1:
    raise SystemExit("SDP format integration point changed")
driver.write_text(content.replace(old, ""))
