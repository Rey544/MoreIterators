import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import export_file_import as imports
import storage


class ExportFileImportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.projects = self.root / 'projects'
        for context in (patch.object(storage, 'PROJECTS', self.projects),
                        patch.object(storage, 'LINKS', []),
                        patch.object(storage, 'available_game_root', return_value=None),
                        patch.object(storage, 'target_mod', return_value=self.root / 'local-mod'),
                        patch.object(imports.room_bindings, 'enabled_asset_roots', return_value=[])):
            context.start();self.addCleanup(context.stop)
        self.project = dict(projectId='one', name='Original', roomConnections={'keep': [0, -1]}, textures={'user': 'unchanged'})
        self.project_file = storage.project_file('one')
        self.project_file.parent.mkdir(parents=True)
        self.project_file.write_text(json.dumps(self.project), 'utf-8')
        self.report = {'snapshotToken': 'a' * 64, 'missingFiles': []}
        context = patch.object(imports.room_source_choices, 'preflight', side_effect=lambda *args, **kwargs: copy.deepcopy(self.report))
        self.preflight = context.start();self.addCleanup(context.stop)
        self.server = SimpleNamespace(export_projects=lambda ids: [json.loads(storage.project_file(pid).read_text('utf-8')) for pid in ids],
                                      export_checked_rooms=lambda data, projects: data.get('extraRooms', []))

    def png(self):
        stream = io.BytesIO();Image.new('RGBA', (4, 3), (12, 34, 56, 78)).save(stream, 'PNG');return stream.getvalue()

    def geometry(self, name='XX_AI'):
        return (name + '\n48*36|-1|0\n\n0,0\n\n\n\n\n\n20|3|15|0,1,0,0,1,|0,1,0,0,1,|1,1,0,0,1,|\n').encode()

    def row(self, relative='rooms/XX_AI/rendered/XX_AI_settings.txt', kind='settings', pid='one', room='XX_AI', target=None):
        if target is None:target = 'rooms/rendered/' + relative.rsplit('/', 1)[-1] if relative.startswith('rooms/') else 'rooms/' + relative
        row = dict(id=str(len(self.report['missingFiles'])), projectId=pid, room=room, relative=relative, targetRelative=target, kind=kind, reason='missing_file')
        self.report['missingFiles'].append(row)
        return row

    def file(self, row, content=b'Palette: 26\nCustomExtension: keep this\n'):
        return dict(missingFileId=row['id'], name=row['relative'].rsplit('/', 1)[-1], base64=base64.b64encode(content).decode())

    def request(self, files, **kwargs):
        return dict(projects=['one'], extraRooms=[], scope='project', snapshotToken=self.report['snapshotToken'], files=files, **kwargs)

    def run_import(self, files, **kwargs):
        return imports.import_missing(self.request(files, **kwargs), self.server)

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

    def assert_error(self, code, call):
        with self.assertRaises(imports.ImportFileError) as error:call()
        self.assertEqual(error.exception.code, 'export.fileImport.' + code)

    def test_cancel_is_success_without_scanning(self):
        result = imports.import_missing({'files': []}, self.server)
        self.assertTrue(result['cancelled']);self.preflight.assert_not_called()

    def test_settings_import_preserves_all_old_files_and_unknown_lines(self):
        old = self.project_file.parent / 'rooms/palettes/palette7.png'
        old.parent.mkdir(parents=True);old.write_bytes(self.png())
        before = self.snapshot();row = self.row();payload = self.file(row)
        result = self.run_import([payload])
        target = self.project_file.parent / row['targetRelative']
        self.assertEqual(target.read_bytes(), base64.b64decode(payload['base64']))
        self.assertEqual({name: self.snapshot()[name] for name in before}, before)
        self.assertEqual(len(result['imported']), 1)
        self.preflight.assert_called_once_with([self.project], [], region=None)
        markers = list((self.project_file.parent / 'rooms/rendered/.mi-export-imports').glob('*.json'))
        self.assertEqual(len(markers), 1)
        marker = json.loads(markers[0].read_text('utf-8'))
        self.assertEqual(marker, {'schema': 'moreiterators.export-file-import.v1', 'files': [{'path': row['targetRelative'], 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}]})

    def test_multiple_known_file_types_are_validated_and_written_to_private_paths(self):
        files = [self.file(self.row('rooms/XX_AI/rendered/XX_AI.txt', 'render'), self.geometry()),
                 self.file(self.row('rooms/XX_AI/rendered/XX_AI_1.png', 'render'), self.png()),
                 self.file(self.row('palettes/palette12.png', 'asset'), self.png()),
                 self.file(self.row('assets/decals/water.png', 'asset'), self.png()),
                 self.file(self.row('regions/XX/map_xx.txt', 'region'), b'XX_AI: 1><2><0><0><1\n'),
                 self.file(self.row('regions/XX/xx_settingstemplate_mine.txt', 'region'), b'')]
        self.assertEqual(len(self.run_import(files)['imported']), 6)
        for row in self.report['missingFiles']:self.assertTrue((self.project_file.parent / row['targetRelative']).is_file())

    def test_explicit_location_contract_and_top_level_id_are_supported(self):
        row = self.row();file = self.file(row);del file['missingFileId']
        file.update({key: row[key] for key in ('projectId', 'room', 'relative')})
        self.assertTrue(self.run_import([file])['ok'])
        second = self.row('rooms/XX_AI/rendered/XX_AI_properties.txt');file = self.file(second);del file['missingFileId']
        self.assertTrue(self.run_import([file], missingFileId=second['id'])['ok'])

    def test_invalid_png_aborts_batch_before_any_directory_or_file_creation(self):
        row = self.row();image = self.row('rooms/XX_AI/rendered/XX_AI_1.png', 'render');before = self.snapshot()
        self.assert_error('invalidFile', lambda: self.run_import([self.file(row), self.file(image, b'invalid PNG')]))
        self.assertEqual(self.snapshot(), before);self.assertFalse((self.project_file.parent / 'rooms').exists())

    def test_invalid_geometry_name_and_settings_encoding_are_rejected(self):
        row = self.row('rooms/XX_AI/rendered/XX_AI.txt', 'render')
        self.assert_error('invalidFile', lambda: self.run_import([self.file(row, self.geometry('YY_AI'))]))
        setting = self.row()
        self.assert_error('invalidFile', lambda: self.run_import([self.file(setting, 'Palette: 2'.encode('utf-16'))]))

    def test_changed_snapshot_is_rejected_before_writing(self):
        row = self.row();request = self.request([self.file(row)]);request['snapshotToken'] = 'stale'
        self.assert_error('stale', lambda: imports.import_missing(request, self.server))
        self.assertFalse((self.project_file.parent / 'rooms').exists())

    def test_refresh_must_still_report_the_exact_missing_file(self):
        row = self.row();request = self.request([self.file(row)]);self.report['missingFiles'] = []
        self.assert_error('unmatched', lambda: imports.import_missing(request, self.server))

    def test_filename_and_project_cannot_be_guessed(self):
        row = self.row();file = self.file(row);file['name'] = 'YY_OTHER.txt'
        self.assert_error('nameMismatch', lambda: self.run_import([file]))
        file = self.file(row);file['projectId'] = 'other'
        self.assert_error('unmatched', lambda: self.run_import([file]))
        row['projectId'] = 'other'
        self.assert_error('unmatched', lambda: self.run_import([self.file(row)]))

    def test_existing_or_invalid_original_file_is_never_overwritten(self):
        row = self.row();path = self.project_file.parent / row['targetRelative'];path.parent.mkdir(parents=True);path.write_bytes(b'Original authored settings')
        self.assert_error('existing', lambda: self.run_import([self.file(row)]));self.assertEqual(path.read_bytes(), b'Original authored settings')
        path.unlink();row['reason'] = 'invalid_file'
        self.assert_error('existing', lambda: self.run_import([self.file(row)]));self.assertFalse(path.exists())

    def test_case_alias_is_not_overwritten(self):
        row = self.row();path = self.project_file.parent / row['targetRelative'].lower();path.parent.mkdir(parents=True);path.write_bytes(b'preserve')
        self.assert_error('existing', lambda: self.run_import([self.file(row)]));self.assertEqual(path.read_bytes(), b'preserve')

    def test_client_target_and_server_mapping_outside_allowed_directories_are_rejected(self):
        row = self.row();file = self.file(row);file['targetRelative'] = '../../project.json'
        self.assert_error('invalid', lambda: self.run_import([file]))
        row['targetRelative'] = '../escape.txt'
        self.assert_error('unsafe', lambda: self.run_import([self.file(row)]))
        row['targetRelative'] = 'project.json'
        self.assert_error('unsafe', lambda: self.run_import([self.file(row)]))

    def test_linked_or_game_owned_destinations_are_rejected(self):
        row = self.row()
        with patch.object(storage, 'available_game_root', return_value=self.root):
            self.assert_error('unsafe', lambda: self.run_import([self.file(row)]))
        with patch.object(imports.room_bindings, 'enabled_asset_roots', return_value=[self.root]):
            self.assert_error('unsafe', lambda: self.run_import([self.file(row)]))
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda path: path == self.project_file.parent / 'rooms' or original(path)):
            self.assert_error('unsafe', lambda: self.run_import([self.file(row)]))

    def test_all_new_files_and_directories_roll_back_on_write_failure(self):
        one = self.row();two = self.row('palettes/palette12.png', 'asset');before = self.snapshot();write = imports._write_file
        count = 0
        def fail_second(path, content, created):
            nonlocal count
            count += 1
            if count == 2:raise OSError('simulated disk failure')
            return write(path, content, created)
        with patch.object(imports, '_write_file', side_effect=fail_second):
            self.assert_error('writeFailed', lambda: self.run_import([self.file(one), self.file(two, self.png())]))
        self.assertEqual(self.snapshot(), before);self.assertFalse((self.project_file.parent / 'rooms').exists())

    def test_import_marker_failure_rolls_back_new_assets_without_touching_older_markers(self):
        old = self.row();self.run_import([self.file(old)])
        before = self.snapshot();row = self.row('palettes/palette12.png', 'asset');write = imports._write_file
        def fail_marker(path, content, created):
            if path.suffix == '.json':raise OSError('marker write failed')
            return write(path, content, created)
        with patch.object(imports, '_write_file', side_effect=fail_marker):
            self.assert_error('writeFailed', lambda: self.run_import([self.file(row, self.png())]))
        self.assertEqual(self.snapshot(), before)

    def test_duplicate_target_is_rejected_before_writes(self):
        row = self.row();before = self.snapshot()
        self.assert_error('invalid', lambda: self.run_import([self.file(row), self.file(row)]));self.assertEqual(self.snapshot(), before)

    def test_limits_apply_before_base64_decoding(self):
        row = self.row();file = self.file(row)
        with patch.object(imports, 'MAX_FILE', 1), patch.object(imports.base64, 'b64decode', side_effect=AssertionError('decoded')):
            self.assert_error('tooLarge', lambda: self.run_import([file]))
        with patch.object(imports, 'MAX_FILES', 1):self.assert_error('tooLarge', lambda: self.run_import([file, file]))
        file['base64'] = '@@@'
        self.assert_error('invalidFile', lambda: self.run_import([file]))

    def test_server_reported_unknown_data_can_be_kept_but_executable_payloads_cannot(self):
        row = self.row('assets/customrooms/custom.dat', 'asset')
        self.assertTrue(self.run_import([self.file(row, b'plugin resource bytes')])['ok'])
        row = self.row('assets/customrooms/run.py', 'asset')
        self.assert_error('invalidFile', lambda: self.run_import([self.file(row, b'print(1)')]))
        row = self.row('assets/customrooms/payload.bin', 'asset')
        executable = b'MZ' + bytes(58) + (64).to_bytes(4, 'little') + b'PE\0\0' + bytes(20)
        self.assert_error('invalidFile', lambda: self.run_import([self.file(row, executable)]))

    def test_room_name_starting_with_mz_is_not_mistaken_for_a_program(self):
        row = self.row('rooms/MZ_AI/rendered/MZ_AI.txt', 'render', room='MZ_AI')
        self.assertTrue(self.run_import([self.file(row, self.geometry('MZ_AI'))])['ok'])


if __name__ == '__main__':unittest.main()
