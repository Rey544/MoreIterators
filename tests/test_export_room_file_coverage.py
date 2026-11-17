import copy
import hashlib
import json
import os
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image

import room_source_choices as choices
import project_packages
import storage


class ExportRoomFileCoverageTests(unittest.TestCase):
    def setUp(self):
        from test_room_source_choices import RoomSourceChoiceTests
        self.f = RoomSourceChoiceTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.cache.with_name('XX_AI_settings.txt').write_text('Effects: \n', 'utf-8')
        context = patch.object(choices, '_rained_levels', return_value=None)
        context.start()
        self.addCleanup(context.stop)

    def row(self, report, name='XX_AI'):
        return next(row for row in report['rooms'] if row['room'] == name)

    def manifest(self, files):
        metadata = dict(schema=choices.LOCAL_SCHEMA, projectId='selected', rooms=[], files=[{'path': value} for value in files])
        (storage.project_file('selected').parent / 'room-package.json').write_text(json.dumps(metadata), 'utf-8')

    def enabled(self, name, settings='Effects: \n'):
        base = self.f.root / 'enabled/world' / (name.split('_')[0].lower() + '-rooms') / name
        self.f.render(base, name=name, settings=settings)
        context = patch.object(choices.room_bindings, 'enabled_asset_roots', return_value=[self.f.root / 'enabled'])
        context.start()
        self.addCleanup(context.stop)
        return base

    def test_selected_external_room_without_manifest_reports_missing_main_settings(self):
        source = self.enabled('COT_S01')
        source.with_name('COT_S01_settings.txt').unlink()
        report = choices.preflight([self.f.project], ['COT_S01'])
        row = self.row(report, 'COT_S01')
        self.assertEqual((row['kind'], row['required'], row['owned'], row['syncable']), ('extra', False, False, False))
        self.assertEqual(row['state'], 'missing')
        missing = row['missingFiles'][0]
        self.assertEqual(missing['relative'], 'rooms/COT_S01/rendered/COT_S01_settings.txt')
        self.assertEqual(missing['targetRelative'], 'rooms/rendered/COT_S01_settings.txt')
        self.assertEqual(missing['reason'], 'missing_file')
        self.assertIn(missing, report['missingFiles'])

    def test_existing_entry_is_checked_and_never_marked_for_sync(self):
        self.f.existing.with_name('YY_EXISTING_2.png').unlink()
        row = self.row(self.f.report(), 'YY_EXISTING')
        self.assertEqual((row['kind'], row['required'], row['syncable']), ('entry', True, False))
        self.assertEqual([item['name'] for item in row['missingFiles']], ['YY_EXISTING_2.png'])

    def test_nonexternal_rooms_are_checked_without_changing_design(self):
        self.f.project['editor']['externalRoomTools'] = False
        before = copy.deepcopy(self.f.project)
        self.f.cache.with_name('XX_AI_settings.txt').unlink()
        row = self.row(self.f.report())
        self.assertEqual(row['missingFiles'][0]['name'], 'XX_AI_settings.txt')
        self.assertEqual(self.f.project, before)

    def test_missing_known_imported_variant_is_reported(self):
        self.manifest(['rooms/rendered/XX_AI_settings-Red.txt'])
        row = self.row(self.f.report())
        self.assertEqual([item['name'] for item in row['missingFiles']], ['XX_AI_settings-Red.txt'])
        self.assertFalse(any(value['complete'] for value in row['settingsVersions']))

    def test_missing_variant_remains_importable_when_saved_palette_scanner_is_enabled(self):
        self.f.project['editor']['externalRoomTools'] = False
        self.manifest(['rooms/rendered/XX_AI_settings-Red.txt'])
        (self.f.root / 'enabled/OutputPalettes').mkdir(parents=True)
        with patch.object(choices.room_bindings, 'enabled_asset_roots', return_value=[self.f.root / 'enabled']):
            report = self.f.report()
        self.assertEqual([item['name'] for item in self.row(report)['missingFiles']], ['XX_AI_settings-Red.txt'])
        self.assertIn(self.row(report)['missingFiles'][0], report['missingFiles'])

    def test_independent_local_version_does_not_inherit_imported_variant_obligation(self):
        self.manifest(['rooms/rendered/XX_AI_settings-Red.txt'])
        self.f.render(self.f.output, settings='Effects: \n')
        report = self.f.report()
        row = self.row(report)
        self.assertEqual(row['state'], 'ready')
        self.assertEqual(row['missingFiles'], [])
        with choices.resolution_scope([self.f.project]):
            self.assertEqual(choices.selected_settings('selected', 'XX_AI'), self.f.output.with_name('XX_AI_settings.txt'))

    def test_present_setting_variants_and_properties_are_all_checked(self):
        self.f.cache.with_name('XX_AI_settings-Red.txt').write_text('Palette: 9123\n', 'utf-8')
        self.f.cache.with_name('XX_AI_properties.txt').write_text('Palette: 9124\n', 'utf-8')
        report = self.f.report()
        missing = {item['relative'] for item in self.row(report)['missingFiles']}
        self.assertEqual(missing, {'palettes/palette9123.png', 'palettes/palette9124.png'})
        self.assertEqual(set(self.row(report)['settingsVersions'][0]['files']), {'XX_AI_settings.txt', 'XX_AI_settings-Red.txt', 'XX_AI_properties.txt'})

    def test_no_unmentioned_optional_variants_are_invented(self):
        report = self.f.report()
        self.assertEqual(report['missingFiles'], [])
        self.assertEqual(self.row(report)['settingsVersions'][0]['files'], ['XX_AI_settings.txt'])

    def test_corrupt_setting_reports_invalid_file_and_exact_name(self):
        self.f.cache.with_name('XX_AI_settings-Red.txt').write_bytes(b'\x00')
        row = self.row(self.f.report())
        self.assertEqual([(item['name'], item['reason']) for item in row['missingFiles']], [('XX_AI_settings-Red.txt', 'invalid_file')])

    def test_malformed_ambient_reference_is_not_silently_ignored(self):
        self.f.cache.with_name('XX_AI_settings.txt').write_text('AmbientSounds: malformed\n', 'utf-8')
        row = self.row(self.f.report())
        self.assertEqual(row['missingFiles'][0]['reason'], 'invalid_file')
        self.assertIn('XX_AI_settings.txt', row['settingsVersions'][0]['errors'][0])
        self.assertNotIn(str(self.f.root), json.dumps(row))

    def test_valid_ambient_alternative_prevents_false_missing_dependency(self):
        self.f.cache.with_name('XX_AI_settings.txt').write_text('AmbientSounds: OMNI><wind.wav><1><1><1,\n', 'utf-8')
        path = storage.project_file('selected').parent / 'rooms/assets/soundeffects/wind.wav'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'RIFF' + bytes(4) + b'WAVE' + bytes(32))
        self.assertEqual(self.f.report()['missingFiles'], [])
        self.assertEqual(project_packages.asset_source('selected', 'soundeffects/wind.wav'), path)

    def test_optional_terrain_palette_variants_do_not_become_required(self):
        self.f.cache.with_name('XX_AI_settings.txt').write_text('TerrainPalette: stone\n', 'utf-8')
        root = storage.project_file('selected').parent / 'rooms/assets/terrainpalettes'
        root.mkdir(parents=True)
        for name in ('stone', 'rot'):
            Image.new('RGB', (8, 8), 'white').save(root / (name + '.png'))
        report = self.f.report()
        self.assertEqual(report['missingFiles'], [])
        self.assertTrue(any(asset['missing'] for asset in report['assets']))

    def test_missing_registered_region_template_has_importable_relative_path(self):
        folder = self.f.local / 'world/xx'
        folder.mkdir(parents=True)
        (folder / 'properties.txt').write_text('Room Setting Templates: Storm\n', 'utf-8')
        item = self.row(self.f.report())['missingFiles'][0]
        self.assertEqual(item['kind'], 'region')
        self.assertEqual(item['relative'], 'regions/XX/xx_settingstemplate_storm.txt')
        self.assertEqual(item['targetRelative'], 'rooms/regions/XX/xx_settingstemplate_storm.txt')

    def test_unselected_settings_version_does_not_require_its_missing_palette(self):
        self.f.cache.with_name('XX_AI_settings.txt').write_text('Palette: 9123\n', 'utf-8')
        self.f.render(self.f.output, settings='Effects: \n')
        os.utime(self.f.cache.with_name('XX_AI_settings.txt'), ns=(1000000000, 1000000000))
        row = self.row(self.f.report())
        self.assertTrue(row['settingsConflict'])
        self.assertEqual(row['missingFiles'], [])

    def test_nonexternal_default_settings_follow_original_main_file_timestamp(self):
        self.f.project['editor']['externalRoomTools'] = False
        self.f.render(self.f.output, settings='Effects: ZeroG-0-0-0,\n')
        self.f.cache.with_name('XX_AI_settings-Red.txt').write_text('Effects: ZeroG-1-0-0,\n', 'utf-8')
        for path, stamp in ((self.f.cache.with_name('XX_AI_settings.txt'), 1000000000),
                            (self.f.output.with_name('XX_AI_settings.txt'), 2000000000),
                            (self.f.cache.with_name('XX_AI_settings-Red.txt'), 3000000000)):
            os.utime(path, ns=(stamp, stamp))
        report = self.f.report()
        row = self.row(report)
        chosen = next(value for value in row['settingsVersions'] if value['id'] == row['recommendedSettingsId'])
        self.assertEqual(chosen['origin'], 'local')
        self.assertFalse(report['requiresChoices'])
        with choices.resolution_scope([self.f.project]):
            self.assertEqual(choices.selected_settings('selected', 'XX_AI'), self.f.output.with_name('XX_AI_settings.txt'))

    def test_source_token_tracks_source_bytes_without_timestamp_guess(self):
        source = self.f.source()
        first = self.row(self.f.report())['sourceToken']
        stamp = source.stat()
        source.write_text('[[[changed content]]]', 'utf-8')
        os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        second = self.row(self.f.report())['sourceToken']
        self.assertNotEqual(first, second)
        os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1000))
        self.assertEqual(second, self.row(self.f.report())['sourceToken'])

    def test_legacy_default_template_is_checked_without_replacing_its_export_path(self):
        self.f.project.pop('roomBinding')
        self.f.project['editor']['externalRoomTools'] = False
        with patch.object(choices.room_bindings, 'source_for', return_value=self.f.cache):
            report = self.f.report()
            self.assertTrue(all(row['state'] == 'ready' and not row['syncable'] for row in report['rooms']))
            with choices.resolution_scope([self.f.project]):
                for row in report['rooms']:
                    self.assertIsNone(choices.selected_source('selected', row['room']))

    def test_complete_scan_keeps_every_project_file_and_connection_unchanged(self):
        self.enabled('COT_S01')
        self.f.project['roomConnections'] = {'test': 'preserved without reinterpretation'}
        before = self.f.snapshot()
        project = copy.deepcopy(self.f.project)
        choices.preflight([self.f.project], ['COT_S01'])
        self.assertEqual(self.f.snapshot(), before)
        self.assertEqual(self.f.project, project)

    def test_missing_file_identity_is_stable_and_contains_no_absolute_paths(self):
        self.f.cache.with_name('XX_AI_2.png').unlink()
        first, second = self.f.report(), self.f.report()
        self.assertEqual(first['missingFiles'], second['missingFiles'])
        serialized = json.dumps(first)
        self.assertNotIn(str(self.f.root), serialized)
        self.assertTrue(all(len(item['id']) == 64 for item in first['missingFiles']))

    def supplemented_geometry(self, base):
        name = base.name
        original = base.with_suffix('.txt')
        content = original.read_bytes()
        count = choices.room_bindings.geometry(original)['exitCount']
        original.unlink()
        private = storage.project_file('selected').parent / ('rooms/rendered/' + name + '.txt')
        private.parent.mkdir(parents=True, exist_ok=True)
        private.write_bytes(content)
        folder = private.parent / '.mi-export-imports'
        folder.mkdir(exist_ok=True)
        (folder / ('a' * 32 + '.json')).write_text(json.dumps(dict(schema='moreiterators.export-file-import.v1',
            files=[dict(path='rooms/rendered/' + name + '.txt', sha256=hashlib.sha256(content).hexdigest())])), 'utf-8')
        return count

    def test_connection_check_reads_manually_supplied_geometry(self):
        self.f.render(self.f.output, settings='Effects: \n')
        for path in self.f.cache.parent.glob('XX_AI*'):path.unlink()
        count = self.supplemented_geometry(self.f.output)
        with choices.resolution_scope([self.f.project]):
            with patch.object(project_packages, '_connections', return_value=(['DISCONNECTED'] * count, '', 'saved')):
                check = project_packages.connection_snapshot(self.f.project, 'XX_AI', rows={}, source=self.f.output)
            self.assertEqual(check['actualExitCount'], count)
            self.assertEqual(check['issues'], [])

    def test_playable_extra_plan_reads_selected_supplemented_geometry(self):
        import standalone
        source = self.enabled('COT_S01')
        (self.f.root / 'enabled/modinfo.json').write_text(json.dumps(dict(id='external', name='External')), 'utf-8')
        count = self.supplemented_geometry(source)
        row = dict(name='COT_S01', region='COT', connections=['DISCONNECTED'] * count, tags='', conditional=False)
        catalog = dict(regions=[dict(name='COT', rooms=[row])])
        with choices.resolution_scope([self.f.project], {'extraRooms': ['COT_S01']}):
            with patch.object(choices.room_bindings, 'catalog', return_value=catalog):
                plan = standalone.extra_room_plan({'extraRooms': ['COT_S01']}, [self.f.project],
                    {'selected': ('XX_AI', 'YY_EXISTING')}, SimpleNamespace(roomnames=lambda project: ('XX_AI', 'YY_EXISTING', 'test')))
        self.assertEqual(plan[0]['sourcePath'], source)
        self.assertEqual(plan[0]['connections'], row['connections'])


if __name__ == '__main__':
    unittest.main()
