"""Build 022 synthetic host-only tests: no repo sync, QEMU or TV access."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import q60t_lineage_init_evidence as init_evidence
import q60t_lineage_preflight as preflight


class Build022Tests(unittest.TestCase):
    def test_official_source_candidate_refs_are_pinned_but_unselected(self):
        data = preflight.load_candidates()
        self.assertIsNone(data["selected_branch"])
        self.assertEqual({c["branch"] for c in data["candidates"]},
                         {"cm-14.1", "lineage-15.1", "lineage-16.0", "lineage-17.1"})
        self.assertEqual(data["upstream_repo"], "https://github.com/LineageOS/android.git")
        self.assertFalse(preflight.load_virtual_board()["flash_authorized"])

    def test_preflight_evaluates_candidate_without_selecting_it(self):
        for branch in ("cm-14.1", "lineage-15.1", "lineage-16.0", "lineage-17.1"):
            report = preflight.evaluate(branch)
            self.assertFalse(report["lineage_version_selected"])
            self.assertFalse(report["android_tv_build_ready"])
            self.assertFalse(report["safe_to_flash"])
            self.assertEqual(report["source_manifest"]["status"], "NOT_PROVIDED")
            self.assertEqual(report["kernel_config"]["status"], "NOT_PROVIDED")

    def test_unlisted_or_invented_branch_rejected(self):
        with self.assertRaisesRegex(ValueError, "Nicht erfasster"):
            preflight.evaluate("lineage-14.1")

    def test_forged_compatibility_or_selected_version_rejected(self):
        data = preflight.load_candidates()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "candidates.json"
            data["selected_branch"] = "cm-14.1"
            p.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "neutral"):
                preflight.load_candidates(p)
            data["selected_branch"] = None
            data["candidates"][0]["qemu_virt_compatible"] = True
            p.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Ungültiger"):
                preflight.load_candidates(p)

    def test_exact_official_manifest_blob_hash_verification(self):
        xml = b'<manifest><remote name="origin" fetch="."/><default remote="origin" revision="x"/><project name="platform/bionic" path="bionic"/></manifest>\n'
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "default.xml"
            manifest.write_bytes(xml)
            sha = preflight.git_blob_sha1(xml)
            check = preflight.check_official_manifest(manifest, sha)
            self.assertEqual(check["manifest_blob_sha1"], sha)
            self.assertEqual(check["projects_in_top_level_manifest"], 1)
            self.assertFalse(check["source_repositories_synced"])
            manifest.write_bytes(xml + b"\n")
            with self.assertRaisesRegex(ValueError, "Blob-SHA"):
                preflight.check_official_manifest(manifest, sha)

    def test_manifest_rejects_non_manifest_and_dtd(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "default.xml"
            for xml in (b"<notmanifest/>",
                        b'<!DOCTYPE manifest [<!ENTITY x "y">]><manifest><project name="x"/></manifest>'):
                manifest.write_bytes(xml)
                with self.assertRaises(ValueError):
                    preflight.check_official_manifest(manifest, preflight.git_blob_sha1(xml))

    def test_kernel_config_reports_builtin_module_disabled_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / ".config"
            config.write_text("CONFIG_DEVTMPFS=y\nCONFIG_ANDROID_BINDER_IPC=y\n"
                              "CONFIG_SECURITY_SELINUX=m\n# CONFIG_CGROUPS is not set\n",
                              encoding="ascii")
            result = preflight.inspect_kernel_config(config)
            flags = result["features"]
            self.assertEqual(flags["binder"]["status"], "BUILT_IN")
            self.assertEqual(flags["selinux"]["status"], "MODULE_ONLY_NOT_AUTOMATICALLY_LOADABLE")
            self.assertEqual(flags["cgroups"]["status"], "DISABLED")
            self.assertEqual(flags["ion_legacy"]["status"], "UNKNOWN_OR_ABSENT")
            self.assertFalse(result["all_feature_switches_built_in"])

    def test_config_does_not_certify_android_boot_even_if_all_config_yes(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / ".config"
            config.write_text("".join(f"{key}=y\n" for key in preflight.KERNEL_FEATURES.values()))
            report = preflight.evaluate("cm-14.1", kernel_config=config)
            self.assertTrue(report["kernel_config"]["all_feature_switches_built_in"])
            self.assertFalse(report["guest_android_init_executed"])
            self.assertFalse(report["android_tv_build_ready"])

    def test_reject_symlinked_input_and_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "real.xml"
            source.write_text("<manifest/>")
            alias = root / "alias.xml"
            alias.symlink_to(source)
            with self.assertRaisesRegex(ValueError, "reguläre"):
                preflight.check_official_manifest(alias, preflight.git_blob_sha1(source.read_bytes()))
            out = root / "result.json"
            out.write_text("DO_NOT_TOUCH")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(preflight.main(["--candidate", "cm-14.1", "--output", str(out)]), 2)
            self.assertEqual(out.read_text(), "DO_NOT_TOUCH")

    def test_init_log_without_android_init_is_not_a_boot_pass(self):
        log = b"Linux version 4.1.10\nQ60T_BIONIC_HELLO version=020 host_only=1\n"
        result = init_evidence.inspect(log)
        self.assertTrue(result["markers_seen"]["linux_kernel"])
        self.assertFalse(result["markers_seen"]["android_init_first_stage"])
        self.assertFalse(result["real_lineageos_android_init_proven"])

    def test_init_markers_alone_are_never_a_verified_boot(self):
        log = (b"Linux version 4.1.10\n"
               b"init: init first stage started!\n"
               b"init: init second stage started!\n"
               b"init: property service started\n"
               b"init: starting service 'logd'...\n")
        report = init_evidence.inspect(log)
        self.assertTrue(report["markers_seen"]["android_init_first_stage"])
        self.assertTrue(report["markers_seen"]["android_init_second_stage"])
        self.assertFalse(report["real_lineageos_android_init_proven"])
        self.assertFalse(report["android_system_services_proven_running"])

    def test_kernel_panic_invalidates_even_observed_init_progress(self):
        log = b"Linux version 4.1.10\ninit: init first stage started!\nKernel panic - not syncing\n"
        report = init_evidence.inspect(log)
        self.assertTrue(report["kernel_panic_or_fatal_signal_seen"])
        self.assertFalse(report["init_first_stage_log_observed"])


if __name__ == "__main__":
    unittest.main()
