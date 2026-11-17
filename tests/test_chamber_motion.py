import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'editor'))
import server
import standalone
import storage


class ChamberMotionTests(unittest.TestCase):
    def test_provenance_is_compiled_without_adding_or_changing_editable_design(self):
        project=server.default()
        project['projectId']='motion-test'
        for preset in ('','mi-chamber-pebbles','mi-chamber-moon','mi-chamber-broken','mi-chamber-irregular','mi-chamber-multi-screen','broken','mi-chamber-unknown'):
            with self.subTest(preset=preset):
                value=copy.deepcopy(project)
                if preset:value['chamberPreset']=preset
                original=copy.deepcopy(value)
                compiled=server.compile_design(value)
                expected=preset if preset in ('mi-chamber-pebbles','mi-chamber-moon','mi-chamber-broken','mi-chamber-irregular','mi-chamber-multi-screen') else ''
                self.assertEqual(compiled['chamberPreset'],expected)
                self.assertNotIn('chamberPreset',value['design'])
                self.assertEqual(value,original)
                runtime=standalone.runtime_fields(compiled,standalone.runtime_design_schema(),'design')
                self.assertEqual(runtime['chamberPreset'],expected)

    def test_unmarked_old_runtime_is_not_inferred_from_names_or_editable_design(self):
        value=server.default();value['projectId']='mi-chamber-broken';value['name']='mi-chamber-moon'
        value['design']['chamberPreset']='mi-chamber-broken'
        compiled=server.compile_design(value)
        self.assertEqual(compiled['chamberPreset'],'')
        self.assertEqual(value['design']['chamberPreset'],'mi-chamber-broken')

    def test_standalone_carries_the_same_motion_class(self):
        with patch.object(storage,'WORKSPACE',ROOT),tempfile.TemporaryDirectory() as folder:
            inputs=standalone.runtime_source_inputs()
            self.assertIn('src/CreatorChamberMotion.cs',inputs)
            result=standalone.compiler_sources(Path(folder),{'id':'motion.test','name':'Motion test','version':'0.4.1'})
            motion=Path(folder)/'CreatorChamberMotion.cs'
            self.assertTrue(motion.is_file())
            self.assertIn('class CreatorChamberMotion',motion.read_text('utf-8'))
            self.assertIn('namespace IteratorContent_',motion.read_text('utf-8'))

    def test_actual_template_geometry_and_editor_playback_motion(self):
        compiler=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.is_file():self.skipTest('C# compiler required')
        with tempfile.TemporaryDirectory() as folder:
            for mode in ('editor','playback'):
                executable=Path(folder)/(mode+'.exe')
                command=[str(compiler),'/nologo','/out:'+str(executable),str(ROOT/'src/CreatorChamberMotion.cs'),str(ROOT/'tests/chamber_motion_check.cs')]
                if mode=='playback':command.append('/define:PLAYBACK')
                compiled=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace')
                self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
                result=subprocess.run([str(executable),str(ROOT/'templates/rooms/chambers')],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('checks passed',result.stdout)
                print(mode+': '+result.stdout.strip())

    def test_room_loader_first_placement_and_external_copies(self):
        compiler=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.is_file():self.skipTest('C# compiler required')
        with tempfile.TemporaryDirectory() as folder:
            executable=Path(folder)/'initial-placement.exe'
            command=[str(compiler),'/nologo','/out:'+str(executable),str(ROOT/'src/CreatorChamberMotion.cs'),str(ROOT/'src/CreatorOracleLifecycle.cs'),str(ROOT/'tests/oracle_initial_placement_check.cs')]
            compiled=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace')
            self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            result=subprocess.run([str(executable)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('14 checks passed',result.stdout)


if __name__=='__main__':unittest.main()
