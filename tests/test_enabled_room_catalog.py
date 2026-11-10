import copy
import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import room_bindings as rooms
import storage


class EnabledRoomCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'steamapps/common/Rain World'
        self.assets = self.game / 'RainWorld_Data/StreamingAssets'
        self.workshop = self.root / 'steamapps/workshop/content/312520'
        self.options = self.root / 'profile/options'
        self.assets.mkdir(parents=True)
        (self.game / 'RainWorld.exe').touch()
        (self.assets / 'GameVersion.txt').write_text('v1.11.8', 'utf-8')
        for name, value in [('GAME', self.game), ('DATA', self.root / 'data'),
                            ('RUNTIME', self.root / 'data/runtime'), ('LINKS', [])]:
            replacement = patch.object(storage, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        replacement = patch.object(rooms, '_options_paths', return_value=[self.options])
        replacement.start()
        self.addCleanup(replacement.stop)
        self.base_geometry = self.world(self.assets, 'SU', 'SU_A01')

    def mod(self, folder, mid, region, name, workshop=False):
        base = (self.workshop if workshop else self.assets / 'mods') / folder
        base.mkdir(parents=True)
        (base / 'modinfo.json').write_text(json.dumps(dict(id=mid)), 'utf-8')
        self.world(base, region, name)
        return base

    def world(self, base, region, room):
        world = base / 'world' / region.lower() / ('world_' + region.lower() + '.txt')
        world.parent.mkdir(parents=True, exist_ok=True)
        world.write_text('ROOMS\n' + room + ' : DISCONNECTED\nEND ROOMS\n', 'utf-8')
        geometry = base / 'world' / (region.lower() + '-rooms') / (room.lower() + '.txt')
        geometry.parent.mkdir(parents=True, exist_ok=True)
        geometry.write_text('room geometry', 'utf-8')
        return geometry

    def enable(self, ids, order=None, xml=False):
        text = 'EnabledMods<optB>' + '<optC>'.join(ids) + '<optA>'
        text += 'ModLoadOrder<optB>' + '<optC>'.join(mid + '<optD>' + str(n) for mid, n in (order or {}).items()) + '<optA>'
        if xml:
            doc = ET.Element('UserData')
            ET.SubElement(ET.SubElement(doc, 'Keys'), 'string').text = 'options'
            ET.SubElement(ET.SubElement(doc, 'Values'), 'string').text = text
            text = ET.tostring(doc, encoding='unicode')
        self.options.parent.mkdir(parents=True, exist_ok=True)
        self.options.write_text(text, 'utf-8')

    def snapshot(self, ids, rows, stale=False):
        now = datetime.datetime.now(datetime.timezone.utc)
        if stale:now -= datetime.timedelta(minutes=5)
        value = dict(schema=rooms.SCHEMA, activeMods=ids, generation='test', complete=True,
                     capturedAt=now.isoformat(), regions=[dict(name=row['name'].split('_')[0], rooms=[row]) for row in rows])
        path = storage.RUNTIME / 'creator/room-catalog.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), 'utf-8')
        if stale and self.options.exists():
            os.utime(self.options, (now.timestamp() - 10, now.timestamp() - 10))
        return path

    def names(self):
        return {row['name'] for region in rooms.catalog()['regions'] for row in region['rooms']}

    def test_unknown_state_only_lists_base_but_reserves_disabled_names(self):
        self.mod('off', 'off.mod', 'XX', 'XX_A01')
        self.assertEqual(self.names(), {'SU_A01'})
        self.assertIn('XX_A01', rooms.catalog()['reservedRooms'])
        self.assertIn('XX', rooms.catalog()['reservedRegions'])

    def test_xml_options_enable_pure_content_without_loader_entry(self):
        self.mod('content', 'map.only', 'XX', 'XX_A01')
        self.mod('disabled', 'map.disabled', 'YY', 'YY_A01')
        (self.assets / 'enabledMods.txt').write_text('', 'utf-8')
        self.enable(['map.only'], xml=True)
        self.assertEqual(self.names(), {'SU_A01', 'XX_A01'})

    def test_loader_file_does_not_enable_disabled_assets(self):
        self.mod('off', 'off.mod', 'XX', 'XX_A01')
        (self.assets / 'enabledMods.txt').write_text('off', 'utf-8')
        self.enable([])
        self.assertEqual(self.names(), {'SU_A01'})

    def test_invalid_options_never_fall_back_to_all_installs(self):
        self.mod('off', 'off.mod', 'XX', 'XX_A01')
        self.options.parent.mkdir(parents=True)
        self.options.write_text('<broken XML', 'utf-8')
        self.assertEqual(self.names(), {'SU_A01'})

    def test_empty_xml_options_value_is_unknown(self):
        self.mod('off', 'off.mod', 'XX', 'XX_A01')
        self.options.parent.mkdir(parents=True)
        self.options.write_text('<UserData><Keys><string>options</string></Keys><Values><string /></Values></UserData>', 'utf-8')
        self.assertEqual(self.names(), {'SU_A01'})

    def test_malformed_snapshot_does_not_break_room_list(self):
        self.enable([])
        path = storage.RUNTIME / 'creator/room-catalog.json'
        path.parent.mkdir(parents=True)
        for value in ([], None, 123, 'wrong', dict(schema=rooms.SCHEMA, regions=[], capturedAt=None)):
            with self.subTest(value=value):
                path.write_text(json.dumps(value), 'utf-8')
                self.assertEqual(self.names(), {'SU_A01'})

    def test_dlc_must_be_enabled(self):
        dlc = self.mod('moreslugcats', 'moreslugcats', 'DM', 'DM_AI')
        self.enable([])
        self.assertNotIn('DM_AI', self.names())
        self.assertFalse(rooms.is_enabled_asset(dlc / 'palettes/palette1.png'))
        self.enable(['moreslugcats'])
        self.assertIn('DM_AI', self.names())

    def test_local_same_id_wins_and_workshop_path_is_rejected(self):
        local = self.mod('local', 'same.mod', 'XX', 'XX_LOCAL')
        remote = self.mod('100', 'same.mod', 'XX', 'XX_WORKSHOP', workshop=True)
        self.enable(['same.mod'])
        self.assertEqual(self.names(), {'SU_A01', 'XX_LOCAL'})
        self.assertTrue(rooms.is_enabled_asset(local / 'world/xx-rooms/xx_local.txt'))
        self.assertFalse(rooms.is_enabled_asset(remote / 'world/xx-rooms/xx_workshop.txt'))
        self.assertIn('XX_WORKSHOP', rooms.catalog()['reservedRooms'])

    def test_disabled_under_streaming_assets_cannot_bypass_root_check(self):
        disabled = self.mod('off', 'off.mod', 'XX', 'XX_A01')
        self.enable([])
        self.assertFalse(rooms.is_enabled_asset(disabled / 'world/xx-rooms/xx_a01.txt'))
        self.assertFalse(rooms.is_enabled_asset(self.assets / 'mergedmods/world/xx-rooms/xx_a01.txt'))
        self.assertTrue(rooms.is_enabled_asset(self.base_geometry))

    def test_targeted_version_then_newest_then_root(self):
        mod = self.mod('on', 'on.mod', 'XX', 'XX_ROOT')
        self.world(mod / 'newest', 'XX', 'XX_NEWEST')
        self.world(mod / 'v1.11.8', 'XX', 'XX_TARGET')
        self.world(mod / 'v1.10.0', 'OLD', 'OLD_ROOM')
        self.enable(['on.mod'])
        self.assertEqual(self.names(), {'SU_A01', 'XX_TARGET'})
        self.assertFalse(rooms.is_enabled_asset(mod / 'v1.10.0/world/old-rooms/old_room.txt'))

    def test_geometry_index_uses_enabled_priority_and_explicit_refresh(self):
        mod = self.mod('on', 'on.mod', 'SU', 'SU_A01')
        newest = self.world(mod / 'newest', 'SU', 'SU_A01')
        self.enable(['on.mod'])
        roots = rooms.enabled_asset_roots()
        self.assertEqual(rooms.room_geometry_index(roots)[('SU', 'SU_A01')], newest)
        added = self.world(mod, 'XX', 'XX_NEW')
        self.assertNotIn(('XX', 'XX_NEW'), rooms.room_geometry_index(roots))
        self.assertEqual(rooms.room_geometry_index(roots, refresh=True)[('XX', 'XX_NEW')], added)

    def test_geometry_index_skips_settings_and_unknown_version(self):
        mod = self.mod('on', 'on.mod', 'XX', 'XX_A01')
        self.world(mod / 'v1.10.0', 'OLD', 'OLD_A01')
        (mod / 'world/xx-rooms/xx_a01_settings.txt').write_text('Palette: 25', 'utf-8')
        self.enable(['on.mod'])
        index = rooms.room_geometry_index()
        self.assertNotIn(('OLD', 'OLD_A01'), index)
        self.assertNotIn(('XX', 'XX_A01_SETTINGS'), index)

    def test_highest_load_order_wins_and_ties_are_stable(self):
        first = self.mod('a', 'a.mod', 'XX', 'XX_A')
        second = self.mod('b', 'b.mod', 'XX', 'XX_B')
        self.enable(['a.mod', 'b.mod'], {'a.mod': 4, 'b.mod': 4})
        self.assertEqual(self.names(), {'SU_A01', 'XX_B'})
        self.enable(['a.mod', 'b.mod'], {'a.mod': 5, 'b.mod': 4})
        self.assertEqual(self.names(), {'SU_A01', 'XX_A'})
        self.assertLess(rooms.enabled_asset_roots().index(first), rooms.enabled_asset_roots().index(second))

    def test_disable_invalidates_cache_immediately(self):
        self.mod('on', 'on.mod', 'XX', 'XX_A01')
        self.enable(['on.mod'])
        before = rooms.asset_selection_key()
        self.assertIn('XX_A01', self.names())
        self.enable([])
        self.assertNotEqual(before, rooms.asset_selection_key())
        self.assertNotIn('XX_A01', self.names())

    def test_fresh_runtime_can_supply_ids_when_options_unknown(self):
        mod = self.mod('on', 'on.mod', 'XX', 'XX_A01')
        path = mod / 'world/xx-rooms/xx_a01.txt'
        self.snapshot(['on.mod'], [dict(name='XX_A01', geometryPath=str(path))])
        self.assertEqual(rooms.catalog()['source'], 'live')
        self.assertIn('XX_A01', self.names())

    def test_expired_unknown_snapshot_cannot_authorize_mod_assets(self):
        mod = self.mod('on', 'on.mod', 'XX', 'XX_A01')
        self.snapshot(['on.mod'], [dict(name='XX_A01', geometryPath=str(mod / 'world/xx-rooms/xx_a01.txt'))], stale=True)
        self.assertEqual(self.names(), {'SU_A01'})
        self.assertEqual(rooms.catalog()['source'], 'offline')
        self.assertFalse(rooms.is_enabled_asset(mod / 'world/xx-rooms/xx_a01.txt'))

    def test_snapshot_old_enabled_ids_falls_back_to_current_list(self):
        mod = self.mod('off', 'off.mod', 'XX', 'XX_A01')
        self.enable([])
        self.snapshot(['off.mod'], [dict(name='XX_A01', geometryPath=str(mod / 'world/xx-rooms/xx_a01.txt'))])
        self.assertEqual(rooms.catalog()['source'], 'offline')
        self.assertEqual(self.names(), {'SU_A01'})

    def test_stale_matching_snapshot_reads_enabled_geometry(self):
        mod = self.mod('on', 'on.mod', 'XX', 'XX_A01')
        self.enable(['on.mod'])
        path = mod / 'world/xx-rooms/xx_a01.txt'
        self.snapshot(['on.mod'], [dict(name='XX_A01', geometryPath=str(path))], stale=True)
        self.assertEqual(rooms.catalog()['source'], 'stale')
        self.assertEqual(rooms.resolve_room_source('XX_A01'), path.with_suffix(''))

    def test_merged_assets_require_current_fresh_snapshot(self):
        self.enable([])
        merged = self.world(self.assets / 'mergedmods', 'ZZ', 'ZZ_OLD')
        self.assertNotIn('ZZ_OLD', self.names())
        self.snapshot([], [dict(name='ZZ_OLD', geometryPath=str(merged))])
        self.assertIn('ZZ_OLD', self.names())
        self.assertTrue(rooms.is_enabled_asset(merged))
        self.snapshot([], [dict(name='ZZ_OLD', geometryPath=str(merged))], stale=True)
        self.assertFalse(rooms.is_enabled_asset(merged))
        self.assertNotIn('ZZ_OLD', self.names())

    def test_old_workshop_snapshot_rebinds_current_local_geometry(self):
        local = self.mod('local', 'same.mod', 'XX', 'XX_A01')
        remote = self.mod('100', 'same.mod', 'XX', 'XX_A01', workshop=True)
        self.enable(['same.mod'])
        self.snapshot(['same.mod'], [dict(name='XX_A01', geometryPath=str(remote / 'world/xx-rooms/xx_a01.txt'), verified=True)], stale=True)
        self.assertEqual(rooms.resolve_room_source('XX_A01'), (local / 'world/xx-rooms/xx_a01.txt').with_suffix(''))
        self.assertFalse(rooms.catalog()['regions'][0]['rooms'][0]['verified'])

    def test_existing_project_reference_is_not_modified_or_cleared(self):
        self.enable([])
        project = dict(projectId='old-project', roomBinding=dict(region='XX', ai='XX_AI', entry='XX_A01'))
        before = copy.deepcopy(project)
        with patch.object(rooms, '_fixed', return_value=None):
            self.assertEqual(rooms.binding(project), project['roomBinding'])
        rooms.catalog()
        self.assertEqual(project, before)
        self.assertFalse(storage.DATA.exists())

    def test_snapshot_does_not_authorize_arbitrary_outside_path(self):
        self.enable([])
        outside = self.root / 'private/su_a01.txt'
        self.snapshot([], [dict(name='SU_A01', geometryPath=str(outside))])
        self.assertEqual(rooms.resolve_room_source('SU_A01'), self.base_geometry.with_suffix(''))
        self.assertFalse(rooms.is_enabled_asset(outside))


if __name__ == '__main__':
    unittest.main()
