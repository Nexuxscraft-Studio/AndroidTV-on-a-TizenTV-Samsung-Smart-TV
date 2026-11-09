#!/usr/bin/env python3
"""Opt-in, host-only Binder three-context *compile experiment* for Nike 4.1.

Transforms only a checked Samsung binder.c shadow copy. This is NOT an
upstream Android Binder backport and is NOT production or TV safe.
"""

from __future__ import annotations

import difflib
import hashlib
from pathlib import Path


ORIGINAL_BINDER_SHA256 = "2c94aa4a57c3d19e9586e2185b8a3d97f95148e5d1a56926ca7ae876d01ac777"


def replace_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"Binder-Quellmarker erwartet einmal, gefunden: {count}: {old[:70]!r}")
    return source.replace(old, new, 1)


def transform(source: str) -> str:
    """Return an experimental separate-manager, separate-misc-device source."""
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != ORIGINAL_BINDER_SHA256:
        raise ValueError("Binder-Quelltext ist nicht der erwartete Samsung-Originalstand")

    result = replace_once(source, (
        "static struct binder_node *binder_context_mgr_node;\n"
        "static kuid_t binder_context_mgr_uid = INVALID_UID;"
    ), (
        "/* Build-016 host laboratory: one manager and UID per Binder domain. */\n"
        "struct binder_context {\n"
        "\tstruct binder_node *mgr_node;\n"
        "\tkuid_t mgr_uid;\n"
        "\tconst char *name;\n"
        "};\n"
        "struct binder_device {\n"
        "\tstruct miscdevice miscdev;\n"
        "\tstruct binder_context context;\n"
        "};"
    ))
    result = replace_once(result, (
        "struct binder_proc {\n"
        "\tstruct hlist_node proc_node;"
    ), (
        "struct binder_proc {\n"
        "\tstruct binder_context *context;\n"
        "\tstruct hlist_node proc_node;"
    ))
    # A binder node can outlive its owning process. Preserve the old
    # special-case while checking proc existence before reading its context.
    result = replace_once(result, (
        "!(node == binder_context_mgr_node &&\n"
        "\t\t\t    node->has_strong_ref)"
    ), (
        "!(node->proc &&\n"
        "\t\t\t    node == node->proc->context->mgr_node &&\n"
        "\t\t\t    node->has_strong_ref)"
    ))
    # All remaining manager-node/UID occurrences are inside binder_proc
    # handlers; binder_inc_node was the one special case above.
    if result.count("binder_context_mgr_node") != 14:
        raise ValueError("Unbekannter Binder-manager-Referenzstand")
    result = result.replace("binder_context_mgr_node", "proc->context->mgr_node")
    if result.count("binder_context_mgr_uid") != 4:
        raise ValueError("Unbekannter Binder-manager-UID-Referenzstand")
    result = result.replace("binder_context_mgr_uid", "proc->context->mgr_uid")

    # Never manufacture cross-context binder references: even if the old
    # driver has other bugs, a reference cannot be moved to a foreign domain.
    signature = (
        "static struct binder_ref *binder_get_ref_for_node(struct binder_proc *proc,\n"
        "\t\t\t\t\t\t  struct binder_node *node)\n"
        "{\n"
        "\tstruct rb_node *n;"
    )
    if result.count(signature) != 1:
        raise ValueError("Unerwartete Binder-Referenzfunktionssignatur")
    result = replace_once(result, (
        "\tstruct binder_ref *ref, *new_ref;\n\n"
        "\twhile (*p) {"
    ), (
        "\tstruct binder_ref *ref, *new_ref;\n\n"
        "\tif (node->proc && node->proc->context != proc->context)\n"
        "\t\treturn NULL;\n\n"
        "\twhile (*p) {"
    ))

    # Prevent a user-provided handle from routing into another Binder
    # context. This check covers both regular transactions and replies.
    result = replace_once(result, (
        "\tif (target_thread) {\n"
        "\t\te->to_thread = target_thread->pid;"
    ), (
        "\tif (target_proc && target_proc->context != proc->context) {\n"
        "\t\treturn_error = BR_FAILED_REPLY;\n"
        "\t\tgoto err_invalid_target_handle;\n"
        "\t}\n"
        "\tif (target_thread) {\n"
        "\t\te->to_thread = target_thread->pid;"
    ))

    result = replace_once(result,
        "if (ref->desc != target) {",
        "if (ref && ref->desc != target) {")

    # misc_open() hands the miscdevice to the driver's .open() as
    # filp->private_data. Bind each opened process to that device's context.
    result = replace_once(result, (
        "static int binder_open(struct inode *nodp, struct file *filp)\n"
        "{\n"
        "\tstruct binder_proc *proc;"
    ), (
        "static int binder_open(struct inode *nodp, struct file *filp)\n"
        "{\n"
        "\tstruct binder_proc *proc;\n"
        "\tstruct binder_device *device = container_of(filp->private_data,\n"
        "\t\t\t\t\tstruct binder_device, miscdev);"
    ))
    result = replace_once(result, (
        "\tproc->tsk = current;\n"
        "\tINIT_LIST_HEAD(&proc->todo);"
    ), (
        "\tproc->tsk = current;\n"
        "\tproc->context = &device->context;\n"
        "\tINIT_LIST_HEAD(&proc->todo);"
    ))
    result = replace_once(result, (
        "\t\tchar strbuf[11];\n\n"
        "\t\tsnprintf(strbuf, sizeof(strbuf), \"%u\", proc->pid);"
    ), (
        "\t\tchar strbuf[32];\n\n"
        "\t\tsnprintf(strbuf, sizeof(strbuf), \"%u-%s\",\n"
        "\t\t\t proc->pid, proc->context->name);"
    ))

    result = replace_once(result, (
        "static struct miscdevice binder_miscdev = {\n"
        "\t.minor = MISC_DYNAMIC_MINOR,\n"
        "\t.name = \"binder\",\n"
        "\t.fops = &binder_fops\n"
        "};"
    ), (
        "/* Three isolated service-manager domains; no BinderFS in this tree. */\n"
        "static struct binder_device binder_devices[] = {\n"
        "\t{ { MISC_DYNAMIC_MINOR, \"binder\", &binder_fops },\n"
        "\t  { NULL, INVALID_UID, \"binder\" } },\n"
        "\t{ { MISC_DYNAMIC_MINOR, \"hwbinder\", &binder_fops },\n"
        "\t  { NULL, INVALID_UID, \"hwbinder\" } },\n"
        "\t{ { MISC_DYNAMIC_MINOR, \"vndbinder\", &binder_fops },\n"
        "\t  { NULL, INVALID_UID, \"vndbinder\" } },\n"
        "};"
    ))
    result = replace_once(result, (
        "static int __init binder_init(void)\n"
        "{\n"
        "\tint ret;"
    ), (
        "static int __init binder_init(void)\n"
        "{\n"
        "\tint ret;\n"
        "\tint i;"
    ))
    result = replace_once(result, (
        "\tret = misc_register(&binder_miscdev);"
    ), (
        "\tfor (i = 0; i < ARRAY_SIZE(binder_devices); i++) {\n"
        "\t\tret = misc_register(&binder_devices[i].miscdev);\n"
        "\t\tif (ret) {\n"
        "\t\t\twhile (i--)\n"
        "\t\t\t\tmisc_deregister(&binder_devices[i].miscdev);\n"
        "\t\t\tdebugfs_remove_recursive(binder_debugfs_dir_entry_root);\n"
        "\t\t\tdestroy_workqueue(binder_deferred_workqueue);\n"
        "\t\t\treturn ret;\n"
        "\t\t}\n"
        "\t}"
    ))

    if "binder_context_mgr_node" in result or "binder_context_mgr_uid" in result:
        raise ValueError("Nicht alle globalen Binder-Manager ersetzt")
    for needle in ('"binder"', '"hwbinder"', '"vndbinder"',
                   "node->proc->context->mgr_node", "proc->context->mgr_node",
                   "target_proc->context != proc->context"):
        if needle not in result:
            raise ValueError(f"Unvollständige Binder-Domäne: {needle}")
    return result


def patch_shadow(shadow: Path, workspace: Path) -> dict:
    """Edit only an exclusive shadow copy and save its reviewable diff."""
    path = shadow / "drivers/android/binder.c"
    if path.is_symlink() or not path.is_file():
        raise ValueError("Binder-Schattenquelle fehlt oder ist ein Symlink")
    if workspace.resolve().is_relative_to(shadow.resolve()):
        raise ValueError("Patchbericht darf nicht im Samsung-Schattenbaum liegen")
    original = path.read_text(encoding="utf-8")
    modified = transform(original)
    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True), modified.splitlines(keepends=True),
        fromfile="a/drivers/android/binder.c", tofile="b/drivers/android/binder.c"))
    # The diff lives with the host-run report, never in a TV firmware image.
    review = workspace / "binder-multicontext-lab.patch"
    with review.open("x", encoding="utf-8") as output:
        output.write(diff)
    path.chmod(path.stat().st_mode | 0o200)
    path.write_text(modified, encoding="utf-8")
    return {"experimental": True, "patch_file": review.name,
            "original_sha256": ORIGINAL_BINDER_SHA256,
            "patched_sha256": hashlib.sha256(modified.encode("utf-8")).hexdigest(),
            "runtime_tested": False, "flash_authorized": False}
