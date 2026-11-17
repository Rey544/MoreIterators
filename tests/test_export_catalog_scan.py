import copy
from unittest.mock import patch
import unittest

import test_enabled_room_catalog as fixtures
import room_bindings as rooms
import storage


class ExportCatalogScanTests(unittest.TestCase):
    setUp = fixtures.EnabledRoomCatalogTests.setUp
    mod = fixtures.EnabledRoomCatalogTests.mod
    world = fixtures.EnabledRoomCatalogTests.world
    enable = fixtures.EnabledRoomCatalogTests.enable
    snapshot = fixtures.EnabledRoomCatalogTests.snapshot

    def names(self, value):
        return {row['name'] for region in value['regions'] for row in region['rooms']}

    def test_export_does_not_scan_disabled_reserved_roots(self):
        self.mod('on', 'on.mod', 'XX', 'XX_A01')
        self.mod('off', 'off.mod', 'YY', 'YY_A01')
        self.enable(['on.mod'])
        with patch.object(rooms, '_asset_roots', side_effect=AssertionError('reserved scan must not run')):
            value = rooms.offline_catalog(include_reserved=False, refresh=True)
            self.assertEqual(self.names(value), {'SU_A01', 'XX_A01'})
            self.assertEqual(value['reservedRooms'], [])
            self.assertEqual(value['reservedRegions'], [])
            self.assertEqual(rooms.catalog(include_reserved=False)['regions'], value['regions'])

    def test_full_and_export_caches_are_independent_and_return_copies(self):
        self.mod('off', 'off.mod', 'YY', 'YY_A01')
        self.enable([])
        with patch.object(rooms, '_asset_roots', wraps=rooms._asset_roots) as scan:
            slim = rooms.offline_catalog(include_reserved=False, refresh=True)
            full = rooms.offline_catalog()
            self.assertEqual(scan.call_count, 1)
            self.assertIn('YY_A01', full['reservedRooms'])
            self.assertEqual(slim['reservedRooms'], [])
            full['reservedRooms'].clear()
            slim['regions'].clear()
            self.assertIn('YY_A01', rooms.offline_catalog()['reservedRooms'])
            self.assertIn('SU_A01', self.names(rooms.offline_catalog(include_reserved=False)))
            rooms.offline_catalog(include_reserved=False, refresh=True)
            self.assertIn('YY_A01', rooms.offline_catalog()['reservedRooms'])
            self.assertEqual(scan.call_count, 1)

    def test_export_refresh_discovers_new_world_and_geometry(self):
        enabled = self.mod('on', 'on.mod', 'XX', 'XX_A01')
        self.enable(['on.mod'])
        rooms.offline_catalog(include_reserved=False, refresh=True)
        geometry = self.world(enabled, 'ZZ', 'ZZ_NEW')
        self.assertNotIn('ZZ_NEW', self.names(rooms.offline_catalog(include_reserved=False)))
        value = rooms.offline_catalog(include_reserved=False, refresh=True)
        row = next(row for region in value['regions'] for row in region['rooms'] if row['name'] == 'ZZ_NEW')
        self.assertEqual(row['geometryPath'], str(geometry))
        self.assertFalse(row['verified'])

    def test_export_enable_changes_invalidate_cache_immediately(self):
        self.mod('on', 'on.mod', 'XX', 'XX_A01')
        self.enable(['on.mod'])
        self.assertIn('XX_A01', self.names(rooms.offline_catalog(include_reserved=False)))
        self.enable([])
        self.assertNotIn('XX_A01', self.names(rooms.offline_catalog(include_reserved=False)))

    def test_export_preserves_live_stale_and_enabled_filtering(self):
        enabled = self.mod('on', 'on.mod', 'XX', 'XX_A01')
        disabled = self.mod('off', 'off.mod', 'YY', 'YY_A01')
        self.enable(['on.mod'])
        rows = [dict(name='XX_A01', geometryPath=str(enabled / 'world/xx-rooms/xx_a01.txt')),
                dict(name='YY_A01', geometryPath=str(disabled / 'world/yy-rooms/yy_a01.txt'))]
        for stale, source in ((False, 'live'), (True, 'stale')):
            with self.subTest(stale=stale):
                self.snapshot(['on.mod'], rows, stale=stale)
                value = rooms.catalog(include_reserved=False)
                self.assertEqual(value['source'], source)
                self.assertEqual(value['fresh'], not stale)
                self.assertEqual(self.names(value), {'XX_A01'})
                self.assertEqual(value['reservedRooms'], [])

    def test_default_rename_validation_keeps_disabled_room_collision(self):
        self.mod('off', 'off.mod', 'TEST', 'TEST_DISABLED')
        self.enable([])
        rooms.offline_catalog(include_reserved=False, refresh=True)
        project = dict(projectId='one', name='One')
        original = copy.deepcopy(project)
        binding = dict(region='TEST', ai='TEST_DISABLED', entry='TEST_ENTRY', oracleId='one_oracle',
                       entryMode='copy', aiNode=0, entryNode=0)
        with patch.object(rooms, '_projects', return_value=[project]), patch.object(rooms, '_fixed', return_value=None):
            with self.assertRaises(rooms.RoomBindingError) as caught:
                rooms.validate(project, binding)
        self.assertEqual(caught.exception.code, 'rooms.error.roomTaken')
        self.assertEqual(caught.exception.params['room'], 'TEST_DISABLED')
        self.assertEqual(project, original)

    def test_legacy_purge_reset_invalidates_both_catalog_caches(self):
        self.enable([])
        rooms.offline_catalog(refresh=True)
        rooms.offline_catalog(include_reserved=False, refresh=True)
        self.world(self.assets, 'ZZ', 'ZZ_NEW')
        rooms._offline_cache = None
        rooms._offline_at = 0
        self.assertIn('ZZ_NEW', self.names(rooms.offline_catalog()))
        self.assertIn('ZZ_NEW', self.names(rooms.offline_catalog(include_reserved=False)))

    def test_original_positional_true_still_refreshes_full_catalog(self):
        self.enable([])
        rooms.offline_catalog(True)
        disabled = self.mod('off', 'off.mod', 'YY', 'YY_OLD')
        rooms.offline_catalog(True)
        self.world(disabled, 'YY', 'YY_NEW')
        self.assertNotIn('YY_NEW', rooms.offline_catalog()['reservedRooms'])
        self.assertIn('YY_NEW', rooms.offline_catalog(True)['reservedRooms'])


if __name__ == '__main__':
    unittest.main()
