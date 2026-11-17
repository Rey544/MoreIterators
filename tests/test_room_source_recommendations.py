import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import room_source_choices as choices
import storage


class RoomSourceRecommendationTests(unittest.TestCase):
    def setUp(self):
        from test_room_source_choices import RoomSourceChoiceTests
        self.f = RoomSourceChoiceTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        from PIL import Image
        folder = storage.project_file('selected').parent / 'rooms/palettes'
        folder.mkdir(parents=True, exist_ok=True)
        for index in (9100, 9200, 9300):
            Image.new('RGB', (8, 8), 'white').save(folder / ('palette' + str(index) + '.png'))
        context = patch.dict(storage.settings, {}, clear=True)
        context.start()
        self.addCleanup(context.stop)

    def stamp(self, base, value, settings=None):
        for path in base.parent.glob(base.name + '*'):
            if path.is_file():
                stamp = settings if settings is not None and '_settings' in path.name else value
                os.utime(path, ns=(stamp, stamp))

    def certificate(self):
        record = choices.pairing_record('selected', 'XX_AI')
        self.f.cache.with_name('XX_AI.source.json').write_text(json.dumps(record), 'utf-8')
        return record

    def rained(self):
        exe = self.f.root / 'rained/Rained.exe'
        exe.parent.mkdir()
        exe.touch()
        data = self.f.root / 'custom-rained-data'
        data.mkdir()
        config = exe.parent / 'config'
        config.mkdir()
        (config / 'preferences.json').write_text(json.dumps({'dataPath': str(data)}), 'utf-8')
        storage.settings['rainedExecutable'] = str(exe)
        return data / 'Levels/XX_AI'

    def test_ready_recommends_latest_complete_render_and_settings_independently(self):
        f = self.f
        f.render(f.output, color='blue', settings='Palette: 9200\n')
        f.render(f.live, color='red', settings='Palette: 9300\n')
        self.stamp(f.cache, 1000000000)
        self.stamp(f.output, 3000000000, settings=2000000000)
        self.stamp(f.live, 2000000000, settings=4000000000)
        before = f.snapshot()
        report = f.report()
        row = report['rooms'][0]
        self.assertEqual(row['state'], 'ready')
        self.assertTrue(report['requiresChoices'])
        render = next(v for v in row['renderVersions'] if v['id'] == row['recommendedSourceId'])
        setting = next(v for v in row['settingsVersions'] if v['id'] == row['recommendedSettingsId'])
        self.assertEqual(render['origin'], 'local')
        self.assertEqual(setting['origin'], 'installed')
        with choices.resolution_scope([f.project], {'snapshotToken': report['snapshotToken'], 'choices': {
                'selected/XX_AI': {'source': row['recommendedSourceId'], 'settings': row['recommendedSettingsId']}}}):
            self.assertEqual(choices.selected_source('selected', 'XX_AI'), f.output)
            self.assertEqual(choices.selected_settings('selected', 'XX_AI'), f.live.with_name('XX_AI_settings.txt'))
        self.assertEqual(f.snapshot(), before)

    def test_incomplete_newer_render_is_not_recommended(self):
        f = self.f
        f.render(f.output, color='blue')
        f.output.with_name('XX_AI_2.png').unlink()
        self.stamp(f.output, 2000000000000000000)
        row = f.report()['rooms'][0]
        self.assertEqual(row['state'], 'ready')
        selected = next(v for v in row['renderVersions'] if v['id'] == row['recommendedSourceId'])
        self.assertEqual(selected['origin'], 'project')

    def test_missing_camera_has_a_filename_and_no_recommendation(self):
        f = self.f
        f.cache.with_name('XX_AI_2.png').unlink()
        row = f.report()['rooms'][0]
        self.assertEqual(row['state'], 'missing')
        self.assertIn('XX_AI_2.png', row['missing'])
        self.assertIsNone(row['recommendedSourceId'])

    def test_unchanged_source_hash_ignores_timestamp_only_touch(self):
        f = self.f
        source = f.source()
        self.certificate()
        os.utime(source, ns=(2000000000000000000, 2000000000000000000))
        before = f.snapshot()
        row = f.report()['rooms'][0]
        self.assertEqual(row['state'], 'ready')
        self.assertTrue(row['renderVersions'][0]['pairedSource'])
        self.assertEqual(f.enter(), f.cache)
        self.assertEqual(f.snapshot(), before)

    def test_source_hash_change_requires_sync_even_with_unchanged_timestamp(self):
        f = self.f
        source = f.source()
        self.certificate()
        stamp = source.stat()
        source.write_text('[[[authored change]]]', 'utf-8')
        os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        row = f.report()['rooms'][0]
        self.assertEqual((row['state'], row['reason']), ('needs_sync', 'source_changed'))
        self.assertFalse(row['renderVersions'][0]['pairedSource'])
        f.assertCode('room_choices_needs_sync', f.enter)

    def test_manifest_source_hash_proof_precedes_timestamps(self):
        f = self.f
        source = f.source()
        root = storage.project_file('selected').parent
        files = [source, f.cache.with_suffix('.txt'), f.cache.with_name('XX_AI_1.png'), f.cache.with_name('XX_AI_2.png')]
        manifest = dict(schema=choices.LOCAL_SCHEMA, projectId='selected', rooms=[dict(name='XX_AI', sourceAvailable=True)],
                        files=[dict(path=p.relative_to(root).as_posix(), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files])
        (root / 'room-package.json').write_text(json.dumps(manifest), 'utf-8')
        os.utime(source, ns=(2000000000000000000, 2000000000000000000))
        self.assertEqual(f.report()['rooms'][0]['state'], 'ready')

    def test_changed_source_light_map_does_not_bypass_sync_when_unreadable(self):
        from PIL import Image
        f = self.f
        source = f.source()
        light = source.with_suffix('.png')
        Image.new('RGB', (8, 8), 'white').save(light)
        self.certificate()
        stamp = light.stat()
        light.write_bytes(b'broken light map')
        os.utime(light, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        row = f.report()['rooms'][0]
        self.assertEqual((row['state'], row['reason']), ('needs_sync', 'source_changed'))
        self.assertFalse(row['sourceAvailable'])
        f.assertCode('room_choices_needs_sync', f.enter)

    def test_unpaired_new_source_needs_sync_without_calling_it_missing(self):
        f = self.f
        self.stamp(f.cache, 1000000000)
        source = f.source()
        os.utime(source, ns=(2000000000, 2000000000))
        row = f.report()['rooms'][0]
        self.assertEqual(row['state'], 'needs_sync')
        self.assertFalse(row['renderVersions'][0]['pairedSource'])

    def test_unpaired_older_source_is_not_reported_as_verified(self):
        f = self.f
        source = f.source()
        os.utime(source, ns=(1000000000, 1000000000))
        self.stamp(f.cache, 2000000000)
        row = f.report()['rooms'][0]
        self.assertEqual(row['state'], 'ready')
        self.assertFalse(row['renderVersions'][0]['pairedSource'])

    def test_no_render_with_editable_source_is_needs_sync(self):
        f = self.f
        f.source()
        f.cache.with_suffix('.txt').unlink()
        f.cache.with_name('XX_AI_1.png').unlink()
        f.cache.with_name('XX_AI_2.png').unlink()
        row = f.report()['rooms'][0]
        self.assertEqual(row['state'], 'needs_sync')
        self.assertIsNone(row['recommendedSourceId'])

    def test_configured_rained_output_is_scanned_without_copying_or_requiring_settings(self):
        f = self.f
        output = self.rained()
        f.render(output, color='blue')
        output.with_name('XX_AI_settings.txt').unlink()
        self.stamp(f.cache, 1000000000)
        self.stamp(output, 2000000000)
        unrelated = output.with_name('XX_OTHER')
        f.render(unrelated, name='XX_OTHER')
        before = f.snapshot()
        row = f.report()['rooms'][0]
        version = next(v for v in row['renderVersions'] if v['origin'] == 'rained')
        self.assertEqual(row['recommendedSourceId'], version['id'])
        self.assertFalse(version['pairedSource'])
        self.assertTrue(version['complete'])
        self.assertEqual(row['state'], 'ready')
        self.assertFalse(any(v['origin'] == 'rained' for v in row['settingsVersions']))
        self.assertNotIn(str(f.root), json.dumps(row))
        self.assertEqual(f.snapshot(), before)

    def test_unconfigured_rained_is_not_discovered_or_scanned(self):
        import room_editor
        with patch.object(room_editor, 'rained_data_root', side_effect=AssertionError('unexpected discovery')):
            self.assertEqual(self.f.report()['rooms'][0]['state'], 'ready')

    def test_rained_data_directory_change_invalidates_the_report(self):
        f = self.f
        output = self.rained()
        f.render(output, color='blue')
        report = f.report()
        row = report['rooms'][0]
        selected = next(v['id'] for v in row['renderVersions'] if v['origin'] == 'rained')
        new_data = f.root / 'another-rained-data'
        new_data.mkdir()
        preferences = Path(storage.settings['rainedExecutable']).parent / 'config/preferences.json'
        preferences.write_text(json.dumps({'dataPath': str(new_data)}), 'utf-8')
        f.assertCode('room_choices_stale', lambda: f.enter({'snapshotToken': report['snapshotToken'],
            'choices': {'selected/XX_AI': {'source': selected, 'settings': row['recommendedSettingsId']}}}))

    def test_rained_same_mtime_content_change_invalidates_the_report(self):
        from PIL import Image
        f = self.f
        output = self.rained()
        f.render(output, color='blue')
        report = f.report()
        row = report['rooms'][0]
        selected = next(v['id'] for v in row['renderVersions'] if v['origin'] == 'rained')
        camera = output.with_name('XX_AI_1.png')
        stamp = camera.stat()
        Image.new('RGB', (8, 8), 'red').save(camera)
        os.utime(camera, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        f.assertCode('room_choices_stale', lambda: f.enter({'snapshotToken': report['snapshotToken'],
            'choices': {'selected/XX_AI': {'source': selected, 'settings': row['recommendedSettingsId']}}}))

    def test_same_render_dedupes_rained_and_retains_pairing_proof(self):
        f = self.f
        f.source()
        self.certificate()
        output = self.rained()
        f.render(output)
        report = f.report()
        row = report['rooms'][0]
        self.assertEqual(len(row['renderVersions']), 1)
        self.assertEqual(set(row['renderVersions'][0]['origins']), {'project', 'rained'})
        self.assertTrue(row['renderVersions'][0]['pairedSource'])
        self.assertEqual(row['state'], 'ready')
        self.assertFalse(report['requiresChoices'])

    def test_newer_unpaired_rained_render_does_not_hide_a_proven_source_change(self):
        f = self.f
        source = f.source()
        self.certificate()
        source.write_text('[[[new unsynced geometry]]]', 'utf-8')
        output = self.rained()
        f.render(output, color='blue')
        self.stamp(output, 2000000000000000000)
        row = f.report()['rooms'][0]
        self.assertEqual(row['state'], 'needs_sync')
        self.assertFalse(next(v for v in row['renderVersions'] if v['origin'] == 'rained')['pairedSource'])

    def test_same_mtime_different_render_content_remains_an_explicit_choice(self):
        f = self.f
        f.render(f.output, color='blue')
        self.stamp(f.cache, 1000000000)
        self.stamp(f.output, 1000000000)
        first = f.report()
        second = f.report()
        self.assertTrue(first['requiresChoices'])
        self.assertTrue(first['rooms'][0]['sourceConflict'])
        self.assertEqual(first['rooms'][0]['recommendedSourceId'], second['rooms'][0]['recommendedSourceId'])
        f.assertCode('room_choices_required', f.enter)

    def test_saved_parameter_modes_do_not_prompt_or_mutate_project(self):
        f = self.f
        f.project['design'].update(roomPaletteMode='mi', roomGravityMode='mi', entryGravityMode='zero')
        f.cache.with_name('XX_AI_settings.txt').write_text('Palette: 9100\nEffects: ZeroG-1-0-0,\n', 'utf-8')
        before = copy.deepcopy(f.project)
        report = f.report()
        self.assertEqual(report['parameterConflicts'], [])
        self.assertFalse(report['requiresChoices'])
        with choices.resolution_scope([f.project]):
            self.assertEqual(choices.export_project(f.project), before)
        self.assertEqual(f.project, before)

    def test_unflagged_project_does_not_scan_configured_rained(self):
        f = self.f
        self.rained()
        f.project['editor']['externalRoomTools'] = False
        import room_editor
        with patch.object(room_editor, 'rained_data_root', side_effect=AssertionError('unexpected scan')):
            self.assertEqual([row['room'] for row in f.report()['rooms']], ['XX_AI', 'YY_EXISTING'])
            self.assertEqual(f.enter(), f.cache)


if __name__ == '__main__':
    unittest.main()
