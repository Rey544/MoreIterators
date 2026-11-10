import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
try:
    from .csharp_sources import with_dialogue_line
except ImportError:
    from csharp_sources import with_dialogue_line


class RuntimeOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        game_assembly = Path(os.environ.get('RAIN_WORLD_GAME', '')) / 'RainWorld_Data/Managed/Assembly-CSharp.dll'
        if not compiler.exists() or not game_assembly.exists():
            raise unittest.SkipTest('Windows compiler and installed Rain World JSON parser are required')
        cls.temp = tempfile.TemporaryDirectory(prefix='mi-ownership-test-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        shutil.copy2(game_assembly, cls.work / game_assembly.name)
        sources = [str(root / 'src/AudioTrackDesign.cs')]
        sources.extend([str(root / 'src/ContentAssets.cs'), str(root / 'tests/content_assets_host.cs'), str(root / 'tests/ui_text_identity.cs')])
        sources.append(str(root / 'src/CreatorDialogueModels.cs'))
        
        for filename, boundary in [('CreatorReadingPresentation.cs', '// Presentation owns'),
                                   ('PlaybackMode.cs', 'public sealed class CreatorSpeech'),
                                   ('CreatorPearls.cs', 'public static class CreatorPearlRuntime'),
                                   ('CreatorBroadcasts.cs', 'public static class CreatorBroadcastRuntime')]:
            text = (root / 'src' / filename).read_text('utf-8').split(boundary, 1)[0] + '\n}\n'
            target = cls.work / filename
            target.write_text(text, 'utf-8')
            sources.append(str(target))
        harness=cls.work/'check.cs';harness.write_text(with_dialogue_line(root,(root/'tests/runtime_ownership_check.cs').read_text('utf-8')),'utf-8')
        for mode in ('core', 'playback'):
            runtime = root / ('src/RuntimePaths.cs' if mode == 'core' else 'templates/standalone/RuntimePaths.cs')
            target = cls.work / (mode + '-paths.cs')
            target.write_text(runtime.read_text('utf-8').replace('__MOD_ID__', 'standalone'), 'utf-8')
            command = [str(compiler), '/nologo', '/out:' + str(cls.work / (mode + '.exe')),
                       '/r:' + str(game_assembly), str(target),
                       str(harness), *sources]
            if mode == 'playback':
                command.append('/define:PLAYBACK')
            result = subprocess.run(command, capture_output=True, text=True, errors='replace', timeout=30)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)

    def run_scenario(self, mode, scenario):
        folder = self.work / (mode + '-' + scenario)
        folder.mkdir()
        result = subprocess.run([str(self.work / (mode + '.exe')), scenario, str(folder)],
                                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('ownership assertions passed: ' + scenario, result.stdout)

    def test_core_catalogues_exclude_independent_and_keep_registered_content(self):
        self.run_scenario('core', 'catalogues')

    def test_local_registry_cannot_reclaim_an_independent_package(self):
        self.run_scenario('core', 'local')

    def test_inactive_applied_local_content_is_menu_only_until_enabled(self):
        self.run_scenario('core', 'pending')

    def test_only_explicit_boolean_ownership_excludes_ordinary_content(self):
        self.run_scenario('core', 'metadata')

    def test_playback_keeps_its_own_catalogues_with_core_filter_present(self):
        self.run_scenario('playback', 'catalogues')


if __name__ == '__main__':
    unittest.main()
