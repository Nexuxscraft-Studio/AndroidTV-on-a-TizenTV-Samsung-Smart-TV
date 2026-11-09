"""Build 019 synthetic checks. No real ARM guest, Samsung TV or flash access."""

from pathlib import Path
import tempfile
import unittest

import q60t_android_userspace as audit


def synthetic_log(*, failure=None, missing=None, duplicate=None, panic=False):
    lines = [b"Linux version 4.1.10-lab #1", audit.BEGIN]
    for feature in audit.FEATURES:
        if feature == missing:
            continue
        state = "fail" if feature == failure else "pass"
        line = f"Q60T_ANDROID_PROBE_FEATURE name={feature} result={state}".encode()
        lines.append(line)
        if feature == duplicate:
            lines.append(line)
    lines.append(audit.END)
    if panic:
        lines.append(b"Kernel panic - not syncing")
    return b"\r\n".join(lines) + b"\r\n"


class AndroidUserspaceTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.log = Path(holder.name) / "qemu-serial-android019.log"

    def test_complete_linux_abi_test_never_claims_android_boot(self):
        self.log.write_bytes(synthetic_log())
        report = audit.create_report(self.log)
        self.assertEqual(report["kernel_abi_probe"]["status"],
                         "ARM32_KERNEL_ABI_SMOKE_PASS_REPORTED")
        self.assertTrue(report["kernel_abi_probe"]["stage1_kernel_abi_smoke_pass_reported"])
        self.assertFalse(report["android_boot_ready"])
        self.assertFalse(report["flash_authorized"])
        self.assertTrue(all(v == "unverified" for v in report["device_hardware_gates"].values()))

    def test_optional_selinux_unavailable_does_not_fake_policy(self):
        self.log.write_bytes(synthetic_log(failure="selinux_enforcing"))
        outcome = audit.inspect_log(self.log)
        self.assertTrue(outcome["stage1_kernel_abi_smoke_pass_reported"])
        self.assertFalse(outcome["android_userspace_compatible"])

    def test_required_binder_failure_stops_smoke_success(self):
        self.log.write_bytes(synthetic_log(failure="hwbinder"))
        self.assertEqual(audit.inspect_log(self.log)["status"],
                         "ARM32_KERNEL_ABI_SMOKE_INCOMPLETE")

    def test_missing_feature_fails_closed(self):
        self.log.write_bytes(synthetic_log(missing="epoll"))
        result = audit.inspect_log(self.log)
        self.assertIn("epoll", result["missing_features"])
        self.assertFalse(result["stage1_kernel_abi_smoke_pass_reported"])

    def test_duplicate_feature_fails_closed(self):
        self.log.write_bytes(synthetic_log(duplicate="binder"))
        result = audit.inspect_log(self.log)
        self.assertEqual(result["duplicate_feature_names"], ["binder"])
        self.assertFalse(result["stage1_kernel_abi_smoke_pass_reported"])

    def test_feature_outside_markers_fails_closed(self):
        blob = synthetic_log()
        line = b"Q60T_ANDROID_PROBE_FEATURE name=procfs result=pass"
        self.log.write_bytes(blob.replace(line + b"\r\n", b"", 1) + line + b"\r\n")
        outcome = audit.inspect_log(self.log)
        self.assertFalse(outcome["marker_order_valid"])
        self.assertFalse(outcome["stage1_kernel_abi_smoke_pass_reported"])

    def test_kernel_panic_overrides_markers(self):
        self.log.write_bytes(synthetic_log(panic=True))
        self.assertEqual(audit.inspect_log(self.log)["status"],
                         "KERNEL_PANIC_OBSERVED")

    def test_without_kernel_banner_is_not_evidence(self):
        self.log.write_bytes(synthetic_log().replace(b"Linux version 4.1.10-lab #1", b"not a real kernel"))
        self.assertEqual(audit.inspect_log(self.log)["status"],
                         "INCOMPLETE_OR_INVALID_GUEST_PROBE")

    def test_malformed_result_fails_closed(self):
        blob = synthetic_log().replace(b"name=binder result=pass", b"name=binder result=yes")
        self.log.write_bytes(blob)
        outcome = audit.inspect_log(self.log)
        self.assertTrue(outcome["invalid_feature_lines"])
        self.assertFalse(outcome["stage1_kernel_abi_smoke_pass_reported"])

    def test_existing_report_remains_intact(self):
        self.log.write_bytes(synthetic_log())
        dest = self.log.with_suffix(".json")
        dest.write_text("KEEP")
        self.assertEqual(audit.main(["--log", str(self.log), "--output", str(dest)]), 2)
        self.assertEqual(dest.read_text(), "KEEP")

    def test_new_report_is_created_exclusively(self):
        self.log.write_bytes(synthetic_log())
        dest = self.log.with_suffix(".json")
        self.assertEqual(audit.main(["--log", str(self.log), "--output", str(dest)]), 0)
        self.assertTrue(dest.exists())


if __name__ == "__main__":
    unittest.main()
