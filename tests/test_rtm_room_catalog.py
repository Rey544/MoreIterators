import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import room_bindings as rooms
import storage


class RtmRoomCatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.game = self.directory / 'game'
        self.assets = self.game / 'RainWorld_Data/StreamingAssets'
        self.root = self.assets / 'mods/rtm'
        self.region = self.root / 'templates/cot'
        self.room = self.region / 'rooms/COT_A02.txt'
        self.room.parent.mkdir(parents=True)
        self.room.write_text('COT_A02\n', 'utf-8')
        (self.root / 'modinfo.json').write_text(json.dumps(dict(id='octooltestmod')), 'utf-8')
        self.spec = dict(schemaVersion=1, enabled=True, id='cot', code='COT', rooms=[dict(name='COT_A02', connections=['COT_A03'])])
        self.save_spec()
        self.state = dict(roots=[self.root, self.assets], assets=self.assets, enabled={'octooltestmod'},
                          installed={'octooltestmod': self.root}, snapshot=None, compatible=False, live=False, key='enabled')
        for context in (patch.object(rooms, '_selection', side_effect=lambda: self.state),
                        patch.object(rooms, '_offline_cache', None),
                        patch.object(rooms, '_geometry_cache', None),
                        patch.object(rooms, '_geometry_key', None),
                        patch.object(rooms, '_geometry_at', 0),
                        patch.object(storage, 'GAME', self.game),
                        patch.object(storage, 'DATA', self.directory / 'data'),
                        patch.object(storage, 'available_game_root', return_value=self.game),
                        patch.object(storage, 'require_game_root', return_value=self.game)):
            context.start()
            self.addCleanup(context.stop)

    def save_spec(self):
        (self.region / 'region.json').write_text(json.dumps(self.spec), 'utf-8')

    def test_template_only_room_is_listed_and_resolved(self):
        self.assertFalse((self.root / 'world').exists())
        indexed = rooms.room_geometry_index(refresh=True)
        self.assertEqual(indexed[('COT', 'COT_A02')], self.room)
        value = rooms.offline_catalog(refresh=True, include_reserved=False)
        row, = value['regions'][0]['rooms']
        self.assertEqual(row['name'], 'COT_A02')
        self.assertEqual(row['connections'], ['COT_A03'])
        self.assertEqual(rooms.resolve_room_source('COT_A02'), self.room.with_suffix(''))
        self.assertFalse((self.root / 'world').exists())

    def test_disabled_mod_is_not_visible_or_resolved(self):
        self.state.update(roots=[self.assets], enabled=set(), key='disabled')
        self.assertNotIn(('COT', 'COT_A02'), rooms.room_geometry_index(refresh=True))
        self.assertEqual(rooms.offline_catalog(refresh=True, include_reserved=False)['regions'], [])
        with self.assertRaises(ValueError):
            rooms.resolve_room_source('COT_A02')

    def test_region_changes_are_visible_after_refresh(self):
        self.assertEqual(len(rooms.offline_catalog(refresh=True, include_reserved=False)['regions']), 1)
        self.spec['enabled'] = False
        self.save_spec()
        self.assertEqual(rooms.offline_catalog(refresh=True, include_reserved=False)['regions'], [])
        with self.assertRaises(ValueError):
            rooms.resolve_room_source('COT_A02')
        self.spec['enabled'] = True
        self.spec['rooms'][0]['connections'] = ['DISCONNECTED']
        self.save_spec()
        value = rooms.offline_catalog(refresh=True, include_reserved=False)
        self.assertEqual(value['regions'][0]['rooms'][0]['connections'], ['DISCONNECTED'])

    def test_added_geometry_is_visible_after_refresh(self):
        rooms.offline_catalog(refresh=True, include_reserved=False)
        (self.room.parent / 'COT_A03.txt').write_text('COT_A03\n', 'utf-8')
        value = rooms.offline_catalog(refresh=True, include_reserved=False)
        self.assertEqual({row['name'] for row in value['regions'][0]['rooms']}, {'COT_A02', 'COT_A03'})

    def test_own_mirror_uses_authoritative_settings_source(self):
        mirror = self.root / 'world/cot-rooms/COT_A02.txt'
        mirror.parent.mkdir(parents=True)
        mirror.write_text('old mirrored geometry', 'utf-8')
        self.assertEqual(rooms.room_geometry_index(refresh=True)[('COT', 'COT_A02')], self.room)
        self.assertEqual(rooms.resolve_room_source('COT_A02'), self.room.with_suffix(''))

    def test_other_enabled_provider_is_not_silently_replaced(self):
        other = self.assets / 'mods/other'
        geometry = other / 'world/cot-rooms/COT_A02.txt'
        geometry.parent.mkdir(parents=True)
        geometry.write_text('other provider geometry', 'utf-8')
        world = other / 'world/cot/world_cot.txt'
        world.parent.mkdir(parents=True)
        world.write_text('ROOMS\nCOT_A02 : OTHER_ROOM\nEND ROOMS\n', 'utf-8')
        self.state['roots'].insert(0, other)
        indexed = rooms.room_geometry_index(refresh=True)
        self.assertEqual(indexed[('COT', 'COT_A02')], geometry)
        value = rooms.offline_catalog(refresh=True, include_reserved=False)
        self.assertEqual(value['regions'][0]['rooms'][0]['connections'], ['OTHER_ROOM'])
        self.assertEqual(rooms.resolve_room_source('COT_A02'), geometry.with_suffix(''))


if __name__ == '__main__':
    unittest.main()
