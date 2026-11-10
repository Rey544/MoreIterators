import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import playable_export
import room_bindings
import server
import standalone
import storage
import broadcasts
import pearls
import pearl_projects
import test_standalone_extra_rooms as project_fixtures
import test_region_packages as region_fixtures


class PlayableProjectTests(unittest.TestCase):
    def setUp(self):
        self.fixture=project_fixtures.ExtraRoomExportTests()
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.request={**self.fixture.request,'scope':'project','settingsProject':'selected','startRoom':'ZX_ENTRY'}

    def archive(self,**changes):
        result=playable_export.build({**self.request,**changes},server)
        return zipfile.ZipFile(storage.EXPORTS/Path(result['url']).name)

    def read(self,archive,path):return archive.read(self.request['id']+'/'+path)

    def test_scene_files_and_native_features_are_in_final_audited_archive(self):
        from test_scene_assets import draft
        import scene_assets
        scene=draft()
        with self.archive(scene=scene) as archive:
            manifest=json.loads(self.read(archive,'playable-manifest.json'))
            campaign=json.loads(self.read(archive,manifest['campaignFile']))
            features,files=scene_assets._planned(self.request['id'],scene)
            self.assertEqual(manifest['sceneFeatures'],features)
            self.assertEqual(manifest['sceneFiles'],sorted(files))
            for key,value in features.items():self.assertEqual(campaign['features'][key],value)
            for name,raw in files.items():self.assertEqual(self.read(archive,name),raw)
            self.assertNotIn('data:image',json.dumps(manifest))
            self.assertFalse(any(name.endswith('export-settings.json') for name in archive.namelist()))

    def test_story_entry_preserves_existing_data_and_does_not_inherit_preview_flags(self):
        before={path:path.read_bytes() for path in self.fixture.data.rglob('*') if path.is_file()}
        with self.archive(extraRooms=['ZX_EXTRA']) as archive:
            manifest=json.loads(self.read(archive,'playable-manifest.json'))
            campaign=json.loads(self.read(archive,manifest['campaignFile']))
            self.assertEqual(campaign['features'],dict(start_room='ZX_ENTRY',world_state=['White'],story_regions=['ZX']))
            self.assertEqual(campaign['id'],playable_export.campaign_id(self.request['id']))
            self.assertFalse(any(Path(name).name.lower().startswith('readme') for name in archive.namelist()))
            self.assertEqual(manifest['rooms'],['ZX_AI','ZX_ENTRY','ZX_EXTRA'])
            info=json.loads(self.read(archive,'modinfo.json'))
            self.assertIn('slime-cubed.slugbase',info['requirements'])
            self.assertNotIn('henpemaz_rainmeadow',info['requirements'])
            self.assertEqual(json.loads(self.read(archive,'rainmeadow.json')),dict(sync_required_mods=[self.request['id']]))
            self.assertNotIn('ZX_UNUSED',self.read(archive,'world/zx/world_zx.txt').decode())
            self.assertNotIn(str(self.fixture.root),json.dumps(campaign))
            self.assertFalse(any(name.endswith(('.cs','.log')) or 'project.json' in name or 'config.json' in name for name in archive.namelist()))
        self.assertEqual(before,{path:path.read_bytes() for path in self.fixture.data.rglob('*') if path.is_file()})

    def test_selected_extra_start_is_valid_and_unselected_start_is_rejected(self):
        with self.archive(extraRooms=['ZX_EXTRA'],startRoom='ZX_EXTRA') as archive:
            self.assertEqual(json.loads(self.read(archive,'playable-manifest.json'))['startRoom'],'ZX_EXTRA')
        for room in ('ZX_UNUSED','../../secret','GATE_ZX_SU'):
            with self.subTest(room=room),self.assertRaises(ValueError):self.archive(startRoom=room)

    def test_disconnected_start_is_rejected_instead_of_silently_adding_connections(self):
        self.fixture.rows[2]['connections']=['DISCONNECTED','DISCONNECTED']
        self.fixture.rows[0]['connections']=['ZX_ENTRY','DISCONNECTED']
        world=self.fixture.local/'world/zx/world_zx.txt'
        world.write_text(world.read_text('utf-8').replace('ZX_EXTRA : ZX_AI, ZX_UNUSED','ZX_EXTRA : DISCONNECTED, DISCONNECTED').replace('ZX_AI : ZX_ENTRY, ZX_EXTRA','ZX_AI : ZX_ENTRY, DISCONNECTED'),'utf-8')
        with self.assertRaises(ValueError):
            self.archive(extraRooms=['ZX_EXTRA'],startRoom='ZX_EXTRA')

    def test_missing_camera_blocks_new_format_too(self):
        Path(str(self.fixture.source('ZX_ENTRY'))+'_1.png').unlink()
        with self.assertRaises(ValueError):self.archive()

    def test_campaign_identity_is_stable_and_separate_between_mods(self):
        first=playable_export.campaign_id('author.first')
        self.assertEqual(first,playable_export.campaign_id('author.first'))
        self.assertNotEqual(first,playable_export.campaign_id('author.second'))
        self.assertNotEqual(first,'White')

    def test_story_start_uses_final_mapped_room_not_the_source_name(self):
        names={'selected':('MABCDE_001_AI','MABCDE_001_ENTRY')}
        with patch.object(standalone,'export_room_names',return_value=names),self.archive() as archive:
            manifest=json.loads(self.read(archive,'playable-manifest.json'))
            self.assertEqual(manifest['startRoom'],'MABCDE_001_ENTRY')
            self.assertIn(self.request['id']+'/world/mabcde-rooms/MABCDE_001_ENTRY.txt',archive.namelist())
            campaign=json.loads(self.read(archive,manifest['campaignFile']))
            self.assertEqual(campaign['features']['start_room'],'MABCDE_001_ENTRY')

    def test_final_zip_audit_rejects_changed_story_data_and_removes_failed_output(self):
        verify=playable_export.verify_archive
        def corrupt(stage,path):
            with zipfile.ZipFile(path,'a') as archive:archive.writestr(stage.name+'/unexpected.cs','test')
            verify(stage,path)
        with patch.object(playable_export,'verify_archive',side_effect=corrupt),self.assertRaisesRegex(ValueError,'清单不一致'):
            self.archive()
        self.assertEqual(list(storage.EXPORTS.glob('*.zip')),[])

    def test_original_standalone_export_remains_unchanged(self):
        with self.fixture.archive() as archive:
            self.assertFalse(any('/slugbase/' in name or 'playable-manifest' in name for name in archive.namelist()))
            self.assertNotIn('slime-cubed.slugbase',json.loads(self.read(archive,'modinfo.json'))['requirements'])


class PlayableRegionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=region_fixtures.RegionPackageTests()
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.world=self.fixture.world.replace('White : ZZ_A01 : ZZ_A02\n','White : ZZ_A01 : ZZ_A02 : ZZ_A02\n')
        (self.fixture.owner/'world/zz/world_zz.txt').write_text(self.fixture.world,'utf-8')
        self.request={**self.fixture.metadata,'scope':'region','region':'ZZ','startRoom':'ZZ_A02','projects':[]}

    def archive(self,**changes):
        result=playable_export.build({**self.request,**changes},server)
        return zipfile.ZipFile(storage.EXPORTS/Path(result['url']).name)

    def read(self,archive,path):return archive.read(self.request['id']+'/'+path)

    def test_pure_region_scene_assets_are_audited_without_adding_runtime_or_editor_data(self):
        from test_scene_assets import draft
        import scene_assets
        scene=draft()
        with self.archive(scene=scene) as archive:
            manifest=json.loads(self.read(archive,'playable-manifest.json'))
            features,files=scene_assets._planned(self.request['id'],scene)
            self.assertEqual(manifest['sceneFeatures'],features)
            for name,raw in files.items():self.assertEqual(self.read(archive,name),raw)
            self.assertFalse(any(name.endswith(('.dll','.cs','export-settings.json')) for name in archive.namelist()))

    def test_whole_region_keeps_world_rules_assets_and_source_dependency(self):
        before={path:path.read_bytes() for path in self.fixture.owner.rglob('*') if path.is_file()}
        with self.archive() as archive:
            self.assertEqual(self.read(archive,'world/zz/world_zz.txt').decode().splitlines(),self.fixture.world.splitlines())
            info=json.loads(self.read(archive,'modinfo.json'))
            self.assertEqual(set(info['requirements']),{'author.map','slime-cubed.slugbase'})
            self.assertEqual(self.read(archive,'world/zz/map_zz.png'),(self.fixture.owner/'world/zz/map_zz.png').read_bytes())
            self.assertIn(self.request['id']+'/palettes/palette9011.png',archive.namelist())
            self.assertNotIn(self.request['id']+'/private-notes.txt',archive.namelist())
            manifest=json.loads(self.read(archive,'playable-manifest.json'))
            self.assertEqual(manifest['startRoom'],'ZZ_A02')
            self.assertEqual(manifest['rooms'],['ZZ_A01','ZZ_A02'])
            self.assertFalse(any(name.endswith(('.dll','.cs','.log')) for name in archive.namelist()))
        self.assertEqual(before,{path:path.read_bytes() for path in self.fixture.owner.rglob('*') if path.is_file()})

    def test_missing_and_unselected_local_content_block_whole_region(self):
        self.fixture.text(storage.PROJECTS/'private/project.json',json.dumps(dict(projectId='private',roomBinding=dict(region='ZZ',ai='ZZ_A01',entry='ZZ_A02',entryMode='copy',oracleId='private',aiNode=0,entryNode=0))))
        with self.assertRaisesRegex(ValueError,'未选择'):self.archive()
        (storage.PROJECTS/'private/project.json').unlink()
        (self.fixture.owner/'world/zz-rooms/ZZ_A02_1.png').unlink()
        with self.assertRaises(ValueError):self.archive()

    def test_existing_mod_id_cannot_be_reused_as_its_own_dependency(self):
        with self.assertRaisesRegex(ValueError,'不能覆盖'):self.archive(id='author.map')

    def test_gate_and_outside_region_are_not_accepted_as_story_starts(self):
        for start in ('SU_A01','GATE_ZZ_SU','ZZ_OFFSCREEN',''):
            with self.subTest(start=start),self.assertRaises(ValueError):self.archive(startRoom=start)

    def test_map_without_selected_iterator_cannot_silently_drop_custom_runtime_content(self):
        with self.assertRaises(ValueError):self.archive(broadcasts=True)


class PlayableLocalRegionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=project_fixtures.ExtraRoomExportTests()
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture
        (f.local/'modinfo.json').write_text(json.dumps(dict(id='moreiterators.local',name='Local',requirements=['moreiterators.core'])),'utf-8')
        core=f.assets/'mods/more_iterators';core.mkdir(parents=True)
        (core/'modinfo.json').write_text(json.dumps(dict(id='moreiterators.core',name='MI')),'utf-8')
        for row in f.rows:
            prefix=f.local/'world/zx-rooms'/row['name'];f.render(prefix,row['name']);row['geometryPath']=str(prefix.with_suffix('.txt'))
        (f.local/'world/zx/properties.txt').write_text('Palette: 26\n','utf-8')
        (f.local/'world/zx/displayname.txt').write_text('My Region\n','utf-8')
        f.roots=[f.local,core,f.assets]
        f.catalog=dict(regions=[dict(name='ZX',rooms=f.rows)],activeMods=['moreiterators.local','moreiterators.core'])
        self.request={**f.request,'scope':'region','region':'ZX','startRoom':'ZX_ENTRY','settingsProject':'selected'}

    def test_whole_local_region_has_runtime_and_every_room_without_local_mod_dependency(self):
        f=self.fixture;world=f.local/'world/zx/world_zx.txt'
        world.write_text(world.read_text('utf-8')+'CREATURES\nZX_EXTRA : 0-Lizard\nEND CREATURES\n','utf-8')
        before={path:path.read_bytes() for path in f.data.rglob('*') if path.is_file()}
        result=playable_export.build(self.request,server)
        with zipfile.ZipFile(storage.EXPORTS/Path(result['url']).name) as archive:
            prefix=self.request['id']+'/'
            self.assertEqual(archive.read(prefix+'world/zx/world_zx.txt'),world.read_bytes())
            manifest=json.loads(archive.read(prefix+'playable-manifest.json'))
            self.assertEqual(set(manifest['rooms']),{row['name'] for row in f.rows})
            self.assertTrue(any(name.endswith('.dll') for name in archive.namelist()))
            info=json.loads(archive.read(prefix+'modinfo.json'))
            self.assertFalse(any(identifier.startswith('moreiterators') for identifier in info['requirements']))
            self.assertIn('slime-cubed.slugbase',info['requirements'])
        self.assertEqual(before,{path:path.read_bytes() for path in f.data.rglob('*') if path.is_file()})

    def test_conflicting_actual_region_links_are_not_silently_replaced(self):
        path=self.fixture.local/'world/zx/world_zx.txt'
        path.write_text(path.read_text('utf-8').replace('ZX_AI : ZX_ENTRY','ZX_AI : DISCONNECTED'),'utf-8')
        with self.assertRaises(ValueError):playable_export.build(self.request,server)

    def test_complete_region_preserves_nonportable_room_effects(self):
        settings=self.fixture.local/'world/zx-rooms/ZX_ENTRY_settings.txt'
        text='Template: NONE\nPalette: 26\nEffects: AboveCloudsView-0.391-0-0, ZeroG-0.25-0-0\n'
        settings.write_text(text,'utf-8')
        result=playable_export.build(self.request,server)
        with zipfile.ZipFile(storage.EXPORTS/Path(result['url']).name) as archive:
            self.assertEqual(archive.read(self.request['id']+'/world/zx-rooms/ZX_ENTRY_settings.txt'),settings.read_bytes())

    def test_extra_room_broadcast_and_explicit_pearl_are_not_silently_filtered(self):
        broadcast=broadcasts.default();broadcast.update(room='ZX_EXTRA',region='ZX')
        broadcast['pages'][0]['lines'][0]['text']='Selected region broadcast'
        with patch.object(pearl_projects,'resolve',return_value='fixture'),patch.object(pearls,'listing',return_value=[]):pearl=pearls.default('fixture')
        pearl['spawnRooms']=['ZX_EXTRA'];pearl['spawnProjects']=[]
        other=copy.deepcopy(pearl);other.update(id='A02',uid='1'*32,spawnRooms=['SU_A01'])
        request={**self.request,'broadcasts':True,'pearls':True,'pearlCollectionId':'fixture'}
        with patch.object(broadcasts,'listing',return_value=[broadcast]),patch.object(pearl_projects,'catalog',return_value=dict(activeId='fixture',projects=[dict(id='fixture')])),patch.object(pearls,'listing',return_value=[pearl,other]):
            result=playable_export.build(request,server)
        with zipfile.ZipFile(storage.EXPORTS/Path(result['url']).name) as archive:
            prefix=self.request['id']+'/'
            exported=json.loads(archive.read(prefix+'moreiterators/broadcasts/'+broadcast['id']+'.json'))
            self.assertEqual(exported['room'],'ZX_EXTRA')
            exported=json.loads(archive.read(prefix+'moreiterators/pearls/'+pearl['id']+'.json'))
            self.assertEqual(exported['spawns'],[dict(entry='ZX_EXTRA')])
            self.assertNotIn(prefix+'moreiterators/pearls/A02.json',archive.namelist())
            self.assertIn(prefix+'world/zx-rooms/ZX_EXTRA.txt',archive.namelist())

    def test_whole_region_rejects_an_isolated_start_room(self):
        world=self.fixture.local/'world/zx/world_zx.txt'
        original=world.read_text('utf-8')
        world.write_text(original.replace('ZX_EXTRA : ZX_AI, ZX_UNUSED','ZX_EXTRA : DISCONNECTED, DISCONNECTED').replace('ZX_AI : ZX_ENTRY, ZX_EXTRA','ZX_AI : ZX_ENTRY, DISCONNECTED').replace('ZX_UNUSED : ZX_ENTRY, ZX_EXTRA','ZX_UNUSED : ZX_ENTRY, DISCONNECTED'),'utf-8')
        with self.assertRaises(ValueError):playable_export.build({**self.request,'startRoom':'ZX_EXTRA'},server)

    def test_white_conditional_disconnect_cannot_pass_reachability(self):
        world=self.fixture.local/'world/zx/world_zx.txt'
        world.write_text(world.read_text('utf-8')+'CONDITIONAL LINKS\nWhite : ZX_ENTRY : ZX_AI : DISCONNECTED\nWhite : ZX_ENTRY : ZX_UNUSED : DISCONNECTED\nEND CONDITIONAL LINKS\n','utf-8')
        with self.assertRaises(ValueError):playable_export.build(self.request,server)

    def test_gate_assets_use_their_actual_world_gates_path(self):
        f=self.fixture;name='GATE_ZX_SU';prefix=f.local/'world/gates'/name
        f.render(prefix,name)
        f.rows.append({**f.row(name,['ZX_UNUSED','DISCONNECTED']),'tags':'GATE','geometryPath':str(prefix.with_suffix('.txt'))})
        world=f.local/'world/zx/world_zx.txt'
        world.write_text(world.read_text('utf-8').replace('ZX_UNUSED : ZX_ENTRY, ZX_EXTRA','ZX_UNUSED : ZX_ENTRY, '+name).replace('END ROOMS',name+' : ZX_UNUSED, DISCONNECTED : GATE\nEND ROOMS'),'utf-8')
        (f.local/'world/gates/locks.txt').write_text(name+' : 1 : 1\n','utf-8')
        result=playable_export.build(self.request,server)
        with zipfile.ZipFile(storage.EXPORTS/Path(result['url']).name) as archive:
            base=self.request['id']+'/'
            self.assertIn(base+'world/gates/'+name+'_settings.txt',archive.namelist())
            self.assertNotIn(base+'world/gate-rooms/'+name+'_settings.txt',archive.namelist())
            self.assertEqual(archive.read(base+'modify/world/gates/locks.txt'),('[ADD]'+name+' : 1 : 1\n').encode())


if __name__=='__main__':unittest.main()
