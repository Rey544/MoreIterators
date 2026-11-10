import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import room_editor,room_migration,storage


class RoomEditorSyncTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.exe=self.root/'rained/Rained.exe';self.exe.parent.mkdir();self.exe.touch()
        self.data=self.root/'assets';self.data.mkdir()
        self.project=self.root/'project';self.project.mkdir()
        self.name='TEST_ROOM_ENTRY'
        self.p=dict(projectId='room-test',waitingRoomTemplate='mi-waiting')
        self.names=lambda p:('TEST_ROOM_AI',self.name,'room-test')
        for context in (patch.object(room_editor,'rained_root',return_value=self.exe),
                        patch.object(storage,'project_file',return_value=self.project/'project.json'),
                        patch.object(storage,'load_project',return_value=self.p),
                        patch.object(storage,'binding',return_value=None),
                        patch.dict(os.environ,{'APPDATA':str(self.root/'roaming'),'XDG_CONFIG_HOME':str(self.root/'config')})):
            context.start();self.addCleanup(context.stop)

    def preferences(self,root=None,value=None):
        file=(root or self.exe.parent)/'config/preferences.json';file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps(dict(dataPath=str(self.data) if value is None else value)),'utf-8')
        return file

    def render_files(self,name=None,cameras=1):
        base=self.data/'Levels'/(name or self.name);base.parent.mkdir(parents=True,exist_ok=True)
        base.with_suffix('.txt').write_text((name or self.name)+'\n48*35|-1|0\n0|0|0\n'+'|'.join('0,0' for _ in range(cameras))+'\n','utf-8')
        for i in range(1,cameras+1):Path(str(base)+'_'+str(i)+'.png').write_bytes(b'new-image-'+str(i).encode())
        return base

    def editable(self):
        source=self.project/'rooms'/(self.name+'.txt');source.parent.mkdir(exist_ok=True)
        source.write_text('[[[geometry]]]','utf-8');source.with_suffix('.png').write_bytes(b'light')
        return source

    def cached(self):
        base=self.project/'rooms/rendered'/self.name;base.parent.mkdir(parents=True,exist_ok=True)
        for suffix,content in (('.txt',b'old geometry'),('_1.png',b'old camera'),('_2.png',b'old extra camera'),('_settings.txt',b'Palette: 12\n')):
            Path(str(base)+suffix).write_bytes(content)
        return base

    @staticmethod
    def snapshot(folder):return {p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}

    def test_portable_preferences_override_adjacent_data(self):
        (self.exe.parent/'Data').mkdir();self.preferences()
        self.assertEqual(room_editor.rained_data_root(),self.data)

    def test_installed_preferences_are_supported(self):
        self.preferences(self.root/'roaming/rained')
        self.assertEqual(room_editor.rained_data_root(),self.data)

    def test_relative_preference_uses_rained_working_directory(self):
        (self.exe.parent/'relative-data').mkdir();self.preferences(value='relative-data')
        self.assertEqual(room_editor.rained_data_root(),self.exe.parent/'relative-data')

    def test_installed_preferences_without_path_use_profile_default(self):
        profile=self.root/'roaming/rained';(profile/'Data').mkdir(parents=True)
        file=self.preferences(profile);file.write_text('{}','utf-8')
        self.assertEqual(room_editor.rained_data_root(),profile/'Data')

    def test_missing_preferences_keep_portable_default(self):
        (self.exe.parent/'Data').mkdir()
        self.assertEqual(room_editor.rained_data_root(),self.exe.parent/'Data')

    def test_invalid_preferences_do_not_silently_use_different_assets(self):
        file=self.preferences();(self.exe.parent/'Data').mkdir()
        for value in ('{broken','null','[]','{"dataPath":null}','{"dataPath":""}','{"dataPath":"missing-folder"}'):
            with self.subTest(value=value):
                file.write_text(value,'utf-8')
                with self.assertRaisesRegex(ValueError,'Rained 素材目录无效'):room_editor.rained_data_root()
                self.assertEqual(file.read_text('utf-8'),value)

    def test_existing_editable_source_can_open_before_rained_data_setup(self):
        source=self.editable()
        with patch.object(room_editor.desktop_launch,'open_rained') as launch:
            result=room_editor.open_room('room-test','entry',self.names)
        self.assertEqual(result['path'],str(source));launch.assert_called_once_with(self.exe,source)

    def test_ai_source_is_taken_from_configured_data_folder(self):
        self.preferences();source=self.data/'LevelEditorProjects/EditorSamples/SS_AI.txt';source.parent.mkdir(parents=True)
        source.write_text('[[[geometry]]]','utf-8');source.with_suffix('.png').write_bytes(b'light')
        _,prepared=room_editor.prepare('room-test','ai',self.names)
        self.assertEqual(prepared.read_bytes(),source.read_bytes())
        self.assertEqual(prepared.with_suffix('.png').read_bytes(),b'light')

    def test_render_uses_and_reads_configured_data(self):
        self.preferences();source=self.editable();output=self.render_files()
        with patch.object(room_editor.subprocess,'run',return_value=subprocess.CompletedProcess([],0,b'',b'')) as run:
            self.assertEqual(room_editor.render('room-test','entry',self.names),output)
        command=run.call_args.args[0]
        self.assertEqual(command[command.index('--data')+1],str(self.data));self.assertEqual(command[-1],str(source))

    def test_render_keeps_one_data_directory_if_preferences_change_mid_render(self):
        self.editable();output=self.render_files()
        with patch.object(room_editor,'rained_data_root',side_effect=[self.data,self.root/'different']) as lookup, \
             patch.object(room_editor.subprocess,'run',return_value=subprocess.CompletedProcess([],0,b'',b'')):
            self.assertEqual(room_editor.render('room-test','entry',self.names),output)
        lookup.assert_called_once_with(self.exe)

    def test_failed_renderer_does_not_touch_prior_cache(self):
        self.preferences();self.editable();cache=self.cached();before=self.snapshot(cache.parent)
        settings=self.root/'settings.txt';settings.write_text('Palette: 42\n','utf-8')
        with patch.object(room_editor.subprocess,'run',return_value=subprocess.CompletedProcess([],1,b'render failure',b'')):
            with self.assertRaisesRegex(ValueError,'render failure'):room_editor.import_render('room-test','entry',self.names,settings)
        self.assertEqual(self.snapshot(cache.parent),before)

    def test_missing_rendered_camera_preserves_prior_cache(self):
        output=self.render_files(cameras=2);Path(str(output)+'_2.png').unlink();cache=self.cached();before=self.snapshot(cache.parent)
        settings=self.root/'settings.txt';settings.write_text('Palette: 42\n','utf-8')
        with patch.object(room_editor,'render',return_value=output):
            with self.assertRaises(FileNotFoundError):room_editor.import_render('room-test','entry',self.names,settings)
        self.assertEqual(self.snapshot(cache.parent),before)

    def test_cache_write_failure_rolls_back_geometry_settings_and_cameras(self):
        output=self.render_files();cache=self.cached();before=self.snapshot(cache.parent)
        settings=self.root/'settings.txt';settings.write_text('Palette: 42\n','utf-8')
        original=room_migration.Files.write;failed=False
        def write_once_fail(transaction,file,content):
            nonlocal failed
            if not failed and Path(file).name.endswith('_1.png'):
                failed=True;raise OSError('simulated full disk')
            return original(transaction,file,content)
        with patch.object(room_editor,'render',return_value=output),patch.object(room_migration.Files,'write',write_once_fail):
            with self.assertRaisesRegex(OSError,'simulated full disk'):room_editor.import_render('room-test','entry',self.names,settings)
        self.assertEqual(self.snapshot(cache.parent),before)

    def test_success_preserves_authored_settings_and_removes_only_old_cameras(self):
        output=self.render_files();cache=self.cached();other=cache.parent/'OTHER_1.png';other.write_bytes(b'other room')
        settings=self.root/'settings.txt';settings.write_text('Palette: 42\nEffects: Sky-1-0-0, \n','utf-8')
        with patch.object(room_editor,'render',return_value=output):result=room_editor.import_render('room-test','entry',self.names,settings)
        self.assertEqual(result['cameras'],1)
        self.assertEqual(Path(str(cache)+'_settings.txt').read_bytes(),settings.read_bytes())
        self.assertEqual(Path(str(cache)+'_1.png').read_bytes(),b'new-image-1')
        self.assertFalse(Path(str(cache)+'_2.png').exists());self.assertEqual(other.read_bytes(),b'other room')

    def test_settings_can_be_the_existing_cache_file(self):
        output=self.render_files();cache=self.cached();settings=Path(str(cache)+'_settings.txt')
        before=settings.read_bytes()
        with patch.object(room_editor,'render',return_value=output):room_editor.import_render('room-test','entry',self.names,settings)
        self.assertEqual(settings.read_bytes(),before)


if __name__=='__main__':unittest.main()
