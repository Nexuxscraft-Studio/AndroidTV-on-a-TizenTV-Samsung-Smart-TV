"""Synthetic offline test data only; no Samsung firmware distributed."""

from pathlib import Path
import struct
import sys
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
import zipfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import q60t_lab  # noqa: E402
import q60t_hardware  # noqa: E402
import q60t_rootfs  # noqa: E402
import q60t_portcheck  # noqa: E402
import q60t_release_audit  # noqa: E402
import q60t_kernel_build  # noqa: E402
import q60t_graphics  # noqa: E402
import q60t_boot_safety  # noqa: E402
import q60t_source_provenance  # noqa: E402
import q60t_gpu_strategy  # noqa: E402
import q60t_build007_preflight  # noqa: E402


def synthetic_uimage(payload=b"Synthetic kernel data"):
    """Create a structurally valid *fake* uImage for integrity tests."""
    name = b"FAKE TEST IMAGE".ljust(32, b"\x00")
    payload_crc = zlib.crc32(payload) & 0xFFFFFFFF
    fields = (0x27051956, 0, 0, len(payload), 0x80008000,
              0x80008000, payload_crc, 5, 2, 2, 0, name)
    header = struct.pack(">7I4B32s", *fields)
    header_crc = zlib.crc32(header) & 0xFFFFFFFF
    fields = list(fields)
    fields[1] = header_crc
    return struct.pack(">7I4B32s", *fields) + payload


def synthetic_dtb():
    # Minimal valid structural stream with non-sensitive model/compatible tags.
    strings = b"model\x00compatible\x00"
    props = [(0, b"Synthetic Q60T\x00"), (6, b"samsung,q60t-test\x00")]
    structure = struct.pack(">I", 1) + b"\x00" * 4  # root node
    for name_offset, value in props:
        structure += struct.pack(">III", 3, len(value), name_offset) + value
        structure += b"\x00" * ((-len(value)) % 4)
    structure += struct.pack(">II", 2, 9)
    struct_offset = 56  # 40-byte header, 16-byte reserved-memory terminator
    strings_offset = struct_offset + len(structure)
    total = strings_offset + len(strings)
    header = struct.pack(">10I", 0xD00DFEED, total, struct_offset,
                         strings_offset, 40, 17, 16, 0, len(strings), len(structure))
    return header + b"\x00" * 16 + structure + strings


def synthetic_dtb_tree(cpu_name="cpu@0", model="Synthetic Q60T", profile="nikel-2G"):
    # Two nested subtrees with selectable model/CPU, explicitly fake.
    strings = b"model\x00compatible\x00bootargs\x00"
    offsets = {"model": 0, "compatible": 6, "bootargs": 17}

    def begin(name):
        raw = name.encode("ascii") + b"\x00"
        return struct.pack(">I", 1) + raw + (b"\x00" * (-len(raw) % 4))

    def prop(key, value):
        p = struct.pack(">III", 3, len(value), offsets[key]) + value
        return p + b"\x00" * (-len(value) % 4)

    s = begin("") + prop("model", model.encode() + b"\x00")
    s += prop("compatible", b"samsung,sdp-nikel\x00")
    bootargs = (f"dtsversion=0000000_{profile} root=/dev/mmcblk0p18 "
                "ip=SECRET ro").encode("ascii") + b"\x00"
    s += begin("chosen") + prop("bootargs", bootargs)
    s += struct.pack(">I", 2)
    s += begin("cpus") + begin(cpu_name)
    s += prop("compatible", b"arm,cortex-a57\x00arm,armv8\x00")
    s += struct.pack(">II", 2, 2)
    s += struct.pack(">II", 2, 9)
    struct_offset = 56
    strings_offset = struct_offset + len(s)
    total = strings_offset + len(strings)
    header = struct.pack(">10I", 0xD00DFEED, total, struct_offset,
                         strings_offset, 40, 17, 16, 0, len(strings), len(s))
    return header + b"\x00" * 16 + s + strings


class ZipTests(unittest.TestCase):
    def test_firmware_metadata_and_magic(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "T-NKLDEUC.zip"
            with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
                z.writestr("image/info.txt", "Model T-NKLDEUC\nVersion 2743.0\n")
                z.writestr("image/upgrade.msd", b"MSDU11" + b"synthetic")
            report = q60t_lab.inspect_firmware_zip(path)
            self.assertTrue(report["msdu11_magic"])
            self.assertEqual(report["metadata"]["detected_family"], "T-NKLDEUC")
            self.assertEqual(report["metadata"]["detected_version"], "2743.0")
            self.assertFalse(report["reference_sha256_match"])

    def test_archive_escape_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("../escape.txt", "do not extract")
            report = q60t_lab.inspect_firmware_zip(path)
            self.assertTrue(any("Nicht vertrauenswürdiger" in w for w in report["warnings"]))


    def test_samsung_prefixed_archive_layout(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "firmware.zip"
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("T-NKLDEUC/image/info.txt", "model string: T-NKLDEUC\nmajor version: 2743\nminor version: 0")
                z.writestr("T-NKLDEUC/image/upgrade.msd", b"MSDU11" + b"synthetic")
            report = q60t_lab.inspect_firmware_zip(path)
            self.assertTrue(report["msdu11_magic"])
            self.assertEqual(report["metadata"]["detected_family"], "T-NKLDEUC")
            self.assertEqual(report["metadata"]["detected_version"], "2743.0")

    def test_streaming_extraction_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            zip_path = Path(temp) / "source.zip"
            dest = Path(temp) / "firmware.msd"
            payload = b"MSDU11" + b"synthetic" * 1024
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("T-NKLDEUC/image/upgrade.msd", payload)
            result = q60t_lab.extract_zip_member(
                zip_path, "T-NKLDEUC/image/upgrade.msd", dest
            )
            self.assertEqual(result["size_bytes"], len(payload))
            self.assertEqual(dest.read_bytes(), payload)
            with self.assertRaises(ValueError):
                q60t_lab.extract_zip_member(
                    zip_path, "T-NKLDEUC/image/upgrade.msd", dest
                )

    def test_json_cli_does_not_overwrite_existing_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            out = root / "report.json"
            out.write_text("important user report", encoding="utf-8")
            self.assertEqual(q60t_lab.main(["inventory", str(root),
                                            "--output", str(out)]), 2)
            self.assertEqual(out.read_text(encoding="utf-8"),
                             "important user report")


class PortCheckTests(unittest.TestCase):
    def test_real_port_state_stays_blocked(self):
        source = Path(__file__).resolve().parents[1]
        result = q60t_portcheck.check_port(
            source / "porting", source / "reports/hardware_2743.0_build004_final.json")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["blocker_count"], 9)
        self.assertTrue(result["reference_hardware_verified"])
        self.assertTrue(result["official_exact_model_and_firmware_verified"])
        self.assertTrue(next(g for g in result["gates"] if g["name"] == "exact_model_code")["passed"])
        self.assertEqual(result["firmware_dt_status_by_profile"]["nikel-2g"]["hdmi_cec"],
                         "disabled")
        self.assertEqual(result["firmware_dt_status_by_profile"]["nikel-1.5g"]["infrared_irb"],
                         "okay")
        self.assertFalse(result["flash_authorized"])
        self.assertFalse(result["image_build_enabled"])

    def test_reference_report_mismatch_fails_closed(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            mismatch = Path(temp) / "invalid.json"
            mismatch.write_text('{"dtb_bundle_sha256":"invalid"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                q60t_portcheck.check_port(source / "porting", mismatch)

    def test_unknown_model_is_rejected(self):
        source = Path(__file__).resolve().parents[1]
        import json
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            (dest / "profiles").mkdir()
            for path in (source / "porting/profiles").glob("*.json"):
                (dest / "profiles" / path.name).write_bytes(path.read_bytes())
            manifest = json.loads((source / "porting/port-state.json").read_text())
            manifest["exact_model_code"] = "GQ55Q60TGUXZG"
            (dest / "port-state.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                q60t_portcheck.check_port(dest)

    def test_invalid_profile_is_not_silently_accepted(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            (dest / "profiles").mkdir()
            for p in (source / "porting/profiles").glob("*.json"):
                (dest / "profiles" / p.name).write_bytes(p.read_bytes())
            (dest / "port-state.json").write_text(
                '{"actual_tv_ram_profile":"arbitrary-value"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                q60t_portcheck.check_port(dest)

    def test_mismatched_ram_ranges_block_port_preflight(self):
        source = Path(__file__).resolve().parents[1]
        import json
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            (dest / "profiles").mkdir()
            for p in (source / "porting/profiles").glob("*.json"):
                value = json.loads(p.read_text(encoding="utf-8"))
                if value["id"] == "nikel-2g":
                    value["fdt_memory_reg_advertised_mib"] = 1118.25
                (dest / "profiles" / p.name).write_text(json.dumps(value), encoding="utf-8")
            (dest / "port-state.json").write_bytes(
                (source / "porting/port-state.json").read_bytes())
            with self.assertRaises(ValueError):
                q60t_portcheck.check_port(
                    dest, source / "reports/hardware_2743.0_build004_final.json")

    def test_port_report_never_overwrites(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "preflight.json"
            self.assertEqual(q60t_portcheck.main([
                "--project", str(source / "porting"), "--output", str(out)]), 1)
            content = out.read_text(encoding="utf-8")
            self.assertIn('"status": "BLOCKED"', content)
            self.assertEqual(q60t_portcheck.main([
                "--project", str(source / "porting"), "--output", str(out)]), 2)
            self.assertEqual(out.read_text(encoding="utf-8"), content)


class ReleaseAuditTests(unittest.TestCase):
    def test_source_tree_passes_without_proprietary_firmware(self):
        source = Path(__file__).resolve().parents[1]
        result = q60t_release_audit.audit(source)
        self.assertEqual(result["status"], "PASS", result["problems"])
        self.assertGreater(result["files_checked"], 10)

    def test_binary_and_credentials_block_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "ok.md").write_text("Synthetic example", encoding="utf-8")
            (root / "vendor.bin").write_bytes(b"\x01\x02")
            (root / "credentials.md").write_bytes(b"-----BEGIN " + b"PRIVATE KEY-----")
            result = q60t_release_audit.audit(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(len(result["problems"]), 2)


class KernelBuildTests(unittest.TestCase):
    def test_reference_source_version_from_synthetic_kernel_tree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "arch/arm").mkdir(parents=True)
            (root / "arch/arm/Makefile").write_text("# synthetic", encoding="utf-8")
            (root / "Makefile").write_text(
                "VERSION = 4\nPATCHLEVEL = 1\nSUBLEVEL = 10\n", encoding="utf-8")
            self.assertEqual(q60t_kernel_build.source_version(root), "4.1.10")
            config = root / "test.config"
            config.write_text("CONFIG_ARM=y\nCONFIG_AEABI=y\n", encoding="utf-8")
            report = q60t_kernel_build.make_plan(root, config, "arm-none-eabi-",
                                                  root / "out", toolchain_override={
                                                      "reference_version_match": True})
            self.assertTrue(report["checks"]["kernel_config_basic_arm_flags"])
            self.assertTrue(report["checks"]["source_version_matches_reference"])
            self.assertFalse(report["checks"]["source_provenance_for_exact_2743_firmware"])
            self.assertEqual(report["status"], "BLOCKED")
            self.assertFalse(report["image_built"])
            steps = report["build_commands_not_executed"]
            self.assertEqual(steps[0][:2], ["mkdir", "-p"])
            self.assertEqual(steps[1][:2], ["cp", "--"])
            self.assertTrue(steps[1][-1].endswith("/out/.config"))
            self.assertEqual(steps[2][-1], "olddefconfig")
            self.assertEqual(steps[3][-1], "zImage")
            self.assertFalse(report["checks"]["samsung_gpl_source_available"])
            self.assertTrue(report["checks"]["toolchain_version_matches_reference"])
            self.assertFalse(report["checks"]["matching_tizen_linaro_toolchain"])

    def test_matching_compiler_banner_does_not_prove_samsung_toolchain(self):
        report = q60t_kernel_build.make_plan(
            None, None, None, None, toolchain_override={
                "reference_version_match": True,
                "arm32_target_match": True,
                "tizen_linaro_brand_claimed": True,
                "exact_samsung_toolchain_provenance_verified": False,
            })
        self.assertTrue(report["checks"]["toolchain_target_is_arm32"])
        self.assertFalse(report["checks"]["matching_tizen_linaro_toolchain"])
        self.assertEqual(report["status"], "BLOCKED")

    def test_build008_source_registry_separates_findings_from_downloads(self):
        catalog = json.loads((Path(__file__).resolve().parents[1]
                              / "porting/source-candidates-build008.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["target_model"], "GQ50Q60TGUXZG")
        self.assertEqual(catalog["status"], "BLOCKED")
        self.assertEqual(catalog["downloaded_original_files"], 0)
        candidates = {item["id"]: item for item in catalog["candidates"]}
        self.assertTrue(candidates["samsung_q60t_gpl_kernel"]["official_listing_verified_in_browser"])
        self.assertEqual(candidates["samsung_q60t_gpl_kernel"]["artifact_filename"],
                         "20_DTV_NikeL.zip")
        self.assertFalse(candidates["samsung_q60t_gpl_kernel"]["verified_download"])
        self.assertEqual(candidates["arm_bifrost_r11p0_kernel"]["artifact_filename"],
                         "BX301A01B-SW-99002-r11p0-01rel0.tgz")
        self.assertTrue(candidates["linux_4_1_10_kants_comparison_only"]["known_wrong_board"])
        self.assertFalse(any(item["verified_for_firmware_2743_0"]
                             for item in catalog["candidates"]))

    def test_kernel_source_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "arch/arm").mkdir(parents=True)
            (root / "arch/arm/Makefile").write_text("# synthetic")
            (root / "Makefile").write_text(
                "VERSION = 5\nPATCHLEVEL = 10\nSUBLEVEL = 0\n")
            self.assertEqual(q60t_kernel_build.source_version(root), "5.10.0")
            report = q60t_kernel_build.make_plan(root, None, None, None)
            self.assertFalse(report["checks"]["source_version_matches_reference"])

    def test_kernel_banner_extracts_toolchain(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "uImage"
            banner = (b"Linux version 4.1.10 (synthetic) (gcc version 6.2.1 "
                      b"20161213 (Tizen/Linaro GCC 6.2.1) ) #1 SMP "
                      b"Thu Jul 2 08:47:01 UTC 2026\x00")
            path.write_bytes(synthetic_uimage(banner))
            report = q60t_hardware.inspect_kernel(path)
            self.assertEqual(report["gcc_version_from_banner"], "6.2.1")
            self.assertTrue(report["tizen_linaro_toolchain_string_present"])
            self.assertEqual(report["build_timestamp_from_banner"],
                             "Thu Jul 2 08:47:01 UTC 2026")


class GraphicsTests(unittest.TestCase):
    def test_elf_abi_detection_32_and_64_bit(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "fake.so"
            payload = bytearray(64)
            payload[:6] = b"\x7fELF\x01\x01"
            struct.pack_into("<HH", payload, 16, 3, 40)
            p.write_bytes(payload)
            self.assertEqual(q60t_graphics.inspect_elf(p)["machine"], "ARM32")
            p.write_bytes(payload + b"\x00vermagic=4.1.10 SMP preempt ARMv7\x00")
            self.assertEqual(q60t_graphics.inspect_elf(p)["module_vermagic_string"],
                             "4.1.10 SMP preempt ARMv7")
            payload[4] = 2
            struct.pack_into("<H", payload, 18, 183)
            p.write_bytes(payload)
            self.assertEqual(q60t_graphics.inspect_elf(p)["machine"], "AArch64")

    def test_reject_bad_or_truncated_elf_section_table(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "bad.so"
            payload = bytearray(64)
            payload[:6] = b"\x7fELF\x01\x01"
            struct.pack_into("<I", payload, 32, 2000)
            struct.pack_into("<HH", payload, 46, 40, 4)
            p.write_bytes(payload)
            with self.assertRaises(ValueError):
                q60t_graphics.inspect_elf(p)

    def test_graphics_report_does_not_claim_compatibility(self):
        root = Path(__file__).resolve().parents[1]
        import json
        hardware = json.loads((root / "reports/hardware_2743.0_build004_final.json").read_text())
        kernel = json.loads((root / "reports/kernel_build005.json").read_text())
        report = q60t_graphics.graphics_preflight(hardware, kernel)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertFalse(report["checks"]["android_composer3_hal_implemented"])
        self.assertFalse(report["flash_authorized"])
        with self.assertRaises(ValueError):
            q60t_graphics.graphics_preflight({**hardware, "dtb_bundle_sha256": "bad"}, kernel)


class GpuStrategyTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.hardware = json.loads((root / "reports/hardware_2743.0_build004_final.json").read_text())
        self.kernel = json.loads((root / "reports/kernel_build005.json").read_text())

    def test_reference_vendor_and_panfrost_paths_are_both_blocked(self):
        result = q60t_gpu_strategy.strategy_report(self.hardware, self.kernel)
        self.assertTrue(result["paths"]["legacy_vendor_kbase"]["checks"][
            "original_firmware_gpu_node_identified_in_both_profiles"])
        self.assertFalse(result["paths"]["legacy_vendor_kbase"]["ready"])
        self.assertFalse(result["paths"]["upstream_panfrost_drm"]["ready"])
        self.assertFalse(result["flash_authorized"])

    def test_source_path_detection_does_not_claim_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "drivers/gpu/arm/bifrost").mkdir(parents=True)
            (root / "drivers/gpu/drm/panfrost").mkdir(parents=True)
            result = q60t_gpu_strategy.strategy_report(self.hardware, self.kernel, root)
            self.assertTrue(result["paths"]["legacy_vendor_kbase"]["checks"][
                "candidate_kbase_source_tree_seen"])
            self.assertTrue(result["paths"]["upstream_panfrost_drm"]["checks"][
                "kernel_source_contains_panfrost_drm"])
            self.assertFalse(result["source_scan"]["drivers_built"])
            self.assertFalse(result["android_bootable"])

    def test_wrong_firmware_report_rejected(self):
        with self.assertRaises(ValueError):
            q60t_gpu_strategy.strategy_report(self.hardware, {"uimage_sha256": "wrong"})


class SourceCandidateTests(unittest.TestCase):
    def test_empty_candidate_never_claims_verified_sources(self):
        candidate = q60t_source_provenance.candidate_report(None, None)
        self.assertEqual(candidate["status"], "BLOCKED")
        self.assertFalse(candidate["checks"]["official_samsung_source_identity_independently_verified"])

    def test_zip_good_candidate_still_requires_manual_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "candidate.zip"
            with zipfile.ZipFile(archive, "w") as out:
                out.writestr("linux-4.1.10/Makefile", "VERSION = 4\n")
                out.writestr("linux-4.1.10/arch/arm/Makefile", "# fake\n")
            source = root / "linux-4.1.10"
            (source / "arch/arm").mkdir(parents=True)
            (source / "Makefile").write_text("VERSION = 4\nPATCHLEVEL = 1\nSUBLEVEL = 10\n")
            (source / "arch/arm/Makefile").write_text("# synthetic")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            result = q60t_source_provenance.candidate_report(archive, source, digest)
            self.assertEqual(result["status"], "MANUAL_REVIEW_REQUIRED")
            self.assertTrue(result["checks"]["archive_sha256_matches_supplied_hash"])
            self.assertFalse(result["checks"]["source_tree_matches_archive_contents"])
            self.assertFalse(result["kernel_build_reproduced"])

    def test_hash_mismatch_stays_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "a.zip"
            with zipfile.ZipFile(archive, "w") as out:
                out.writestr("Makefile", "synthetic")
            result = q60t_source_provenance.candidate_report(archive, None, "0" * 64)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(result["checks"]["archive_sha256_matches_supplied_hash"])

    def test_unsafe_paths_and_duplicate_entries_are_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as out:
                out.writestr("../escape", "bad")
                out.writestr("good/a", "first")
                out.writestr("good/a", "second")
            report = q60t_source_provenance.archive_inventory(archive)
            self.assertFalse(report["archive_paths_safe_for_separate_review"])
            self.assertEqual(len(report["member_issues"]), 2)

    def test_windows_and_double_slash_paths_are_rejected(self):
        for value in ("C:/boot", "/abs", "a\\b", "a//b", "a/../b", "a/./b", "a:b", ""):
            self.assertFalse(q60t_source_provenance.safe_member(value), value)
        self.assertTrue(q60t_source_provenance.safe_member("linux-4.1.10/drivers/mali.c"))

    def test_tar_links_are_flagged_without_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "candidate.tar.gz"
            with tarfile.open(archive, "w:gz") as out:
                target = tarfile.TarInfo("source/Makefile")
                payload = b"VERSION = 4\n"
                target.size = len(payload)
                out.addfile(target, io.BytesIO(payload))
                link = tarfile.TarInfo("source/danger")
                link.type = tarfile.SYMTYPE
                link.linkname = "../../outside"
                out.addfile(link)
            report = q60t_source_provenance.archive_inventory(archive)
            self.assertFalse(report["archive_paths_safe_for_separate_review"])
            self.assertFalse(report["archive_extracted"])

    def test_candidate_report_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "existing.json"
            out.write_text("KEEP", encoding="utf-8")
            self.assertEqual(q60t_source_provenance.main(["--report", str(out)]), 2)
            self.assertEqual(out.read_text(), "KEEP")


class IntegratedBuild007Tests(unittest.TestCase):
    def test_merged_preflight_is_still_non_bootable(self):
        root = Path(__file__).resolve().parents[1]
        result = q60t_build007_preflight.assess(root)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(result["checks"]["official_model_and_firmware_reference_verified"])
        self.assertTrue(result["checks"]["device_board_explicitly_fails_closed"])
        self.assertIn("verified_kernel_source_and_config", result["port_blockers"])
        self.assertFalse(result["android_build_attempted"])
        self.assertFalse(result["boot_or_flash_attempted"])
        self.assertFalse(result["flash_authorized"])

    def test_build_guard_cannot_be_silently_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            device = root / "porting/device/samsung/nikel"
            device.mkdir(parents=True)
            (device / "BoardConfig.mk").write_text("TARGET_BOARD_PLATFORM := nikel\n")
            (device / "lineage_nikel.mk").write_text(
                "PRODUCT_IS_ATV := true\n"
                "$(call inherit-product, device/samsung/nikel/device.mk)\n")
            with self.assertRaisesRegex(ValueError, "build guard removed"):
                q60t_build007_preflight.assess(root)

    def test_build007_report_cannot_overwrite(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "preexisting.json"
            out.write_text("KEEP")
            self.assertEqual(q60t_build007_preflight.main([
                "--project-root", str(root), "--report", str(out)]), 2)
            self.assertEqual(out.read_text(), "KEEP")


class BootSafetyTests(unittest.TestCase):
    def test_reference_firmware_components_are_only_static_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p / "uImage").write_bytes(synthetic_uimage())
            (p / "sign.bin").write_bytes(b"synthetic signature-looking bytes")
            inventory = q60t_boot_safety.safe_component_inventory(p)
            self.assertEqual(inventory["status"], "REFERENCE_MISMATCH")
            self.assertTrue(inventory["uimage_header_crc_valid"])
            self.assertFalse(inventory["signature_cryptographically_verified"])

    def test_manual_evidence_never_authorizes_flash(self):
        empty = q60t_boot_safety.boot_safety_report(
            {}, q60t_boot_safety.safe_component_inventory(None))
        self.assertEqual(empty["blocker_count"], 8)
        self.assertFalse(empty["rollback_proven"])
        review = q60t_boot_safety.boot_safety_report(
            {k: True for k in q60t_boot_safety.BOOT_GATES},
            q60t_boot_safety.safe_component_inventory(None))
        self.assertEqual(review["status"], "MANUAL_REVIEW_REQUIRED")
        self.assertFalse(review["boot_attempted"])
        self.assertFalse(review["flash_authorized"])


class ImageTests(unittest.TestCase):
    def test_valid_uimage_and_corrupted_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "uImage"
            data = synthetic_uimage()
            path.write_bytes(data)
            report = q60t_lab.inspect_uimage(path)
            self.assertTrue(report["valid"])
            self.assertEqual(report["arch_id"], 2)
            path.write_bytes(data[:-1] + b"!")
            report = q60t_lab.inspect_uimage(path)
            self.assertFalse(report["valid"])
            self.assertFalse(report["payload_crc_valid"])

    def test_valid_dtb_header_and_bad_magic(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "dtb.bin"
            data = synthetic_dtb()
            path.write_bytes(data)
            report = q60t_lab.inspect_dtb(path)
            self.assertTrue(report["valid"])
            self.assertEqual(report["hardware"]["model"], "Synthetic Q60T")
            self.assertEqual(report["hardware"]["compatible"], ["samsung,q60t-test"])
            path.write_bytes(b"ABCD" + data[4:])
            self.assertFalse(q60t_lab.inspect_dtb(path)["valid"])

    def test_inventory_and_rea_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "uImage").write_bytes(synthetic_uimage())
            (folder / "dtb.bin").write_bytes(synthetic_dtb())
            (folder / "ignore_me").write_bytes(b"irrelevant")
            report = q60t_lab.inventory(folder)
            self.assertEqual(len(report["files"]), 2)
            plan = q60t_lab.rea_plan(folder)
            self.assertEqual(len(plan["steps"]), 2)
            self.assertTrue(any("rea " in step["command_linux"]
                                for step in plan["steps"] if step["command_linux"]))
            self.assertTrue(any(step["component"] == "uImage" and
                                step["command_linux"] is None for step in plan["steps"]))

    def test_multiple_dtb_candidates(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "dtb.bin"
            first = synthetic_dtb()
            path.write_bytes(first + b"\x00" * 32 + first)
            report = q60t_lab.scan_embedded_dtbs(path)
            self.assertEqual(len(report), 2)
            self.assertEqual(report[1]["offset_bytes"], len(first) + 32)

    def test_hardware_report_sanitizes_bootargs_and_compares_trees(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "dtb.bin"
            first = synthetic_dtb_tree("cpu@0")
            second = synthetic_dtb_tree("cpu@1", "Variant", "nikel-1.5G")
            path.write_bytes(first + b"\x00" * 32 + second)
            report = q60t_hardware.hardware_report(path)
            self.assertEqual(report["device_trees_found"], 2)
            tree1 = report["trees"][0]["summary"]
            self.assertEqual(tree1["node_count"], 4)
            self.assertEqual(tree1["memory_profile_label"], "2 GiB (firmware profile label)")
            self.assertEqual(report["trees"][1]["summary"]["memory_profile_label"],
                             "1.5 GiB (firmware profile label)")
            self.assertEqual(len(tree1["hardware_categories"]["cpu"]), 1)
            self.assertEqual(tree1["bootargs_safe_subset"],
                             ["root=/dev/mmcblk0p18", "ro"])
            self.assertEqual(report["comparison_first_two"]["only_first_node_count"], 1)
            self.assertEqual(report["comparison_first_two"]["only_second_node_count"], 1)
            self.assertNotIn("SECRET", str(report))

    def test_memory_profiles_from_firmware_bootargs(self):
        t = q60t_hardware.parse_fdt(synthetic_dtb_tree())
        self.assertEqual(q60t_hardware.summarize_tree(t)["memory_profile_label"],
                         "2 GiB (firmware profile label)")

    def test_memory_reg_addresses_and_sizes(self):
        nodes = {
            "/": {"#address-cells": struct.pack(">I", 2),
                  "#size-cells": struct.pack(">I", 2)},
            "/memory": {"reg": struct.pack(">8I", 0, 0x40000000,
                                                  0, 0x10000000,
                                                  0, 0xA0000000,
                                                  0, 0x08000000)},
        }
        memory = q60t_hardware.memory_reg_map(nodes)
        self.assertEqual(memory["ranges"][0]["base_hex"], "0x40000000")
        self.assertEqual(memory["ranges"][0]["size_mib"], 256)
        self.assertEqual(memory["sum_advertised_mib"], 384)
        self.assertIn("Not measured physical RAM", memory["warning"])

    def test_memory_reg_bad_cell_layout_is_not_trusted(self):
        nodes = {"/": {"#address-cells": struct.pack(">I", 3)},
                 "/memory": {"reg": b"\x00" * 16}}
        self.assertIsNone(q60t_hardware.memory_reg_map(nodes))
        nodes = {"/": {}, "/memory": {"reg": b"\x00" * 7}}
        self.assertIsNone(q60t_hardware.memory_reg_map(nodes))

    def test_device_tree_status_distinguishes_disabled_interfaces(self):
        status = q60t_hardware._safe_dt_status
        self.assertEqual(status({"status": b"disabled\x00"}), "disabled")
        self.assertEqual(status({"status": b"okay\x00"}), "okay")
        self.assertEqual(status({}), "unspecified")
        self.assertEqual(status({"status": b"random\x00"}), "unknown")

    def test_invalid_or_truncated_fdt_rejected(self):
        with self.assertRaises(ValueError):
            q60t_hardware.parse_fdt(b"BAD FDT")
        with self.assertRaises(ValueError):
            q60t_hardware.parse_fdt(synthetic_dtb_tree()[:-30])

    def test_kernel_report_without_embedded_config(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "uImage"
            path.write_bytes(synthetic_uimage(b"Linux version 4.1.10 (synthetic)"))
            result = q60t_hardware.inspect_kernel(path)
            self.assertEqual(result["version_from_banner"], "4.1.10")
            self.assertFalse(result["embedded_ikconfig_marker_present"])
            self.assertIsNone(result["embedded_kconfig"])

    def test_rootfs_string_survey_never_assumes_existence(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "platform.img"
            p.write_bytes(b"VDFS2007\x00config /lib/modules/mali.ko\x00"
                          b"/usr/lib/driver/libmali.so\x00/dev/mali0\x00"
                          b"/lib/modules/../../bad.ko\x00")
            data = q60t_rootfs.scan_rootfs_strings(p)
            self.assertEqual(data["format_marker"], "VDFS2007")
            self.assertIn("/lib/modules/mali.ko", data["path_references"])
            self.assertNotIn("/lib/modules/../../bad.ko", data["path_references"])
            self.assertIn("/dev/mali0", data["device_node_references"])


if __name__ == "__main__":
    unittest.main()
