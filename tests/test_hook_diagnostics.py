
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class HookDiagnosticsRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.is_file():
            raise unittest.SkipTest('The existing Windows .NET Framework compiler is required')
        cls.temp = tempfile.TemporaryDirectory(prefix='mi-hook-diagnostics-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        cls.exe = cls.work / 'diagnostics-check.exe'
        result = subprocess.run([
            str(compiler), '/nologo', '/debug', '/out:' + str(cls.exe),
            str(root / 'src/MiDiagnostics.cs'), str(root / 'tests/hook_diagnostics_check.cs'),
        ], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def run_scenario(self, name):
        
        result = subprocess.run([str(self.exe), name], cwd=self.work, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('diagnostic assertions passed: ' + name, result.stdout)

    def test_failed_precondition_is_logged_and_shown(self):
        self.run_scenario('require')

    def test_hook_invokes_original_once_and_preserves_exception(self):
        self.run_scenario('hook')

    def test_repeated_errors_retain_counts_without_flooding(self):
        self.run_scenario('repeated')

    def test_external_error_and_fatal_do_not_become_mi_notifications(self):
        self.run_scenario('external')

    def test_log_observer_is_safe_for_missing_and_broken_arguments(self):
        self.run_scenario('listener-safety')

    def test_notification_preview_is_bounded_and_full_detail_stays_in_log(self):
        self.run_scenario('summary')

    def test_unity_errors_respect_existing_logging_policy_and_mi_errors_still_persist(self):
        self.run_scenario('unity-disk')

    def test_notification_wraps_measured_cjk_words_paths_and_unicode_without_overflow(self):
        self.run_scenario('wrap')

    def test_startup_error_logs_immediately_and_waits_for_stable_font_screen_once(self):
        self.run_scenario('startup-queue')

    def test_rethrows_across_mi_hooks_form_one_cause_without_external_capture(self):
        self.run_scenario('rethrow-identity')

    def test_distinct_throwing_signatures_and_unlocated_sources_are_not_merged(self):
        self.run_scenario('distinct-identity')

    def test_nested_exception_identifies_inner_throwing_function(self):
        self.run_scenario('nested-identity')

    def test_behavior_guard_warning_is_not_a_thrown_exception_or_death_claim(self):
        self.run_scenario('behavior')

    def test_batch_index_keeps_other_independent_errors_searchable_on_small_screen(self):
        self.run_scenario('batch-locator')

    def test_capture_cache_is_bounded_without_dropping_new_full_stack_variants(self):
        self.run_scenario('capture-variants')

    def test_levels_gate_detail_and_hits_without_filtering_errors_or_capturing_other_mods(self):
        self.run_scenario('levels')


if __name__ == '__main__':
    unittest.main()
