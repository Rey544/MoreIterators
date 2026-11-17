import hashlib
import json
import os
import unittest
from unittest.mock import patch

import test_project_packages as package_tests
import test_rained_sync_transaction as sync_tests
import project_packages
import playable_export
import room_bindings
import room_source_choices


class ExportRoomRefreshTests(unittest.TestCase):
    setUp = package_tests.ProjectPackageTests.setUp
    validate = package_tests.ProjectPackageTests.validate
    render = package_tests.ProjectPackageTests.render
    palette = package_tests.ProjectPackageTests.palette

    def test_current_room_status_matches_the_export_scan_without_changing_files(self):
        self.project['editor'] = {'externalRoomTools': True}
        self.project_file.write_text(json.dumps(self.project), 'utf-8')
        source = self.project_file.parent / 'rooms/XX_AI.txt'
        source.parent.mkdir(parents=True)
        source.write_text('[[[saved modified geometry]]]', 'utf-8')
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        with patch.object(room_bindings, 'enabled_asset_roots', return_value=[]):
            report = room_source_choices.preflight([self.project])
            listing = project_packages.inspect_choices('selected', self.server)
        expected = next(row for row in report['rooms'] if row['room'] == 'XX_AI')
        actual = next(row for row in listing['rooms'] if row['name'] == 'XX_AI')
        self.assertEqual(actual['state'], 'needs_sync')
        self.assertTrue(actual['available'])
        self.assertTrue(actual['sourceAvailable'])
        self.assertEqual(actual['reason'], expected['reason'])
        self.assertEqual(actual['recommendedSourceId'], expected['recommendedSourceId'])
        after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_fresh_disk_room_is_available_even_when_missing_from_the_game_snapshot(self):
        new_room = self.external / 'world/yy-rooms/YY_NEW'
        self.render(new_room, 'YY_NEW')
        fresh = {'regions': [{'name': 'YY', 'rooms': [{'name': 'YY_NEW', 'geometryPath': str(new_room.with_suffix('.txt'))}]}]}
        with patch.object(room_bindings, 'offline_catalog', return_value=fresh) as scan:
            listing = project_packages.inspect_choices('selected', self.server)
        room = next(row for row in listing['rooms'] if row['name'] == 'YY_NEW')
        self.assertTrue(room['available'])
        self.assertFalse(room['required'])
        scan.assert_called_once_with(refresh=True, include_reserved=False)

    def test_room_listing_can_skip_duplicate_preflight(self):
        with patch.object(room_source_choices, 'preflight', side_effect=AssertionError('duplicate preflight')):
            listing = project_packages.inspect_choices('selected', self.server, check=False)
        self.assertEqual({row['name'] for row in listing['rooms'] if row['required']}, {'XX_AI', 'XX_ENTRY'})

    def test_source_listing_reads_new_files_and_only_checks_matching_names(self):
        source_dir = self.project_file.parent / 'rooms'
        source_dir.mkdir()
        (source_dir / 'XX_AI.txt').write_text('source', 'utf-8')
        with patch.object(project_packages, '_safe', wraps=project_packages._safe) as safe:
            first = project_packages.inspect_choices('selected', self.server, check=False)
        rooms = {row['name']: row for row in first['rooms']}
        self.assertTrue(rooms['XX_AI']['sourceAvailable'])
        self.assertFalse(rooms['XX_ENTRY']['sourceAvailable'])
        self.assertFalse(any(call.args[1] == 'rooms/XX_ENTRY.txt' for call in safe.call_args_list))
        (source_dir / 'XX_ENTRY.txt').write_text('new source', 'utf-8')
        second = project_packages.inspect_choices('selected', self.server, check=False)
        self.assertTrue(next(row for row in second['rooms'] if row['name'] == 'XX_ENTRY')['sourceAvailable'])

    def test_source_listing_preserves_filename_case_behavior(self):
        source_dir = self.project_file.parent / 'rooms'
        source_dir.mkdir()
        (source_dir / 'xx_ai.txt').write_text('source', 'utf-8')
        listing = project_packages.inspect_choices('selected', self.server, check=False)
        self.assertEqual(next(row for row in listing['rooms'] if row['name'] == 'XX_AI')['sourceAvailable'], (source_dir / 'XX_AI.txt').is_file())

    def test_source_listing_rejects_linked_directories_and_matching_files(self):
        source_dir = self.project_file.parent / 'rooms'
        outside = self.root / 'outside'
        outside.mkdir()
        try:os.symlink(outside, source_dir, target_is_directory=True)
        except OSError as error:self.skipTest(str(error))
        with self.assertRaisesRegex(ValueError, '链接'):
            project_packages.inspect_choices('selected', self.server, check=False)
        source_dir.unlink()
        source_dir.mkdir()
        (outside / 'XX_AI.txt').write_text('source', 'utf-8')
        os.symlink(outside / 'XX_AI.txt', source_dir / 'XX_AI.txt')
        with self.assertRaisesRegex(ValueError, '链接'):
            project_packages.inspect_choices('selected', self.server, check=False)

    def test_source_listing_keeps_path_checks_before_directory_and_file_reads(self):
        source_dir = self.project_file.parent / 'rooms'
        source_dir.mkdir()
        source = source_dir / 'XX_AI.txt'
        source.write_text('source', 'utf-8')
        original = type(source).is_symlink
        for rejected in (source_dir, source):
            with self.subTest(path=rejected.name), patch.object(type(source), 'is_symlink', lambda path: path == rejected or original(path)):
                with self.assertRaisesRegex(ValueError, '链接'):
                    project_packages.inspect_choices('selected', self.server, check=False)

    def test_json_format_preference_does_not_require_room_files(self):
        with patch.object(project_packages, 'inspect_choices', side_effect=AssertionError('room scan')):
            result = playable_export.save_preferences({'settingsProject': 'selected', 'projects': ['selected'], 'format': 'json'}, self.server)
        self.assertTrue(result['ok'])
        value = json.loads((self.project_file.parent / 'export-settings.json').read_text('utf-8'))
        self.assertEqual(value['format'], 'json')

    def test_empty_templates_do_not_capture_following_parameters(self):
        for newline in ('\n', '\r\n'):
            project_packages._check_template('Template: \t' + newline + 'AmbientSounds:', 'XX_AI')
            project_packages._check_template('Room Setting Templates:' + newline + 'Palette: 8', 'XX', properties=True)


class ExportSyncOnlyTests(unittest.TestCase):
    setUp = sync_tests.RainedSyncTransactionTests.setUp
    start = sync_tests.RainedSyncTransactionTests.start
    stop = sync_tests.RainedSyncTransactionTests.stop
    request = sync_tests.RainedSyncTransactionTests.request
    output = sync_tests.RainedSyncTransactionTests.output

    def test_sync_for_export_updates_cache_without_applying_to_game(self):
        output = self.output()
        roots = [self.data / 'local-mod', self.assets / 'mods', self.data / 'runtime', self.data / 'archive/project-history']
        snapshot = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for root in roots for p in root.rglob('*') if p.is_file()}
        before = snapshot()
        project_before = (self.directory / 'project.json').read_bytes()
        result = self.request('/api/sync-room', {'projectId': self.pid, 'kind': 'entry', 'apply': False})
        self.assertEqual(result['room'], self.binding['entry'])
        self.assertEqual((self.directory / 'rooms/rendered' / output.with_suffix('.txt').name).read_bytes(), output.with_suffix('.txt').read_bytes())
        self.assertEqual(snapshot(), before)
        self.assertEqual((self.directory / 'project.json').read_bytes(), project_before)

    def test_invalid_sync_flag_is_rejected_before_render(self):
        result = self.request('/api/sync-room', {'projectId': self.pid, 'kind': 'entry', 'apply': 'false'}, status=400)
        self.assertIn('Invalid room sync request', result['error'])


if __name__ == '__main__':
    unittest.main()
