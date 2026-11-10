import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'editor'))
import room_controls
import projections
import project_packages
import room_bindings
import server
import standalone
import storage


class RoomControlTests(unittest.TestCase):
    def fixture(self):
        from test_project_packages import ProjectPackageTests
        value=ProjectPackageTests();value.setUp();self.addCleanup(value.doCleanups)
        return value

    def test_old_data_keeps_three_original_modes_and_invalid_mode_fails(self):
        self.assertEqual(room_controls.validate({}),dict(roomPaletteMode='mi',roomGravityMode='mi',entryGravityMode='zero'))
        for name in room_controls.MODES:
            with self.assertRaises(ValueError):room_controls.validate({name:'automatic'})
        schema=standalone.runtime_design_schema()
        for name in room_controls.MODES:self.assertIn(name,schema)

    def test_native_copy_preserves_latest_dev_settings_template_fade_and_effects(self):
        f=self.fixture();f.project['design']=dict(roomPaletteMode='room',roomGravityMode='room',entryGravityMode='room')
        for name,kind in [('XX_AI','ai'),('XX_ENTRY','entry')]:
            source=f.local/'world/xx-rooms'/name
            f.render(f.installed/'world/xx-rooms'/name,name)
            selected=f.installed/'world/xx-rooms'/(name+'_settings.txt')
            text='Template: XX_SettingsTemplate_Outside\nPalette: 17\nFadePalette: 20, 0.25, 0.75\nEffects: ZeroG-0.5-0-0, AboveCloudsView-1-0-0,\n'
            selected.write_text(text,'utf-8');os.utime(selected,(2000000000,2000000000))
            target=room_controls.copy_owned_room(f.project,source,f.root/'copy',name,kind,server,replace=True)
            self.assertEqual(target.read_text('utf-8'),text)
            self.assertEqual(selected.read_text('utf-8'),text)

    def test_legacy_copy_still_has_mi_palette_and_waiting_zero_gravity(self):
        f=self.fixture()
        ai=room_controls.copy_owned_room(f.project,f.local/'world/xx-rooms/XX_AI',f.root/'copy','XX_AI','ai',server,replace=True)
        entry=room_controls.copy_owned_room(f.project,f.local/'world/xx-rooms/XX_ENTRY',f.root/'copy','XX_ENTRY','entry',server,replace=True)
        self.assertIn('Palette: 26',ai.read_text('utf-8'));self.assertIn('ZeroG-1-0-0',entry.read_text('utf-8'))
        self.assertNotIn('ZeroG-0.25',entry.read_text('utf-8'))

    def test_rained_sync_uses_newest_settings_not_installed_directory_priority(self):
        f=self.fixture()
        installed=f.render(f.installed/'world/xx-rooms/XX_AI','XX_AI',2)
        cached=f.render(f.project_file.parent/'rooms/rendered/XX_AI','XX_AI',2)
        authored=f.local/'world/xx-rooms/XX_AI_settings.txt'
        candidates=[Path(str(installed)+'_settings.txt'),authored,Path(str(cached)+'_settings.txt')]
        rendered=f.render(f.root/'rained/Levels/XX_AI','XX_AI',2)
        for index,latest in enumerate(candidates):
            with self.subTest(origin=('installed','local','project')[index]):
                for candidate in candidates:
                    candidate.write_text('Template: NONE\nPalette: 9100\nEffectColorA: 1\n','utf-8')
                    os.utime(candidate,(1000,1000))
                expected=('Template: NONE\nPalette: 9100\nEffectColorA: 9\nEffectColorB: '+str(index)+'\nFadePalette: 9100, 0.25, 0.75\n').encode('utf-8')
                latest.write_bytes(expected);os.utime(latest,(3000,3000))
                selected=server.rained_settings_source(f.project,'XX_AI','ai')
                self.assertEqual(selected,latest)
                with patch.object(server.room_editor,'render',return_value=rendered):
                    server.room_editor.import_render('selected','ai',server.roomnames,selected)
                self.assertEqual(Path(str(cached)+'_settings.txt').read_bytes(),expected)
                self.assertEqual(latest.read_bytes(),expected)

    def test_rained_sync_without_settings_keeps_existing_template_fallback(self):
        f=self.fixture();assets=f.root/'assets';entry=f.root/'waiting/default'
        for name,kind in [('XX_AI','ai'),('XX_ENTRY','entry')]:
            (f.local/'world/xx-rooms'/(name+'_settings.txt')).unlink()
            expected=Path(str(assets/'world/ss-rooms/ss_ai' if kind=='ai' else entry)+'_settings.txt')
            with patch.object(server,'ASSETS',assets),patch.object(server,'entry_room_template',return_value=entry):
                self.assertEqual(server.rained_settings_source(f.project,name,kind),expected)

    def test_native_palette_uses_template_and_per_camera_fade_without_mi_tint(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'world/zz-rooms/ZZ_AI';source.parent.mkdir(parents=True)
            props=root/'world/zz';props.mkdir();(props/'properties.txt').write_text('Room Setting Templates: outside\n','utf-8')
            (props/'zz_settingstemplate_outside.txt').write_text('Palette: 12\n','utf-8')
            settings=Path(str(source)+'_settings.txt');settings.write_text('FadePalette: 13, 0, 1\n','utf-8')
            (root/'palettes').mkdir()
            for number,color in [(0,'black'),(12,'red'),(13,'blue')]:Image.new('RGB',(32,16),color).save(root/'palettes'/('palette'+str(number)+'.png'))
            native={'design':{'roomPaletteMode':'room','roomWorkColor':'#00ff00','roomBrightness':.1}}
            with patch.object(room_bindings,'enabled_asset_roots',return_value=[root]),patch.object(room_bindings,'is_enabled_asset',return_value=True):
                self.assertEqual(projections.room_palette(native,source,0).getpixel((4,3)),(255,0,0))
                self.assertEqual(projections.room_palette(native,source,1).getpixel((4,3)),(0,0,255))
                settings.write_text('Template: NONE\n','utf-8')
                self.assertEqual(projections.room_palette(native,source).getpixel((0,0)),(0,0,0))
                settings.write_text('Template: ZZ_SettingsTemplate_Outside\nPalette: 13\n','utf-8')
                palette=projections.room_palette(native,source)
                self.assertEqual(palette.getpixel((0,0)),(0,0,255))
                image=Image.new('RGBA',(1,1),(255,255,255,255))
                self.assertEqual(projections.decode_room_image(image,palette,native['design']).getpixel((0,0)),(0,0,255,255))

    def test_subset_sky_and_template_dependencies_are_blocked_not_erased(self):
        f=self.fixture();settings=f.local/'world/xx-rooms/XX_AI_settings.txt'
        text=settings.read_text('utf-8')+'Effects: AboveCloudsView-1-0-0,\n'
        
        text=text.replace('Effects: ZeroG-0.25-1-1,\n','');settings.write_text(text,'utf-8')
        with self.assertRaisesRegex(ValueError,'整片区域'):f.payload()
        with self.assertRaisesRegex(ValueError,'整片区域'):
            standalone.copy_selected_room(f.project,settings.with_name('XX_AI'),'XX_AI','YY_AI',f.root/'copy',server)
        self.assertEqual(settings.read_text('utf-8'),text)
        settings.write_text('Template: XX_SettingsTemplate_Outside\nPalette: 9100\n','utf-8')
        with self.assertRaisesRegex(ValueError,'模板'):f.payload()
        self.assertIn('Outside',settings.read_text('utf-8'))

    def test_import_and_actual_apply_keep_native_settings_and_original_json_modes(self):
        f=self.fixture();f.project['design']=dict(roomPaletteMode='room',roomGravityMode='room',entryGravityMode='room')
        f.project_file.write_text(__import__('json').dumps(f.project),'utf-8')
        payload=f.payload();f.target();p=project_packages.import_package(payload,f.server)['project']
        with patch.object(server,'save',side_effect=copy.deepcopy),patch.object(server,'compile_design',side_effect=lambda p:p['design']), \
             patch.object(server,'MOD',f.local),patch.object(server,'DESIGNS',storage.RUNTIME),patch.object(server,'ASSETS',f.game/'RainWorld_Data/StreamingAssets'), \
             patch.object(server,'installation_paths',return_value={}),patch.object(server.audio_assets,'copy_referenced'),patch.object(server.local_content,'status',return_value={}), \
             patch.object(server.waiting_room,'prepare',side_effect=AssertionError('no fallback')),patch.object(server,'copy_room',side_effect=AssertionError('no defaults')):
            self.assertTrue(server.deploy(p)['ok'])
        self.assertEqual(p['design'],f.project['design'])
        self.assertIn('ZeroG-0.25', (f.installed/'world/xx-rooms/XX_ENTRY_settings.txt').read_text('utf-8'))
        self.assertIn('Palette: 9100',(f.installed/'world/xx-rooms/XX_AI_settings.txt').read_text('utf-8'))

    def test_runtime_native_controls_and_f8_restore_in_editor_and_playback(self):
        compiler=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.is_file():self.skipTest('C# compiler required')
        with tempfile.TemporaryDirectory() as folder:
            for mode in ('editor','playback'):
                exe=Path(folder)/(mode+'.exe')
                command=[str(compiler),'/nologo','/out:'+str(exe),str(ROOT/'src/CreatorRoomSettings.cs'),str(ROOT/'tests/room_controls_check.cs')]
                if mode=='playback':command.append('/define:PLAYBACK')
                result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace')
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                result=subprocess.run([str(exe)],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('room controls passed',result.stdout)


if __name__=='__main__':unittest.main()
