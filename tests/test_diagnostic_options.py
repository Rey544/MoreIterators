from pathlib import Path
import json,os,subprocess,tempfile,unittest

ROOT=Path(__file__).resolve().parents[1]

class DiagnosticOptionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.exists():raise unittest.SkipTest('Windows compiler required')
        cls.temp=tempfile.TemporaryDirectory(prefix='mi-diagnostic-options-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.exe=Path(cls.temp.name)/'options.exe'
        result=subprocess.run([str(compiler),'/nologo','/out:'+str(cls.exe),str(ROOT/'src/MiOptions.cs'),str(ROOT/'tests/diagnostic_options_check.cs')],capture_output=True,text=True,timeout=30)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)

    def check_saved_value(self,value):
        result=subprocess.run([str(self.exe),value],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('20 options assertions passed',result.stdout)

    def test_legacy_infor_loads_as_info_and_saves_canonical_value(self):
        self.check_saved_value('infor')

    def test_info_registration_saved_value_and_change_event(self):
        self.check_saved_value('info')

    def test_debug_registration_saved_value_and_change_event(self):
        self.check_saved_value('debug')

    def test_trace_registration_saved_value_and_change_event(self):
        self.check_saved_value('trace')

    def test_standalone_excludes_core_settings_ui(self):
        sources=json.loads((ROOT/'templates/standalone/sources.json').read_text('utf-8'))
        self.assertNotIn('src/MiOptions.cs',sources['sources'])
        self.assertIn('src/MiOptions.cs',sources['excluded'])
        plugin=(ROOT/'src/MoreIteratorsPlugin.cs').read_text('utf-8')
        self.assertIn('#if !PLAYBACK\n            MiOptions.Install(removeHooks);',plugin)

if __name__=='__main__':unittest.main()
