import copy
from contextlib import ExitStack, contextmanager
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_project_packages as fixtures
import chamber_presets
import project_packages
import room_asset_dependencies
import room_bindings
import room_editor
import server
import standalone
import storage


class ChamberApplyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ProjectPackageTests('test_roundtrip_preserves_room_source_settings_cameras_palette_and_plan')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.palette = self.fixture.local / 'palettes/palette9100.png'

    @contextmanager
    def assets(self):
        def references(project, source, text):
            return {paths[0]: self.palette for paths in room_asset_dependencies.references(text) if paths[0].endswith('.png')}
        with patch.object(standalone, 'room_palette_source', return_value=self.palette), \
             patch.object(standalone, 'room_settings_assets', side_effect=references), \
             patch.object(room_asset_dependencies, 'has_native_ambient_reference', return_value=True):
            yield

    def room_snapshot(self, project, name):
        root = storage.project_file(project['projectId']).parent
        return {path.relative_to(root).as_posix(): path.read_bytes()
                for path in (root / 'rooms').rglob('*')
                if path.is_file() and (path.name.startswith(name + '.') or path.name.startswith(name + '_'))}

    def replace(self, project, preset='mi-chamber-broken'):
        return chamber_presets.replace(dict(project=project, presetId=preset,
            token=chamber_presets.state(project['projectId'])['token']), server)['project']

    def test_new_project_replacement_prepares_both_rooms_for_apply(self):
        for preset in ('mi-chamber-broken', 'mi-chamber-moon'):
            with self.subTest(preset=preset):
                project = chamber_presets.create({'presetId': 'mi-chamber-pebbles'}, server)['project']
                binding = room_bindings.binding(project)
                before = copy.deepcopy(project)
                waiting = self.room_snapshot(project, binding['entry'])
                changed = self.replace(project, preset)
                with self.assets():
                    prepared = project_packages.before_deploy(changed, server)
                self.assertEqual(self.room_snapshot(changed, binding['entry']), waiting)
                for key in ('projectId', 'name', 'textures', 'dialogue', 'editor'):
                    self.assertEqual(changed.get(key), before.get(key), key)
                self.assertEqual(changed['design'], before['design'])
                self.assertEqual(set(prepared['rooms']), {binding['ai'], binding['entry']})
                for kind in ('ai', 'entry'):
                    name = binding[kind]
                    source = room_editor.cached_source(project['projectId'], name)
                    relative = 'world/' + binding['region'].lower() + '-rooms/' + name
                    self.assertEqual(prepared['files'][relative + '.txt'], source.with_suffix('.txt').read_bytes())
                    cameras = [value for value in source.with_suffix('.txt').read_text('utf-8-sig').splitlines()[3].split('|') if value]
                    for number in range(1, len(cameras) + 1):
                        self.assertEqual(prepared['files'][relative + '_' + str(number) + '.png'],
                            source.with_name(name + '_' + str(number) + '.png').read_bytes())
                entry = next(row for row in project_packages.load_metadata(project['projectId'])['rooms'] if row['kind'] == 'entry')
                self.assertEqual(entry.get('updatedAtNs'), 0)

    def test_imported_package_replacement_keeps_entry_extra_regions_and_palettes(self):
        self.fixture.project['dialogue'] = server.dialogue.profile(dict(design={'firstDialogue': 'keep authored dialogue'}))
        self.fixture.project_file.write_text(json.dumps(self.fixture.project), 'utf-8')
        extra = self.fixture.external / 'world/yy-rooms/YY_ONE'
        self.fixture.render(extra, 'YY_ONE', color='green')
        self.fixture.palette(self.fixture.external / 'palettes/palette9100.png', 'red')
        self.fixture.catalogue['regions'] = [dict(name='YY', rooms=[dict(name='YY_ONE', region='YY',
            connections=['DISCONNECTED', 'DISCONNECTED'], conditional=False, geometryPath=str(extra.with_suffix('.txt')))])]
        payload = self.fixture.payload(['YY_ONE'])
        self.fixture.target()
        self.fixture.catalogue['regions'] = []
        project = project_packages.import_package(payload, self.fixture.server)['project']
        binding = room_bindings.binding(project)
        original = copy.deepcopy(project_packages.load_metadata(project['projectId']))
        waiting = self.room_snapshot(project, binding['entry'])
        extra_files = self.room_snapshot(project, 'YY_ONE')
        changed = self.replace(project)
        metadata = project_packages.load_metadata(project['projectId'])
        for key in ('regions', 'palettes', 'importedAtNs'):
            self.assertEqual(metadata[key], original[key], key)
        for kind in ('entry', 'extra'):
            self.assertEqual([row for row in metadata['rooms'] if row['kind'] == kind],
                [row for row in original['rooms'] if row['kind'] == kind])
        self.assertEqual(self.room_snapshot(changed, binding['entry']), waiting)
        self.assertEqual(self.room_snapshot(changed, 'YY_ONE'), extra_files)
        with self.assets():
            prepared = project_packages.before_deploy(changed, server)
        self.assertIn('world/yy-rooms/YY_ONE_1.png', prepared['files'])
        self.assertEqual(prepared['files']['world/yy-rooms/YY_ONE_1.png'], extra.with_name('YY_ONE_1.png').read_bytes())
        self.assertIn('YY_ONE : DISCONNECTED, DISCONNECTED', prepared['worldFiles']['world/yy/world_yy.txt'])

    def test_legacy_ai_only_manifest_can_apply_without_changing_waiting_room(self):
        project = chamber_presets.create({'presetId': 'mi-chamber-pebbles'}, server)['project']
        project = self.replace(project)
        pid = project['projectId']
        binding = room_bindings.binding(project)
        waiting = self.room_snapshot(project, binding['entry'])
        path = storage.project_file(pid).parent / project_packages.LOCAL_MANIFEST
        metadata = project_packages.load_metadata(pid)
        metadata['rooms'] = [row for row in metadata['rooms'] if row['kind'] == 'ai']
        metadata['files'] = [item for item in metadata['files'] if binding['entry'] not in Path(item['path']).name]
        metadata.pop('regions', None)
        metadata.pop('palettes', None)
        path.write_text(json.dumps(metadata), 'utf-8')
        with self.assets():
            prepared = project_packages.before_deploy(project, server)
        self.assertEqual(set(prepared['rooms']), {binding['ai'], binding['entry']})
        self.assertEqual(self.room_snapshot(project, binding['entry']), waiting)

    def test_room_identity_mismatch_still_blocks_stale_manifest(self):
        project = chamber_presets.create({'presetId': 'mi-chamber-pebbles'}, server)['project']
        project = self.replace(project)
        project['roomBinding']['ai'] = 'TEST_RENAMED_AI'
        storage.project_file(project['projectId']).write_text(json.dumps(project), 'utf-8')
        with self.assertRaisesRegex(ValueError, '清单尚未迁移'):
            project_packages.before_deploy(project, server)

    def test_existing_entry_replacement_keeps_external_files_and_other_connections(self):
        project = chamber_presets.create({'presetId': 'mi-chamber-pebbles'}, server)['project']
        binding = copy.deepcopy(room_bindings.binding(project))
        binding.update(entry='TEST_EXTERNAL', entryMode='existing', entryNode=0)
        external = self.fixture.external / 'world/yy-rooms/TEST_EXTERNAL'
        self.fixture.render(external, 'TEST_EXTERNAL', color='green')
        self.fixture.catalogue['regions'] = [dict(name='TEST', rooms=[dict(name='TEST_EXTERNAL', region='TEST',
            connections=['DISCONNECTED', 'TEST_OTHER'], conditional=False, verified=True, exitCount=2,
            geometryPath=str(external.with_suffix('.txt')))])]
        project['roomBinding'] = binding
        storage.project_file(project['projectId']).write_text(json.dumps(project), 'utf-8')
        before = {path: path.read_bytes() for path in self.fixture.external.rglob('*') if path.is_file()}
        changed = self.replace(project)
        with self.assets():
            prepared = project_packages.before_deploy(changed, server)
        self.assertEqual(prepared['rooms'], [binding['ai']])
        self.assertFalse(any('TEST_EXTERNAL' in path for path in prepared['files']))
        text = prepared['worldFiles']['modify/world/test/world_test.txt']
        self.assertIn('[REPLACE]TEST_EXTERNAL : ' + binding['ai'] + ', TEST_OTHER', text)
        project_packages.write_deploy_assets(prepared)
        self.assertEqual({path: path.read_bytes() for path in self.fixture.external.rglob('*') if path.is_file()}, before)
        self.assertFalse(any(path.name.startswith('TEST_EXTERNAL') for path in self.fixture.local.rglob('*') if path.is_file()))

    def test_save_and_apply_replacement_writes_both_rooms_and_keeps_authored_data(self):
        project = chamber_presets.create({'presetId': 'mi-chamber-pebbles'}, server)['project']
        project['name'] = 'pure vessel'
        project['design']['bodyColor'] = '#abcdef'
        project = server.save(project)
        before = copy.deepcopy(project)
        binding = room_bindings.binding(project)
        waiting = self.room_snapshot(project, binding['entry'])
        changed = self.replace(project)
        with self.assets(), ExitStack() as stack:
            for context in (
                patch.object(server, 'compile_design', return_value=dict(projectId=project['projectId'])),
                patch.object(server, 'MOD', self.fixture.local),
                patch.object(server, 'DESIGNS', storage.RUNTIME),
                patch.object(server, 'ASSETS', self.fixture.game / 'RainWorld_Data/StreamingAssets'),
                patch.object(server, 'installation_paths', return_value={}),
                patch.object(server.audio_assets, 'copy_referenced'),
                patch.object(server.local_content, 'status', return_value={}),
                patch.object(server.waiting_room, 'prepare', side_effect=AssertionError('must keep waiting room')),
                patch.object(server, 'copy_room', side_effect=AssertionError('must keep selected preset')),
            ):
                stack.enter_context(context)
            result = server.deploy(changed)
        self.assertTrue(result['ok'])
        self.assertEqual(self.room_snapshot(project, binding['entry']), waiting)
        saved = storage.load_project(project['projectId'])
        for key in ('projectId', 'name', 'design', 'textures', 'dialogue', 'editor'):
            self.assertEqual(saved.get(key), before.get(key), key)
        for name in (binding['ai'], binding['entry']):
            source = room_editor.cached_source(project['projectId'], name)
            relative = Path('world') / (binding['region'].lower() + '-rooms')
            for root in (self.fixture.local, self.fixture.installed):
                self.assertEqual((root / relative / (name + '.txt')).read_bytes(), source.with_suffix('.txt').read_bytes())
                self.assertTrue((root / relative / (name + '_1.png')).is_file())
                self.assertTrue((root / relative / (name + '_settings.txt')).is_file())
        text = (self.fixture.installed / 'world' / binding['region'].lower() / ('world_' + binding['region'].lower() + '.txt')).read_text('utf-8')
        self.assertIn(binding['ai'] + ' : ' + binding['entry'], text)
        self.assertIn(binding['entry'] + ' : ' + binding['ai'], text)


if __name__ == '__main__':
    unittest.main()
