#!/usr/bin/env python3
"""Offline-only review of archived Q60T kernel configs; never contacts a TV."""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

MAX_INPUT_BYTES = 2 * 1024 * 1024
SYMBOLS = ('CONFIG_KEXEC', 'CONFIG_KEXEC_FILE', 'CONFIG_IKCONFIG',
           'CONFIG_IKCONFIG_PROC', 'CONFIG_DEVMEM')
GATES = ('exact_target_hardware_identified',
         'bootloader_authentication_policy_verified',
         'nonpersistent_test_boot_interface_demonstrated',
         'recovery_entrypoint_verified', 'known_good_backup_verified',
         'rollback_drill_completed_on_spare_hardware',
         'watchdog_fallback_verified', 'power_loss_recovery_verified')


def read_local(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError('Only regular, non-symlink local files are accepted')
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError('Input exceeds 2 MiB limit')
    data = path.read_bytes()
    if data.startswith(b'\x1f\x8b'):
        data = gzip.decompress(data)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError('Decompressed input exceeds 2 MiB limit')
    return data


def parse_config(path: Path) -> dict[str, str]:
    values = {symbol: 'unknown' for symbol in SYMBOLS}
    for line in read_local(path).decode('utf-8', 'replace').splitlines():
        match = re.fullmatch(r'(CONFIG_[A-Z0-9_]+)=(y|n|m)', line.strip())
        if match and match.group(1) in values:
            values[match.group(1)] = match.group(2)
            continue
        match = re.fullmatch(r'# (CONFIG_[A-Z0-9_]+) is not set', line.strip())
        if match and match.group(1) in values:
            values[match.group(1)] = 'n'
    return values


def audit(stock_defconfig: Path | None, runtime_config: Path | None,
          evidence: Path) -> dict:
    gates = json.loads(read_local(evidence).decode('utf-8'))
    if not isinstance(gates, dict):
        raise ValueError('Evidence must be a JSON object')
    baseline = parse_config(stock_defconfig) if stock_defconfig else None
    runtime = parse_config(runtime_config) if runtime_config else None
    runtime_kexec = runtime['CONFIG_KEXEC'] if runtime else 'unknown'
    if runtime_kexec == 'n':
        feasibility = 'NO_KEXEC_IN_SUPPLIED_RUNTIME_CONFIG'
    elif runtime_kexec == 'y':
        feasibility = 'CONFIG_ONLY_NOT_A_BOOT_PROOF'
    else:
        feasibility = 'NOT_VERIFIED_ON_TV'
    verified_gates = {gate: gates.get(gate) is True for gate in GATES}
    return {
        'report_type': 'build072_offline_ramboot_audit',
        'target': 'Samsung GQ50Q60TGUXZG',
        'stock_reference_config': baseline,
        'supplied_runtime_config': runtime,
        'runtime_config_provenance': 'USER_SUPPLIED_NOT_ATTESTED' if runtime else 'MISSING',
        'kexec_feasibility': feasibility,
        'samsung_uefi_or_alternate_loader': 'NOT_DEMONSTRATED',
        'memory_layout_compatibility': 'NOT_VERIFIED',
        'secure_boot_acceptance': 'NOT_VERIFIED',
        'nonpersistent_boot_path': 'NOT_DEMONSTRATED',
        'recovery_gates': verified_gates,
        'recovery_gate_status': 'UNVERIFIED' if not all(verified_gates.values()) else 'MANUAL_REVIEW_REQUIRED',
        'decision': 'BLOCKED_NO_DEVICE_BOOT',
        'flash_authorized': False,
        'execute_kexec': False,
        'device_contacted': False,
        'explanation': ('A stock defconfig is not proof of a retail runtime config. '
                        'Even CONFIG_KEXEC=y is only a prerequisite; privileges, '
                        'driver shutdown, hardware handoff, authentication and '
                        'recovery remain unverified.'),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-defconfig', type=Path,
                        help='Optional saved Samsung release_defconfig (reference only)')
    parser.add_argument('--runtime-config', type=Path,
                        help='Optional saved /proc/config.gz or /boot/config from the real TV')
    parser.add_argument('--evidence', type=Path,
                        default=Path(__file__).resolve().parents[2] / 'porting/boot-evidence.json')
    parser.add_argument('--output', type=Path, help='Create a NEW JSON report; never overwrite')
    args = parser.parse_args(argv)
    try:
        payload = json.dumps(audit(args.stock_defconfig, args.runtime_config, args.evidence),
                             indent=2, ensure_ascii=False) + '\n'
        if args.output:
            if args.output.is_symlink():
                raise ValueError('Output symlink refused')
            with args.output.open('x', encoding='utf-8') as outfile:
                outfile.write(payload)
        else:
            print(payload, end='')
        return 0
    except (ValueError, OSError, json.JSONDecodeError, gzip.BadGzipFile) as exc:
        print(f'build072: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
