"""No TV, no network, no kexec: synthetic-only Build 072 checks."""
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ramboot_audit import audit, main, parse_config


class RambootAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.gates = self.base / 'evidence.json'
        self.gates.write_text('{}', encoding='utf-8')

    def write(self, name, content):
        path = self.base / name
        path.write_text(content, encoding='utf-8')
        return path

    def test_stock_config_does_not_prove_runtime(self):
        stock = self.write('release_defconfig', '# CONFIG_KEXEC is not set\n')
        report = audit(stock, None, self.gates)
        self.assertEqual(report['stock_reference_config']['CONFIG_KEXEC'], 'n')
        self.assertEqual(report['kexec_feasibility'], 'NOT_VERIFIED_ON_TV')
        self.assertFalse(report['flash_authorized'])

    def test_disabled_in_runtime(self):
        runtime = self.write('config', '# CONFIG_KEXEC is not set\n')
        self.assertEqual(audit(None, runtime, self.gates)['kexec_feasibility'],
                         'NO_KEXEC_IN_SUPPLIED_RUNTIME_CONFIG')

    def test_enabled_runtime_is_not_a_boot_permission(self):
        runtime = self.write('config', 'CONFIG_KEXEC=y\n')
        report = audit(None, runtime, self.gates)
        self.assertEqual(report['kexec_feasibility'], 'CONFIG_ONLY_NOT_A_BOOT_PROOF')
        self.assertEqual(report['decision'], 'BLOCKED_NO_DEVICE_BOOT')
        self.assertFalse(report['execute_kexec'])

    def test_all_gates_still_require_human_review(self):
        from ramboot_audit import GATES
        self.gates.write_text(json.dumps(dict.fromkeys(GATES, True)))
        report = audit(None, None, self.gates)
        self.assertEqual(report['recovery_gate_status'], 'MANUAL_REVIEW_REQUIRED')
        self.assertFalse(report['flash_authorized'])

    def test_gzipped_runtime_config(self):
        data = self.base / 'config.gz'
        data.write_bytes(gzip.compress(b'CONFIG_KEXEC=y\nCONFIG_IKCONFIG=y\n'))
        self.assertEqual(parse_config(data)['CONFIG_KEXEC'], 'y')

    def test_reject_symlink_input(self):
        p = self.write('config', 'CONFIG_KEXEC=y\n')
        link = self.base / 'link'
        link.symlink_to(p)
        with self.assertRaises(ValueError):
            parse_config(link)

    def test_never_overwrite_report(self):
        output = self.write('report.json', 'existing data')
        self.assertEqual(main(['--evidence', str(self.gates), '--output', str(output)]), 2)
        self.assertEqual(output.read_text(), 'existing data')


if __name__ == '__main__':
    unittest.main()
