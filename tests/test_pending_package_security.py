import copy
import hashlib
import json
import unittest

import project_packages as packages
import room_workflow
import storage
from test_project_packages import ProjectPackageTests


class PendingPackageSecurityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ProjectPackageTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def snapshot(self):
        return {str(path.relative_to(self.fixture.root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.fixture.root.rglob('*') if path.is_file() and 'exports' not in path.parts}

    def pending(self, links=None, saved=False):
        f = self.fixture
        links = ['XX_AI'] if links is None else links
        world = f.local / 'world/xx/world_xx.txt'
        world.write_text('ROOMS\nXX_AI : DISCONNECTED, XX_ENTRY\nXX_ENTRY : ' + ', '.join(links) + '\nEND ROOMS\n', 'utf-8')
        if saved:
            f.project['roomConnections'] = dict(version=2, ownedRegions=['XX'], rows=[
                dict(name='XX_AI', region='XX', connections=['DISCONNECTED', 'XX_ENTRY'], tags='', owned=True, kind='ai'),
                dict(name='XX_ENTRY', region='XX', connections=links, tags='', owned=True, kind='entry')])
            f.project_file.write_text(json.dumps(f.project), 'utf-8')
        before = self.snapshot()
        payload = f.payload()
        self.assertEqual(self.snapshot(), before)
        return payload

    def repack(self, files):
        manifest = json.loads(files['manifest.json'])
        manifest['files'] = packages._records({name: value for name, value in files.items() if name != 'manifest.json'})
        files['manifest.json'] = json.dumps(manifest).encode()
        return self.fixture.archive(files)

    def entry(self, manifest):
        return next(row for row in manifest['rooms'] if row['kind'] == 'entry')

    def test_pending_roundtrip_preserves_authored_data_and_does_not_apply(self):
        f = self.fixture
        payload = self.pending(saved=True)
        files = f.unpack(payload)
        original = copy.deepcopy(f.project)
        self.assertEqual(self.entry(json.loads(files['manifest.json']))['connections'], ['XX_AI'])
        f.target()
        result = packages.import_package(payload, f.server)
        self.assertTrue(result['ok'])
        self.assertEqual(result['project']['roomConnections'], original['roomConnections'])
        self.assertEqual(result['project']['dialogue'], original['dialogue'])
        root = storage.project_file('selected').parent
        for path, content in files.items():
            if path.startswith(('rooms/', 'palettes/', 'regions/')):
                self.assertEqual((root / packages._local_path(path)).read_bytes(), content, path)
        self.assertFalse(storage.RUNTIME.exists())
        self.assertFalse(f.local.exists())
        workflow = room_workflow.load('selected')
        self.assertFalse(next(row for row in workflow['rooms'] if row['name'] == 'XX_ENTRY')['verified'])
        with self.assertRaises(ValueError):
            packages.before_deploy(result['project'], f.server)
        again = f.unpack(f.payload())
        self.assertEqual(self.entry(json.loads(again['manifest.json']))['connections'], ['XX_AI'])
        for path, content in files.items():
            if path.startswith(('rooms/', 'palettes/', 'regions/')):
                self.assertEqual(again[path], content, path)

    def test_connected_surplus_exit_is_preserved_and_cannot_be_trimmed(self):
        f = self.fixture
        payload = self.pending(['XX_AI', 'DISCONNECTED', 'XX_OTHER'])
        f.target()
        result = packages.import_package(payload, f.server)
        self.assertTrue(result['ok'])
        state = room_workflow.load('selected')
        entry = next(row for row in state['rooms'] if row['name'] == 'XX_ENTRY')
        self.assertEqual(entry['connections'], ['XX_AI', 'DISCONNECTED', 'XX_OTHER'])
        self.assertFalse(entry['issues'][0]['canReconcile'])
        before = self.snapshot()
        with self.assertRaises(ValueError):
            room_workflow.apply(dict(projectId='selected', revision=state['revision'], connections=[], reconcileRooms=['XX_ENTRY']), f.server)
        self.assertEqual(self.snapshot(), before)

    def test_pending_marker_does_not_accept_invalid_connection_name(self):
        files = self.fixture.unpack(self.pending())
        manifest = json.loads(files['manifest.json'])
        self.entry(manifest)['connections'] = ['../../outside']
        files['manifest.json'] = json.dumps(manifest).encode()
        before = self.snapshot()
        with self.assertRaises(ValueError):
            packages.import_package(self.repack(files), self.fixture.server, replace=True)
        self.assertEqual(self.snapshot(), before)

    def test_pending_marker_does_not_accept_invalid_geometry(self):
        files = self.fixture.unpack(self.pending())
        name = 'rooms/XX_ENTRY/rendered/XX_ENTRY.txt'
        files[name] = files[name].replace(b'XX_ENTRY', b'XX_OTHER', 1)
        before = self.snapshot()
        with self.assertRaises(ValueError):
            packages.import_package(self.repack(files), self.fixture.server, replace=True)
        self.assertEqual(self.snapshot(), before)

    def test_pending_marker_does_not_accept_missing_camera(self):
        files = self.fixture.unpack(self.pending())
        del files['rooms/XX_ENTRY/rendered/XX_ENTRY_1.png']
        before = self.snapshot()
        with self.assertRaises(ValueError):
            packages.import_package(self.repack(files), self.fixture.server, replace=True)
        self.assertEqual(self.snapshot(), before)

    def test_pending_marker_does_not_accept_missing_palette(self):
        files = self.fixture.unpack(self.pending())
        del files['palettes/palette9100.png']
        before = self.snapshot()
        with self.assertRaises(ValueError):
            packages.import_package(self.repack(files), self.fixture.server, replace=True)
        self.assertEqual(self.snapshot(), before)

    def test_pending_marker_does_not_accept_unlisted_or_escaping_files(self):
        original = self.fixture.unpack(self.pending())
        before = self.snapshot()
        for name in ('../outside.txt', 'plugins/unwanted.dll'):
            with self.subTest(name=name):
                files = dict(original)
                files[name] = b'not part of the project'
                with self.assertRaises(ValueError):
                    packages.import_package(self.repack(files), self.fixture.server, replace=True)
                self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
