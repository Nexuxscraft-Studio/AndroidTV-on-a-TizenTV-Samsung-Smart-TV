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
# The GP buffer does not establish an OSDP route or mixer active timing.
# Keep those candidate registers in BUILD089 for evidence review only.
def replace_once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit(f"SDP integration point changed: {old!r}")
    return text.replace(old, new)

content = replace_once(content, "geometry[7]", "geometry[3]")
for line in content.splitlines(keepends=True):
    if line.startswith(("#define SDP_OSDP_", "#define SDP_MIXER_MAIN_",
                        "\t\t\t{ SDP_OSDP,", "\t\t\t{ SDP_MIXER,")):
        content = replace_once(content, line, "")
start = content.index("/*\n * Describe vendor geometry in RAM.")
end = content.index("static inline int sdp_test_prepare_plan", start)
content = content[:start] + "/* GP geometry only. The DMA address is not a register value. */\n" + content[end:]
content = replace_once(content, ".gp_dma_address", ".dma_address")
content = replace_once(content, "u32 gp_dma_address;", "u32 dma_address;")
content = replace_once(content, "#endif\n", """
static inline int sdp_test_prepare_scanout(const struct sdp_scanout *scanout,
                                          u32 xrgb8888, struct sdp_test_plan *plan)
{
    if (scanout->width != SDP_TEST_WIDTH ||
        scanout->height != SDP_TEST_HEIGHT ||
        scanout->pitch != SDP_TEST_PITCH ||
        scanout->format != xrgb8888)
        return -EINVAL;

    return sdp_test_prepare_plan(scanout->dma_addr, plan);
}

#endif
""")
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
	return sdp_test_prepare_scanout(&prepared, DRM_FORMAT_XRGB8888, &plan);"""
if content.count(old) != 1:
    raise SystemExit("SDP atomic plane integration point changed")
content = content.replace(old, new)
old = "\tDRM_FORMAT_ARGB8888,\n"
if content.count(old) != 1:
    raise SystemExit("SDP format integration point changed")
driver.write_text(content.replace(old, ""))
