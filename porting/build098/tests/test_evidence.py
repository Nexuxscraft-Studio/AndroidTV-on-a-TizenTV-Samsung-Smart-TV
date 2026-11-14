import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class ReadinessEvidence(unittest.TestCase):
    def setUp(self):
        self.manifest = read_json("porting/build098/manifest.json")

    def test_required_topics_and_local_sources(self):
        evidence = self.manifest["evidence"]
        self.assertCountEqual(
            [entry["id"] for entry in evidence],
            ["boot-chain", "cpu-handoff", "boot-data", "kernel-address",
             "memory", "uart", "recovery"],
        )
        for entry in evidence:
            with self.subTest(topic=entry["id"]):
                self.assertIn(entry["grade"], {
                    "historischer-binaerbefund", "statische-deklaration", "offen",
                })
                self.assertTrue(entry["observation"].strip())
                self.assertTrue(entry["blocker"].strip())
                self.assertTrue(entry["sources"])
                for source in entry["sources"]:
                    path = (ROOT / source).resolve()
                    self.assertTrue(path.is_relative_to(ROOT))
                    self.assertTrue(path.is_file(), source)

    def test_stock_addresses_are_outside_both_archived_profiles(self):
        report = read_json("reports/hardware_2743.0_build004_final.json")
        self.assertEqual([tree["offset_bytes"] for tree in report["trees"]], [0, 0x15000])
        header = self.manifest["stock_header"]
        stock_report = (ROOT / "BUILD061_REPORT.md").read_text(encoding="utf-8")
        self.assertIn(f"| load / entry | `{header['load']}` / `{header['entry']}` |",
                      stock_report)
        for tree, count in zip(report["trees"], (3, 4)):
            banks = tree["summary"]["memory_reg"]["ranges"]
            self.assertEqual(len(banks), count)
            for bank in banks:
                base = int(bank["base_hex"], 16)
                size = bank["size_bytes"]
                self.assertGreater(size, 0)
                for address in header.values():
                    self.assertFalse(base <= int(address, 16) < base + size)

    def test_boot_decision_remains_blocked(self):
        self.assertEqual(self.manifest["decision"], "BLOCKED")
        self.assertEqual(self.manifest["ram_boot"], "HYPOTHETICAL_ONLY")
        gates = read_json("porting/boot-evidence.json")
        for gate in ("bootloader_authentication_policy_verified",
                     "nonpersistent_test_boot_interface_demonstrated",
                     "recovery_entrypoint_verified",
                     "rollback_drill_completed_on_spare_hardware"):
            self.assertIs(gates[gate], False)


if __name__ == "__main__":
    unittest.main()
