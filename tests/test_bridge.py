"""Contract tests for the public adapter, not tests of OCR quality."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/notebooklm-ppt/scripts/convert.py"


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SCRIPT.exists():
            spec = importlib.util.spec_from_file_location("ppt_bridge", SCRIPT)
            cls.bridge = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.bridge)
        else:
            cls.bridge = None

    def setUp(self):
        self.assertIsNotNone(self.bridge, "Skill adapter has not been implemented")

    def test_local_mode_does_not_inherit_online_or_engine_overrides(self):
        env = self.bridge.worker_environment({"DEEPSEEK_API_KEY": "private-value", "DEEPSEEK_BASE_URL": "https://elsewhere.example", "NOTEBOOKLM_PPT_PAGE_WORKERS": "32", "PATH": "/bin"}, Path("/app/Contents/Resources"), online=False)
        self.assertEqual(env["DEEPSEEK_API_KEY"], "")
        self.assertNotIn("DEEPSEEK_BASE_URL", env)
        self.assertNotIn("NOTEBOOKLM_PPT_PAGE_WORKERS", env)
        self.assertEqual(env["PATH"], "/bin")
        self.assertEqual(env["NOTEBOOKLM_PPT_VISION_HELPER"], "/app/Contents/Resources/vision-verify")

    def test_online_requires_key_and_https(self):
        for env in ({}, {"DEEPSEEK_API_KEY": "test", "DEEPSEEK_BASE_URL": "http://untrusted.example"}):
            with self.assertRaises(ValueError):
                self.bridge.worker_environment(env, Path("/app"), online=True)

    def test_explicit_online_preserves_only_requested_provider_configuration(self):
        env = self.bridge.worker_environment({"DEEPSEEK_API_KEY": "test", "DEEPSEEK_MODEL": "chosen-model"}, Path("/app"), online=True)
        self.assertEqual(env["DEEPSEEK_API_KEY"], "test")
        self.assertEqual(env["DEEPSEEK_MODEL"], "chosen-model")
        self.assertEqual(env["NOTEBOOKLM_PPT_DEEPSEEK_ON_FAILURE"], "stop")

    def test_page_selection_rejects_invalid_values_instead_of_converting_all(self):
        for value in ("0", "-1", "1,,3", "3-1", "2-x", "1;whoami", "1-1000000000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.bridge.validate_pages(value)
        self.assertEqual(self.bridge.validate_pages("1，3-5"), "1,3-5")

    def test_top_level_selftest_failure_is_not_hidden_by_successful_subcheck(self):
        with self.assertRaises(ValueError):
            self.bridge.require_self_test(0, '{"type":"self-test","ok":false,"checks":[{"ok":true}]}')

    def test_nonzero_selftest_exit_is_not_hidden_by_ok(self):
        with self.assertRaises(ValueError):
            self.bridge.require_self_test(3, '{"type":"self-test","ok":true}')

    def test_selftest_accepts_true_only_with_zero_exit(self):
        self.bridge.require_self_test(0, '{"type":"self-test","ok":true}')

    def _deck(self, folder):
        path = Path(folder) / "result.pptx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("ppt/presentation.xml", "<presentation/>")
        return path

    def test_review_verdict_overrides_passed_status(self):
        with tempfile.TemporaryDirectory() as folder:
            event = {"type": "completed", "status": "passed", "result_status": "需修正", "output_pptx": str(self._deck(folder)), "coverage": "47/65"}
            report, code = self.bridge.conversion_result(4, json.dumps(event))
            self.assertEqual(code, 4)
            self.assertEqual(report["result_status"], "需修正")
            self.assertEqual(report["coverage"], "47/65")

    def test_notice_is_preserved_not_promoted_to_clean_success(self):
        with tempfile.TemporaryDirectory() as folder:
            event = {"type": "completed", "status": "passed", "result_status": "可用但有提醒", "output_pptx": str(self._deck(folder))}
            report, code = self.bridge.conversion_result(0, json.dumps(event))
            self.assertEqual(code, 0)
            self.assertEqual(report["result_status"], "可用但有提醒")

    def test_partial_failure_keeps_run_directory_without_fake_output(self):
        event = {"type": "completed", "status": "incomplete", "result_status": "需修正", "output_pptx": "", "run_dir": "/tmp/run", "failed": 1}
        report, code = self.bridge.conversion_result(4, json.dumps(event))
        self.assertEqual(code, 4)
        self.assertEqual(report["run_dir"], "/tmp/run")
        self.assertFalse(report["output_pptx"])

    def test_success_requires_existing_pptx(self):
        for output in ("", "/missing/result.pptx"):
            with self.assertRaises(ValueError):
                self.bridge.conversion_result(0, json.dumps({"type": "completed", "status": "passed", "result_status": "通过", "output_pptx": output}))

    def test_false_pptx_is_not_delivered(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = Path(folder) / "file.pptx"
            fake.write_text("not a PowerPoint file")
            with self.assertRaises(ValueError):
                self.bridge.conversion_result(0, json.dumps({"type": "completed", "status": "passed", "result_status": "通过", "output_pptx": str(fake)}))

    def test_unexpected_failure_exit_is_not_a_success(self):
        with self.assertRaises(ValueError):
            self.bridge.conversion_result(2, '{"type":"completed","status":"passed","result_status":"通过"}')

    def test_missing_completed_event_is_not_success(self):
        with self.assertRaises(ValueError):
            self.bridge.conversion_result(0, '{"type":"progress","stage":"qa"}')

    def test_missing_app_is_actionable_and_no_download_occurs(self):
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(ValueError, "App|应用"):
            self.bridge.find_app(str(Path(folder) / "missing.app"))

    def test_wrong_platform_fails_before_engine_execution(self):
        with patch.object(self.bridge.platform, "system", return_value="Windows"), self.assertRaises(ValueError):
            self.bridge.require_platform()

    def test_run_worker_uses_literal_arguments_not_a_shell(self):
        result = self.bridge.run_worker([sys.executable, "-c", "import sys;print(sys.argv[1])", "a; echo secret"], dict(os.environ), 5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "a; echo secret")

    def test_run_worker_has_bounded_timeout(self):
        with self.assertRaisesRegex(ValueError, "超时"):
            self.bridge.run_worker([sys.executable, "-c", "import time;time.sleep(10)"], dict(os.environ), 0.05)

    def test_help_needs_no_app(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("doctor", result.stdout)
        self.assertIn("convert", result.stdout)


if __name__ == "__main__":
    unittest.main()
