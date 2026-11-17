import copy
import hashlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import zipfile

import test_project_packages as fixtures
import project_bundles
import project_packages
import room_bindings
import storage


class SameRegionBundleTests(unittest.TestCase):
    def fixture(self):
        value = fixtures.ProjectPackageTests()
        value.setUp()
        self.addCleanup(value.doCleanups)
        return value

    def projects(self, f):
        projects = []
        world = ['ROOMS']
        positions = []
        for index, identifier in enumerate(('first', 'second', 'unselected')):
            prefix = 'TEST_' + identifier.upper()
            project = copy.deepcopy(f.project)
            project.update(projectId=identifier, name=identifier)
            project['roomBinding'].update(region='TEST', ai=prefix+'_AI', entry=prefix+'_ENTRY', oracleId=identifier+'_oracle')
            path = storage.project_file(identifier)
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(project), 'utf-8')
            for offset, kind in enumerate(('AI', 'ENTRY')):
                name = prefix+'_'+kind
                f.render(f.local/'world/test-rooms'/name, name)
                if kind == 'ENTRY':
                    (f.local/'world/test-rooms'/(name+'_settings.txt')).write_text('Template: TEST_SettingsTemplate_Outside\n', 'utf-8')
                positions.append(name+': '+str(index*400+offset*100)+'><'+str(index*250))
            world.extend((prefix+'_AI : DISCONNECTED, '+prefix+'_ENTRY', prefix+'_ENTRY : '+prefix+'_AI, DISCONNECTED : SHELTER'))
            projects.append(project)
        folder=f.local/'world/test'
        folder.mkdir(parents=True)
        (folder/'world_test.txt').write_text('\n'.join(world+['END ROOMS'])+'\n', 'utf-8')
        (folder/'map_test.txt').write_text('\n'.join(positions)+'\n', 'utf-8')
        (folder/'properties.txt').write_text('Room Setting Templates: Outside\nCloudsStart: 100\n', 'utf-8')
        (folder/'test_settingstemplate_outside.txt').write_text('Palette: 9100\nMorePalette0: 9101, 0.5\nEffects: AboveCloudsView-1-0-0,\n', 'utf-8')
        f.palette(f.local/'palettes/palette9101.png', 'blue')
        return projects

    def test_two_test_projects_import_apply_and_reexport_without_unselected_work(self):
        import server
        f=self.fixture()
        self.projects(f)
        def snapshot():
            return {str(path.relative_to(f.root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in f.root.rglob('*') if path.is_file() and not path.is_relative_to(storage.EXPORTS)}
        before=snapshot()
        result=project_bundles.export_package(dict(projects=['first','second'], packageName='泳池分享', packageVersion='0.4.3'), f.server)
        payload=(storage.EXPORTS/unquote(Path(result['url']).name)).read_bytes()
        self.assertEqual(before, snapshot())
        inner={}
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertEqual(set(archive.namelist()), {'bundle.json','projects/first.zip','projects/second.zip'})
            for identifier in ('first','second'):
                inner[identifier]=f.unpack(archive.read('projects/'+identifier+'.zip'))
                self.assertNotIn(b'UNSELECTED',inner[identifier]['regions/TEST/map_test.txt'])
                self.assertFalse(any('UNSELECTED' in name for name in inner[identifier]))
        f.target()
        unrelated=storage.PROJECTS/'my-old-work/project.json'
        unrelated.parent.mkdir(parents=True)
        existing=copy.deepcopy(f.project)
        existing.update(projectId='my-old-work',name='My old work')
        unrelated.write_text(json.dumps(existing), 'utf-8')
        old=unrelated.read_bytes()
        imported=project_bundles.import_package(payload,f.server)
        self.assertTrue(imported['ok'])
        self.assertEqual(len(imported['projects']),2)
        self.assertEqual(unrelated.read_bytes(),old)

        with patch.object(server,'save',side_effect=copy.deepcopy), patch.object(server,'compile_design',side_effect=lambda project:{'projectId':project['projectId']}), \
             patch.object(server,'MOD',f.local), patch.object(server,'DESIGNS',storage.RUNTIME), patch.object(server,'ASSETS',f.game/'RainWorld_Data/StreamingAssets'), \
             patch.object(server,'installation_paths',return_value={}), patch.object(server.audio_assets,'copy_referenced'), patch.object(server.local_content,'status',return_value={}), \
             patch.object(server.waiting_room,'prepare',side_effect=AssertionError('Unexpected template replacement')), patch.object(server,'copy_room',side_effect=AssertionError('Unexpected default room')):
            for project in imported['projects']:
                self.assertTrue(server.deploy(project)['ok'])
        installed=f.installed/'world/test/map_test.txt'
        text=installed.read_text('utf-8')
        self.assertIn('TEST_FIRST_ENTRY:',text)
        self.assertIn('TEST_SECOND_ENTRY:',text)
        self.assertNotIn('UNSELECTED',text)
        for identifier in ('first','second'):
            room='TEST_'+identifier.upper()+'_ENTRY'
            expected=inner[identifier]['rooms/'+room+'/rendered/'+room+'_mi_background.json']
            self.assertEqual((f.installed/'world/test-rooms'/(room+'_mi_background.json')).read_bytes(),expected)
        result=project_bundles.export_package(dict(projects=['first','second'],packageName='泳池分享',packageVersion='0.4.3'),f.server)
        payload=(storage.EXPORTS/unquote(Path(result['url']).name)).read_bytes()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            for identifier in ('first','second'):
                files=f.unpack(archive.read('projects/'+identifier+'.zip'))
                room='TEST_'+identifier.upper()+'_ENTRY'
                relative='rooms/'+room+'/rendered/'+room+'_mi_background.json'
                self.assertEqual(files[relative],inner[identifier][relative])
        self.assertEqual(unrelated.read_bytes(),old)

    def test_conflicting_region_properties_stop_second_apply_without_overwriting_first(self):
        import server
        f=self.fixture()
        self.projects(f)
        result=project_bundles.export_package(dict(projects=['first','second']),f.server)
        payload=(storage.EXPORTS/unquote(Path(result['url']).name)).read_bytes()
        bundle=f.unpack(payload)
        second=f.unpack(bundle['projects/second.zip'])
        second['regions/TEST/properties.txt']=second['regions/TEST/properties.txt'].replace(b'CloudsStart: 100',b'CloudsStart: 900')
        manifest=json.loads(second['manifest.json'])
        manifest['files']=project_packages._records({name:data for name,data in second.items() if name!='manifest.json'})
        second['manifest.json']=json.dumps(manifest).encode()
        bundle['projects/second.zip']=f.archive(second)
        manifest=json.loads(bundle['bundle.json'])
        manifest['files']=project_packages._records({name:data for name,data in bundle.items() if name!='bundle.json'})
        bundle['bundle.json']=json.dumps(manifest).encode()
        f.target()
        imported=project_bundles.import_package(f.archive(bundle),f.server)
        self.assertTrue(imported['ok'])
        def snapshot():
            return {str(path.relative_to(f.root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in f.root.rglob('*') if path.is_file()}
        with patch.object(server,'save',side_effect=copy.deepcopy), patch.object(server,'compile_design',side_effect=lambda project:{'projectId':project['projectId']}), \
             patch.object(server,'MOD',f.local), patch.object(server,'DESIGNS',storage.RUNTIME), patch.object(server,'ASSETS',f.game/'RainWorld_Data/StreamingAssets'), \
             patch.object(server,'installation_paths',return_value={}), patch.object(server.audio_assets,'copy_referenced'), patch.object(server.local_content,'status',return_value={}), \
             patch.object(server.waiting_room,'prepare',side_effect=AssertionError('Unexpected template replacement')), patch.object(server,'copy_room',side_effect=AssertionError('Unexpected default room')):
            self.assertTrue(server.deploy(imported['projects'][0])['ok'])
            before=snapshot()
            with self.assertRaisesRegex(ValueError,'properties.txt'):
                server.deploy(imported['projects'][1])
            self.assertEqual(before,snapshot())


if __name__=='__main__':unittest.main()
