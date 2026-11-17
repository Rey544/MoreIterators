
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
try:
    from .csharp_sources import before_code, extract_block
except ImportError:
    from csharp_sources import before_code, extract_block

ROOT = Path(__file__).resolve().parents[1]


class UnmarkedVoiceFlowTests(unittest.TestCase):
    def test_authored_and_legacy_core_and_playback_voice_without_consuming_story(self):
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        assembly = Path(os.environ.get('RAIN_WORLD_GAME', '')) / 'RainWorld_Data/Managed/Assembly-CSharp.dll'
        if not compiler.exists() or not assembly.exists():
            self.skipTest('Installed C# compiler and game JSON parser required')
        with tempfile.TemporaryDirectory(prefix='mi-unmarked-voice-') as folder:
            work = Path(folder)
            shutil.copy2(assembly, work / assembly.name)
            prefix = 'extern alias rwjson;\nusing Json = rwjson::Json;\n'
            sources = [str(ROOT / 'src/AudioTrackDesign.cs')]
            for name in ('CreatorDialogueModels.cs', 'CreatorDialogue.cs', 'CreatorPearlRules.cs',
                         'CreatorPearlReader.cs', 'CreatorPearlVisits.cs', 'CreatorStomachPearl.cs',
                         'CreatorPearlOffers.cs', 'CreatorDialogueActions.cs', 'CreatorAffinity.cs',
                         'CreatorHeldItems.cs', 'PlaybackMode.cs', 'CreatorVoice.cs', 'CreatorVoicePreview.cs',
                         'CreatorVoiceSequence.cs', 'CreatorVoiceEffects.cs', 'CreatorNativeVoiceGuard.cs', 'CreatorVoiceControl.cs'):
                target = work / name
                target.write_text(prefix + (ROOT / 'src' / name).read_text('utf-8-sig'), 'utf-8')
                sources.append(str(target))
            models = work / 'PearlModels.cs'
            models.write_text(prefix + before_code((ROOT / 'src/CreatorPearls.cs').read_text('utf-8-sig'), 'public static class CreatorPearlCatalog') + '\n}\n', 'utf-8')
            sources.append(str(models))
            
            
            host = (ROOT / 'tests/social_runtime_check.cs').read_text('utf-8-sig').split('class SocialRuntimeCheck', 1)[0]
            host = host.replace('public static class CreatorVoicePreview {public static bool WithoutMark(Oracle oracle){return false;}}', '')
            host = host.replace('public static class RuntimePaths {', 'public static class RuntimePaths {public static string DataDirectory;')
            host = host.replace('public class BodyChunk {', 'public class BodyChunk {public object owner;')
            host = host.replace('public class OracleBehavior {', 'public class OracleBehavior {public ChunkSoundEmitter voice;')
            host = host.replace('public class Oracle:PhysicalObject {', 'public class Oracle:PhysicalObject {public Oracle(){firstChunk.owner=this;}')
            host = host.replace('public class Camera {', 'public class Camera {public Room room;')
            host = host.replace('public class SoundID {', 'public partial class SoundID {')
            host = host.replace('public class Room {', 'public partial class Room {')
            host = host.replace('public void AddObject(object o){', 'public void AddObject(object o){var update=o as UpdatableAndDeletable;if(update!=null)update.room=this;')
            host = host.replace('public class IteratorDesign {', 'public class IteratorDesign {public CreatorVoiceDesign voice=new CreatorVoiceDesign();')
            host = host.replace('public static class CreatorProjections {', 'public static class CreatorProjections {public static int starts;')
            host = host.replace('public static float Prepare(Oracle o,object owner,string id){return 0;}', 'public static float Prepare(Oracle o,object owner,string id){starts++;return 0;}')
            plugin = (ROOT / 'src/MoreIteratorsPlugin.cs').read_text('utf-8-sig')
            mark = extract_block(plugin, 'public static bool HasCommunicationMark(')
            old = 'public static bool HasCommunicationMark(Oracle o){return MoreIteratorsPlugin.Active&&CreatorRuntime.Mark||o.room.game.IsStorySession&&o.room.game.GetStorySession.saveState.deathPersistentSaveData.theMark;}'
            self.assertIn(old, host)
            host = host.replace(old, mark)
            guard = (ROOT / 'src/CreatorMarkGuard.cs').read_text('utf-8-sig')
            mark_guard = extract_block(guard, 'public static bool HasMarkV1(')
            host += '\nnamespace MoreIterators { public static class CreatorMarkGuard {' + mark_guard + '} }\n'
            host_file = work / 'NativeHost.cs'
            host_file.write_text(host, 'utf-8')
            sources.append(str(host_file))
            for mode in ('core', 'playback'):
                exe = work / (mode + '.exe')
                define = ['/define:PLAYBACK'] if mode == 'playback' else []
                build = subprocess.run([str(compiler), '/nologo', '/utf8output', '/out:' + str(exe),
                                        *define, '/r:rwjson=' + str(assembly), *sources,
                                        str(ROOT / 'tests/unmarked_voice_flow_check.cs')],
                                       capture_output=True, text=True, encoding='utf-8', timeout=30)
                self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                run = subprocess.run([str(exe), str(work / (mode + '-data'))], capture_output=True, text=True, encoding='utf-8', timeout=30)
                self.assertEqual(run.returncode, 0, mode + ': ' + run.stdout + run.stderr)
                self.assertIn('unmarked voice flow assertions passed', run.stdout)
                print(mode + ': ' + run.stdout.strip())


if __name__ == '__main__':
    unittest.main()
