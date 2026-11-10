import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import test_project_packages as fixtures
import chamber_presets
import default_text
import room_bindings
import room_editor
import room_source_choices
import server
import storage


class ChamberPresetTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ProjectPackageTests('test_roundtrip_preserves_room_source_settings_cameras_palette_and_plan')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.before=self.snapshot()

    def snapshot(self):
        return {str(file.relative_to(self.fixture.root)):hashlib.sha256(file.read_bytes()).hexdigest()
                for file in self.fixture.root.rglob('*') if file.is_file()}

    def test_all_presets_create_distinct_editable_rooms_without_deploy_or_old_changes(self):
        names=set();ids=set();layouts=set()
        for row in chamber_presets.listing()['presets']:
            with default_text.use_language('zh-CN'):
                result=chamber_presets.create({'presetId':row['id']},server)
            self.assertTrue(result['requiresApply'])
            project=result['project'];pid=project['projectId'];binding=room_bindings.binding(project)
            self.assertNotIn(pid,ids);ids.add(pid)
            self.assertFalse(project['name'].startswith('chamberPresets.'))
            self.assertTrue(project['chamberPreset'].startswith('mi-chamber-'))
            self.assertEqual(storage.load_project(pid),project)
            _,spec=chamber_presets.get(row['id']);self.assertEqual(binding['aiNode'],spec['aiNode'])
            for name in (binding['ai'],binding['entry']):
                self.assertNotIn(name,names);names.add(name)
                room_editor.ensure_synced(pid,name)
                source=storage.project_file(pid).parent/'rooms'/name
                self.assertTrue(source.with_suffix('.txt').read_text('utf-8').startswith('[[['))
                cached=room_editor.cached_source(pid,name)
                self.assertIsNotNone(cached)
                self.assertGreaterEqual(room_bindings.geometry(cached.with_suffix('.txt'))['exitCount'],1)
                if name==binding['ai']:
                    self.assertEqual(room_bindings.geometry(cached.with_suffix('.txt'))['width'],row['width'])
                    for number in range(1,row['cameraCount']+1):
                        self.assertTrue(cached.with_name(cached.name+'_'+str(number)+'.png').is_file())
            layouts.add((room_editor.cached_source(pid,binding['ai']).with_suffix('.txt')).read_text('utf-8').splitlines()[11])
            project['editor']['externalRoomTools']=True
            report=room_source_choices.preflight([project])
            self.assertFalse(report['issues'],report)
            self.assertTrue(all(item['renderVersions'][0]['pairedSource'] for item in report['rooms']))
            self.assertEqual(server.validate(copy.deepcopy(project))['editor']['externalRoomTools'],True)
        self.assertEqual(len(layouts),5)
        current=self.snapshot()
        self.assertEqual({key:current[key] for key in self.before},self.before)
        self.assertFalse(self.fixture.installed.exists())
        self.assertFalse(storage.RUNTIME.exists())

    def test_multi_screen_has_full_camera_assets_and_editable_source(self):
        result=chamber_presets.create({'presetId':'mi-chamber-multi-screen'},server)
        project=result['project'];pid=project['projectId'];room=room_bindings.binding(project)['ai']
        root,value=chamber_presets.get('mi-chamber-multi-screen')
        self.assertEqual((value['width'],value['height'],value['cameraCount']),(106,36,3))
        assets=chamber_presets.validated_assets(root,value)
        self.assertTrue(all('_'+str(i)+'.png' in assets['rendered'] for i in (1,2,3)))
        source=room_editor.cached_source(pid,room)
        from PIL import Image
        with Image.open(storage.project_file(pid).parent/'rooms'/(room+'.png')) as light:
            self.assertEqual(light.size,(2900,1180))
        self.assertEqual(len([v for v in source.with_suffix('.txt').read_text('utf-8').splitlines()[3].split('|') if v]),3)

    def test_failed_creation_removes_only_new_partial_project(self):
        before=self.snapshot()
        with patch.object(room_source_choices,'pairing_record',side_effect=OSError('disk failure')):
            with self.assertRaisesRegex(OSError,'disk failure'):
                chamber_presets.create({'presetId':'mi-chamber-broken'},server)
        self.assertEqual(self.snapshot(),before)
        self.assertEqual([p.name for p in storage.PROJECTS.iterdir()],['selected'])

    def test_invalid_preset_request_cannot_modify_old_project(self):
        for request in ({'presetId':'../waiting'},{'presetId':'mi-chamber-broken','projectId':'selected'}):
            with self.assertRaises(ValueError):chamber_presets.create(request,server)
        self.assertEqual(self.snapshot(),self.before)


if __name__=='__main__':unittest.main()
