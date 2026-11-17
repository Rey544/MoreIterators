import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile
from PIL import Image


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import region_packages
import room_bindings
import room_source_choices as choices
import server
import standalone
import storage


class SavedPaletteExportTests(unittest.TestCase):
    def fixture(self, kind):
        if kind == 'project':
            from test_project_packages import ProjectPackageTests
            fixture = ProjectPackageTests()
        elif kind == 'region':
            from test_region_packages import RegionPackageTests
            fixture = RegionPackageTests()
        else:
            from test_standalone_extra_rooms import ExtraRoomExportTests
            fixture = ExtraRoomExportTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def image(self, path, color):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGBA', (32, 16), color).save(path)
        return path.read_bytes()

    def payload(self, report, origin='palette_output'):
        selected = {}
        for row in report['assets']:
            version = next((version for version in row['versions']
                            if origin in version['origins'] and version['complete']), None)
            if version is not None:
                selected[row['key']] = version['id']
        return dict(snapshotToken=report['snapshotToken'], assetChoices=selected)

    def assert_requires_choice(self, action):
        with self.assertRaises(choices.RoomChoiceError) as caught:
            action()
        self.assertEqual(caught.exception.code, 'room_choices_required')

    def test_project_zip_preserves_saved_palette_rgba_and_room_fields(self):
        fixture = self.fixture('project')
        assets = fixture.game / 'RainWorld_Data/StreamingAssets'
        change = patch.object(room_bindings, 'enabled_asset_roots', return_value=[assets])
        change.start();self.addCleanup(change.stop)
        original = self.image(assets / 'OutputPalettes/palette9100.png', (1, 2, 3, 77))
        settings = fixture.local / 'world/xx-rooms/XX_AI_settings.txt'
        original_settings = settings.read_bytes()
        request = dict(projects=['selected'])
        build = lambda: server.export_with_room_choices(request, fixture.payload, projects=[fixture.project])
        self.assert_requires_choice(build)
        report = choices.preflight([fixture.project])
        self.assertEqual({row['room']: row['state'] for row in report['rooms']},
                         {'XX_AI': 'ready', 'XX_ENTRY': 'ready'})
        self.assertEqual(report['parameterConflicts'], [])
        request['roomSourceChoices'] = self.payload(report)
        with zipfile.ZipFile(io.BytesIO(build())) as archive:
            self.assertEqual(archive.read('palettes/palette9100.png'), original)
            self.assertEqual(archive.read('rooms/XX_AI/rendered/XX_AI_settings.txt'), original_settings)
        self.assertEqual(settings.read_bytes(), original_settings)

    def test_project_zip_can_keep_standard_palette_instead(self):
        fixture = self.fixture('project')
        assets = fixture.game / 'RainWorld_Data/StreamingAssets'
        change = patch.object(room_bindings, 'enabled_asset_roots', return_value=[assets])
        change.start();self.addCleanup(change.stop)
        self.image(assets / 'OutputPalettes/palette9100.png', (1, 2, 3, 77))
        original = (fixture.local / 'palettes/palette9100.png').read_bytes()
        report = choices.preflight([fixture.project])
        request = dict(projects=['selected'], roomSourceChoices=self.payload(report, 'local'))
        result = server.export_with_room_choices(request, fixture.payload, projects=[fixture.project])
        with zipfile.ZipFile(io.BytesIO(result)) as archive:
            self.assertEqual(archive.read('palettes/palette9100.png'), original)

    def test_standalone_uses_saved_palette_without_generator_dependency(self):
        fixture = self.fixture('standalone')
        settings = Path(str(fixture.source('ZX_AI')) + '_settings.txt')
        settings.write_text('Template: NONE\nPalette: 9100\n', 'utf-8')
        self.image(fixture.data / 'projects/selected/rooms/palettes/palette9100.png', (255, 0, 0, 255))
        original = self.image(fixture.assets / 'OutputPalettes/palette9100.png', (1, 2, 3, 77))
        request = dict(fixture.request)
        build = lambda: server.export_with_room_choices(request,
            lambda: standalone.build(request, server, save_preferences=False), projects=[fixture.project])
        self.assert_requires_choice(build)
        report = choices.preflight([fixture.project])
        self.assertEqual({row['room']: row['state'] for row in report['rooms']},
                         {'ZX_AI': 'ready', 'ZX_ENTRY': 'ready'})
        request['roomSourceChoices'] = self.payload(report)
        result = build()
        with zipfile.ZipFile(storage.EXPORTS / Path(result['url']).name) as archive:
            self.assertEqual(fixture.read(archive, 'palettes/palette9100.png'), original)
            info = json.loads(fixture.read(archive, 'modinfo.json'))
            self.assertNotIn('pkuyo.palettecreator', info['requirements'])

    def test_region_without_mi_projects_has_reachable_palette_choice(self):
        fixture = self.fixture('region')
        tool = fixture.assets / 'mods/palette-tool'
        tool.mkdir(parents=True)
        (tool / 'modinfo.json').write_text(json.dumps(dict(id='pkuyo.palettecreator', name='Palette Creator', requirements=[])), 'utf-8')
        fixture.roots.insert(0, tool)
        original = self.image(tool / 'OutputPalettes/palette9010.png', (1, 2, 3, 77))
        request = dict(scope='region', region='ZZ', projects=[])
        build = lambda: server.export_with_room_choices(request, lambda: region_packages.build('ZZ', fixture.metadata, []))
        preview = region_packages.inspect('ZZ')
        self.assertTrue(preview['ok'], preview)
        self.assert_requires_choice(build)
        report = choices.preflight([], region='ZZ')
        self.assertEqual(report['rooms'], [])
        self.assertEqual(report['assets'][0]['projectIds'], [])
        self.assertEqual(report['assets'][0]['region'], 'ZZ')
        request['roomSourceChoices'] = self.payload(report)
        result = build()
        with zipfile.ZipFile(storage.EXPORTS / Path(result['url']).name) as archive:
            self.assertEqual(archive.read('palettes/palette9010.png'), original)
            manifest = json.loads(archive.read('region-manifest.json'))
            self.assertNotIn('pkuyo.palettecreator', {row['id'] for row in manifest['dependencies']})
        self.assertEqual((tool / 'OutputPalettes/palette9010.png').read_bytes(), original)

    def test_devtools_fade_and_regionkit_extra_palette_share_saved_file_support(self):
        fixture = self.fixture('standalone')
        from test_regionkit_palettes import RegionKitPaletteTests
        RegionKitPaletteTests().install_regionkit(fixture)
        settings = Path(str(fixture.source('ZX_AI')) + '_settings.txt')
        text = 'Template: NONE\nPalette: 26\nFadePalette: 9100, 0.3\nMorePalette0: 9101, 0.75\n'
        settings.write_text(text, 'utf-8')
        originals = {}
        for index, alpha in ((9100, 77), (9101, 153)):
            self.image(fixture.data / 'projects/selected/rooms/palettes' / ('palette' + str(index) + '.png'), (255, 0, 0, 255))
            originals[index] = self.image(fixture.assets / 'OutputPalettes' / ('palette' + str(index) + '.png'), (1, 2, 3, alpha))
        report = choices.preflight([fixture.project])
        request = dict(fixture.request, roomSourceChoices=self.payload(report))
        result = server.export_with_room_choices(request,
            lambda: standalone.build(request, server, save_preferences=False), projects=[fixture.project])
        with zipfile.ZipFile(storage.EXPORTS / Path(result['url']).name) as archive:
            self.assertEqual(fixture.read(archive, 'world/zx-rooms/ZX_AI_settings.txt').decode('utf-8').splitlines(), text.splitlines())
            for index, content in originals.items():
                self.assertEqual(fixture.read(archive, 'palettes/palette' + str(index) + '.png'), content)
            requirements = json.loads(fixture.read(archive, 'modinfo.json'))['requirements']
            self.assertIn('regionkit', requirements)
            self.assertIn('pom', requirements)
            self.assertNotIn('pkuyo.palettecreator', requirements)

    def test_region_uses_saved_palette_when_standard_file_is_missing(self):
        fixture = self.fixture('region')
        (fixture.owner / 'palettes/palette9010.png').unlink()
        original = self.image(fixture.assets / 'OutputPalettes/palette9010.png', (1, 2, 3, 77))
        request = dict(scope='region', region='ZZ', projects=[])
        result = server.export_with_room_choices(request, lambda: region_packages.build('ZZ', fixture.metadata, []))
        with zipfile.ZipFile(storage.EXPORTS / Path(result['url']).name) as archive:
            self.assertEqual(archive.read('palettes/palette9010.png'), original)


if __name__ == '__main__':
    unittest.main()
