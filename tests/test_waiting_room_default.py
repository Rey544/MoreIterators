import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import server
import storage
import room_bindings
import room_editor
import room_migration
import standalone
import waiting_room


class WaitingRoomTests(unittest.TestCase):
    def setUp(self):
        self.native = storage.GAME / 'RainWorld_Data/StreamingAssets/world/ss-rooms/ss_d07'
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for target, key, value in [
                (storage, 'DATA', self.root / 'data'), (storage, 'PROJECTS', self.root / 'data/projects'),
                (storage, 'RUNTIME', self.root / 'data/runtime'), (storage, 'GAME', self.root / 'game'),
                (storage, 'LINKS', []), (storage, 'settings', {})]:
            item = patch.object(target, key, value); item.start(); self.addCleanup(item.stop)
        for key, value in [('MOD', storage.DATA / 'local-mod'), ('DESIGNS', storage.RUNTIME),
                           ('ASSETS', storage.GAME / 'RainWorld_Data/StreamingAssets')]:
            item = patch.object(server, key, value); item.start(); self.addCleanup(item.stop)
        storage.GAME.mkdir(parents=True, exist_ok=True)
        (storage.GAME / 'RainWorld.exe').touch()
        storage.settings['gameRoot'] = str(storage.GAME)
        self.project = server.default()
        self.project.update(projectId='waiting-test', name='Waiting room test')
        self.ai, self.entry, _ = server.roomnames(self.project)
        source = server.ASSETS / 'world/ss-rooms/ss_ai'
        source.parent.mkdir(parents=True, exist_ok=True)
        source.with_suffix('.txt').write_text('SS_AI\n48*35|-1|0\n0|0|0\n0,0\n\n\n\n\n\n20|2|15|0,1,0,0,1,|0,1,0,0,1,|\n')
        Path(str(source) + '_settings.txt').write_text('Palette: 26\n')
        shutil.copy2(waiting_room.ROOT / 'entry_1.png', Path(str(source) + '_1.png'))

    def assert_new(self, result):
        self.assertEqual(result['project'][waiting_room.FIELD], waiting_room.ID)
        self.assertEqual(room_bindings.binding(result['project'])['entryNode'], 0)
        for root in (server.MOD, storage.installed_mod(self.project['projectId'])):
            room = root / 'world/test-rooms' / self.entry
            self.assertEqual(room_bindings.geometry(room.with_suffix('.txt'))['exitCount'], 1)
            self.assertIn('48*35', room.with_suffix('.txt').read_text())
            self.assertEqual(len(list(room.parent.glob(self.entry + '_*.png'))), 1)
            self.assertEqual(Path(str(room) + '_1.png').read_bytes(), (waiting_room.ROOT / 'entry_1.png').read_bytes())
            text = Path(str(room) + '_settings.txt').read_text()
            self.assertIn('Palette: 12', text); self.assertIn('FadePalette: 8', text)
            self.assertIn('ZeroG-1-0-0', text)
            world = (root / 'world/test/world_test.txt').read_text()
            self.assertIn(self.ai + ' : DISCONNECTED, ' + self.entry, world)
            self.assertIn(self.entry + ' : ' + self.ai + '\n', world)
        records = json.loads((storage.RUNTIME / 'creator/registry.json').read_text())
        record = next(item for item in records if item['projectId'] == self.project['projectId'])
        self.assertEqual((record['exitNode'], record['entryNode']), (1, 0))

    def legacy(self, cached=False):
        
        value = waiting_room.manifest()
        base = self.root / 'legacy/room'; base.parent.mkdir()
        base.with_suffix('.txt').write_text('SS_D07\n204*35|-1|0\n0|0|0\n0,0|100,0|200,0|300,0\n\n\n\n\n\n20|2|15|0,1,0,0,1,|0,1,0,0,1,|\n')
        Path(str(base) + '_settings.txt').write_text('Template: NONE\nPalette: 26\nEffects: ZeroG-1-0-0, \n')
        spec = value['legacy']
        spec['geometryBodySha256'] = waiting_room._sha(waiting_room._normalized(base.with_suffix('.txt'), True))
        spec['deployedSettingsNormalizedSha256'] = waiting_room._sha(waiting_room._normalized(Path(str(base) + '_settings.txt')))
        for i in range(1, 5):
            Path(str(base) + '_' + str(i) + '.png').write_bytes(b'camera-' + str(i).encode())
            spec['cameraSha256'][str(i)] = waiting_room._sha(Path(str(base) + '_' + str(i) + '.png').read_bytes())
        mock = patch.object(waiting_room, 'manifest', return_value=value); mock.start(); self.addCleanup(mock.stop)
        server.save(self.project)
        bases = waiting_room._bases(self.project['projectId'], self.entry)
        for target in (bases if cached else bases[1:]):
            server.copy_room(base, target.parent, target.name)
        for root in (server.MOD, storage.installed_mod(self.project['projectId'])):
            server.copy_room(server.ASSETS / 'world/ss-rooms/ss_ai', root / 'world/test-rooms', self.ai)
            world = root / 'world/test/world_test.txt'; world.parent.mkdir(parents=True)
            world.write_text('ROOMS\n' + self.ai + ' : DISCONNECTED, ' + self.entry + '\n' + self.entry + ' : DISCONNECTED, ' + self.ai + '\nEND ROOMS\n')
        return bases

    def test_fresh_apply_uses_bundled_source_render_lighting_and_nodes(self):
        result = server.deploy(copy.deepcopy(self.project)); self.assert_new(result)
        source = storage.project_file(self.project['projectId']).parent / 'rooms' / (self.entry + '.txt')
        self.assertEqual(source.read_bytes(), (waiting_room.ROOT / 'source/entry.txt').read_bytes())
        room_editor.ensure_synced(self.project['projectId'], self.entry)
        self.assert_new(server.deploy(copy.deepcopy(self.project)))
        source.write_text(source.read_text() + '\n// an actual new edit')
        with self.assertRaisesRegex(ValueError, '尚未同步'):
            server.deploy(copy.deepcopy(self.project))

    def test_new_unapplied_export_uses_same_default_and_node(self):
        self.assertEqual(server.entry_room_template(), waiting_room.ROOT / 'entry')
        self.assertEqual(standalone.room_source(self.project, self.entry, 'entry', server), waiting_room.ROOT / 'entry')
        self.assertEqual(standalone.room_connections(self.project, self.ai, self.entry, server)[self.entry], [self.ai])

    def test_old_default_and_old_cached_default_both_upgrade(self):
        self.legacy(cached=True)
        result = server.deploy(copy.deepcopy(self.project)); self.assert_new(result)
        archive = storage.project_file(self.project['projectId']).parent / 'room-template-backups'
        self.assertEqual(len(list(archive.glob('*/manifest.json'))), 1)
        self.assert_new(server.deploy(copy.deepcopy(self.project)))
        self.assertEqual(len(list(archive.glob('*/manifest.json'))), 1)

    def test_old_default_without_cache_upgrades(self):
        self.legacy(); self.assert_new(server.deploy(copy.deepcopy(self.project)))

    def test_untouched_explicit_default_pair_upgrades_binding_and_plan(self):
        self.legacy(cached=True)
        project = storage.load_project(self.project['projectId'])
        project['roomBinding'] = room_bindings.binding(project)
        server.atomic(storage.project_file(project['projectId']), project)
        self.assertEqual(project['roomBinding']['entryNode'], 1)
        result = server.deploy(copy.deepcopy(self.project)); self.assert_new(result)
        self.assertEqual(result['project']['roomBinding']['entryNode'], 0)
        plan = json.loads((storage.project_file(project['projectId']).parent / 'room-binding-plan.json').read_text())
        self.assertEqual(plan['binding']['entryNode'], 0)
        self.assert_new(server.deploy(copy.deepcopy(self.project)))

    def test_any_custom_geometry_settings_or_camera_prevents_migration(self):
        bases = self.legacy(cached=True)
        for suffix in ('.txt', '_settings.txt', '_1.png', '_4.png'):
            with self.subTest(suffix=suffix):
                file = Path(str(bases[0]) + suffix); before = file.read_bytes()
                file.write_bytes(before + b'custom')
                result = waiting_room.prepare(storage.load_project(self.project['projectId']))
                self.assertNotIn(waiting_room.FIELD, result)
                self.assertEqual(file.read_bytes(), before + b'custom')
                file.write_bytes(before)

    def test_external_links_and_authored_source_are_never_replaced(self):
        self.legacy()
        world = server.MOD / 'world/test/world_test.txt'; old = world.read_text()
        world.write_text(old.replace('END ROOMS', 'TEST_FOREIGN : ' + self.entry + '\nEND ROOMS'))
        with self.assertRaisesRegex(ValueError, '额外连接'):
            waiting_room.prepare(self.project)
        world.write_text(old)
        source = storage.project_file(self.project['projectId']).parent / 'rooms' / (self.entry + '.txt')
        source.parent.mkdir(parents=True); source.write_text('[[[custom source')
        self.assertNotIn(waiting_room.FIELD, waiting_room.prepare(self.project))
        self.assertEqual(source.read_text(), '[[[custom source')

    def test_explicit_binding_and_template_config_are_preserved(self):
        bound = dict(self.project, roomBinding=dict(room_bindings.binding(self.project), entryNode=1))
        self.assertEqual(waiting_room.prepare(bound), bound)
        storage.settings['entryRoomTemplate'] = 'my-room'
        self.assertEqual(waiting_room.prepare(self.project), self.project)

    def test_migration_failure_restores_geometry_cache_project_and_world(self):
        self.legacy(cached=True)
        roots = (storage.DATA, storage.installed_mod(self.project['projectId']))
        before = {f: f.read_bytes() for root in roots for f in root.rglob('*') if f.is_file()}
        original = room_migration.Files.write
        def fail(transaction, file, content):
            if Path(file) == storage.project_file(self.project['projectId']) and waiting_room.ID.encode() in content:
                raise OSError('test injected project write failure')
            return original(transaction, file, content)
        with patch.object(room_migration.Files, 'write', fail), self.assertRaises(OSError):
            waiting_room.prepare(storage.load_project(self.project['projectId']))
        for file, content in before.items():
            self.assertEqual(file.read_bytes(), content, str(file))
        self.assertFalse((storage.project_file(self.project['projectId']).parent / 'rooms' / (self.entry + '.txt')).exists())

    def test_prepare_editor_seeds_source_without_cf_entry_sample(self):
        server.save(self.project)
        executable = self.root / 'rained/Rained.exe'; executable.parent.mkdir(); executable.touch()
        with patch.object(room_editor, 'rained_root', return_value=executable):
            _, source = room_editor.prepare(self.project['projectId'], 'entry', server.roomnames)
        self.assertEqual(source.read_bytes(), (waiting_room.ROOT / 'source/entry.txt').read_bytes())
        room_editor.ensure_synced(self.project['projectId'], self.entry)

    def test_installed_vanilla_hash_matches_packaged_migration_fingerprint(self):
        if not self.native.with_suffix('.txt').is_file():
            self.skipTest('vanilla room not installed on this machine')
        spec = waiting_room.manifest()['legacy']
        self.assertTrue(waiting_room._legacy(self.native, spec))
        copied = self.root / 'old-deploy' / self.entry
        server.copy_room(self.native, copied.parent, copied.name)
        server.zero_gravity(Path(str(copied) + '_settings.txt'))
        self.assertTrue(waiting_room._legacy(copied, spec))

    def test_renamed_default_render_keeps_matching_editable_source(self):
        project = copy.deepcopy(self.project)
        project['roomBinding'] = dict(region='XY', ai='XY_AI', entry='XY_ENTRY', oracleId='renamed', entryMode='copy', aiNode=1, entryNode=0)
        server.atomic(storage.project_file(project['projectId']), project)
        cache = room_editor.cache_base(project['projectId'], 'XY_ENTRY')
        server.copy_room(waiting_room.rendered(), cache.parent, cache.name)
        exe = self.root / 'rained/Rained.exe'; exe.parent.mkdir(); exe.touch()
        with patch.object(room_editor, 'rained_root', return_value=exe):
            _, editable = room_editor.prepare(project['projectId'], 'entry', server.roomnames)
        self.assertEqual(editable.read_bytes(), (waiting_room.ROOT / 'source/entry.txt').read_bytes())
        room_editor.ensure_synced(project['projectId'], 'XY_ENTRY')
        cache.with_suffix('.txt').write_text(cache.with_suffix('.txt').read_text() + '\ncustom geometry')
        self.assertIsNone(waiting_room.editable_source(project, 'XY_ENTRY'))


if __name__ == '__main__':
    unittest.main()
