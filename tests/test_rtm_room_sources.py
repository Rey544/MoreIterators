import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import rtm_room_sources as rtm


class RtmRoomSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.root = self.directory / 'rtm'
        self.root.mkdir()
        self.write(self.root / 'modinfo.json', dict(id='octooltestmod'))
        self.region = self.add_region()

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), 'utf-8')

    def add_region(self, folder='cot', code='COT', ident=None, prefix='templates'):
        region = self.root / prefix / folder
        self.write(region / 'region.json', dict(schemaVersion=1, enabled=True, code=code, id=ident or folder,
                   rooms=[dict(name=code + '_A02', connections=[code + '_S01', None], tags=[])]))
        rooms = region / 'rooms'
        rooms.mkdir(exist_ok=True)
        (rooms / (code + '_A02.txt')).write_text(code + '_A02\n', 'utf-8')
        (rooms / (code + '_A02_settings.txt')).write_text('Palette: 4108\n', 'utf-8')
        (rooms / (code + '_A02_settings-Red.txt')).write_text('Palette: 4109\n', 'utf-8')
        return region

    def modify(self, **values):
        path = self.region / 'region.json'
        current = json.loads(path.read_text('utf-8'))
        current.update(values)
        self.write(path, current)

    def source(self):
        return rtm.room_sources('COT_A02', [self.root])

    def test_registered_source_has_actual_geometry_and_manifest(self):
        row, = self.source()
        self.assertEqual(row['base'], self.region / 'rooms/COT_A02')
        self.assertEqual(row['manifest'], self.region / 'region.json')
        self.assertEqual(row['regionRoot'], self.region)
        self.assertEqual(row['connections'], ['COT_S01', 'DISCONNECTED'])
        self.assertEqual(rtm.region_root_for_source(row['base'], [self.root]), self.region)
        self.assertEqual(rtm.region_root_for_source(row['base'].with_suffix('.txt'), [self.root]), self.region)
        self.assertIn(self.region / 'region.json', row['records'])

    def test_disabled_mod_is_not_found_through_parent_folder(self):
        self.assertEqual(rtm.room_sources('COT_A02', [self.directory]), [])
        self.write(self.root / 'modinfo.json', dict(id='some.other.mod'))
        self.assertEqual(self.source(), [])

    def test_disabled_region_is_not_returned(self):
        self.modify(enabled=False)
        self.assertEqual(self.source(), [])

    def test_missing_optional_enabled_defaults_to_available(self):
        path = self.region / 'region.json'
        value = json.loads(path.read_text('utf-8'))
        del value['enabled']
        self.write(path, value)
        self.assertEqual(len(self.source()), 1)

    def test_custom_registered_template_directory(self):
        self.add_region(folder='custom', prefix='authored')
        self.write(self.root / 'manifest.json', dict(schemaVersion=1, templatesPath='authored'))
        self.assertEqual(self.source()[0]['regionRoot'], self.root / 'authored/custom')

    def test_mirror_state_and_other_world_provider_do_not_hide_selected_template(self):
        self.write(self.root / '.rainoc-editor-view.json', dict(version=1, templates=['unrelated'], files=[]))
        other = self.directory / 'other'
        path = other / 'world/cot/world_cot.txt'
        path.parent.mkdir(parents=True)
        path.write_text('ROOMS\nCOT_A02 : DISCONNECTED\nEND ROOMS\n', 'utf-8')
        rows = rtm.room_sources('COT_A02', [other, self.root])
        self.assertEqual(rows[0]['base'], self.region / 'rooms/COT_A02')
        self.assertIsNone(rtm.region_root_for_source(other / 'world/cot-rooms/COT_A02', [self.root]))

    def test_duplicate_region_code_and_id_are_not_guessed(self):
        self.add_region(folder='duplicate')
        self.assertEqual(self.source(), [])
        self.write(self.root / 'templates/duplicate/region.json', dict(schemaVersion=1, code='YY', id='cot'))
        self.assertEqual(self.source(), [])

    def test_unregistered_backups_and_disabled_templates_are_not_scanned(self):
        self.add_region(folder='cot-backup', prefix='.rainoc-backups')
        self.modify(enabled=False)
        self.assertEqual(self.source(), [])

    def test_room_discovery_matches_rtm_without_settings_as_geometry(self):
        rooms = self.region / 'rooms'
        (rooms / 'COT_A03.txt').write_text('COT_A03\n', 'utf-8')
        (rooms / 'DIFFERENT_A01.txt').write_text('DIFFERENT_A01\n', 'utf-8')
        names = {row['name'] for row in rtm.registered_rooms([self.root])}
        self.assertEqual(names, {'COT_A02', 'COT_A03'})

    def test_escape_paths_rejected(self):
        for value in ('../templates', '/templates', '\\templates', 'C:/templates', 'C:templates', 'templates/../templates'):
            with self.subTest(value=value):
                self.write(self.root / 'manifest.json', dict(schemaVersion=1, templatesPath=value))
                self.assertEqual(self.source(), [])

    def test_linked_template_directory_rejected(self):
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda path: path == self.region or original(path)):
            self.assertEqual(self.source(), [])

    def test_malformed_and_duplicate_json_are_rejected(self):
        path = self.region / 'region.json'
        for value in ('[]', 'null', '{bad', '{"schemaVersion":1,"schemaVersion":1,"code":"COT"}', '{"schemaVersion":true,"code":"COT"}'):
            with self.subTest(value=value):
                path.write_text(value, 'utf-8')
                self.assertEqual(self.source(), [])

    def test_duplicate_room_registration_is_not_guessed(self):
        self.modify(rooms=[dict(name='COT_A02'), dict(name='cot_a02')])
        self.assertEqual(self.source(), [])

    def test_reads_preserve_all_files(self):
        def snapshot():
            return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.directory.rglob('*') if p.is_file()}
        before = snapshot()
        self.source()
        rtm.registered_rooms([self.root])
        self.assertEqual(before, snapshot())

    def test_metadata_records_describe_the_parsed_bytes_and_missing_manifest(self):
        row, = self.source()
        records = {Path(value['path']): value for value in row['metadataRecords']}
        self.assertEqual(records[self.root / 'manifest.json'], dict(path=str(self.root / 'manifest.json'), missing=True))
        config = self.region / 'region.json'
        self.assertEqual(records[config]['sha256'], hashlib.sha256(config.read_bytes()).hexdigest())
        self.assertEqual(records[config]['size'], config.stat().st_size)

    def test_metadata_change_during_read_does_not_create_a_stale_route(self):
        original = Path.read_bytes
        target = self.region / 'region.json'
        def changing_read(path):
            value = original(path)
            if path == target:
                path.write_text('{"schemaVersion":1,"enabled":false}', 'utf-8')
            return value
        with patch.object(Path, 'read_bytes', changing_read):
            self.assertEqual(self.source(), [])

    def test_created_manifest_invalidates_selected_metadata(self):
        import room_source_choices as choices
        row, = self.source()
        self.write(self.root / 'manifest.json', dict(schemaVersion=1, templatesPath='elsewhere'))
        with self.assertRaises(choices.RoomChoiceError) as caught:
            choices._validate_records(row['metadataRecords'])
        self.assertEqual(caught.exception.code, 'room_choices_stale')


if __name__ == '__main__':
    unittest.main()
