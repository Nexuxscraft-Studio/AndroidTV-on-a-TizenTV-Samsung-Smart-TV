#!/usr/bin/env python3
"""Generate a guarded, *compile-only* first-stage Linux 6.6 Samsung source patch.

Read-only input: SHA-256-pinned Samsung GPL source TGZs. The emitted unified
diff only changes a copy of source if the user later applies it. It is not
a functioning display driver and MUST NOT be used on actual hardware.
"""

import argparse
import difflib
import hashlib
import os
from pathlib import Path
import sys

from q60t_build050_linux66_port_gaps import read_original_text
from q60t_build050_vendor_code_audit import MEMBERS, SOURCE_SHA, sha256_file


PANEL = MEMBERS["kernel"]["panel_legacy"]
DRM = MEMBERS["media"]["drm_display"]
EXPECTED_MEMBER_SHA = {
    PANEL: "4e09eb66ca69d04e2b4bcee57173439621d530d5fb029e45e7a2211c015e3654",
    DRM: "2f35fcfe3fb284c460fb07a00d24f048277b839641b6738e91773ff11128981d",
}


def replace_once(source, before, after, change):
    if source.count(before) != 1:
        raise ValueError(f"Source drift / ambiguous replacement: {change} (matches={source.count(before)})")
    return source.replace(before, after, 1)


def migrate_panel(source):
    edits = [
        ("#include <drm/drmP.h>",
         "#include <linux/fb.h>\n#include <linux/slab.h>\n"
         "#include <drm/drm_connector.h>\n#include <drm/drm_modes.h>",
         "remove drmP legacy header"),
        ("\t.vrefresh = 60,\n", "", "remove obsolete drm_display_mode.vrefresh"),
        ("static int sdp_panel_get_modes(struct drm_panel *panel)",
         "static int sdp_panel_get_modes(struct drm_panel *panel,\n"
         "\t\t\t       struct drm_connector *connector)",
         "update get_modes signature"),
        ("\tstruct drm_connector *connector = p->base.connector;\n"
         "\tstruct drm_device *drm = p->base.drm;",
         "\tstruct drm_device *drm = connector->dev;",
         "use passed connector and its DRM device"),
        ("m->hdisplay, m->vdisplay, m->vrefresh",
         "m->hdisplay, m->vdisplay, drm_mode_vrefresh(m)",
         "use calculated refresh rate"),
        ("\tint ret;\n", "", "drm_panel_add is void"),
        ("\tdrm_panel_init(&panel->base);\n"
         "\tpanel->base.dev = &pdev->dev;\n"
         "\tpanel->base.funcs = &sdp_panel_funcs;",
         "\tdrm_panel_init(&panel->base, &pdev->dev, &sdp_panel_funcs,\n"
         "\t\t       DRM_MODE_CONNECTOR_Unknown);",
         "update drm_panel_init signature; connector type not yet verified"),
        ("\tret = drm_panel_add(&panel->base);\n"
         "\tif (ret < 0)\n\t\tgoto err;",
         "\tdrm_panel_add(&panel->base);",
         "replace old return/error check"),
        ("\nerr:\n\tif (panel->backlight)\n"
         "\t\tput_device(&panel->backlight->dev);\n\n\treturn ret;",
         "", "remove obsolete unreachable error label"),
        ("\tdrm_panel_detach(&panel->base);\n", "", "remove removed panel detach"),
        ('\t{ .compatible = "samsung,sdp1202-panel", },',
         '\t/* Build 050: intentionally DOES NOT bind to the real Samsung DTB. */\n'
         '\t{ .compatible = "nover,compile-only-sdp-panel", },',
         "compile-only hardware bind gate"),
    ]
    for before, after, description in edits:
        source = replace_once(source, before, after, description)
    if any(x in source for x in ("drmP.h", "p->base.connector", "p->base.drm",
                                 "drm_panel_detach", "m->vrefresh", ".vrefresh = 60")):
        raise ValueError("Stale pre-6.6 panel API remained after migration")
    if 'compatible = "samsung,sdp1202-panel"' in source:
        raise ValueError("Danger: unverified stock panel binding remained")
    return source


def fix_drm_safety(source):
    # These are safety/logic fixes only. Full sdp_drm_drv Linux-6.6 port
    # remains blocked by many DRM/GEM APIs; do not label this driver buildable.
    source = replace_once(source, "\t\t/* return -ENXIO; */",
                          "\t\treturn -ENXIO; /* Build 050: fail closed without display outputs. */",
                          "do not register a headless dummy DRM display")
    source = replace_once(
        source,
        "static void sdp_drm_lastclose(struct drm_device *dev)\n"
        "{\n\tstruct sdp_drm_private *priv = dev->dev_private;\n"
        "\tdrm_fbdev_cma_restore_mode(priv->fbdev);\n}\n\n",
        "/* Build 050: obsolete fbdev CMA lastclose callback removed.\n"
        " * A verified modern fbdev client setup is still required. */\n\n",
        "remove obsolete potentially null fbdev restore callback")
    source = replace_once(source, "\t.lastclose\t\t= sdp_drm_lastclose,\n", "",
                          "unregister obsolete lastclose hook")
    return source


def make_patch(originals):
    edits = [(PANEL, migrate_panel(originals[PANEL])),
             (DRM, fix_drm_safety(originals[DRM]))]
    diffs = []
    for path, migrated in edits:
        if originals[path] == migrated:
            raise ValueError("Empty migration patch: " + path)
        diffs.extend(difflib.unified_diff(
            originals[path].splitlines(keepends=True),
            migrated.splitlines(keepends=True),
            fromfile="a/" + path, tofile="b/" + path, n=3))
    return "".join(diffs)


def generate(kernel_tgz, media_tgz):
    archives = {"kernel": Path(kernel_tgz), "media": Path(media_tgz)}
    for family, path in archives.items():
        if sha256_file(path) != SOURCE_SHA[family]:
            raise ValueError("Archive SHA-256 mismatch: " + family)
    originals = {}
    for family, member in (("kernel", PANEL), ("media", DRM)):
        contents, digest = read_original_text(archives[family], member)
        if digest != EXPECTED_MEMBER_SHA[member]:
            raise ValueError("Source-member SHA-256 mismatch: " + member)
        originals[member] = contents
    return make_patch(originals)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-tgz", required=True)
    parser.add_argument("--media-tgz", required=True)
    parser.add_argument("--output", required=True, help="Write NEW standalone unified .patch")
    args = parser.parse_args(argv)
    try:
        patch_data = generate(args.kernel_tgz, args.media_tgz)
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as out:
            out.write(patch_data)
        print(f"Build 050 source-only patch emitted: {len(patch_data)} bytes; safe_to_flash=false")
        return 0
    except (OSError, ValueError, KeyError) as err:
        print("Build 050 source fix refused: " + str(err), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
