#!/usr/bin/env python3
"""Conservative Android/ARM32 static gate for a *resolved* Linux .config.

These are project checklists, not a substitute for the upstream Android kernel
config specifications, CTS/VTS, driver probing or a real-device boot.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


CRITICAL = (
    "CONFIG_AEABI", "CONFIG_ARM_LPAE", "CONFIG_ANDROID_BINDER_IPC",
    "CONFIG_SECURITY_SELINUX", "CONFIG_CGROUPS", "CONFIG_NAMESPACES",
    "CONFIG_DMA_SHARED_BUFFER", "CONFIG_DMABUF_HEAPS", "CONFIG_DEVTMPFS",
    "CONFIG_TMPFS",
)
REVIEW = (
    "CONFIG_ANDROID_BINDERFS", "CONFIG_PID_NS", "CONFIG_NET_NS",
    "CONFIG_MEMCG", "CONFIG_PSI", "CONFIG_SECCOMP", "CONFIG_SECCOMP_FILTER",
    "CONFIG_FHANDLE", "CONFIG_OVERLAY_FS", "CONFIG_DM_VERITY",
)


def parse_config(source: str) -> dict[str, str]:
    """Parse the Kconfig resolved format, including '# ... is not set'."""
    result: dict[str, str] = {}
    for line in source.splitlines():
        enabled = re.fullmatch(r"(CONFIG_[A-Z0-9_]+)=(.*)", line)
        disabled = re.fullmatch(r"# (CONFIG_[A-Z0-9_]+) is not set", line)
        if enabled:
            result[enabled.group(1)] = enabled.group(2)
        elif disabled:
            result[disabled.group(1)] = "n"
    return result


def inspect_config(config: dict[str, str]) -> dict:
    critical = {key: {"value": config.get(key, "absent"),
                       "ok": config.get(key) == "y"} for key in CRITICAL}
    review = {key: {"value": config.get(key, "absent"),
                     "enabled": config.get(key) == "y"} for key in REVIEW}
    # An ARM32 kernel must not accidentally select the ARM64 architecture.
    architecture_ok = config.get("CONFIG_ARM64") != "y"
    passed = all(v["ok"] for v in critical.values()) and architecture_ok
    return {
        "type": "arm32_android15_kernel_config_gate",
        "status": "PASS_STATIC_CONFIG_ONLY" if passed else "BLOCKED_STATIC_CONFIG",
        "critical": critical,
        "review": review,
        "architecture_ok": architecture_ok,
        "runtime_validation": "UNVERIFIED",
        "notes": [
            "Evaluate the final resolved ARM32 kernel .config, not a config fragment.",
            "These flags are a necessary project subset, not Android CDD/VTS completeness.",
            "Binder device nodes, SELinux policy, dma-buf heaps and HALs need runtime tests.",
            "A PASS does not mean the signed Samsung boot chain accepts the kernel.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", required=True, type=Path,
                   help="Final resolved .config from Build059 Linux 6.6.162 ARM32")
    args = p.parse_args(argv)
    try:
        contents = args.config.read_text(encoding="utf-8")
    except OSError as exc:
        p.error(f"Cannot read .config: {exc}")
    report = inspect_config(parse_config(contents))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "PASS_STATIC_CONFIG_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
