#!/usr/bin/env python3
"""Build 068: offline verifier for a LineageOS 22.2 ARM32 Android-TV build.

Reads a finished ``$PRODUCT_OUT`` directory (e.g.
``out/target/product/generic``) and checks, WITHOUT booting anything, whether
the produced userspace really is a pure 32-bit ARM Android 15 TV userspace:

* build properties: Android 15 / SDK 35, ABI list armeabi-v7a only,
  ``ro.zygote=zygote32``, no 64-bit ABI list;
* ELF headers of key binaries (app_process32, servicemanager, init, linker):
  ELFCLASS32 + EM_ARM, and no 64-bit app_process / linker64;
* the Android-TV feature ``android.software.leanback`` is declared;
* which images were produced (informational).

Read-only. No network, no TV access, no emulator start. A missing input is
reported as ``MISSING`` (never as PASS); a check that does not apply to the
build type (e.g. ro.zygote in a vendor-less GSI) is ``N/A``. Exit codes: 0 = all required checks
PASS, 1 = at least one FAIL, 2 = no FAIL but at least one MISSING.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

EM_ARM = 40
EM_AARCH64 = 183
ELFCLASS32 = 1
ELFCLASS64 = 2

# Property files of an Android 15 PRODUCT_OUT, relative paths.
PROP_FILES = (
    "system/build.prop",
    "system/system/build.prop",          # system-as-root staging layout
    "vendor/build.prop",
    "product/etc/build.prop",
    "system_ext/etc/build.prop",
    "odm/etc/build.prop",
    "vendor/default.prop",
    "system/etc/prop.default",            # Android 10+: ro.zygote lives here
    "ramdisk/prop.default",
)

# Binaries that must be 32-bit ARM. First existing candidate per entry wins.
ARM32_BINARIES = {
    "app_process32": ("system/bin/app_process32",),
    "servicemanager": ("system/bin/servicemanager",),
    "init": ("system/bin/init",),
    # system/bin/linker is a symlink into /apex; the real binary is staged
    # under $PRODUCT_OUT/apex/com.android.runtime/bin/linker.
    "linker": ("apex/com.android.runtime/bin/linker",
               "symbols/apex/com.android.runtime/bin/linker",
               "system/apex/com.android.runtime/bin/linker",
               "system/bin/linker"),
}

# Paths whose presence indicates a 64-bit (or multilib) userspace.
FORBIDDEN_64BIT = (
    "system/bin/app_process64",
    "system/bin/linker64",
    "system/lib64",
    "vendor/lib64",
)

IMAGES = ("system.img", "vendor.img", "product.img", "system_ext.img",
          "ramdisk.img", "boot.img", "super.img", "userdata.img",
          "vbmeta.img", "kernel-ranchu")

LEANBACK_FEATURE = "android.software.leanback"
PERMISSION_DIRS = ("system/etc/permissions", "vendor/etc/permissions",
                   "product/etc/permissions", "system_ext/etc/permissions")


def parse_props(text: str) -> dict[str, str]:
    """Parse a build.prop style file; later keys override earlier ones."""
    props: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("import "):
            continue
        key, sep, value = line.partition("=")
        if sep:
            props[key.strip()] = value.strip()
    return props


def collect_props(out: Path) -> tuple[dict[str, str], list[str]]:
    merged: dict[str, str] = {}
    found: list[str] = []
    for rel in PROP_FILES:
        path = out / rel
        if path.is_file():
            found.append(rel)
            merged.update(parse_props(path.read_text(encoding="utf-8",
                                                     errors="replace")))
    return merged, found


def elf_ident(path: Path) -> dict | None:
    """Return class/machine of an ELF file, or None if not ELF/too short."""
    try:
        with path.open("rb") as fh:
            head = fh.read(20)
    except OSError:
        return None
    if len(head) < 20 or head[:4] != b"\x7fELF":
        return None
    ei_class, ei_data = head[4], head[5]
    order = "little" if ei_data == 1 else "big"
    machine = int.from_bytes(head[18:20], order)
    return {"class": ei_class, "machine": machine}


def _first_prop(props: dict[str, str], *keys: str) -> tuple[str | None, str | None]:
    for key in keys:
        if key in props:
            return key, props[key]
    return None, None


def _abi_lists(props: dict[str, str], suffix: str) -> dict[str, str]:
    return {k: v for k, v in props.items()
            if k.endswith("product.cpu." + suffix)}


def check(out: Path) -> dict:
    checks: list[dict] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"check": name, "status": status, "detail": detail})

    props, prop_files = collect_props(out)
    if not prop_files:
        add("build_props_present", "MISSING",
            "keine build.prop unter PRODUCT_OUT gefunden")
    else:
        add("build_props_present", "PASS", ", ".join(prop_files))

    # Android version
    _, release = _first_prop(props, "ro.build.version.release",
                             "ro.system.build.version.release")
    _, sdk = _first_prop(props, "ro.build.version.sdk",
                         "ro.system.build.version.sdk")
    if release is None and sdk is None:
        add("android_15", "MISSING", "ro.build.version.release/sdk fehlen")
    elif sdk == "35" or (release or "").split(".")[0] == "15":
        add("android_15", "PASS", f"release={release} sdk={sdk}")
    else:
        add("android_15", "FAIL", f"release={release} sdk={sdk} (erwartet 15/35)")

    # Primary ABI
    key, abi = _first_prop(props, "ro.product.cpu.abi",
                           "ro.vendor.product.cpu.abi",
                           "ro.system.product.cpu.abi")
    if abi is None:
        # GSI builds (system image only) carry no vendor/build.prop; fall back
        # to the first entry of the system ABI list.
        key, lst = _first_prop(props, "ro.system.product.cpu.abilist",
                               "ro.product.cpu.abilist")
        if lst:
            abi = lst.split(",")[0].strip()
            key = f"{key}[0]"
    if abi is None:
        add("primary_abi_armeabi_v7a", "MISSING", "ro.product.cpu.abi fehlt")
    elif abi == "armeabi-v7a":
        add("primary_abi_armeabi_v7a", "PASS", f"{key}={abi}")
    else:
        add("primary_abi_armeabi_v7a", "FAIL", f"{key}={abi}")

    # ABI lists: no 64-bit entries anywhere
    lists = _abi_lists(props, "abilist")
    lists64 = _abi_lists(props, "abilist64")
    if not lists and not lists64:
        add("no_64bit_abi", "MISSING", "keine *.product.cpu.abilist*-Properties")
    else:
        bad = {k: v for k, v in {**lists, **lists64}.items()
               if "arm64" in v or "x86_64" in v or (k in lists64 and v)}
        if bad:
            add("no_64bit_abi", "FAIL", json.dumps(bad, ensure_ascii=False))
        else:
            add("no_64bit_abi", "PASS",
                "; ".join(f"{k}={v}" for k, v in sorted({**lists, **lists64}.items())))

    # Zygote
    zygote = props.get("ro.zygote")
    vendor_built = (out / "vendor/build.prop").is_file() or (out / "vendor.img").is_file()
    if zygote is None and not vendor_built:
        # GSI / system-only build: ro.zygote is a vendor/device property.
        add("zygote32", "N/A",
            "kein Vendor gebaut (GSI); ro.zygote setzt der Vendor des Geraets")
    elif zygote is None:
        add("zygote32", "MISSING", "ro.zygote fehlt")
    elif zygote == "zygote32":
        add("zygote32", "PASS", "ro.zygote=zygote32")
    else:
        add("zygote32", "FAIL", f"ro.zygote={zygote}")

    # ELF headers
    for name, candidates in ARM32_BINARIES.items():
        path = next((out / c for c in candidates if (out / c).is_file()), None)
        if path is None:
            add(f"elf32_arm:{name}", "MISSING", " | ".join(candidates))
            continue
        ident = elf_ident(path)
        rel = str(path.relative_to(out))
        if ident is None:
            add(f"elf32_arm:{name}", "FAIL", f"{rel}: kein ELF")
        elif ident["class"] == ELFCLASS32 and ident["machine"] == EM_ARM:
            add(f"elf32_arm:{name}", "PASS", f"{rel}: ELF32 EM_ARM")
        else:
            add(f"elf32_arm:{name}", "FAIL",
                f"{rel}: class={ident['class']} machine={ident['machine']}")

    present64 = [p for p in FORBIDDEN_64BIT if (out / p).exists()]
    if present64:
        add("no_64bit_userspace_paths", "FAIL", ", ".join(present64))
    elif (out / "system").is_dir():
        add("no_64bit_userspace_paths", "PASS", "keine lib64/app_process64/linker64")
    else:
        add("no_64bit_userspace_paths", "MISSING", "system/ fehlt")

    # Android TV feature
    perm_dirs = [out / d for d in PERMISSION_DIRS if (out / d).is_dir()]
    if not perm_dirs:
        add("leanback_feature", "MISSING", "keine etc/permissions-Verzeichnisse")
    else:
        hit = None
        for d in perm_dirs:
            for xml in sorted(d.glob("*.xml")):
                try:
                    if LEANBACK_FEATURE in xml.read_text(encoding="utf-8",
                                                         errors="replace"):
                        hit = xml.relative_to(out)
                        break
                except OSError:
                    continue
            if hit:
                break
        if hit:
            add("leanback_feature", "PASS", str(hit))
        else:
            add("leanback_feature", "FAIL", f"{LEANBACK_FEATURE} nicht deklariert")

    images = {img: (out / img).is_file() for img in IMAGES}
    statuses = [c["status"] for c in checks if c["status"] != "N/A"]
    overall = ("FAIL" if "FAIL" in statuses else
               "INCOMPLETE" if "MISSING" in statuses else "PASS")
    return {
        "build": "068",
        "product_out": str(out),
        "overall": overall,
        "checks": checks,
        "images_present": images,
        "product": {k: props.get(k) for k in (
            "ro.product.name", "ro.product.system.name", "ro.build.fingerprint",
            "ro.lineage.version", "ro.build.characteristics")},
        "note": ("Statische Artefaktprüfung. Beweist keinen Boot, keine "
                 "Binder-Laufzeit und nichts über den Q60T."),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("product_out", type=Path, help="$PRODUCT_OUT-Verzeichnis")
    p.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    args = p.parse_args(argv)
    out = args.product_out
    if not out.is_dir():
        p.error(f"{out} ist kein Verzeichnis")
    report = check(out.resolve())
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for c in report["checks"]:
            print(f"  {c['status']:<8} {c['check']}: {c['detail']}")
        present = [k for k, v in report["images_present"].items() if v]
        print(f"  Images: {', '.join(present) or '(keine)'}")
        print(f"GESAMT: {report['overall']}")
    return {"PASS": 0, "FAIL": 1}.get(report["overall"], 2)


if __name__ == "__main__":
    sys.exit(main())
