import hashlib
import os
import time
import unittest

import test_rained_sync_transaction as sync_tests


class ExportAutoSyncSettingsTests(unittest.TestCase):
    setUp = sync_tests.RainedSyncTransactionTests.setUp
    start = sync_tests.RainedSyncTransactionTests.start
    stop = sync_tests.RainedSyncTransactionTests.stop
    request = sync_tests.RainedSyncTransactionTests.request
    output = sync_tests.RainedSyncTransactionTests.output
    protected = sync_tests.RainedSyncTransactionTests.protected

    def exported_sync(self):
        return self.request('/api/sync-room', dict(projectId=self.pid, kind='entry', apply=False, forExport=True))

    def test_export_sync_copies_all_existing_setting_variants_without_deployment(self):
        self.output()
        name = self.binding['entry']
        folder = self.data / 'local-mod/world/test-rooms'
        folder.mkdir(parents=True, exist_ok=True)
        files = {
            name + '_settings.txt': b'Palette: 13\nAmbientSounds: \nTriggers: \n',
            name + '_settings-White.txt': b'Palette: 8\nExternalSetting: untouched\n',
            name + '_settings-Spear.txt': b'Palette: 12\n',
            name + '_properties.txt': b'Shelter: False\n',
        }
        for filename, content in files.items():(folder / filename).write_bytes(content)
        stamp = time.time() + 10
        os.utime(folder / (name + '_settings.txt'), (stamp, stamp))
        roots = [self.data / 'local-mod', self.assets / 'mods', self.data / 'runtime']
        snapshot = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for root in roots for p in root.rglob('*') if p.is_file()}
        before = snapshot()
        project_before = (self.directory / 'project.json').read_bytes()
        self.exported_sync()
        for filename, content in files.items():self.assertEqual((self.directory / 'rooms/rendered' / filename).read_bytes(), content)
        self.assertEqual(before, snapshot())
        self.assertEqual(project_before, (self.directory / 'project.json').read_bytes())

    def test_export_sync_does_not_invent_settings_from_the_native_template(self):
        self.output()
        name = self.binding['entry']
        for root in (self.directory / 'rooms/rendered', self.data / 'local-mod/world/test-rooms', self.assets / 'mods/more_iterators_local/world/test-rooms'):
            (root / (name + '_settings.txt')).unlink(missing_ok=True)
        before = self.protected()
        result = self.request('/api/sync-room', dict(projectId=self.pid, kind='entry', apply=False, forExport=True), status=400)
        self.assertIn(name + '_settings.txt', result['error'])
        self.assertEqual(before, self.protected())

    def test_invalid_setting_variant_prevents_sync_before_replacing_cache(self):
        self.output()
        variant = self.directory / 'rooms/rendered' / (self.binding['entry'] + '_settings-White.txt')
        variant.mkdir()
        before = self.protected()
        result = self.request('/api/sync-room', dict(projectId=self.pid, kind='entry', apply=False, forExport=True), status=400)
        self.assertIn(variant.name, result['error'])
        self.assertEqual(before, self.protected())

    def test_export_sync_rejects_game_apply_and_invalid_request_flags(self):
        self.output()
        before = self.protected()
        for apply, flag in ((True, True), (False, 'true'), (False, None)):
            result = self.request('/api/sync-room', dict(projectId=self.pid, kind='entry', apply=apply, forExport=flag), status=400)
            self.assertEqual(result['details'], 'Invalid room sync request.')
        self.assertEqual(before, self.protected())


if __name__ == '__main__':
    unittest.main()
