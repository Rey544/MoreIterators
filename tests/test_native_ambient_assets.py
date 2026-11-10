import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import project_packages
import region_packages
import room_asset_dependencies as assets
import room_bindings
import standalone


SOUNDS=('AM_IND-SuperStructure.ogg','AM_WIN-StrongWnd2.ogg','SO_SFX-DataTrans2.ogg')


class NativeAmbientTests(unittest.TestCase):
    def fixture(self,kind='standalone'):
        if kind=='project':
            from test_project_packages import ProjectPackageTests
            result=ProjectPackageTests()
        elif kind=='region':
            from test_region_packages import RegionPackageTests
            result=RegionPackageTests()
        else:
            from test_standalone_extra_rooms import ExtraRoomExportTests
            result=ExtraRoomExportTests()
        result.setUp();self.addCleanup(result.doCleanups)
        if kind=='project':
            result.assets=result.game/'RainWorld_Data/StreamingAssets'
            change=patch.object(room_bindings,'enabled_asset_roots',side_effect=lambda:[result.local,result.installed,result.external,result.assets])
            change.start();self.addCleanup(change.stop)
        return result

    def native(self,f,names=SOUNDS):
        folder=f.assets/'AssetBundles';folder.mkdir(parents=True,exist_ok=True)
        bundle=folder/'loadedsoundeffects_ambient';bundle.write_bytes(b'UnityFS\0'+bytes(64))
        manifest=folder/'loadedsoundeffects_ambient.manifest'
        manifest.write_text('ManifestFileVersion: 0\nClassTypes:\n- Class: 83\n  Script: {instanceID: 0}\nAssets:\n'+
                            ''.join('- Assets/LoadedSoundEffects/Ambient/'+name+'\n' for name in names)+'Dependencies: []\n','utf-8')
        for name in names:
            file=f.assets/'loadedsoundeffects/ambient'/name;file.parent.mkdir(parents=True,exist_ok=True);file.touch()
        return manifest,bundle

    def settings(self,file):
        text=file.read_text('utf-8')+'AmbientSounds: '+', '.join('OMNI><'+name+'><0><0><1><1' for name in SOUNDS)+'\n'
        file.write_text(text,'utf-8');return text

    def test_native_identity_requires_placeholder_bundle_and_exact_manifest_entry(self):
        f=self.fixture();manifest,bundle=self.native(f)
        relative='loadedsoundeffects/ambient/'+SOUNDS[0].lower();source=f.assets/relative
        self.assertTrue(assets.native_ambient_reference(relative,source))
        self.assertFalse(assets.native_ambient_reference('soundeffects/ambient/'+SOUNDS[0].lower()))
        original=manifest.read_text('utf-8')
        for invalid in (original.replace(SOUNDS[0],'other.ogg'),original.replace('Class: 83','Class: 28'),
                        original.replace('Assets:\n','NotAssets:\n'),original.replace('Assets/LoadedSoundEffects','Assets/Other')):
            manifest.write_text(invalid,'utf-8')
            self.assertFalse(assets.native_ambient_reference(relative))
        manifest.write_text(original,'utf-8');bundle.write_bytes(b'not a bundle'+bytes(64))
        self.assertFalse(assets.native_ambient_reference(relative))
        bundle.unlink();self.assertFalse(assets.native_ambient_reference(relative))

    def test_external_same_named_empty_file_never_gets_native_exception(self):
        f=self.fixture();self.native(f)
        relative='loadedsoundeffects/ambient/'+SOUNDS[0].lower()
        file=f.local/relative;file.parent.mkdir(parents=True);file.touch()
        self.assertFalse(assets.native_ambient_reference(relative,file))
        self.settings(Path(str(f.source('ZX_AI'))+'_settings.txt'))
        with self.assertRaisesRegex(ValueError,'OGG'):f.archive()

    def test_external_valid_override_is_copied_instead_of_native_fallback(self):
        f=self.fixture();self.native(f)
        relative='loadedsoundeffects/ambient/'+SOUNDS[0].lower();file=f.local/relative
        file.parent.mkdir(parents=True);file.write_bytes(b'OggS'+bytes(40))
        self.settings(Path(str(f.source('ZX_AI'))+'_settings.txt'))
        with f.archive() as archive:
            self.assertEqual(f.read(archive,relative),file.read_bytes())
            self.assertFalse(any(SOUNDS[1].lower() in name.lower() for name in archive.namelist()))

    def test_missing_proof_does_not_turn_empty_or_missing_audio_into_valid_content(self):
        f=self.fixture();manifest,_=self.native(f)
        self.settings(Path(str(f.source('ZX_AI'))+'_settings.txt'))
        manifest.unlink()
        with self.assertRaisesRegex(ValueError,'OGG'):f.archive()
        (f.assets/'loadedsoundeffects/ambient'/SOUNDS[0]).unlink()
        with self.assertRaisesRegex(ValueError,'素材缺失'):f.archive()

    def test_standalone_preserves_native_references_without_shipping_placeholders(self):
        f=self.fixture();manifest,_=self.native(f)
        original=self.settings(Path(str(f.source('ZX_AI'))+'_settings.txt'))
        with f.archive() as archive,tempfile.TemporaryDirectory() as folder:
            self.assertEqual(f.read(archive,'world/zx-rooms/ZX_AI_settings.txt').decode().splitlines(),original.splitlines())
            self.assertFalse(any('soundeffects/' in name.lower() or 'assetbundles/' in name.lower() for name in archive.namelist()))
            archive.extractall(folder);stage=Path(folder)/f.request['id']
            standalone.audit(stage,['selected'])
            manifest.unlink()
            with self.assertRaisesRegex(ValueError,'附加素材缺失'):standalone.audit(stage,['selected'])

    def test_project_export_inspect_import_and_apply_keep_bundle_reference(self):
        f=self.fixture('project');self.native(f)
        original=self.settings(f.local/'world/xx-rooms/XX_AI_settings.txt')
        payload=f.payload();files=f.unpack(payload)
        self.assertFalse(any(name.startswith('assets/') for name in files))
        f.target();project_packages.inspect_import(payload,f.server)
        project=project_packages.import_package(payload,f.server)['project']
        plan=project_packages.before_deploy(project,f.server)
        self.assertEqual(plan['files']['world/xx-rooms/XX_AI_settings.txt'].decode().splitlines(),original.splitlines())
        self.assertFalse(any('soundeffects/' in name for name in plan['files']))
        project_packages.write_deploy_assets(plan)
        self.assertEqual((f.local/'world/xx-rooms/XX_AI_settings.txt').read_text('utf-8'),original)
        self.assertFalse((f.local/'loadedsoundeffects').exists())

    def test_imported_empty_audio_is_rejected_even_when_native_bundle_has_same_name(self):
        f=self.fixture('project');self.native(f)
        self.settings(f.local/'world/xx-rooms/XX_AI_settings.txt')
        files=f.unpack(f.payload());files['assets/loadedsoundeffects/ambient/'+SOUNDS[0].lower()]=b''
        with self.assertRaisesRegex(ValueError,'OGG'):project_packages.inspect_import(f.archive(files),f.server)

    def test_import_omission_requires_receiver_game_bundle_proof(self):
        f=self.fixture('project');manifest,_=self.native(f)
        self.settings(f.local/'world/xx-rooms/XX_AI_settings.txt')
        payload=f.payload();manifest.unlink()
        with self.assertRaisesRegex(ValueError,'素材缺失'):project_packages.inspect_import(payload,f.server)

    def test_region_export_uses_base_dependency_without_zero_byte_audio_files(self):
        f=self.fixture('region');self.native(f)
        original=self.settings(f.owner/'world/zz-rooms/ZZ_A01_settings.txt')
        with f.archive() as archive:
            self.assertEqual(archive.read('world/zz-rooms/ZZ_A01_settings.txt').decode().splitlines(),original.splitlines())
            self.assertFalse(any('soundeffects/' in name or 'AssetBundles/' in name for name in archive.namelist()))
            self.assertTrue(json.loads(archive.read('region-manifest.json'))['gameDependency'])

    def test_region_export_rejects_external_empty_override(self):
        f=self.fixture('region');self.native(f)
        self.settings(f.owner/'world/zz-rooms/ZZ_A01_settings.txt')
        file=f.owner/'loadedsoundeffects/ambient'/SOUNDS[0];file.parent.mkdir(parents=True);file.touch()
        with self.assertRaisesRegex(ValueError,'OGG'):f.archive()


if __name__=='__main__':unittest.main()
