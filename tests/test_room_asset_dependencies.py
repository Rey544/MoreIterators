import io
import json
import os
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import project_packages
import project_lifecycle
import room_asset_dependencies
import room_bindings
import room_cleanup
import standalone
import storage


def settings(decal='my-decal',sound='custom-loop.wav'):
    return ('PlacedObjects: CustomDecal><0><0><'+'~'.join(['0']*11+[decal])+'\n'+
            'AmbientSounds: OMNI><'+sound+'><0><0><1><1\n')


def assets(root,color='red'):
    image=root/'decals/my-decal.png';image.parent.mkdir(parents=True,exist_ok=True);Image.new('RGB',(2,2),color).save(image)
    sound=root/'soundeffects/ambient/custom-loop.wav';sound.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(sound),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(8000);stream.writeframes(b'\0\0'*16)
    return image,sound


def terrain_assets(root,names=('custom','fade','rot'),color='red'):
    result={}
    for name in names:
        file=root/'terrainpalettes'/(name+'.png');file.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGB',(4,5),color).save(file);result[name]=file
    return result


class RoomAssetTests(unittest.TestCase):
    def fixture(self,kind='project'):
        if kind=='project':
            from test_project_packages import ProjectPackageTests
            result=ProjectPackageTests()
        else:
            from test_standalone_extra_rooms import ExtraRoomExportTests
            result=ExtraRoomExportTests()
        result.setUp();self.addCleanup(result.doCleanups)
        return result

    def test_project_roundtrip_deploy_and_delete_restore_exact_referenced_assets(self):
        f=self.fixture();file=f.local/'world/xx-rooms/XX_AI_settings.txt'
        file.write_text(file.read_text('utf-8')+settings(),'utf-8');image,sound=assets(f.local)
        originals={str(path.relative_to(f.local)).replace('\\','/'):path.read_bytes() for path in (image,sound)}
        Image.new('RGB',(2,2),'green').save(image.with_name('not-selected.png'))
        payload=f.payload();files=f.unpack(payload)
        for relative,content in originals.items():self.assertEqual(files['assets/'+relative],content)
        self.assertNotIn('assets/decals/not-selected.png',files)
        f.target();project=project_packages.import_package(payload,f.server)['project']
        for relative,content in originals.items():self.assertEqual(project_packages.asset_source('selected',relative).read_bytes(),content)
        prepared=project_packages.before_deploy(project,f.server);project_packages.write_deploy_assets(prepared)
        for relative,content in originals.items():self.assertEqual((f.local/relative).read_bytes(),content)
        registry=storage.RUNTIME/'creator/registry.json';registry.parent.mkdir(parents=True)
        registry.write_text(json.dumps([storage.registry_record(project,'XX_AI','XX_ENTRY','selected_oracle')]),'utf-8')
        with patch.object(room_cleanup,'_running_game',return_value=False):
            deleted=project_lifecycle.delete({'projectId':'selected'},f.server)
            for relative in originals:self.assertFalse((f.local/relative).exists())
            project_lifecycle.restore(deleted['token'],f.server)
        for relative,content in originals.items():self.assertEqual((f.local/relative).read_bytes(),content)

    def test_missing_dependency_blocks_export_and_incomplete_zip_blocks_import(self):
        f=self.fixture();file=f.local/'world/xx-rooms/XX_AI_settings.txt';file.write_text(file.read_text()+settings(),'utf-8')
        with self.assertRaisesRegex(ValueError,'素材缺失'):f.payload()
        assets(f.local);payload=f.payload();files=f.unpack(payload);del files['assets/soundeffects/ambient/custom-loop.wav']
        manifest=json.loads(files['manifest.json']);manifest['files']=project_packages._records({p:v for p,v in files.items() if p!='manifest.json'});files['manifest.json']=project_packages._json(manifest)
        with self.assertRaisesRegex(ValueError,'素材缺失'):project_packages.inspect_import(f.archive(files),f.server)

    def test_installed_asset_revision_wins_and_conflicting_unowned_output_is_preserved(self):
        f=self.fixture();file=f.local/'world/xx-rooms/XX_AI_settings.txt';file.write_text(file.read_text()+settings(),'utf-8')
        assets(f.local);image,_=assets(f.installed,'blue');os.utime(image,(2000000000,2000000000))
        payload=f.payload();self.assertEqual(f.unpack(payload)['assets/decals/my-decal.png'],image.read_bytes())
        f.target();project=project_packages.import_package(payload,f.server)['project']
        assets(f.local,'green');before=(f.local/'decals/my-decal.png').read_bytes()
        
        imported=project_packages.asset_source('selected','decals/my-decal.png');os.utime(imported,(2100000000,2100000000))
        with self.assertRaisesRegex(ValueError,'未归属'):project_packages.before_deploy(project,f.server)
        self.assertEqual((f.local/'decals/my-decal.png').read_bytes(),before)

    def test_standalone_extra_room_includes_assets_and_audit_rejects_missing_or_unreferenced(self):
        f=self.fixture('standalone');file=Path(str(f.source('ZX_EXTRA'))+'_settings.txt');file.write_text(file.read_text()+settings(),'utf-8')
        image,sound=assets(f.local);image.with_name('private.png').write_bytes(image.read_bytes())
        with f.archive(['ZX_EXTRA']) as archive,tempfile.TemporaryDirectory() as folder:
            self.assertEqual(f.read(archive,'decals/my-decal.png'),image.read_bytes())
            self.assertEqual(f.read(archive,'soundeffects/ambient/custom-loop.wav'),sound.read_bytes())
            self.assertFalse(any(name.endswith('/private.png') for name in archive.namelist()))
            archive.extractall(folder);stage=Path(folder)/f.request['id'];copy=stage/'decals/private.png';copy.write_bytes(image.read_bytes())
            with self.assertRaisesRegex(ValueError,'非运行文件'):standalone.audit(stage,['selected'],['ZX_EXTRA'])
            copy.unlink();(stage/'soundeffects/ambient/custom-loop.wav').unlink()
            with self.assertRaisesRegex(ValueError,'附加素材缺失'):standalone.audit(stage,['selected'],['ZX_EXTRA'])

    def test_disabled_assets_and_unsafe_or_invalid_files_do_not_silently_pass(self):
        f=self.fixture('standalone');file=Path(str(f.source('ZX_EXTRA'))+'_settings.txt');file.write_text(file.read_text()+settings(),'utf-8')
        assets(f.root/'disabled-mod')
        with self.assertRaisesRegex(ValueError,'素材缺失'):f.archive(['ZX_EXTRA'])
        image,sound=assets(f.local);sound.write_bytes(b'not an audio file')
        with self.assertRaisesRegex(ValueError,'WAV'):f.archive(['ZX_EXTRA'])
        with self.assertRaisesRegex(ValueError,'名称无效'):room_asset_dependencies.references(settings('../private'))
        with self.assertRaisesRegex(ValueError,'文件名称无效'):room_asset_dependencies.references(settings(sound='malware.exe'))
        with self.assertRaisesRegex(ValueError,'无法解析'):room_asset_dependencies.references('PlacedObjects: CustomDecal><0><0><bad\n')

    def test_same_named_assets_from_two_rooms_conflict_instead_of_last_writer_wins(self):
        f=self.fixture('standalone');f.external('custom.map');external=f.roots[0]
        
        for prefix,owner in [(f.source('ZX_AI'),f.local),(external/'world/su-rooms/SU_A01',external)]:
            file=Path(str(prefix)+'_settings.txt');file.write_text(file.read_text()+settings(),'utf-8');assets(owner,'red' if owner==f.local else 'blue')
        with self.assertRaisesRegex(ValueError,'同名'):f.archive(['SU_A01'])

    def test_reapply_prunes_unique_old_asset_but_keeps_shared_local_and_installed_copy(self):
        f=self.fixture();file=f.local/'world/xx-rooms/XX_AI_settings.txt';file.write_text(file.read_text()+settings(),'utf-8');assets(f.local)
        payload=f.payload();f.target();project=project_packages.import_package(payload,f.server)['project']
        project_packages.write_deploy_assets(project_packages.before_deploy(project,f.server))
        marker=f.local/project_packages.OUTPUT_MANIFEST;manifest=json.loads(marker.read_text('utf-8'))
        manifest['projects']['other']=['decals/my-decal.png'];marker.write_text(json.dumps(manifest),'utf-8')
        shutil.copytree(f.local,f.installed,dirs_exist_ok=True)
        current=f.local/'world/xx-rooms/XX_AI_settings.txt'
        current.write_text('Template: NONE\nPalette: 9100\n','utf-8');os.utime(current,(2000000000,2000000000))
        result=project_packages.write_deploy_assets(project_packages.before_deploy(project,f.server))
        self.assertIn('soundeffects/ambient/custom-loop.wav',result['removed'])
        for root in (f.local,f.installed):
            self.assertFalse((root/'soundeffects/ambient/custom-loop.wav').exists())
            self.assertTrue((root/'decals/my-decal.png').is_file())

    def test_named_terrain_palettes_follow_native_paths_not_numbered_palette_paths(self):
        text='Palette: 25\nFadePalette: 26, 0.5\nTerrainPalette: Custom\nTerrainFadePalette: 123, 0.25, 0.75\n'
        self.assertEqual(standalone.room_palette_ids(text),{25,26})
        self.assertEqual(room_asset_dependencies.references(text),[
            ('terrainpalettes/custom.png',),('terrainpalettes/123.png',),('terrainpalettes/rot.png',)])
        optional=room_asset_dependencies.optional_references(text)
        self.assertIn(('terrainpalettes/custom_echo.png','terrainpalettes/default_echo.png'),optional)
        self.assertIn(('terrainpalettes/123_rain.png',),optional)
        self.assertEqual(room_asset_dependencies.references('TerrainPalette: NO PALETTE\n'),[])
        self.assertEqual(room_asset_dependencies.references('TerrainPalette: NO PALETTE\nTerrainFadePalette: unused, 0.5\n'),[])
        for value in ('../escape','bad/name','C:\\private','','x'*181):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'名称无效'):
                room_asset_dependencies.references('TerrainPalette: '+value+'\nPalette: 26\n')

    def test_project_terrain_assets_roundtrip_deploy_and_reject_missing_required_or_unrelated(self):
        f=self.fixture();file=f.local/'world/xx-rooms/XX_AI_settings.txt'
        file.write_text(file.read_text()+'TerrainPalette: Custom\nTerrainFadePalette: fade, 0.25, 0.75\n','utf-8')
        sources=terrain_assets(f.local,('custom','fade','rot','custom_rain','custom_echo','default_echo','unrelated'))
        payload=f.payload();files=f.unpack(payload)
        for name in ('custom','fade','rot','custom_rain','custom_echo','default_echo'):
            self.assertEqual(files['assets/terrainpalettes/'+name+'.png'],sources[name].read_bytes())
        self.assertNotIn('assets/terrainpalettes/unrelated.png',files)
        self.assertNotIn('palettes/palette123.png',files)
        changed=dict(files);del changed['assets/terrainpalettes/custom.png']
        with self.assertRaisesRegex(ValueError,'素材缺失'):project_packages.inspect_import(f.archive(changed),f.server)
        changed=dict(files);changed['assets/terrainpalettes/unrelated.png']=sources['unrelated'].read_bytes()
        with self.assertRaisesRegex(ValueError,'未声明'):project_packages.inspect_import(f.archive(changed),f.server)
        original={name:path.read_bytes() for name,path in sources.items() if name!='unrelated'}
        f.target();project=project_packages.import_package(payload,f.server)['project']
        project_packages.write_deploy_assets(project_packages.before_deploy(project,f.server))
        for name,content in original.items():self.assertEqual((f.local/'terrainpalettes'/ (name+'.png')).read_bytes(),content)

    def test_terrain_required_missing_corrupt_or_disabled_blocks_export_optional_absence_is_valid(self):
        f=self.fixture('standalone');settings_file=Path(str(f.source('ZX_EXTRA'))+'_settings.txt')
        settings_file.write_text(settings_file.read_text()+'TerrainPalette: custom\n','utf-8')
        terrain_assets(f.root/'disabled',('custom','rot'))
        with self.assertRaisesRegex(ValueError,'素材缺失'):f.archive(['ZX_EXTRA'])
        sources=terrain_assets(f.local,('custom','rot'))
        with f.archive(['ZX_EXTRA']) as archive:
            self.assertEqual(f.read(archive,'terrainpalettes/custom.png'),sources['custom'].read_bytes())
            self.assertFalse(any('_rain.png' in n or '_echo.png' in n for n in archive.namelist()))
        original=sources['custom'].read_bytes();sources['custom'].write_bytes(b'not a png')
        with self.assertRaisesRegex(ValueError,'图损坏'):f.archive(['ZX_EXTRA'])
        sources['custom'].write_bytes(original);sources['rot'].unlink()
        with self.assertRaisesRegex(ValueError,'素材缺失'):f.archive(['ZX_EXTRA'])

    def test_standalone_terrain_enabled_override_case_and_echo_fallback_order(self):
        f=self.fixture('standalone');prefix=f.external();owner=f.roots[0]
        settings_file=Path(str(prefix)+'_settings.txt');settings_file.write_text('Template: NONE\nTerrainPalette: CUSTOM\n','utf-8')
        terrain_assets(owner,('custom','rot','default_echo'),'red')
        override=f.assets/'mods/palette-patch/newest';override.mkdir(parents=True)
        (override.parent/'modinfo.json').write_text(json.dumps(dict(id='palette.patch',name='Palette patch')),'utf-8')
        patched=terrain_assets(override,('CUSTOM','custom_echo'),'blue');f.roots.insert(0,override)
        with f.archive(['SU_A01']) as archive,tempfile.TemporaryDirectory() as folder:
            self.assertEqual(f.read(archive,'terrainpalettes/custom.png'),patched['CUSTOM'].read_bytes())
            self.assertEqual(f.read(archive,'terrainpalettes/custom_echo.png'),patched['custom_echo'].read_bytes())
            self.assertIn(f.request['id']+'/terrainpalettes/default_echo.png',archive.namelist())
            archive.extractall(folder);stage=Path(folder)/f.request['id']
            (stage/'terrainpalettes/custom.png').unlink()
            with self.assertRaisesRegex(ValueError,'附加素材缺失'):standalone.audit(stage,['selected'],['SU_A01'])

    def test_terrain_optional_fallback_checks_enabled_named_echo_before_authored_default(self):
        f=self.fixture('standalone');text='TerrainPalette: custom\n'
        terrain_assets(f.local,('custom','rot','default_echo'),'red')
        terrain_assets(f.assets,('custom_echo',),'blue')
        found=standalone.room_settings_assets(f.project,f.source('ZX_AI'),text)
        self.assertEqual(found['terrainpalettes/custom_echo.png'],f.assets/'terrainpalettes/custom_echo.png')
        self.assertIn('terrainpalettes/default_echo.png',found)

    def test_region_terrain_template_and_numeric_name_keep_all_native_variants(self):
        from test_region_packages import RegionPackageTests
        f=RegionPackageTests();f.setUp();self.addCleanup(f.doCleanups)
        template=f.owner/'world/zz/zz_settingstemplate_rain.txt'
        template.write_text(template.read_text()+'TerrainPalette: custom\n','utf-8')
        settings_file=f.owner/'world/zz-rooms/ZZ_A01_settings.txt'
        settings_file.write_text(settings_file.read_text()+'TerrainFadePalette: 123, 0.5\n','utf-8')
        sources=terrain_assets(f.owner,('custom','123','rot','custom_rain','123_echo','default_echo','unrelated'))
        with f.archive() as archive:
            for name in ('custom','123','rot','custom_rain','123_echo','default_echo'):
                self.assertEqual(archive.read('terrainpalettes/'+name+'.png'),sources[name].read_bytes())
            self.assertNotIn('palettes/palette123.png',archive.namelist())
            self.assertNotIn('terrainpalettes/unrelated.png',archive.namelist())
        sources['custom'].unlink()
        with self.assertRaisesRegex(ValueError,'素材'):f.archive()


if __name__=='__main__':unittest.main()
