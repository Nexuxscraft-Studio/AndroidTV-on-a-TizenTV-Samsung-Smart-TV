"""Samsung Build 058 CPU/TMU offline source/DT and fail-closed checks."""

from pathlib import Path
import subprocess
import unittest

from q60t_build058_cpu_dvfs_thermal_audit import (
    ROOT, DTS, inspect, parse_legacy_cpu, verify_drafts,
)


KERNEL_TGZ = ROOT / ".build050_vendor/srcarchives/linux-4.1.10-tizen5.5.tgz"
DTB = Path("/tmp/q60t-original-dtb-20261110.bin")


class Build058CpuDvfsThermalTests(unittest.TestCase):
    def test_fail_closed_kernel_prototypes(self):
        verify_drafts()

    def test_frequency_mismatch_and_transitions_cannot_be_accepted_silently(self):
        source = '''NIKE-M/L CPU frequency scaling support
        static struct cpufreq_frequency_table fake[] = {
            { 0, L0, 1700*1000}, { 0, L1, 1000*1000},
            { 0, L2, 500*1000}, { 0, L3, 250*1000},
            { 0, L4, 100*1000}, };
        '''
        with self.assertRaisesRegex(ValueError, "ASV voltage table"):
            parse_legacy_cpu(source)

    def test_host_portable_cpu_model_compiles_and_runs(self):
        cmd = ["bash", str(ROOT / "porting/build058/cpu/run-host-tests.sh")]
        run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                             timeout=30, check=False)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        self.assertIn("PASS: offline Nike CPU/DVFS/TMU model", run.stdout)

    @unittest.skipUnless(KERNEL_TGZ.is_file() and DTB.is_file(), "Original pinned firmware/source unavailable")
    def test_original_vendor_source_and_firmware_crosschecked(self):
        report = inspect(KERNEL_TGZ, DTB)
        self.assertEqual(2, len(report["firmware_variants"]))
        self.assertTrue(report["nike_cpu_source"]["l4_table_divider_mismatch"])
        self.assertEqual(125000, report["nike_cpu_source"]["divided_1ghz_levels_khz"][4])
        self.assertEqual(100000, report["nike_cpu_source"]["nominal_table_khz"][4])
        self.assertEqual([1000000, 700000, 100000],
                         report["firmware_variants"][0]["cpu_throttle_limits_khz"])
        self.assertTrue(report["kernel_drivers_probe_blocked"])
        self.assertFalse(report["hardware_access_performed"])

    def test_no_fabricated_opp_or_enabled_device_tree(self):
        dts = DTS.read_text(encoding="utf-8")
        self.assertEqual(3, dts.count('status = "disabled";'))
        self.assertNotIn("opp-hz =", dts)
        self.assertNotIn("cpu-supply =", dts)


if __name__ == "__main__":
    unittest.main()
