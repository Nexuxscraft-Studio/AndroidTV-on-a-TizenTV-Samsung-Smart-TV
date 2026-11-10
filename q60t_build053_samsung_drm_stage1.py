#!/usr/bin/env python3
"""Generate a first *partial*, non-loadable Samsung DRM/GEM Linux 6.6 port.

Inputs are original SHA-256-pinned Samsung vendor sources. Generate either
a patch for untouched Samsung media sources or one for the Build-050 Stage-1
version of sdp_drm_drv.c (GEM is original in both cases). Neither patch is
yet buildable, nor does it port Samsung CMA/reservation fences.
"""

import argparse
import difflib
import os
from pathlib import Path
import re
import sys

from q60t_build050_linux66_port_gaps import read_original_text
from q60t_build050_stage1_source_fixes import fix_drm_safety, replace_once
from q60t_build050_vendor_code_audit import SOURCE_SHA, sha256_file


DRM = "tztv-media-nike/sdp_drm_nike/sdp_drm_drv.c"
GEM = "tztv-media-nike/sdp_drm_nike/sdp_drm_gem.c"
SHA256 = {
    DRM: "2f35fcfe3fb284c460fb07a00d24f048277b839641b6738e91773ff11128981d",
    GEM: "cd1884314e4194dae7437802a7f1aa6dae1b7c5143392e4292b3b1d1e1284938",
}


def replace_count(source, before, after, number, label):
    actual = source.count(before)
    if actual != number:
        raise ValueError(f"Source drift: {label}: expected {number}, observed {actual}")
    return source.replace(before, after)


def replace_region(source, first, following, replacement, label):
    if source.count(first) != 1 or source.count(following) != 1:
        raise ValueError(f"Source drift / ambiguous region: {label}")
    start = source.index(first)
    stop = source.index(following)
    if stop <= start:
        raise ValueError("Invalid region order: " + label)
    return source[:start] + replacement + source[stop:]


def migrate_drm(source):
    source = replace_once(
        source, '#include <drm/drm_tztv.h>',
        '#include <drm/drm_device.h>\n#include <drm/drm_drv.h>\n'
        '#include <drm/drm_file.h>\n#include <drm/drm_gem.h>\n'
        '#include <drm/drm_ioctl.h>\n#include <drm/drm_tztv.h>',
        "explicit modern DRM core includes")
    source = replace_once(source,
        "DRIVER_HAVE_IRQ | DRIVER_MODESET | DRIVER_GEM | DRIVER_PRIME",
        "DRIVER_HAVE_IRQ | DRIVER_MODESET | DRIVER_GEM",
        "DRIVER_PRIME flag is absent from Linux 6.6")

    # The old platform helper registered the DRM device while .load still
    # initialized the hardware. Stage 1 makes that ordering explicit.
    source = replace_region(source,
        "static int sdp_drm_platform_probe(struct platform_device *pdev)",
        "static const struct of_device_id sdp_drm_dt_match[] = {",
        """static int sdp_drm_platform_probe(struct platform_device *pdev)
{
\tstruct drm_device *drm;
\tint ret;

\t/* Build 053: registration sequence only; module init is disabled. */
\tdrm = drm_dev_alloc(&sdp_drm_driver, &pdev->dev);
\tif (IS_ERR(drm))
\t\treturn PTR_ERR(drm);

\tplatform_set_drvdata(pdev, drm);
\tret = sdp_drm_load(drm, 0);
\tif (ret)
\t\tgoto err_put;

\tret = drm_dev_register(drm, 0);
\tif (ret)
\t\tgoto err_unload;

\tret = sdp_drm_capture_init();
\tif (ret)
\t\tgoto err_unregister;
\treturn 0;

err_unregister:
\tdrm_dev_unregister(drm);
err_unload:
\tsdp_drm_unload(drm);
err_put:
\tplatform_set_drvdata(pdev, NULL);
\tdrm_dev_put(drm);
\treturn ret;
}

""", "DRM probe lifecycle")
    source = replace_region(source,
        "static int sdp_drm_platform_remove(struct platform_device *pdev)",
        "static struct platform_driver sdp_drm_platform_driver = {",
        """static int sdp_drm_platform_remove(struct platform_device *pdev)
{
\tstruct drm_device *drm = platform_get_drvdata(pdev);

\tdrm_dev_unregister(drm);
\tsdp_drm_unload(drm);
\tplatform_set_drvdata(pdev, NULL);
\tdrm_dev_put(drm);
\treturn 0;
}

""", "DRM remove lifecycle")

    # Do not leave load/unload installed as callbacks: the migration now
    # invokes them in probe/remove, otherwise setup would occur twice.
    source = replace_once(source, "\t.load\t\t\t= sdp_drm_load,\n", "",
                          "remove old DRM load callback")
    source = replace_once(source, "\t.unload\t\t\t= sdp_drm_unload,\n", "",
                          "remove old DRM unload callback")

    # These former drm_driver members are absent in v6.6. Their functions
    # stay in the vendor source for a later genuine GEM-object migration.
    # No GEM creation, dma-buf, mmap, hardware or userspace semantics are
    # claimed to work at this stage.
    invalid_fields = (
        "set_busid", "debugfs_cleanup", "gem_free_object", "gem_vm_ops",
        "dumb_destroy", "gem_open_object", "gem_prime_export",
        "gem_prime_get_sg_table", "gem_prime_vmap", "gem_prime_vunmap",
        "gem_prime_mmap",
    )
    for field in invalid_fields:
        match = re.findall(r"(?m)^\t\." + field + r"\s*=.*\n", source)
        if len(match) != 1:
            raise ValueError(f"Source drift in obsolete drm_driver.{field}: {len(match)}")
        source = replace_once(source, match[0], "", "defer obsolete drm_driver." + field)

    # The VMA callbacks need migration to struct drm_gem_object_funcs.
    source = replace_region(source,
        "static const struct vm_operations_struct sdp_drm_gem_vm_ops = {",
        "static struct drm_ioctl_desc sdp_drm_ioctls[] = {",
        "/* Build 053: GEM VM functions must move to per-object operations. */\n",
        "obsolete driver-wide GEM VM operation")

    source = replace_once(source, '{ .compatible = "samsung,sdp-drm" },',
                          '{ .compatible = "nover,compile-only-sdp-drm" },',
                          "prevent binding to the real Samsung hardware")
    source = replace_once(source,
        "\tint ret = 0;\n\tsystem_overhead = 0;",
        "\tint ret = 0;\n\n"
        "\t/* Build 053: hard stop before any Samsung hardware init. */\n"
        "\treturn -ENODEV;\n\n\tsystem_overhead = 0;",
        "module refuses to initialize even on matching test devices")

    if ("drm_platform_init(" in source or "drm_put_dev(" in source or
            'compatible = "samsung,sdp-drm"' in source):
        raise ValueError("Legacy DRM registration or real device binding remains")
    return source


def migrate_gem(source):
    source = replace_once(source, '#include <drm/drmP.h>',
                          '#include <drm/drm_device.h>\n#include <drm/drm_file.h>\n'
                          '#include <drm/drm_gem.h>\n#include <drm/drm_prime.h>',
                          "replace drmP.h in actual vendor GEM C file")

    for old, new, count in (
        ("drm_gem_object_reference(", "drm_gem_object_get(", 2),
        ("drm_gem_object_unreference_unlocked(", "drm_gem_object_put(", 3),
        ("drm_gem_object_unreference(", "drm_gem_object_put(", 2),
        ("drm_gem_object_lookup(dev, file,", "drm_gem_object_lookup(file,", 2),
        ("drm_gem_object_lookup(dev, file_priv,", "drm_gem_object_lookup(file_priv,", 1),
        ("atomic_read(&item->gem_obj->refcount.refcount)",
         "kref_read(&item->gem_obj->refcount)", 1),
        ("atomic_read(&obj->refcount.refcount)",
         "kref_read(&obj->refcount)", 2),
    ):
        source = replace_count(source, old, new, count, old)

    source = replace_once(source, "fput(obj->filp);",
                          "drm_gem_object_release(obj);",
                          "release GEM core allocation after partial initialization")
    for before, after, label in (
        ("Ref[%d] Handle [%d]", "Ref[%u] Handle [%d]", "GEM refcount debug format"),
        ("Alloc Ref %d handle %d", "Alloc Ref %u handle %d", "GEM alloc debug format"),
        ("%p    %d|    ", "%p    %u|    ", "GEM slot debug format"),
    ):
        source = replace_once(source, before, after, label)

    # In particular, do NOT guess a mapping from Samsung reservation_object,
    # fence, CMA slot tracking or custom mmap to dma_resv/dma_fence/DRM DMA.
    if "drm_gem_object_unreference" in source or "drm_gem_object_reference(" in source:
        raise ValueError("Legacy GEM object reference API remains")
    return source


def make_patch(original_drm, original_gem, base="original"):
    if base not in ("original", "stage1"):
        raise ValueError("Unknown patch base: " + base)
    stage1_drm = fix_drm_safety(original_drm)
    drm_base = original_drm if base == "original" else stage1_drm
    edits = ((DRM, drm_base, migrate_drm(stage1_drm)),
             (GEM, original_gem, migrate_gem(original_gem)))
    diff = []
    for path, before, after in edits:
        diff.extend(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile="a/" + path, tofile="b/" + path, n=3))
    return "".join(diff)


def generate(media_tgz, base="original"):
    media_tgz = Path(media_tgz)
    if sha256_file(media_tgz) != SOURCE_SHA["media"]:
        raise ValueError("Original Samsung media archive SHA-256 mismatch")
    inputs = {}
    for member in (DRM, GEM):
        source, sha = read_original_text(media_tgz, member)
        if sha != SHA256[member]:
            raise ValueError("Samsung source-member SHA-256 mismatch: " + member)
        inputs[member] = source
    return make_patch(inputs[DRM], inputs[GEM], base=base)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-tgz", required=True)
    parser.add_argument("--base", choices=("original", "stage1"), default="original")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        data = generate(args.media_tgz, base=args.base)
        with os.fdopen(os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as out:
            out.write(data)
        print("Build 053 partial vendor DRM/GEM patch: " + str(len(data)) +
              " bytes; compile_test_run=false; safe_to_flash=false")
        return 0
    except (OSError, ValueError, KeyError) as error:
        print("Build 053 migration refused: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
