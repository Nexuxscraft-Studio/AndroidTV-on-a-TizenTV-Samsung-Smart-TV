"""Read-only pure-logic boot-contract tests; no proprietary DTB included."""

import unittest

from q60t_build025_boot_contract import inspect_nodes, safe_strings, analyze_bundle


class BootContractTests(unittest.TestCase):
    def test_a57_and_psci_claim_without_boot_proof(self):
        nodes = {"/": {"compatible": b"samsung,sdp-nikel\x00"},
                 "/cpus/cpu@0": {"compatible": b"arm,cortex-a57\x00", "enable-method": b"psci\x00"},
                 "/cpus/cpu@1": {"compatible": b"arm,cortex-a57\x00"},
                 "/psci": {"compatible": b"arm,psci-1.0\x00", "method": b"smc\x00"},
                 "/intc": {"compatible": b"arm,gic-400\x00"},
                 "/timer": {"compatible": b"arm,armv7-timer\x00"}}
        info = inspect_nodes(nodes)
        self.assertTrue(info["cpu_a57_claimed_in_fdt"])
        self.assertTrue(info["psci_declared_in_fdt"])
        self.assertFalse(info["bootloader_aarch64_handoff_verified"])
        self.assertEqual(info["psci_nodes"][0]["method"], ["smc"])

    def test_psci_absence_is_not_an_absolute_architectural_claim(self):
        info = inspect_nodes({"/": {}, "/cpus/cpu@0": {"compatible": b"arm,cortex-a57\x00"}})
        self.assertFalse(info["psci_declared_in_fdt"])
        self.assertTrue(info["cpu_a57_claimed_in_fdt"])
        self.assertFalse(info["aarch64_exception_level_verified"])

    def test_unsafe_properties_never_leak_into_report(self):
        nodes = {"/": {}, "/chosen": {"bootargs": b"secret-password=do-not-print\x00"},
                 "/cpus/cpu@0": {"compatible": b"arm,cortex-a57\x00", "serial-number": b"private\x00"}}
        info = inspect_nodes(nodes)
        self.assertNotIn("private", str(info))
        self.assertNotIn("secret-password", str(info))
        self.assertEqual(safe_strings(b"a\x00b\x00"), ["a", "b"])
        self.assertEqual(safe_strings(b"\xff\x00"), [])

    def test_reference_blob_hash_prevents_accidental_unknown_inputs(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            analyze_bundle(b"untrusted-pseudo-dtb")


if __name__ == "__main__":
    unittest.main()
