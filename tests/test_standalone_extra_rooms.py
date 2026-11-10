import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import project_packages
import room_bindings
import server
import standalone
import storage


class ExtraRoomExportTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.data=self.root/'data';self.local=self.data/'local-mod'
        self.game=self.root/'game';self.assets=self.game/'RainWorld_Data/StreamingAssets'
        self.assets.mkdir(parents=True);self.local.mkdir(parents=True);(self.game/'RainWorld.exe').touch()
        self.project=server.default();self.project.update(projectId='selected',name='Selected',
            roomBinding=dict(region='ZX',ai='ZX_AI',entry='ZX_ENTRY',oracleId='selected',entryMode='copy',aiNode=0,entryNode=0))
        self.rows=[self.row('ZX_AI',['ZX_ENTRY','ZX_EXTRA']),self.row('ZX_ENTRY',['ZX_AI','ZX_UNUSED']),
                   self.row('ZX_EXTRA',['ZX_AI','ZX_UNUSED']),self.row('ZX_UNUSED',['ZX_ENTRY','ZX_EXTRA'])]
        self.package=dict(schema=project_packages.LOCAL_SCHEMA,projectId='selected',rooms=self.rows,regions=[],palettes=[],files=[])
        self.request=dict(id='test.extra-rooms',name='Extra rooms',authors='Test',description='',version='0.1.0',
            projects=['selected'],dialogue=False,pearls=False,broadcasts=False,workPearls=False,projections=False)
        self.roots=[self.assets];self.catalog=dict(regions=[],activeMods=[])
        def project_path(pid):return self.data/'projects'/pid/'project.json'
        for target,attribute,value in (
            (storage,'DATA',self.data),(storage,'PROJECTS',self.data/'projects'),(storage,'EXPORTS',self.root/'exports'),
            (storage,'GAME',self.game),(storage,'LINKS',[]),(storage,'RUNTIME',self.data/'runtime'),
        ):
            change=patch.object(target,attribute,value);change.start();self.addCleanup(change.stop)
        for change in (
            patch.object(storage,'target_mod',return_value=self.local),
            patch.object(storage,'project_file',side_effect=project_path),
            patch.object(storage,'binding',return_value=None),
            patch.object(storage,'load_project',side_effect=lambda pid:copy.deepcopy(self.project)),
            patch.object(standalone.room_editor,'ensure_synced'),
            patch.object(standalone.projections,'listing',return_value=[]),
            patch.object(standalone,'compile_runtime',side_effect=self.compile),
            patch.object(project_packages,'load_metadata',side_effect=lambda pid:copy.deepcopy(self.package)),
            patch.object(project_packages,'rendered_source',side_effect=lambda pid,name:self.source(name)),
            patch.object(project_packages,'palette_source',side_effect=self.palette),
            patch.object(room_bindings,'_asset_roots',side_effect=lambda:self.roots+[self.local]),
            patch.object(room_bindings,'enabled_asset_roots',side_effect=lambda:self.roots),
            patch.object(room_bindings,'catalog',side_effect=lambda:copy.deepcopy(self.catalog)),
        ):
            change.start();self.addCleanup(change.stop)
        for row in self.rows:self.render(self.source(row['name']),row['name'])
        world=self.local/'world/zx/world_zx.txt';world.parent.mkdir(parents=True)
        world.write_text('ROOMS\n'+'\n'.join(row['name']+' : '+', '.join(row['connections']) for row in self.rows)+'\nEND ROOMS\n','utf-8')
        project_path('selected').write_text(json.dumps(self.project),'utf-8')
        (project_path('selected').parent/'room-package.json').write_text(json.dumps(self.package),'utf-8')
        self.image(self.assets/'palettes/palette26.png','gray')

    def row(self,name,connections):return dict(name=name,region=name.split('_')[0],kind='extra',connections=connections,tags='',sourceAvailable=True)
    def source(self,name):return self.data/'projects/selected/rooms/rendered'/name
    def palette(self,pid,index):
        candidate=self.data/'projects'/pid/'rooms/palettes'/('palette'+str(index)+'.png')
        return candidate if candidate.is_file() else None
    def image(self,path,color):
        path.parent.mkdir(parents=True,exist_ok=True);Image.new('RGB',(2,2),color).save(path)
    def render(self,prefix,name,palette=None):
        prefix.parent.mkdir(parents=True,exist_ok=True)
        prefix.with_suffix('.txt').write_text('\n'.join([name,'4*4|-1|0','','0,0','','','','','','1|2|1|0,0|0,0'])+'\n','utf-8')
        Path(str(prefix)+'_settings.txt').write_text('Template: NONE\n'+('Palette: '+str(palette)+'\n' if palette else ''),'utf-8')
        self.image(Path(str(prefix)+'_1.png'),'white')
    def compile(self,stage,sources,meta,projects):
        suffix=hashlib.sha256(meta['id'].encode()).hexdigest()[:12]
        file=stage/'plugins'/('IteratorContent_'+suffix+'.dll');file.parent.mkdir();file.write_bytes(b'MZ isolated fixture')
        return suffix
    def archive(self,extra=None):
        request={**self.request}
        if extra is not None:request['extraRooms']=extra
        result=standalone.build(request,server,save_preferences=False)
        return zipfile.ZipFile(storage.EXPORTS/Path(result['url']).name)
    def read(self,archive,path):return archive.read(self.request['id']+'/'+path)

    def test_default_still_exports_only_current_two(self):
        with self.archive() as archive:
            manifest=json.loads(self.read(archive,'content-manifest.json'))
            self.assertNotIn('extraRooms',manifest)
            world=self.read(archive,'world/zx/world_zx.txt').decode()
            self.assertIn('ZX_AI : ZX_ENTRY, DISCONNECTED',world)
            self.assertNotIn('ZX_EXTRA',world)
            self.assertFalse(any('ZX_EXTRA' in name or 'ZX_UNUSED' in name for name in archive.namelist()))

    def test_explicit_extra_keeps_selected_links_only_and_no_source_mutation(self):
        before={str(f):f.read_bytes() for f in self.data.rglob('*') if f.is_file()}
        self.render(self.source('ZX_EXTRA'),'ZX_EXTRA',9100)
        self.image(self.data/'projects/selected/rooms/palettes/palette9100.png','red')
        self.image(self.data/'projects/selected/rooms/palettes/palette9101.png','blue')
        before={str(f):f.read_bytes() for f in self.data.rglob('*') if f.is_file()}
        with self.archive(['ZX_EXTRA']) as archive:
            world=self.read(archive,'world/zx/world_zx.txt').decode()
            self.assertIn('ZX_AI : ZX_ENTRY, ZX_EXTRA',world)
            self.assertIn('ZX_EXTRA : ZX_AI, DISCONNECTED',world)
            self.assertNotIn('ZX_UNUSED',world)
            manifest=json.loads(self.read(archive,'content-manifest.json'))
            self.assertEqual(manifest['selectedExtraRooms'],['ZX_EXTRA'])
            self.assertEqual(manifest['extraRooms'][0]['files'],['world/zx-rooms/ZX_EXTRA.txt','world/zx-rooms/ZX_EXTRA_settings.txt','world/zx-rooms/ZX_EXTRA_1.png'])
            self.assertIn(self.request['id']+'/palettes/palette9100.png',archive.namelist())
            self.assertFalse(any('9101' in name or 'ZX_UNUSED' in name for name in archive.namelist()))
        self.assertEqual(before,{str(f):f.read_bytes() for f in self.data.rglob('*') if f.is_file()})

    def test_invalid_unknown_duplicate_and_core_selection_rejected(self):
        for extra in (['ZX_EXTRA','ZX_EXTRA'],['ZX_UNKNOWN'],['ZX_AI'],['../escape'],{},[{}]):
            with self.subTest(extra=extra),self.assertRaises(ValueError):self.archive(extra)

    def test_conflicting_names_fail_before_compile(self):
        other=copy.deepcopy(self.project);other['projectId']='second';other['name']='Other'
        other['roomBinding'].update(ai='ZX_OTHER_AI',entry='ZX_OTHER_ENTRY')
        with self.assertRaisesRegex(ValueError,'编号重复'):
            standalone.extra_room_plan({'extraRooms':['ZX_EXTRA']},[self.project,other],
                {'selected':('ZX_AI','ZX_ENTRY'),'second':('ZX_OTHER_AI','ZX_OTHER_ENTRY')},server)

    def external(self,owner='map.test',version='newest'):
        root=self.assets/'mods'/owner;directory=root/version if version else root
        directory.mkdir(parents=True);(root/'modinfo.json').write_text(json.dumps({'id':owner,'name':'Owner map'}),'utf-8')
        prefix=directory/'world/su-rooms/SU_A01';self.render(prefix,'SU_A01')
        self.roots=[directory,root,self.assets]
        self.catalog=dict(activeMods=[owner],regions=[dict(name='SU',rooms=[{**self.row('SU_A01',['ZX_AI','SU_A02']),'geometryPath':str(prefix.with_suffix('.txt'))}])])
        return prefix

    def test_external_is_remapped_and_owner_dependency_declared(self):
        prefix=self.external()
        with self.archive(['SU_A01']) as archive:
            manifest=json.loads(self.read(archive,'content-manifest.json'));row=manifest['extraRooms'][0]
            self.assertEqual((row['sourceRoom'],row['name']),('SU_A01','ZX_SU_A01'))
            self.assertEqual(row['dependency'],dict(id='map.test',name='Owner map'))
            self.assertEqual(row['connections'],['ZX_AI','DISCONNECTED'])
            self.assertIn('map.test',json.loads(self.read(archive,'modinfo.json'))['requirements'])
            self.assertFalse(any('/world/su/' in name or '/world/su-rooms/' in name for name in archive.namelist()))
            self.assertTrue(prefix.with_suffix('.txt').is_file())

    def test_disabled_source_and_conditional_links_fail(self):
        self.external();self.roots=[self.assets]
        with self.assertRaises(ValueError):self.archive(['SU_A01'])
        self.external('map.other');self.catalog['regions'][0]['rooms'][0]['conditional']=True
        with self.assertRaisesRegex(ValueError,'条件连接'):self.archive(['SU_A01'])

    def test_installed_devtools_settings_and_latest_camera_are_preserved(self):
        installed=storage.installed_mod('selected',required=False)
        prefix=installed/'world/zx-rooms/ZX_ENTRY';self.render(prefix,'ZX_ENTRY')
        settings='Template: NONE\nEffects: ZeroG-0.25-0-0\nPalette: 26\n'
        Path(str(prefix)+'_settings.txt').write_text(settings,'utf-8')
        camera=Path(str(prefix)+'_1.png');self.image(camera,'purple')
        os.utime(camera,(2000000000,2000000000))
        with self.archive(['ZX_EXTRA']) as archive:
            self.assertEqual(self.read(archive,'world/zx-rooms/ZX_ENTRY_settings.txt').decode().splitlines(),settings.splitlines())
            self.assertEqual(self.read(archive,'world/zx-rooms/ZX_ENTRY_1.png'),camera.read_bytes())

    def test_template_inheritance_is_blocked_instead_of_silently_erased(self):
        settings=Path(str(self.source('ZX_EXTRA'))+'_settings.txt')
        settings.write_text('Template: ZX_SettingsTemplate_Custom\n','utf-8')
        with self.assertRaisesRegex(ValueError,'模板依赖'):self.archive(['ZX_EXTRA'])
        settings.write_text('Palette: 26\n','utf-8')
        properties=self.local/'world/zx/properties.txt';properties.write_text('Room Setting Templates: Custom\n','utf-8')
        with self.assertRaisesRegex(ValueError,'模板依赖'):self.archive(['ZX_EXTRA'])

    def test_unused_registered_templates_have_exact_manifest_and_palette(self):
        folder=self.local/'world/zx';(folder/'properties.txt').write_text('Room Setting Templates: Empty, Blue\nPalette: 26\n','utf-8')
        (folder/'zx_settingstemplate_empty.txt').write_bytes(b'')
        (folder/'zx_settingstemplate_blue.txt').write_text('Palette: 9102\n','utf-8')
        self.image(self.local/'palettes/palette9102.png','blue')
        with self.archive(['ZX_EXTRA']) as archive:
            manifest=json.loads(self.read(archive,'content-manifest.json'))
            self.assertEqual(manifest['roomTemplates'],['world/zx/zx_settingstemplate_blue.txt','world/zx/zx_settingstemplate_empty.txt'])
            self.assertEqual(self.read(archive,'world/zx/zx_settingstemplate_empty.txt'),b'')
            self.assertIn(self.request['id']+'/palettes/palette9102.png',archive.namelist())

    def test_dlc_dependency_uses_actual_versioned_owner(self):
        self.external('watcher','v1.11.8')
        (self.assets/'GameVersion.txt').write_text('v1.11.8','utf-8')
        with self.archive(['SU_A01']) as archive:
            info=json.loads(self.read(archive,'modinfo.json'))
            self.assertEqual(info['requirements'],['warp','watcher'])
            self.assertEqual(info['requirements_names'][1],standalone.official_requirement('watcher')[1])

    def test_audit_rejects_unselected_file_connection_and_forged_allowlist(self):
        with self.archive(['ZX_EXTRA']) as archive,tempfile.TemporaryDirectory() as folder:
            archive.extractall(folder);stage=Path(folder)/self.request['id']
            extra=stage/'world/zx-rooms/ZX_SECRET.txt';extra.write_text('secret','utf-8')
            with self.assertRaisesRegex(ValueError,'非运行文件'):standalone.audit(stage,['selected'],['ZX_EXTRA'])
            extra.unlink();file=stage/'world/zx/world_zx.txt';original=file.read_text('utf-8')
            file.write_text(original.replace('ZX_EXTRA : ZX_AI, DISCONNECTED','ZX_EXTRA : ZX_AI, ZX_UNSELECTED'),'utf-8')
            with self.assertRaisesRegex(ValueError,'未选择'):standalone.audit(stage,['selected'],['ZX_EXTRA'])
            file.write_text(original,'utf-8')
            manifest=stage/'content-manifest.json';value=json.loads(manifest.read_text('utf-8'))
            value['extraRooms'][0]['files'].append('world/zx-rooms/ZX_SECRET.txt');standalone.dump(manifest,value)
            with self.assertRaisesRegex(ValueError,'白名单'):standalone.audit(stage,['selected'],['ZX_EXTRA'])


if __name__=='__main__':unittest.main()
