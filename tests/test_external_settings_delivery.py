import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'editor'))
import project_packages
import room_bindings
import room_controls
import room_source_choices
import server
import storage


class ExternalSettingsDeliveryTests(unittest.TestCase):
    def fixture(self):
        from test_project_packages import ProjectPackageTests
        value = ProjectPackageTests()
        value.setUp()
        self.addCleanup(value.doCleanups)
        value.project['editor'] = {'externalRoomTools': True}
        value.project_file.write_text(json.dumps(value.project), 'utf-8')
        context = patch.object(room_bindings, 'enabled_asset_roots', return_value=[])
        context.start()
        self.addCleanup(context.stop)
        return value

    def settings(self, base, room, marker):
        base.mkdir(parents=True, exist_ok=True)
        content = ('Template: XX_SettingsTemplate_Outside\nPalette: 9100\nMorePalette0: 9100, 0.4, 0.7\n'
                   'Effects: ZeroG-0.3-0-0, Fog-0.2-0-0,\nPlacedObjects: LightSource><10><20><' + marker + '\n'
                   'UnknownExtension: ' + marker + '\n')
        path = base / (room + '_settings.txt')
        path.write_text(content, 'utf-8')
        return path

    def region(self, root, marker, mtime):
        folder = root / 'world/xx'
        folder.mkdir(parents=True, exist_ok=True)
        values = {'properties.txt': 'Room Setting Templates: Outside\nUnknownRegion: ' + marker + '\n',
                  'xx_settingstemplate_outside.txt': 'Palette: 9100\nMorePalette0: 9100, 0.2\nPlacedObjects: LightSource><' + marker + '\nUnknownTemplate: ' + marker + '\n'}
        for name, text in values.items():
            file = folder / name
            file.write_text(text, 'utf-8')
            os.utime(file, (mtime, mtime))
        return {name: (folder / name).read_bytes() for name in values}

    def prepared_origins(self):
        fixture = self.fixture()
        for name in ('XX_AI', 'XX_ENTRY'):
            self.settings(fixture.local / 'world/xx-rooms', name, 'local-' + name)
        selected = self.settings(fixture.installed / 'world/xx-rooms', 'XX_AI', 'external-ai')
        os.utime(selected, (2000000000, 2000000000))
        expected = self.region(fixture.installed, 'selected-external', 1000)
        self.region(fixture.local, 'newer-geometry-owner', 2100000000)
        return fixture, expected

    def selection(self, fixture):
        report = room_source_choices.preflight([fixture.project])
        choices = {}
        for row in report['rooms']:
            source = next(v['id'] for v in row['renderVersions'] if v['complete'] and 'local' in v['origins'])
            origin = 'installed' if row['room'] == 'XX_AI' else 'local'
            settings = next(v['id'] for v in row['settingsVersions'] if v['complete'] and origin in v['origins'])
            choices[row['projectId'] + '/' + row['room']] = {'source': source, 'settings': settings}
        return {'snapshotToken': report['snapshotToken'], 'choices': choices}

    def test_selected_settings_owns_region_properties_and_template(self):
        fixture, expected = self.prepared_origins()
        originals = {path: path.read_bytes() for root in (fixture.local, fixture.installed) for path in root.rglob('*') if path.is_file()}
        with room_source_choices.resolution_scope([fixture.project], self.selection(fixture)):
            files, paths = project_packages._collect_region(fixture.project, 'XX', fixture.local / 'world/xx-rooms/XX_AI', {'XX_AI'})
        for name, content in expected.items():
            self.assertEqual(files[name], content)
            self.assertEqual(paths[name], fixture.installed / 'world/xx' / name)
        self.assertEqual(files['map_xx.txt'], b'XX_AI: 1><2\n')
        for path, content in originals.items():
            self.assertEqual(path.read_bytes(), content)

    def test_independent_settings_copy_keeps_objects_unknown_fields_and_variants(self):
        fixture = self.fixture()
        selected = self.settings(fixture.installed / 'world/xx-rooms', 'XX_AI', 'author-light')
        variant = selected.with_name('XX_AI_settings-White.txt')
        variant.write_text('Palette: 9100\nPlacedObjects: LightSource><variant\nUnknownVariant: keep\n', 'utf-8')
        properties = selected.with_name('XX_AI_properties.txt')
        properties.write_text('UnknownRoomProperty: keep\n', 'utf-8')
        source = fixture.local / 'world/xx-rooms/XX_AI'
        source.with_name('XX_AI_settings.txt').unlink()
        output = fixture.root / 'selected-copy'
        original = {path.name: path.read_bytes() for path in (selected, variant, properties)}
        room_controls.copy_owned_room(fixture.project, source, output, 'XX_AI', 'ai', server, replace=True)
        for name, content in original.items():
            self.assertEqual((output / name).read_bytes(), content)
            self.assertEqual((selected.parent / name).read_bytes(), content)
        self.assertTrue((output / 'XX_AI_2.png').is_file())
        self.assertEqual(fixture.project['design'], {})

    def test_linked_sync_delivers_settings_variants_without_removing_local_work(self):
        fixture = self.fixture()
        cached = fixture.project_file.parent / 'rooms/rendered'
        for name in ('XX_AI', 'XX_ENTRY'):
            fixture.render(cached / name, name, 2)
        selected = self.settings(cached, 'XX_AI', 'cached-author-light')
        os.utime(selected, (2000000000, 2000000000))
        variant = cached / 'XX_AI_settings-White.txt'
        variant.write_text('Palette: 9100\nPlacedObjects: LightSource><variant\nUnknownVariant: keep\n', 'utf-8')
        properties = cached / 'XX_AI_properties.txt'
        properties.write_text('UnknownRoomProperty: keep\n', 'utf-8')
        fixture.installed.mkdir(parents=True, exist_ok=True)
        unrelated = fixture.installed / 'untouched-author-work.txt'
        unrelated.write_text('keep original', 'utf-8')
        original = {path.name: path.read_bytes() for path in (selected, variant, properties)}
        linked = {'workspace': str(fixture.root), 'folder': fixture.installed.name,
                  'projects': {'selected': copy.deepcopy(fixture.project['roomBinding'])}}
        with patch.object(storage, 'link', return_value=linked), \
             patch.object(storage, 'target_mod', return_value=fixture.local), \
             patch.object(storage, 'installed_mod', return_value=fixture.installed), \
             patch.object(server.room_editor, 'ensure_synced'), \
             patch.object(server.room_editor, 'cached_source', side_effect=lambda pid, room: cached / room):
            server.sync_linked_rooms(fixture.project, 'XX_AI', 'XX_ENTRY')
        for name, content in original.items():
            self.assertEqual((fixture.local / 'world/xx-rooms' / name).read_bytes(), content)
            self.assertEqual((fixture.installed / 'world/xx-rooms' / name).read_bytes(), content)
            self.assertEqual((cached / name).read_bytes(), content)
        self.assertEqual(unrelated.read_text('utf-8'), 'keep original')
        self.assertEqual(fixture.project['design'], {})

    def test_incompatible_selected_room_region_settings_are_reported(self):
        fixture, _ = self.prepared_origins()
        selections = [{'name': 'XX_AI', 'kind': 'ai'}, {'name': 'XX_ENTRY', 'kind': 'entry'}]
        with room_source_choices.resolution_scope([fixture.project], self.selection(fixture)):
            with self.assertRaisesRegex(ValueError, '区域设置不一致.*XX/properties.txt'):
                project_packages.collect_rooms(fixture.project, selections, fixture.server, allow_pending=True)

    def test_apply_rejects_conflicting_selected_region_dependencies_before_writing(self):
        fixture, _ = self.prepared_origins()
        rows = room_bindings.parse_world((fixture.local / 'world/xx/world_xx.txt').read_text('utf-8'), 'XX')
        metadata = {'importedAtNs': 0, 'rooms': [dict(row, kind='ai' if row['name'] == 'XX_AI' else 'entry', region='XX') for row in rows],
                    'regions': [{'code': 'XX', 'files': ['properties.txt', 'xx_settingstemplate_outside.txt']}], 'files': []}
        original = {path: path.read_bytes() for root in (fixture.local, fixture.installed) for path in root.rglob('*') if path.is_file()}
        with room_source_choices.resolution_scope([fixture.project], self.selection(fixture)):
            with patch.object(project_packages, 'load_metadata', return_value=metadata):
                with self.assertRaisesRegex(ValueError, '区域设置不一致.*XX/properties.txt'):
                    project_packages.before_deploy(fixture.project, fixture.server)
        for path, content in original.items():
            self.assertEqual(path.read_bytes(), content)

    def test_selected_settings_does_not_bypass_camera_validation(self):
        fixture = self.fixture()
        selected = self.settings(fixture.installed / 'world/xx-rooms', 'XX_AI', 'author-light')
        source = fixture.local / 'world/xx-rooms/XX_AI'
        source.with_name('XX_AI_2.png').unlink()
        output = fixture.root / 'untouched-copy'
        output.mkdir()
        marker = output / 'old-work.txt'
        marker.write_bytes(b'keep old work')
        with self.assertRaisesRegex(ValueError, 'XX_AI_2.png'):
            server.copy_room(source, output, 'XX_AI', replace=True, settings_source=selected)
        self.assertEqual({path.name: path.read_bytes() for path in output.iterdir()}, {'old-work.txt': b'keep old work'})


if __name__ == '__main__':
    unittest.main()
