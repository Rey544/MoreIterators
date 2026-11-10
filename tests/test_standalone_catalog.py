import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class StandaloneCatalogueRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        game_assembly = Path(os.environ.get('RAIN_WORLD_GAME', '')) / 'RainWorld_Data/Managed/Assembly-CSharp.dll'
        if not compiler.exists() or not game_assembly.exists():
            raise unittest.SkipTest('Windows compiler and installed Rain World JSON parser are required')
        cls.temp = tempfile.TemporaryDirectory(prefix='mi-catalogue-test-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        cls.exe = cls.work / 'catalogue-check.exe'
        source = (root / 'templates/standalone/RuntimePaths.cs').read_text('utf-8')
        (cls.work / 'RuntimePaths.cs').write_text(source.replace('__MOD_ID__', 'test.selected-content'), 'utf-8')
        shutil.copy2(game_assembly, cls.work / game_assembly.name)
        result = subprocess.run([
            str(compiler), '/nologo', '/utf8output', '/define:PLAYBACK', '/out:' + str(cls.exe), '/r:' + str(game_assembly),
            str(cls.work / 'RuntimePaths.cs'), str(root / 'src/ContentAssets.cs'),
            str(root / 'tests/content_assets_host.cs'), str(root / 'tests/standalone_catalog_check.cs'),
            str(root / 'tests/ui_text_identity.cs'),
        ], capture_output=True, text=True, encoding='utf-8', timeout=30)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def run_scenario(self, name):
        folder = self.work / name
        folder.mkdir()
        result = subprocess.run([str(self.exe), name, str(folder)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('catalogue assertions passed: ' + name, result.stdout)

    def test_early_hook_recovers_when_mod_list_becomes_ready(self):
        self.run_scenario('early')

    def test_missing_registry_does_not_poison_cache(self):
        self.run_scenario('missing')

    def test_malformed_or_partial_registry_is_retried_atomically(self):
        self.run_scenario('malformed')

    def test_disabled_and_other_packages_never_supply_cached_projects(self):
        self.run_scenario('isolation')

    def test_version_paths_and_live_registry_changes_keep_owner_isolation(self):
        self.run_scenario('versions')

    def test_registry_design_paths_use_owner_versions_and_preserve_legacy_layout(self):
        self.run_scenario('designs')


if __name__ == '__main__':
    unittest.main()
