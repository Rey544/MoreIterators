import base64
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import export_file_import
import project_packages
import room_bindings
import room_source_choices
import storage
import server as studio_server
import test_project_packages as package_tests


class ExportFileImportIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = package_tests.ProjectPackageTests('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.project = self.fixture.project
        self.project['editor'] = {'externalRoomTools': True}
        self.project['design'].update(roomPaletteMode='room', roomGravityMode='room', entryGravityMode='room')
        self.fixture.project_file.write_text(json.dumps(self.project), 'utf-8')
        for context in (patch.object(room_source_choices, '_rained_levels', return_value=None),
                        patch.object(room_bindings, 'enabled_asset_roots', return_value=[self.fixture.local, self.fixture.installed, self.fixture.external])):
            context.start();self.addCleanup(context.stop)
        self.server = SimpleNamespace(export_projects=lambda ids: [storage.load_project(pid) for pid in ids],
                                      export_checked_rooms=lambda data, projects: data.get('extraRooms', []))

    def report(self):return room_source_choices.preflight([storage.load_project('selected')], [])

    def import_file(self, report, row, content):
        payload = dict(projects=['selected'], extraRooms=[], scope='project', snapshotToken=report['snapshotToken'],
                       files=[dict(missingFileId=row['id'], name=row['relative'].rsplit('/', 1)[-1], base64=base64.b64encode(content).decode())])
        return export_file_import.import_missing(payload, self.server)

    def export_zip(self):
        report = self.report()
        with room_source_choices.resolution_scope([storage.load_project('selected')], {'snapshotToken': report['snapshotToken']}):
            payload = self.fixture.payload()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:return {name: archive.read(name) for name in archive.namelist()}

    def original_files(self):
        return {path: path.read_bytes() for path in self.fixture.root.rglob('*') if path.is_file()}

    def assert_originals_untouched(self, original):
        for path, content in original.items():self.assertEqual(path.read_bytes(), content, str(path))

    def test_missing_main_settings_import_keeps_external_geometry_cameras_variants_and_properties(self):
        folder = self.fixture.local / 'world/xx-rooms'
        settings = folder / 'XX_AI_settings.txt';content = settings.read_bytes();settings.unlink()
        variant = folder / 'XX_AI_settings-Red.txt';variant.write_text('Palette: 9100\nEffects: ZeroG-0.8-1-1,\n', 'utf-8')
        properties = folder / 'XX_AI_properties.txt';properties.write_text('Gravity: 0.2\n', 'utf-8')
        original = self.original_files();report = self.report()
        row = next(row for row in report['missingFiles'] if row['relative'] == 'rooms/XX_AI/rendered/XX_AI_settings.txt')
        self.assertTrue(self.import_file(report, row, content)['ok'])
        after = self.report()
        self.assertNotEqual(report['snapshotToken'], after['snapshotToken'])
        self.assertFalse(any(row['relative'] == 'rooms/XX_AI/rendered/XX_AI_settings.txt' for row in after['missingFiles']))
        files = self.export_zip()
        for name in ('XX_AI.txt', 'XX_AI_1.png', 'XX_AI_2.png', variant.name, properties.name):
            self.assertEqual(files['rooms/XX_AI/rendered/' + name], (folder / name).read_bytes())
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_settings.txt'], content)
        self.assert_originals_untouched(original)

    def test_missing_one_camera_import_combines_only_the_missing_file_with_existing_render(self):
        folder = self.fixture.local / 'world/xx-rooms'
        camera = folder / 'XX_AI_2.png';content = camera.read_bytes();camera.unlink()
        original = self.original_files();report = self.report()
        row = next(row for row in report['missingFiles'] if row['relative'] == 'rooms/XX_AI/rendered/XX_AI_2.png')
        self.import_file(report, row, content)
        self.assertFalse(any(row['relative'] == 'rooms/XX_AI/rendered/XX_AI_2.png' for row in self.report()['missingFiles']))
        files = self.export_zip()
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_2.png'], content)
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_1.png'], (folder / 'XX_AI_1.png').read_bytes())
        self.assertFalse(camera.exists())
        self.assert_originals_untouched(original)

    def test_unmarked_old_private_camera_cannot_fill_an_external_missing_camera(self):
        camera = self.fixture.local / 'world/xx-rooms/XX_AI_2.png';content = camera.read_bytes();camera.unlink()
        private = self.fixture.project_file.parent / 'rooms/rendered/XX_AI_2.png'
        private.parent.mkdir(parents=True);private.write_bytes(content)
        report = self.report()
        room = next(row for row in report['rooms'] if row['room'] == 'XX_AI')
        self.assertFalse(any(version['complete'] for version in room['renderVersions']))

    def test_changed_imported_camera_hash_revokes_permission_to_combine(self):
        camera = self.fixture.local / 'world/xx-rooms/XX_AI_2.png';content = camera.read_bytes();camera.unlink()
        report = self.report();row = next(row for row in report['missingFiles'] if row['relative'] == 'rooms/XX_AI/rendered/XX_AI_2.png')
        self.import_file(report, row, content)
        ready = self.report()
        private = self.fixture.project_file.parent / row['targetRelative'];self.fixture.palette(private, 'yellow')
        changed = self.report();room = next(row for row in changed['rooms'] if row['room'] == 'XX_AI')
        self.assertNotEqual(ready['snapshotToken'], changed['snapshotToken'])
        self.assertFalse(any(version['complete'] for version in room['renderVersions']))

    def test_internal_import_marker_is_not_part_of_the_exported_zip(self):
        camera = self.fixture.local / 'world/xx-rooms/XX_AI_2.png';content = camera.read_bytes();camera.unlink()
        report = self.report();row = next(row for row in report['missingFiles'] if row['relative'] == 'rooms/XX_AI/rendered/XX_AI_2.png')
        self.import_file(report, row, content)
        marker_directory = self.fixture.project_file.parent / 'rooms/rendered/.mi-export-imports'
        self.assertTrue(list(marker_directory.glob('*.json')))
        self.assertFalse(any('.mi-export-imports' in name for name in self.export_zip()))

    def test_imported_camera_does_not_replace_an_existing_external_camera_with_a_private_alternative(self):
        folder = self.fixture.local / 'world/xx-rooms'
        camera = folder / 'XX_AI_2.png';content = camera.read_bytes();camera.unlink()
        private = self.fixture.project_file.parent / 'rooms/rendered/XX_AI_1.png'
        self.fixture.palette(private, 'blue')
        original = self.original_files();report = self.report()
        row = next(row for row in report['missingFiles'] if row['relative'] == 'rooms/XX_AI/rendered/XX_AI_2.png')
        self.import_file(report, row, content)
        report = self.report()
        room = next(row for row in report['rooms'] if row['room'] == 'XX_AI')
        version = next(row for row in room['renderVersions'] if row['complete'] and 'local' in row['origins'])
        payload = {'snapshotToken': report['snapshotToken'], 'choices': {'selected/XX_AI': {'source': version['id']}}}
        with room_source_choices.resolution_scope([storage.load_project('selected')], payload):
            files = self.fixture.unpack(self.fixture.payload())
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_1.png'], (folder / 'XX_AI_1.png').read_bytes())
        self.assertNotEqual(files['rooms/XX_AI/rendered/XX_AI_1.png'], private.read_bytes())
        self.assert_originals_untouched(original)

    def test_palette_import_is_exported_without_modifying_project_or_manifest(self):
        palette = self.fixture.local / 'palettes/palette9100.png';content = palette.read_bytes();palette.unlink()
        original = self.original_files();report = self.report()
        row = next(row for row in report['missingFiles'] if row['relative'] == 'palettes/palette9100.png')
        self.import_file(report, row, content)
        self.assertEqual(self.export_zip()['palettes/palette9100.png'], content)
        self.assertFalse((self.fixture.project_file.parent / 'room-package.json').exists())
        self.assert_originals_untouched(original)

    def test_new_referenced_decal_is_exported_without_manifest_registration(self):
        settings = self.fixture.local / 'world/xx-rooms/XX_AI_settings.txt'
        values = ['0'] * 11 + ['missing-decal']
        settings.write_text(settings.read_text('utf-8') + 'PlacedObjects: CustomDecal><0><0><' + '~'.join(values) + '\n', 'utf-8')
        content = (self.fixture.local / 'palettes/palette9100.png').read_bytes()
        original = self.original_files();report = self.report()
        row = next(row for row in report['missingFiles'] if row['relative'] == 'assets/decals/missing-decal.png')
        self.import_file(report, row, content)
        self.assertEqual(self.export_zip()['assets/decals/missing-decal.png'], content)
        self.assertFalse((self.fixture.project_file.parent / 'room-package.json').exists())
        self.assert_originals_untouched(original)

    def test_missing_geometry_import_reuses_existing_camera_files(self):
        geometry = self.fixture.local / 'world/xx-rooms/XX_AI.txt';content = geometry.read_bytes();geometry.unlink()
        original = self.original_files();report = self.report()
        row = next(row for row in report['missingFiles'] if row['relative'] == 'rooms/XX_AI/rendered/XX_AI.txt')
        self.import_file(report, row, content)
        self.assertEqual(self.export_zip()['rooms/XX_AI/rendered/XX_AI.txt'], content)
        self.assert_originals_untouched(original)

    def test_http_route_returns_localizable_errors_and_success_is_visible_on_recheck(self):
        settings = self.fixture.local / 'world/xx-rooms/XX_AI_settings.txt'
        content = settings.read_bytes();settings.unlink()
        http = studio_server.ThreadingHTTPServer(('127.0.0.1', 0), studio_server.Handler)
        worker = threading.Thread(target=http.serve_forever, daemon=True)
        port = http.server_address[1]
        with patch.object(studio_server, 'PORT', port):
            worker.start()
            try:
                def request(path, data=None, language='en'):
                    raw = None if data is None else json.dumps(data).encode()
                    req = urllib.request.Request('http://127.0.0.1:' + str(port) + path, data=raw,
                        headers={'Origin': 'http://127.0.0.1:' + str(port), 'Content-Type': 'application/json', 'X-MI-Language': language})
                    try:
                        with urllib.request.urlopen(req, timeout=30) as response:return response.status, json.load(response)
                    except urllib.error.HTTPError as error:return error.code, json.load(error)
                selection = dict(projects=['selected'], extraRooms=[], scope='project')
                status, report = request('/api/export-room-check', selection)
                self.assertEqual(status, 200)
                row = next(row for row in report['missingFiles'] if row['relative'] == 'rooms/XX_AI/rendered/XX_AI_settings.txt')
                payload = dict(selection, snapshotToken=report['snapshotToken'], files=[dict(missingFileId=row['id'], name='wrong.txt', base64=base64.b64encode(content).decode())])
                for language, expected in [('en', 'Select XX_AI_settings.txt'), ('zh-CN', '请选择 XX_AI_settings.txt')]:
                    status, error = request('/api/export-file-import', payload, language)
                    self.assertEqual(status, 400);self.assertEqual(error['code'], 'export.fileImport.nameMismatch')
                    status, messages = request('/locales/' + language + '.json')
                    self.assertEqual(status, 200)
                    self.assertEqual(messages[error['code']].format(**error['params']), expected)
                payload['files'][0]['name'] = 'XX_AI_settings.txt'
                status, result = request('/api/export-file-import', payload)
                self.assertEqual(status, 200);self.assertTrue(result['ok'])
                status, refreshed = request('/api/export-room-check', selection)
                self.assertEqual(status, 200);self.assertNotEqual(refreshed['snapshotToken'], report['snapshotToken'])
                self.assertFalse(any(item['id'] == row['id'] for item in refreshed['missingFiles']))
                self.assertFalse(settings.exists())
            finally:
                http.shutdown();http.server_close();worker.join(timeout=5)


if __name__ == '__main__':unittest.main()
