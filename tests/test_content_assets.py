import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class ContentAssetsRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.is_file():
            raise unittest.SkipTest('Windows .NET Framework compiler is required')
        cls.temp = tempfile.TemporaryDirectory(prefix='mi-content-assets-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        for mode in ('core', 'playback'):
            command = [str(compiler), '/nologo', '/utf8output',
                       '/out:' + str(cls.work / (mode + '.exe')),
                       str(root / 'src/ContentAssets.cs'), str(root / 'tests/content_assets_check.cs'),
                       str(root / 'tests/ui_text_identity.cs')]
            if mode == 'playback':
                command.append('/define:PLAYBACK')
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)

    def check(self, scenario, mode='core'):
        folder = self.work / (mode + '-' + scenario)
        folder.mkdir()
        result = subprocess.run([str(self.work / (mode + '.exe')), scenario, str(folder)],
                                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('content asset assertions passed: ' + scenario, result.stdout)

    def test_same_filename_from_two_content_packages_is_not_dropped(self):
        self.check('same-name')

    def test_targeted_newest_and_root_priorities_follow_native_order(self):
        self.check('versions')

    def test_unique_merged_owner_is_used_and_ambiguous_merged_owner_is_not_guessed(self):
        self.check('merged')

    def test_disabled_reenabled_and_moved_packages_are_resolved_from_current_state(self):
        self.check('lifecycle')

    def test_asset_paths_remain_relative_and_follow_native_case_conventions(self):
        self.check('paths')

    def test_native_base_resources_are_still_discoverable(self):
        self.check('base')

    def test_core_does_not_manage_independent_runtime_content(self):
        self.check('managed')

    def test_playback_only_manages_its_own_package(self):
        self.check('managed', 'playback')


if __name__ == '__main__':
    unittest.main()
