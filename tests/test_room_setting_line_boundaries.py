from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import projections
import region_packages
import room_asset_dependencies
import room_bindings
import room_controls
import standalone


class RoomSettingLineBoundaryTests(unittest.TestCase):
    def fixture(self, module, name):
        value = getattr(__import__(module), name)()
        value.setUp()
        self.addCleanup(value.doCleanups)
        return value

    def test_empty_asset_fields_end_at_their_own_line(self):
        for newline in ('\n', '\r\n'):
            for padding in ('', ' ', '\t', ' \t '):
                with self.subTest(newline=repr(newline), padding=repr(padding)):
                    text = newline.join(('Effects:' + padding, 'PlacedObjects:' + padding,
                                         'AmbientSounds:' + padding, 'Triggers:', ''))
                    self.assertEqual(room_asset_dependencies.references(text), [])

    def test_empty_placed_objects_does_not_hide_the_next_declared_objects(self):
        decal = 'CustomDecal><0><0><' + '~'.join(['0'] * 11 + ['third-party-decal'])
        text = 'PlacedObjects:\nPlacedObjects: ' + decal + '\n'
        self.assertEqual(room_asset_dependencies.references(text), [('decals/third-party-decal.png',)])

    def test_named_assets_and_real_invalid_references_keep_validation(self):
        for kind in ('OMNI', 'DIR', 'SPOT', 'ThirdPartySound'):
            with self.subTest(kind=kind):
                text = 'AmbientSounds: ' + kind + '><Custom Loop.wav><0><0><1><1,\nTriggers:\n'
                self.assertEqual(room_asset_dependencies.references(text), [
                    ('soundeffects/ambient/custom loop.wav', 'loadedsoundeffects/ambient/custom loop.wav',
                     'soundeffects/custom loop.wav')])
        for text in ('AmbientSounds: OMNI\nTriggers:\n',
                     'AmbientSounds: OMNI><../bad.wav\nTriggers:\n',
                     'AmbientSounds: OMNI><bad.exe\nTriggers:\n',
                     'PlacedObjects: CustomDecal><0><0><bad\nAmbientSounds:\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                room_asset_dependencies.references(text)

    def test_project_zip_keeps_empty_asset_fields_and_other_mod_settings(self):
        f = self.fixture('test_project_packages', 'ProjectPackageTests')
        settings = f.local / 'world/xx-rooms/XX_AI_settings.txt'
        content = settings.read_bytes() + b'PlacedObjects:\nAmbientSounds:\nTriggers:\nThirdParty: unchanged\n'
        settings.write_bytes(content)
        files = f.unpack(f.payload())
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_settings.txt'], content)
        self.assertEqual(settings.read_bytes(), content)

    def test_standalone_zip_keeps_empty_asset_fields(self):
        f = self.fixture('test_standalone_extra_rooms', 'ExtraRoomExportTests')
        settings = Path(str(f.source('ZX_EXTRA')) + '_settings.txt')
        content = settings.read_bytes() + b'AmbientSounds:\nTriggers:\n'
        settings.write_bytes(content)
        with f.archive(['ZX_EXTRA']) as archive:
            self.assertEqual(f.read(archive, 'world/zx-rooms/ZX_EXTRA_settings.txt').decode().splitlines(), content.decode().splitlines())
        self.assertEqual(settings.read_bytes(), content)

    def test_region_zip_keeps_empty_asset_fields(self):
        f = self.fixture('test_region_packages', 'RegionPackageTests')
        settings = f.owner / 'world/zz-rooms/ZZ_A01_settings.txt'
        content = settings.read_bytes() + b'AmbientSounds: \r\nTriggers:\r\n'
        settings.write_bytes(content)
        with f.archive() as archive:
            self.assertEqual(archive.read('world/zz-rooms/ZZ_A01_settings.txt'), content)
        self.assertEqual(settings.read_bytes(), content)

    def test_empty_region_template_list_does_not_read_next_property(self):
        for newline in ('\n', '\r\n'):
            for padding in ('', ' ', '\t'):
                with self.subTest(newline=repr(newline), padding=repr(padding)):
                    text = 'Room Setting Templates:' + padding + newline + 'Palette: 12' + newline
                    self.assertEqual(standalone.region_template_names(text), [])

    def test_real_template_names_and_errors_keep_validation(self):
        self.assertEqual(standalone.region_template_names('Room Setting Templates: Rain, Outside\nPalette: 12\n'), ['rain', 'outside'])
        for text in ('Room Setting Templates: ../private\nPalette: 12\n',
                     'Room Setting Templates: Rain, Rain\nPalette: 12\n',
                     'Room Setting Templates: Rain\nRoom Setting Templates: Outside\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                standalone.region_template_names(text)

    def test_empty_effects_does_not_treat_another_mod_field_as_sky(self):
        text = 'Effects:\nThirdParty: preserved, AboveCloudsView-1-0-0,\n'
        self.assertIsNone(room_controls.require_portable_subset(text, 'ZZ_A01'))
        with self.assertRaises(ValueError):
            room_controls.require_portable_subset('Effects: AboveCloudsView-1-0-0,\n', 'ZZ_A01')

    def test_empty_template_and_fade_use_only_their_own_lines(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'world/zz-rooms/ZZ_A01'
            source.parent.mkdir(parents=True)
            settings = Path(str(source) + '_settings.txt')
            region = root / 'world/zz'
            region.mkdir()
            properties = region / 'properties.txt'
            for padding in ('', ' ', '\t'):
                with self.subTest(padding=repr(padding)):
                    text = 'Template:' + padding + '\nPalette: 12\nFadePalette:' + padding + '\nThirdParty: keep, this\n'
                    settings.write_text(text, 'utf-8')
                    properties.write_text('Room Setting Templates:' + padding + '\nPalette: 20\n', 'utf-8')
                    with patch.object(room_bindings, 'enabled_asset_roots', return_value=[root]):
                        result = room_controls.effective_palette_settings({}, source)
                    self.assertEqual(result, {'palette': 12, 'fade': [], 'text': text})
                    self.assertEqual(settings.read_text('utf-8'), text)

    def test_preview_does_not_read_another_mod_field_as_fade_palette(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'world/zz-rooms/ZZ_A01'
            source.parent.mkdir(parents=True)
            text = 'Template: NONE\nPalette: 12\nFadePalette:\nThirdParty: keep, this\n'
            Path(str(source) + '_settings.txt').write_text(text, 'utf-8')
            palettes = root / 'palettes'
            palettes.mkdir()
            Image.new('RGB', (32, 8), 'red').save(palettes / 'palette12.png')
            with patch.object(room_bindings, 'enabled_asset_roots', return_value=[root]), \
                 patch.object(room_bindings, 'is_enabled_asset', return_value=True):
                palette = projections.room_palette({'design': {'roomPaletteMode': 'room'}}, source)
            self.assertEqual(palette.getpixel((0, 0)), (255, 0, 0))

    def test_region_template_check_does_not_read_the_next_setting(self):
        f = self.fixture('test_region_packages', 'RegionPackageTests')
        settings = f.owner / 'world/zz-rooms/ZZ_A01_settings.txt'
        content = b'Template:\nPalette: 9010\n'
        settings.write_bytes(content)
        collector, names, room_files = region_packages._collect('ZZ', (), include_dependencies=False)
        self.assertEqual(set(names), {'ZZ_A01', 'ZZ_A02'})
        self.assertIn('world/zz-rooms/ZZ_A01_settings.txt', collector.files)
        self.assertEqual(settings.read_bytes(), content)


if __name__ == '__main__':
    unittest.main()
