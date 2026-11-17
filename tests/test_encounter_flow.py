
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
try:
    from .csharp_sources import before_code, between_code
except ImportError:
    from csharp_sources import before_code, between_code


class EncounterFlowTests(unittest.TestCase):
    def test_first_completion_death_reentry_and_save_boundaries(self):
        root = Path(__file__).resolve().parents[1]
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        assembly = Path(os.environ.get('RAIN_WORLD_GAME', '')) / 'RainWorld_Data/Managed/Assembly-CSharp.dll'
        if not compiler.exists() or not assembly.exists():
            self.skipTest('Installed C# compiler and game JSON parser required')
        with tempfile.TemporaryDirectory(prefix='mi-social-runtime-') as folder:
            work = Path(folder)
            shutil.copy2(assembly, work / assembly.name)
            prefix = 'extern alias rwjson;\nusing Json = rwjson::Json;\n'
            sources = [str(root / 'src/AudioTrackDesign.cs')]
            for name in ('CreatorDialogueModels.cs', 'CreatorDialogue.cs', 'CreatorPearlRules.cs',
                         'CreatorPearlReader.cs', 'CreatorPearlVisits.cs', 'CreatorStomachPearl.cs', 'CreatorPearlOffers.cs', 'CreatorDialogueActions.cs', 'CreatorAffinity.cs',
                         'CreatorHeldItems.cs', 'PlaybackMode.cs'):
                target = work / name
                target.write_text(prefix + (root / 'src' / name).read_text('utf-8-sig'), 'utf-8')
                sources.append(str(target))
            target = work / 'PearlModels.cs'
            target.write_text(prefix + before_code((root / 'src/CreatorPearls.cs').read_text('utf-8-sig'), 'public static class CreatorPearlCatalog') + '\n}\n', 'utf-8')
            sources.append(str(target))
            runtime = (root / 'src/CreatorRuntime.cs').read_text('utf-8-sig')
            predicate = between_code(runtime, 'static bool HasEncounter(', 'public static void Hit(')
            plugin = (root / 'src/MoreIteratorsPlugin.cs').read_text('utf-8-sig')
            hook = between_code(plugin, 'var affinityHitHook=', 'var registeredHook28=')
            target = work / 'ActualHitHook.cs'
            target.write_text('using System;using System.Collections.Generic;namespace MoreIterators {public partial class CreatorEncounter {' + predicate + '}public static class ActualHitHook {static readonly List<Action> removeHooks=new List<Action>();public static void Install(){' + hook + '}}}', 'utf-8')
            sources.append(str(target))
            for mode in ('core', 'playback'):
                exe = work / (mode + '.exe')
                defines = ['/define:PLAYBACK'] if mode == 'playback' else []
                result = subprocess.run([str(compiler), '/nologo', '/utf8output', '/out:' + str(exe), '/main:EncounterFlowCheck', *defines,
                                         '/r:rwjson=' + str(assembly), *sources, str(root / 'tests/social_runtime_check.cs'), str(root / 'tests/encounter_flow_check.cs')],
                                        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                result = subprocess.run([str(exe)], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
                self.assertEqual(result.returncode, 0, mode + ': ' + result.stdout + result.stderr)
                self.assertIn('encounter flow assertions passed', result.stdout)
                print(mode + ': ' + result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
