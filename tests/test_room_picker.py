import base64
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import room_preview


class RoomPickerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.enabled = self.root / 'enabled'
        self.disabled = self.root / 'disabled'
        for root in (self.enabled, self.disabled):
            (root / 'world/su').mkdir(parents=True)
            (root / 'world/su-rooms').mkdir()
            (root / 'palettes').mkdir()
        self.source = self.enabled / 'world/su-rooms/SU_A01'
        rows = ['SU_A01', '4*3|0', '', '0,0|', '', '', '', '', '', '', '', '1|0|0|0|4|0|0|0|0|0|0|1|']
        self.source.with_suffix('.txt').write_text('\n'.join(rows), 'utf-8')
        Path(str(self.source) + '_settings.txt').write_text('Palette: 0\n', 'utf-8')
        Image.new('RGBA', (80, 60), (31, 0, 0, 255)).save(str(self.source) + '_1.png')
        Image.new('RGB', (32, 8), (50, 80, 100)).save(self.enabled / 'palettes/palette0.png')
        (self.enabled / 'world/su/map_su.txt').write_text('SU_A01: 15><25><900><1000><1><Outskirts\nSU_A02: invalid><0\n', 'utf-8')
        (self.disabled / 'world/su/map_su.txt').write_text('SU_A01: 999><999\n', 'utf-8')
        (self.enabled / 'world/su/displayname.txt').write_text('Outskirts\n', 'utf-8')
        (self.enabled / 'text/text_chi').mkdir(parents=True)
        (self.enabled / 'text/text_chi/strings.txt').write_text('0Outskirts|郊外\n', 'utf-8')
        self.catalog = dict(regions=[dict(name='SU', rooms=[dict(name='SU_A01', connections=['SU_A02']), dict(name='SU_A02', connections=['SU_A01'])])])
        self.patches = [patch.object(room_preview.room_bindings, 'enabled_asset_roots', return_value=[self.enabled]),
                        patch.object(room_preview.room_bindings, 'catalog', return_value=self.catalog),
                        patch.object(room_preview.room_bindings, 'resolve_room_source', side_effect=self.resolve)]
        for item in self.patches:item.start()

    def resolve(self, name):
        if name != 'SU_A01':raise ValueError('Unavailable room')
        return self.source

    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.temp.cleanup()

    def test_native_map_coordinates_and_translation(self):
        value = room_preview.map_catalog('SU')
        self.assertEqual(value['rooms'][0]['position'], [15.0, 25.0])
        self.assertEqual(value['regions'][0]['name'], '郊外')
        self.assertEqual(value['layout'], 'map')
        self.assertIsNone(value['rooms'][1]['position'])
        self.assertNotIn('path', str(value))
        self.assertEqual(room_preview.map_catalog('SU', locale='en')['regions'][0]['name'], 'Outskirts')

    def test_missing_map_is_explicit_connections_layout(self):
        (self.enabled / 'world/su/map_su.txt').unlink()
        self.assertEqual(room_preview.map_catalog('SU')['layout'], 'connections')

    def test_only_enabled_assets(self):
        (self.enabled / 'world/su/map_su.txt').unlink()
        self.assertIsNone(room_preview.map_catalog('SU')['rooms'][0]['position'])
        with self.assertRaises(ValueError):room_preview.preview('SU_DISABLED')

    def test_geometry_coordinate_system(self):
        result = room_preview.geometry(self.source)
        self.assertEqual(result['solids'], [[0, 2], [3, 0]])
        self.assertEqual(result['shortcuts'], [[1, 1]])
        self.assertEqual(result['cameras'], [[0, 0]])

    def test_real_palette_decoder_and_no_file_writes(self):
        before = {file.relative_to(self.root): file.read_bytes() for file in self.root.rglob('*') if file.is_file()}
        result = room_preview.preview('SU_A01')
        self.assertTrue(result['image'].startswith('data:image/png;base64,'))
        image = Image.open(io.BytesIO(base64.b64decode(result['image'].split(',', 1)[1])))
        self.assertEqual(image.size, (80, 60))
        self.assertEqual(image.getpixel((10, 10)), (50, 80, 100, 255))
        self.assertEqual(before, {file.relative_to(self.root): file.read_bytes() for file in self.root.rglob('*') if file.is_file()})

    def test_no_camera_keeps_terrain(self):
        Path(str(self.source) + '_1.png').unlink()
        result = room_preview.preview('SU_A01')
        self.assertIsNone(result['image'])
        self.assertTrue(result['solids'])

    def test_untrusted_paths_rejected(self):
        for name in ('../SU_A01', 'C:/private/file', 'SU_A01/../../other'):
            with self.assertRaises(ValueError):room_preview.preview(name)
        with self.assertRaises(ValueError):room_preview.map_catalog('../SU')

    def test_current_project_is_explicit_not_all_disabled_projects(self):
        project = dict(projectId='oc-fixture')
        binding = dict(ai='TEST_AI', entry='TEST_ENTRY', region='TEST', entryMode='copy')
        with patch.object(room_preview.storage, 'load_project', return_value=project), patch.object(room_preview.room_bindings, 'binding', return_value=binding), patch.object(room_preview.room_bindings, 'source_for', return_value=self.source):
            value = room_preview.map_catalog('TEST', 'oc-fixture')
            self.assertEqual([item['name'] for item in value['rooms']], ['TEST_AI', 'TEST_ENTRY'])
            self.assertTrue(all(item['project'] for item in value['rooms']))


if __name__ == '__main__':unittest.main()
