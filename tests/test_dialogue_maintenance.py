import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

try:
    from .csharp_sources import before_code, extract_class, replace_code
except ImportError:
    from csharp_sources import before_code, extract_class, replace_code

ROOT = Path(__file__).resolve().parents[1]


class DialogueMaintenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        assembly = Path(os.environ.get('RAIN_WORLD_GAME', '')) / 'RainWorld_Data/Managed/Assembly-CSharp.dll'
        if not compiler.is_file() or not assembly.is_file():
            raise unittest.SkipTest('Windows compiler and installed Rain World JSON parser required')
        cls.temporary = tempfile.TemporaryDirectory(prefix='mi-dialogue-maintenance-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        shutil.copy2(assembly, cls.work / assembly.name)
        prefix = 'using Json = JsonProbe;\n'
        sources = [str(ROOT / 'src/AudioTrackDesign.cs')]
        override = Path(os.environ.get('MI_DIALOGUE_REVIEW_SOURCE', str(ROOT / 'src')))
        for name in ('CreatorDialogueModels.cs', 'CreatorDialogue.cs', 'CreatorPearlRules.cs',
                     'CreatorPearlReader.cs', 'CreatorPearlVisits.cs', 'CreatorStomachPearl.cs',
                     'CreatorPearlOffers.cs', 'CreatorDialogueActions.cs', 'CreatorAffinity.cs',
                     'CreatorHeldItems.cs', 'PlaybackMode.cs'):
            source = override / name if name in ('CreatorDialogue.cs', 'CreatorAffinity.cs') else ROOT / 'src' / name
            target = cls.work / name
            target.write_text(prefix + source.read_text('utf-8-sig'), 'utf-8')
            sources.append(str(target))
        models = cls.work / 'PearlModels.cs'
        models.write_text(prefix + before_code((ROOT / 'src/CreatorPearls.cs').read_text('utf-8-sig'),
                                               'public static class CreatorPearlCatalog') + '\n}\n', 'utf-8')
        sources.append(str(models))
        host = (ROOT / 'tests/social_runtime_check.cs').read_text('utf-8-sig')
        host = replace_code(host, extract_class(host, 'SocialRuntimeCheck'), '', 'unused social checks')
        host = replace_code(host, extract_class(host, 'Debug'),
                            'public static class Debug {public static int warnings;public static void Log(object value){}public static void LogWarning(object value){warnings++;}}', 'warning counter')
        host = replace_code(host, 'public static string LanguageKey {get{return "English";}}',
                            'public static string CurrentLanguage="English";public static string LanguageKey {get{return CurrentLanguage;}}', 'mutable fixture language')
        host = replace_code(host, 'public bool shortcutThrows;', 'public bool shortcutThrows;public int shortcutLookups;', 'shortcut counter field')
        host = replace_code(host, 'if(shortcutThrows)throw new InvalidOperationException("missing shortcut");',
                            'shortcutLookups++;if(shortcutThrows)throw new InvalidOperationException("missing shortcut");', 'shortcut counter')
        host = replace_code(host, 'public static int ExitNode(string room){return 0;}',
                            'public static int node;public static int ExitNode(string room){return node;}', 'mutable exit node')
        host_file = cls.work / 'NativeHost.cs'
        host_file.write_text(host, 'utf-8')
        sources.append(str(host_file))
        cls.executables = {}
        for mode in ('core', 'playback'):
            exe = cls.work / (mode + '.exe')
            define = ['/define:PLAYBACK'] if mode == 'playback' else []
            result = subprocess.run([str(compiler), '/nologo', '/utf8output', '/langversion:5',
                                     '/out:' + str(exe), '/main:DialogueMaintenanceCheck',
                                     *define, '/r:rwjson=' + str(assembly), *sources,
                                     str(ROOT / 'tests/dialogue_maintenance_check.cs')],
                                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            cls.executables[mode] = exe

    def scenario(self, name):
        for mode, executable in self.executables.items():
            with self.subTest(mode=mode):
                result = subprocess.run([str(executable), name], cwd=self.work, capture_output=True,
                                        text=True, encoding='utf-8', errors='replace', timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('PASS ' + name, result.stdout)
                print(mode + ': ' + result.stdout.strip())

    def test_profile_reuses_single_parse_and_invalidates_authored_and_language_changes(self):
        self.scenario('profile')

    def test_faults_report_once_and_pearl_rules_survive_an_independent_dialogue_error(self):
        self.scenario('profile-errors')

    def test_sessions_keep_live_game_state_and_release_abandoned_games(self):
        self.scenario('sessions')

    def test_disabled_affinity_hit_does_not_create_or_change_save_data(self):
        self.scenario('affinity')

    def test_exit_guards_bound_native_fault_retries_and_recover_without_losing_departure(self):
        self.scenario('exits')


if __name__ == '__main__':
    unittest.main()
