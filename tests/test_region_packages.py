import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import project_packages
import region_packages
import room_bindings
import storage
import room_source_choices


class RegionPackageTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.game=self.root/'game';self.assets=self.game/'RainWorld_Data/StreamingAssets';self.assets.mkdir(parents=True)
        (self.game/'RainWorld.exe').touch()
        self.owner=self.assets/'mods/author-map';self.owner.mkdir(parents=True)
        (self.owner/'modinfo.json').write_text(json.dumps(dict(id='author.map',name='Author map',requirements=[])),'utf-8')
        self.roots=[self.owner,self.assets]
        self.rows=[dict(name='ZZ_A01',connections=['ZZ_A02'],tags=''),dict(name='ZZ_A02',connections=['ZZ_A01'],tags='SHELTER')]
        self.catalog=dict(regions=[dict(name='ZZ',rooms=self.rows)],activeMods=['author.map'])
        self.metadata=dict(id='author.copy',name='Region data',authors='Author',description='',version='0.1.0')
        for change in (
            patch.object(storage,'GAME',self.game),patch.object(storage,'PROJECTS',self.root/'projects'),
            patch.object(storage,'EXPORTS',self.root/'exports'),patch.object(storage,'DATA',self.root/'data'),
            patch.object(storage,'LINKS',[]),patch.object(storage,'binding',return_value=None),
            patch.object(room_bindings,'enabled_asset_roots',side_effect=lambda:self.roots),
            patch.object(room_bindings,'catalog',side_effect=lambda:copy.deepcopy(self.catalog)),
        ):
            change.start();self.addCleanup(change.stop)
        self.world='ROOMS\nZZ_A01 : ZZ_A02\nZZ_A02 : ZZ_A01 : SHELTER\nEND ROOMS\n\nCREATURES\nZZ_A01 : 0-Lizard\nEND CREATURES\nCONDITIONAL LINKS\nWhite : ZZ_A01 : ZZ_A02\nEND CONDITIONAL LINKS\n'
        self.text(self.owner/'world/zz/world_zz.txt',self.world)
        self.text(self.owner/'world/zz/properties.txt','Palette: 9010\nRoom Setting Templates: Rain\n')
        self.text(self.owner/'world/zz/displayname.txt','My Region\n')
        self.text(self.owner/'world/zz/zz_settingstemplate_rain.txt','Palette: 9011\nEffects: Rain-0.2-0-0\n')
        self.text(self.owner/'world/zz/map_zz.txt','ZZ_A01: 1,1\nZZ_A02: 2,2\n')
        self.image(self.owner/'world/zz/map_zz.png','gray')
        for index in (9010,9011):self.image(self.owner/'palettes'/('palette'+str(index)+'.png'),'blue')
        for row in self.rows:
            source=self.owner/'world/zz-rooms'/row['name'];row['geometryPath']=str(source.with_suffix('.txt'))
            self.text(source.with_suffix('.txt'),'\n'.join([row['name'],'4*4|-1|0','','0,0','','','','','','1|1|1|0,0'])+'\n')
            self.text(Path(str(source)+'_settings.txt'),'Template: ZZ_SettingsTemplate_Rain\n')
            self.image(Path(str(source)+'_1.png'),'white')
        self.text(self.owner/'world/zz/private-notes.txt','must not export')
        self.text(self.owner/'src/private.cs','must not export')
        self.text(self.owner/'world/other/world_other.txt','must not export')

    def text(self,path,text):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,'utf-8')
    def image(self,path,color):path.parent.mkdir(parents=True,exist_ok=True);Image.new('RGB',(2,2),color).save(path)
    def archive(self,project_ids=()):
        result=region_packages.build('ZZ',self.metadata,project_ids)
        return zipfile.ZipFile(storage.EXPORTS/Path(result['url']).name)

    def test_complete_world_templates_map_and_assets_survive_without_unrelated_files(self):
        before={str(p):p.read_bytes() for p in self.owner.rglob('*') if p.is_file()}
        preview=region_packages.inspect('ZZ');self.assertTrue(preview['ok'],preview)
        with self.archive() as archive:
            self.assertEqual(archive.read('world/zz/world_zz.txt').decode().splitlines(),self.world.splitlines())
            names=set(archive.namelist());self.assertIn('world/zz/map_zz.png',names)
            self.assertIn('world/zz/zz_settingstemplate_rain.txt',names)
            self.assertIn('palettes/palette9011.png',names)
            self.assertEqual(archive.read('modify/world/regions.txt'),b'[ADD]ZZ\n')
            self.assertFalse(any('other' in name or 'private' in name or name.endswith(('.cs','.dll','.log')) for name in names))
            self.assertNotIn('modinfo.json',names)
            manifest=json.loads(archive.read('region-manifest.json'));self.assertEqual(manifest['rooms'],['ZZ_A01','ZZ_A02'])
            self.assertEqual(manifest['dependencies'],[dict(id='author.map',name='Author map')])
            self.assertEqual({item['path'] for item in manifest['files']},names-{'region-manifest.json'})
            self.assertNotIn(str(self.root),json.dumps(manifest))
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.owner.rglob('*') if p.is_file()})

    def test_disabled_region_and_missing_camera_template_or_palette_are_blocked(self):
        for relative in ('world/zz-rooms/ZZ_A01_1.png','world/zz/zz_settingstemplate_rain.txt','palettes/palette9011.png'):
            path=self.owner/relative;content=path.read_bytes();path.unlink()
            result=region_packages.inspect('ZZ');self.assertFalse(result['ok'],relative)
            with self.assertRaises(ValueError):self.archive()
            path.write_bytes(content)
        self.roots=[self.assets]
        self.assertFalse(region_packages.inspect('ZZ')['ok'])

    def test_enabled_override_and_settings_variants_win(self):
        override=self.assets/'mods/override';override.mkdir(parents=True)
        (override/'modinfo.json').write_text(json.dumps(dict(id='map.patch',name='Patch',requirements=['author.map'])),'utf-8')
        self.text(override/'world/zz-rooms/ZZ_A01_settings.txt','Template: NONE\nEffects: ZeroG-0.25-0-0\n')
        self.text(override/'world/zz-rooms/ZZ_A01_settings-White.txt','Template: NONE\nPalette: 9011\n')
        self.roots.insert(0,override)
        with self.archive() as archive:
            self.assertIn(b'ZeroG-0.25',archive.read('world/zz-rooms/ZZ_A01_settings.txt'))
            self.assertIn('world/zz-rooms/ZZ_A01_settings-White.txt',archive.namelist())
            self.assertEqual({item['id'] for item in json.loads(archive.read('region-manifest.json'))['dependencies']},{'author.map','map.patch'})

    def test_decal_and_ambient_references_are_precise(self):
        data='~'.join(['0']*11+['my-decal'])
        self.text(self.owner/'world/zz-rooms/ZZ_A01_settings.txt','Template: NONE\nPlacedObjects: CustomDecal><0><0><'+data+'\nAmbientSounds: OMNI><custom-loop.ogg><0><0><1><1\n')
        self.image(self.owner/'decals/my-decal.png','red');self.image(self.owner/'decals/not-used.png','green')
        self.text(self.owner/'soundeffects/ambient/custom-loop.ogg','OggS'+'\0'*40)
        with self.archive() as archive:
            self.assertIn('decals/my-decal.png',archive.namelist())
            self.assertIn('soundeffects/ambient/custom-loop.ogg',archive.namelist())
            self.assertNotIn('decals/not-used.png',archive.namelist())
        (self.owner/'decals/my-decal.png').unlink()
        self.assertFalse(region_packages.inspect('ZZ')['ok'])

    def test_other_local_projects_are_not_silently_included(self):
        project=dict(projectId='mine',roomBinding=dict(region='ZZ',ai='ZZ_A01',entry='ZZ_A02',entryMode='copy',oracleId='mine',aiNode=0,entryNode=0))
        self.text(storage.PROJECTS/'mine/project.json',json.dumps(project))
        self.assertFalse(region_packages.choices()['regions'][0]['available'])
        self.assertFalse(region_packages.inspect('ZZ')['ok'])
        self.assertTrue(region_packages.inspect('ZZ',['mine'])['ok'])
        with self.archive(['mine']) as archive:self.assertNotIn('project.json',archive.namelist())
        with self.assertRaises(ValueError):region_packages.build('TEST',self.metadata)

    def test_missing_declared_mod_dependency_blocks(self):
        (self.owner/'modinfo.json').write_text(json.dumps(dict(id='author.map',name='Author map',requirements=['missing.framework'])),'utf-8')
        result=region_packages.inspect('ZZ');self.assertFalse(result['ok']);self.assertIn('missing.framework',result['blockers'][0])

    def test_merged_world_and_only_actual_patch_dependencies(self):
        merged=self.assets/'mergedmods';patch_mod=self.assets/'mods/patch'
        self.text(patch_mod/'modinfo.json',json.dumps(dict(id='map.patch',name='Patch')))
        self.text(patch_mod/'modify/world/zz/world_zz.txt','[ADD]// patch marker\n')
        final=self.world+'// merged current world\n';self.text(merged/'world/zz/world_zz.txt',final)
        self.roots=[merged,patch_mod,self.owner,self.assets]
        with self.archive() as archive:
            self.assertEqual(archive.read('world/zz/world_zz.txt').decode().splitlines(),final.splitlines())
            dependencies=json.loads(archive.read('region-manifest.json'))['dependencies']
            self.assertEqual({item['id'] for item in dependencies},{'author.map','map.patch'})
            self.assertNotIn('modify/world/zz/world_zz.txt',archive.namelist())

    def test_gate_requirements_are_filtered_without_overwriting_global_locks(self):
        name='GATE_ZZ_SU';prefix=self.owner/'world/gates'/name
        self.text(prefix.with_suffix('.txt'),'\n'.join([name,'4*4|-1|0','','0,0','','','','','','1|1|1|0,0'])+'\n')
        self.text(Path(str(prefix)+'_settings.txt'),'Template: NONE\n')
        self.image(Path(str(prefix)+'_1.png'),'white')
        self.rows.append(dict(name=name,connections=['ZZ_A01'],tags='GATE',geometryPath=str(prefix.with_suffix('.txt'))))
        world=self.world.replace('END ROOMS',name+' : ZZ_A01 : GATE\nEND ROOMS')
        self.text(self.owner/'world/zz/world_zz.txt',world)
        self.text(self.owner/'world/gates/locks.txt',name+' : 2 : 3\nGATE_OTHER : 5 : 5\n')
        with self.archive() as archive:
            self.assertEqual(archive.read('modify/world/gates/locks.txt'),b'[ADD]GATE_ZZ_SU : 2 : 3\n')
            self.assertNotIn('world/gates/locks.txt',archive.namelist())
            self.assertIn('world/gates/GATE_ZZ_SU_1.png',archive.namelist())

    def test_unparsed_room_or_unsafe_decal_does_not_make_partial_package(self):
        world=self.world.replace('END ROOMS','ZZ_BAD-2 : ZZ_A01\nEND ROOMS')
        self.text(self.owner/'world/zz/world_zz.txt',world)
        self.assertFalse(region_packages.inspect('ZZ')['ok'])
        self.text(self.owner/'world/zz/world_zz.txt',self.world)
        data='~'.join(['0']*11+['../secret'])
        self.text(self.owner/'world/zz-rooms/ZZ_A01_settings.txt','Template: NONE\nPlacedObjects: CustomDecal><0><0><'+data+'\n')
        self.assertFalse(region_packages.inspect('ZZ')['ok'])

    def test_plain_metadata_is_optional(self):
        result=region_packages.build('ZZ')
        self.assertEqual(result['manifest']['metadata'],dict(name='ZZ'))

    def selected_project(self):
        project=dict(projectId='mine',editor={'externalRoomTools':True},design=dict(roomPaletteMode='room',roomGravityMode='room',entryGravityMode='room'),roomBinding=dict(region='ZZ',ai='ZZ_A01',entry='ZZ_A02',entryMode='copy',oracleId='mine',aiNode=0,entryNode=0))
        self.text(storage.PROJECTS/'mine/project.json',json.dumps(project))
        for name in ('ZZ_A01','ZZ_A02'):
            base=storage.PROJECTS/'mine/rooms/rendered'/name
            self.text(base.with_suffix('.txt'),'\n'.join([name,'4*4|-1|0','','0,0|10,10','','','','','','1|1|1|0,0'])+'\n')
            self.text(base.with_name(name+'_settings.txt'),'Template: NONE\nPalette: 9010\n')
            self.image(base.with_name(name+'_1.png'),'red')
            self.image(base.with_name(name+'_2.png'),'green')
        return project

    def test_selected_project_cache_geometry_and_all_cameras_reach_region_export(self):
        project=self.selected_project()
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with room_source_choices.resolution_scope([project]):
            with self.archive(['mine']) as archive:
                self.assertIn('world/zz-rooms/ZZ_A01_2.png',archive.namelist())
                self.assertEqual(archive.read('world/zz-rooms/ZZ_A01_1.png'),(storage.PROJECTS/'mine/rooms/rendered/ZZ_A01_1.png').read_bytes())
                self.assertEqual(archive.read('world/zz/world_zz.txt').decode().splitlines(),self.world.splitlines())
                self.assertNotIn('project.json',archive.namelist())
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file() and not p.is_relative_to(storage.EXPORTS)})

    def test_selected_geometry_exit_mismatch_blocks_before_output(self):
        project=self.selected_project()
        path=storage.PROJECTS/'mine/rooms/rendered/ZZ_A01.txt'
        path.write_text(path.read_text('utf-8').replace('1|1|1|0,0','1|2|1|0,0|0,0'),'utf-8')
        with room_source_choices.resolution_scope([project]):
            with self.assertRaisesRegex(ValueError,'出口数量'):
                self.archive(['mine'])
        self.assertFalse(storage.EXPORTS.exists())

    def test_selected_palette_applies_to_region_properties_and_rooms(self):
        project=self.selected_project()
        palette=storage.PROJECTS/'mine/rooms/palettes/palette9010.png'
        self.image(palette,'red')
        report=room_source_choices.preflight([project])
        row=next(row for row in report['assets'] if row['relative']=='palettes/palette9010.png')
        version=next(version['id'] for version in row['versions'] if version['origin']=='project')
        payload=dict(snapshotToken=report['snapshotToken'],assetChoices={row['key']:version})
        with room_source_choices.resolution_scope([project],payload):
            with self.archive(['mine']) as archive:
                self.assertEqual(archive.read('palettes/palette9010.png'),palette.read_bytes())

    def test_region_rejects_unverified_path_as_a_choice(self):
        project=self.selected_project()
        with room_source_choices.resolution_scope([project]):
            collector=region_packages.Collector()
            with self.assertRaisesRegex(ValueError,'版本无法确认'):
                collector.add('world/zz-rooms/ZZ_A01.txt',self.owner/'world/zz-rooms/ZZ_A01.txt',('mine','ZZ_A01'))

    def test_selected_settings_keep_their_variants_and_properties(self):
        project=self.selected_project()
        cache=storage.PROJECTS/'mine/rooms/rendered'
        self.text(cache/'ZZ_A01_settings-White.txt','Template: NONE\nPalette: 9011\n')
        self.text(cache/'ZZ_A01_properties.txt','SomeRoomProperty: 1\n')
        self.text(self.owner/'world/zz-rooms/ZZ_A01_settings-Yellow.txt','Template: NONE\n')
        with room_source_choices.resolution_scope([project]):
            with self.archive(['mine']) as archive:
                self.assertEqual(archive.read('world/zz-rooms/ZZ_A01_settings-White.txt'),(cache/'ZZ_A01_settings-White.txt').read_bytes())
                self.assertIn('world/zz-rooms/ZZ_A01_properties.txt',archive.namelist())
                self.assertNotIn('world/zz-rooms/ZZ_A01_settings-Yellow.txt',archive.namelist())


if __name__=='__main__':unittest.main()
