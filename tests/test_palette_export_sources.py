import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import palette_export_sources as palette_sources
import room_source_choices as choices
import storage


class PaletteExportSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='mi-saved-palette-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.base = self.root / 'game'
        self.active = self.root / 'active'
        self.inactive = self.root / 'inactive'
        self.project = self.root / 'projects/selected/project.json'
        self.project.parent.mkdir(parents=True)
        self.roots = [self.active / 'newest', self.active, self.base]
        for context in (patch.object(storage, 'project_file', return_value=self.project),
                        patch.object(storage, 'target_mod', return_value=self.root / 'local'),
                        patch.object(storage, 'installed_mod', return_value=None),
                        patch.object(storage, 'available_game_root', return_value=None)):
            context.start()
            self.addCleanup(context.stop)

    def image(self, root, name='OutputPalettes/palette9100.png', color=(5, 15, 25, 77)):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGBA', (32, 16), color).save(path)
        return path

    def versions(self, index=9100):
        return choices._asset_versions('selected', 'palettes/palette' + str(index) + '.png', self.roots)

    def snapshot(self):
        return {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.root.rglob('*') if path.is_file()}

    def test_finds_only_referenced_saved_palette_in_enabled_roots_and_game(self):
        first = self.image(self.active / 'newest')
        second = self.image(self.base, color=(40, 50, 60, 255))
        self.image(self.active, 'OutputPalettes/palette9999.png')
        self.image(self.inactive)
        self.assertEqual(palette_sources.saved_files(9100, self.roots), [first, second])
        versions, records = self.versions()
        self.assertEqual({entry['path'] for entry in versions}, {first, second})
        self.assertTrue(all(entry['meta']['origin'] == 'palette_output' for entry in versions))
        self.assertTrue(all(not entry['meta']['providers'] for entry in versions))
        self.assertFalse(any('inactive' in record['path'] or '9999' in record['path'] for record in records))

    def test_same_number_different_bytes_remain_separate_choices(self):
        standard = self.image(self.active, 'palettes/palette9100.png', (255, 0, 0, 255))
        saved = self.image(self.base, color=(0, 0, 255, 77))
        before = self.snapshot()
        versions, _ = self.versions()
        self.assertEqual(len(versions), 2)
        self.assertEqual({version['path'] for version in versions}, {standard, saved})
        self.assertEqual(len({version['meta']['id'] for version in versions}), 2)
        self.assertTrue(all(version['meta']['complete'] for version in versions))
        self.assertEqual(self.snapshot(), before)

    def test_equal_bytes_deduplicate_and_keep_saved_origin(self):
        self.image(self.active, 'palettes/palette9100.png')
        self.image(self.base)
        versions, _ = self.versions()
        self.assertEqual(len(versions), 1)
        self.assertEqual(set(versions[0]['meta']['origins']), {'enabled', 'palette_output'})

    def test_raw_rgba_bytes_remain_unchanged_without_creator_plugin(self):
        saved = self.image(self.base)
        original = saved.read_bytes()
        versions, _ = self.versions()
        self.assertEqual(versions[0]['path'].read_bytes(), original)
        with Image.open(versions[0]['path']) as image:
            self.assertEqual(image.getpixel((3, 4)), (5, 15, 25, 77))
        self.assertEqual(versions[0]['meta']['providers'], [])
        self.assertTrue(palette_sources.is_saved_palette(saved, 9100, self.roots))

    def test_case_insensitive_saved_path(self):
        saved = self.image(self.base, 'outputpalettes/PALETTE9100.PNG')
        self.assertEqual(palette_sources.saved_files(9100, self.roots), [saved])
        self.assertEqual(self.versions()[0][0]['path'], saved)

    def test_unrelated_asset_and_invalid_reference_are_not_scanned(self):
        self.image(self.base)
        for relative in ('illustrations/palette9100.png', 'palettes/palette-1.png',
                         'palettes/palette1000001.png', 'palettes/../OutputPalettes/palette9100.png'):
            self.assertEqual(palette_sources.output_locations(relative, self.roots), [])

    def test_damaged_png_is_not_a_complete_choice(self):
        saved = self.image(self.base)
        saved.write_bytes(b'not a png')
        versions, _ = self.versions()
        self.assertEqual(len(versions), 1)
        self.assertFalse(versions[0]['meta']['complete'])
        self.assertEqual(versions[0]['meta']['issues'], ['invalid_asset'])

    def test_linked_saved_palette_is_rejected(self):
        outside = self.image(self.inactive)
        linked = self.base / 'OutputPalettes/palette9100.png'
        linked.parent.mkdir(parents=True, exist_ok=True)
        try:
            linked.symlink_to(outside)
        except OSError:
            original = Path.is_symlink
            context = patch.object(Path, 'is_symlink', lambda path: path == linked or original(path))
            context.start()
            self.addCleanup(context.stop)
        with self.assertRaises(ValueError):
            palette_sources.saved_files(9100, self.roots)
        with self.assertRaises(choices.RoomChoiceError):
            self.versions()


class PaletteExportChoiceIntegrationTests(unittest.TestCase):
    def fixture(self):
        from test_room_source_choices import RoomSourceChoiceTests
        fixture = RoomSourceChoiceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        base = fixture.root / 'game'
        for context in (patch.object(choices.room_bindings, 'enabled_asset_roots', return_value=[base]),
                        patch.object(choices.room_bindings, '_asset_roots', return_value=[fixture.local, base]),
                        patch.object(storage, 'available_game_root', return_value=None)):
            context.start()
            self.addCleanup(context.stop)
        standard = fixture.local / 'palettes/palette9100.png'
        saved = base / 'OutputPalettes/palette9100.png'
        for path, color in ((standard, (255, 0, 0, 255)), (saved, (0, 0, 255, 77))):
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGBA', (32, 16), color).save(path)
        return fixture, saved

    def test_conflict_requires_author_choice_and_keeps_original_bytes(self):
        fixture, saved = self.fixture()
        before = fixture.snapshot()
        report = fixture.report()
        self.assertTrue(report['requiresChoices'])
        fixture.assertCode('room_choices_required', fixture.enter)
        row = report['assets'][0]
        self.assertTrue(row['conflict'])
        selection = next(version for version in row['versions'] if 'palette_output' in version['origins'])
        payload = fixture.pick(report)
        payload['assetChoices'] = {row['key']: selection['id']}
        with choices.resolution_scope([fixture.project], payload):
            selected = choices.selected_asset('selected', 'palettes/palette9100.png')
            self.assertEqual(selected, saved)
            self.assertEqual(selected.read_bytes(), saved.read_bytes())
        self.assertEqual(fixture.snapshot(), before)

    def test_saved_palette_change_invalidates_previous_choice(self):
        fixture, saved = self.fixture()
        report = fixture.report()
        payload = fixture.pick(report)
        row = report['assets'][0]
        payload['assetChoices'] = {row['key']: next(version['id'] for version in row['versions']
                                                   if 'palette_output' in version['origins'])}
        Image.new('RGBA', (32, 16), (0, 255, 0, 77)).save(saved)
        fixture.assertCode('room_choices_stale', lambda: fixture.enter(payload))

    def test_unflagged_project_gets_only_referenced_palette_choices(self):
        fixture, saved = self.fixture()
        fixture.project['editor']['externalRoomTools'] = False
        before = fixture.snapshot()
        report = fixture.report()
        self.assertEqual({row['room']: row['state'] for row in report['rooms']},
                         {'XX_AI': 'ready', 'YY_EXISTING': 'ready'})
        self.assertEqual(report['parameterConflicts'], [])
        self.assertEqual([asset['key'] for asset in report['assets']], ['palettes/palette9100.png'])
        self.assertTrue(report['requiresChoices'])
        fixture.assertCode('room_choices_required', fixture.enter)
        row = report['assets'][0]
        payload = dict(snapshotToken=report['snapshotToken'], assetChoices={row['key']: next(
            version['id'] for version in row['versions'] if 'palette_output' in version['origins'])})
        with choices.resolution_scope([fixture.project], payload):
            self.assertEqual(choices.selected_asset('selected', row['key']), saved)
        self.assertEqual(fixture.snapshot(), before)

    def test_unflagged_project_ignores_saved_palettes_not_in_effective_settings(self):
        fixture, _ = self.fixture()
        fixture.project['editor']['externalRoomTools'] = False
        fixture.render(fixture.output, settings='Template: NONE\nPalette: 9101\n')
        before = fixture.snapshot()
        report = fixture.report()
        self.assertFalse(report['requiresChoices'])
        self.assertEqual({row['room']: row['state'] for row in report['rooms']},
                         {'XX_AI': 'missing', 'YY_EXISTING': 'ready'})
        self.assertEqual([row['key'] for row in report['assets']], ['palettes/palette9101.png'])
        self.assertEqual([row['relative'] for row in report['missingFiles']], ['palettes/palette9101.png'])
        self.assertEqual(report['assets'][0]['versions'], [])
        self.assertEqual(fixture.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
