import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(os.environ.get('MI_ROOM_IDENTITY_EVIDENCE', str(ROOT.parent.parent / 'mi-041/evidence/pl-workflow-20261110')))
BOOT = "import sys;sys.path.insert(0,sys.argv[1]);import server,chamber_presets,storage;chamber_presets.create({'presetId':'mi-chamber-pebbles','name':'PL workflow fixture'},server) if not list(storage.project_files()) else None;server.server_lifecycle.EditorServer(('127.0.0.1',server.PORT),server.Handler).run()"


class RoomIdentityWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='mi-pl-workflow-')
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.data = self.folder / 'data'
        self.game = self.folder / 'game'
        self.assets = self.game / 'RainWorld_Data/StreamingAssets'
        self.data.mkdir()
        self.game.mkdir()
        (self.game / 'RainWorld.exe').write_bytes(b'isolated-test-fixture')
        palette = self.assets / 'palettes'
        palette.mkdir(parents=True)
        palette_root = Path(os.environ['MI_ROOM_IDENTITY_PALETTES']) if os.environ.get('MI_ROOM_IDENTITY_PALETTES') else None
        for number in (8, 12, 13, 26):
            name = 'palette' + str(number) + '.png'
            if palette_root is None:
                Image.new('RGB', (32, 8), '#6c8999').save(palette / name)
            else:
                shutil.copyfile(palette_root / name, palette / name)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.base = 'http://127.0.0.1:' + str(self.port)
        (self.data / 'config.json').write_text(json.dumps({'studioPort': self.port, 'gameRoot': str(self.game)}), 'utf-8')
        self.env = {**os.environ, 'MORE_ITERATORS_DATA': str(self.data), 'RAIN_WORLD_ROOT': str(self.game), 'PYTHONDONTWRITEBYTECODE': '1'}
        self.process = None
        self.log = None
        self.addCleanup(self.stop)
        self.start()
        self.report = {'ok': False, 'transport': 'real editor HTTP', 'fixtures': 'isolated data and game roots, bundled rendered chamber and waiting room', 'palettes': 'synthetic' if palette_root is None else 'read-only copies of native game palettes', 'checks': []}

    def start(self):
        self.log = (self.folder / 'server.log').open('a', encoding='utf-8')
        self.process = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', '-c', BOOT, str(ROOT / 'editor')], env=self.env, stdout=self.log, stderr=self.log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for _ in range(500):
            try:
                self.request('/api/health', timeout=.5)
                return
            except (OSError, ValueError):
                if self.process.poll() is not None:
                    self.fail((self.folder / 'server.log').read_text('utf-8'))
                time.sleep(.05)
        self.fail('Isolated editor failed to become ready.')

    def stop(self):
        if self.process is not None:
            self.process.terminate()
            self.process.wait(timeout=10)
            self.process = None
        if self.log is not None:
            self.log.close()
            self.log = None

    def request(self, path, body=None, status=200, language='zh-CN', timeout=45):
        headers = {'Origin': self.base, 'X-MI-Language': language}
        payload = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            payload = json.dumps(body).encode('utf-8')
        req = urllib.request.Request(self.base + path, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                code, result = response.status, json.load(response)
        except urllib.error.HTTPError as error:
            code, result = error.code, json.load(error)
        self.assertEqual(code, status, result)
        return result

    def protected(self):
        result = {}
        for root in (self.data / 'projects', self.data / 'runtime', self.data / 'local-mod', self.assets / 'mods'):
            for path in sorted(root.rglob('*')):
                if path.is_file():
                    result[path.relative_to(self.folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result

    def external_region(self, source='mod'):
        root = self.assets if source == 'native' else self.assets / 'mods/foreign-pl'
        if source != 'native':
            root.mkdir(parents=True, exist_ok=True)
            (root / 'modinfo.json').write_text(json.dumps({'id': 'fixture.foreign.pl', 'name': 'Foreign PL fixture'}), 'utf-8')
        path = root / 'world/pl/world_pl.txt'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('ROOMS\nPL_A01 : DISCONNECTED\nEND ROOMS\nCREATURES\nEND CREATURES\n', 'utf-8')
        return path

    def rejected_unchanged(self, path, request, expected_code=None):
        before = self.protected()
        result = self.request(path, request, status=400)
        self.assertIn('PL', result['error'])
        if expected_code:
            self.assertEqual(result['code'], expected_code, result)
        self.assertEqual(self.protected(), before)
        return {key: result[key] for key in ('code', 'params', 'error') if key in result}

    def test_actual_rooms_page_saves_pl_and_reopens_both_previews(self):
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        chrome = shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        result = subprocess.run([shutil.which('node') or 'C:/Program Files/node.exe', str(Path(__file__).with_name('room_identity_workflow_browser.mjs')), chrome, self.base, str(self.folder / 'profile'), str(EVIDENCE)], capture_output=True, encoding='utf-8', timeout=150)
        self.assertEqual(result.returncode, 0, result.stderr[-7000:])
        report = json.loads(result.stdout)
        self.assertTrue(report['ok'], report)
        (EVIDENCE / 'actual-page-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
        print(json.dumps(report, ensure_ascii=False))

    def test_pl_saved_applied_previewed_restarted_and_collisions_preserve_content(self):
        project = next(p for p in self.request('/api/projects') if p['name'] == 'PL workflow fixture')
        pid = project['projectId']
        saved = self.request('/api/room-binding?' + urllib.parse.urlencode({'projectId': pid}))
        original = saved['binding']
        request = {'projectId': pid, 'binding': dict(original, region='PL', ai='PL_AI', entry='PL_POOL', entryMode='copy')}
        initial_sources = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (self.data / 'projects' / pid / 'rooms').iterdir() if path.is_file()}
        before = self.protected()
        invalid = self.request('/api/room-binding/preview', dict(request, binding=dict(request['binding'], region='PL_')), status=400)
        self.assertEqual(self.protected(), before)
        self.report['checks'].append({'case': 'PL_ rejected without writing', 'error': invalid['error']})

        foreign = self.external_region()
        error = self.rejected_unchanged('/api/room-binding/preview', request, 'rooms.error.regionTaken')
        self.report['checks'].append({'case': 'installed foreign PL rejected', **error})
        before = self.protected()
        english = self.request('/api/room-binding/preview', request, status=400, language='en')
        self.assertEqual(english['code'], 'rooms.error.regionTaken')
        self.assertEqual(english['params']['region'], 'PL')
        self.assertIn('PL', english['error'])
        self.assertFalse(any('\u3400' <= char <= '\u9fff' for char in english['error']))
        self.assertEqual(self.protected(), before)
        self.report['checks'].append({'case': 'English collision message', 'error': english['error']})
        foreign.rename(foreign.with_suffix('.fixture-backup'))
        self.stop()
        self.start()

        plan = self.request('/api/room-binding/preview', request)
        self.assertEqual(plan['binding'], request['binding'])
        self.assertIn('world/pl/world_pl.txt', plan['worldFiles'])
        self.assertIn('PL_AI', plan['worldFiles']['world/pl/world_pl.txt'])
        self.assertIn('PL_POOL', plan['worldFiles']['world/pl/world_pl.txt'])
        native = self.external_region('native')
        error = self.rejected_unchanged('/api/room-binding/apply', dict(request, token=plan['token']), 'rooms.error.regionTaken')
        self.report['checks'].append({'case': 'native PL added after preview blocks apply', **error})
        native.rename(native.with_suffix('.fixture-backup'))
        self.stop()
        self.start()

        plan = self.request('/api/room-binding/preview', request)
        applied = self.request('/api/room-binding/apply', dict(request, token=plan['token']))
        self.assertTrue(applied['ok'])
        self.assertEqual(applied['binding'], request['binding'])
        project_disk = json.loads((self.data / 'projects' / pid / 'project.json').read_text('utf-8'))
        self.assertEqual(project_disk['roomBinding'], request['binding'])
        installed = self.assets / 'mods/more_iterators_local'
        local = self.data / 'local-mod'
        self.assertEqual((installed / 'world/pl/world_pl.txt').read_bytes(), (local / 'world/pl/world_pl.txt').read_bytes())
        for room in ('PL_AI', 'PL_POOL'):
            for suffix in ('.txt', '_settings.txt', '_1.png'):
                relative = 'world/pl-rooms/' + room + suffix
                self.assertTrue((installed / relative).is_file(), relative)
                self.assertEqual((installed / relative).read_bytes(), (local / relative).read_bytes())
        for name, digest in initial_sources.items():
            self.assertFalse((self.data / 'projects' / pid / 'rooms' / name).exists())
            backups=list((self.data / 'projects' / pid / 'room-backups').glob('*/source/' + name))
            self.assertEqual(len(backups),1)
            self.assertEqual(hashlib.sha256(backups[0].read_bytes()).hexdigest(), digest)
        self.report['checks'].append({'case': 'PL applied to project, local output and installed output', 'binding': applied['binding'], 'oldSourcesMovedToVerifiedBackup': len(initial_sources)})

        for restart in (False, True):
            if restart:
                self.stop()
                self.start()
            read = self.request('/api/room-binding?' + urllib.parse.urlencode({'projectId': pid}))
            self.assertEqual(read['binding'], request['binding'])
            catalog = self.request('/api/room-picker-map?' + urllib.parse.urlencode({'projectId': pid, 'region': 'PL', 'lang': 'zh-CN'}))
            self.assertEqual(catalog['region'], 'PL')
            self.assertTrue({'PL_AI', 'PL_POOL'}.issubset({room['name'] for room in catalog['rooms']}))
            previews = []
            for room in ('PL_AI', 'PL_POOL'):
                preview = self.request('/api/room-picker-preview?' + urllib.parse.urlencode({'projectId': pid, 'room': room}))
                self.assertEqual(preview['room'], room)
                self.assertGreater(preview['width'], 0)
                self.assertGreater(preview['height'], 0)
                self.assertTrue(preview['image'].startswith('data:image/png;base64,'))
                previews.append({'room': room, 'width': preview['width'], 'height': preview['height'], 'cameraCount': len(preview['cameras']), 'imageAvailable': True})
            self.report['checks'].append({'case': 'preview after restart' if restart else 'preview after apply', 'region': catalog['region'], 'rooms': previews})

        plan = self.request('/api/room-binding/preview', request)
        again = self.request('/api/room-binding/apply', dict(request, token=plan['token']))
        self.assertTrue(again['ok'])
        self.report['checks'].append({'case': 'same project reapplies own PL without false collision'})

        second = self.request('/api/chamber-preset-project', {'presetId': 'mi-chamber-moon', 'name': 'Other PL fixture'})['project']
        other = self.request('/api/room-binding?' + urllib.parse.urlencode({'projectId': second['projectId']}))['binding']
        competing = {'projectId': second['projectId'], 'binding': dict(other, region='PL', ai='PL_OTHER_AI', entry='PL_OTHER_POOL')}
        error = self.rejected_unchanged('/api/room-binding/preview', competing, 'rooms.error.regionProject')
        self.report['checks'].append({'case': 'other project cannot claim PL', **error})

        foreign = self.external_region()
        error = self.rejected_unchanged('/api/room-binding/preview', request, 'rooms.error.regionTaken')
        self.report['checks'].append({'case': 'foreign PL added after save is not mistaken for own output', **error})
        self.assertTrue(all(path.resolve().is_relative_to(self.folder.resolve()) for path in (self.data, self.game, installed, local)))
        self.report['ok'] = True
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / 'workflow-result.json').write_text(json.dumps(self.report, ensure_ascii=False, indent=2), 'utf-8')
        print(json.dumps(self.report, ensure_ascii=False))

    def test_v2_json_missing_room_assets_rejects_deploy_before_any_write(self):
        original = self.request('/api/projects')[0]
        binding = self.request('/api/room-binding?' + urllib.parse.urlencode({'projectId': original['projectId']}))['binding']
        source = self.data / 'projects' / original['projectId'] / 'rooms/rendered'
        native = self.assets / 'world/ss-rooms'
        native.mkdir(parents=True)
        for file in source.glob(binding['ai'] + '*'):
            if file.is_file():
                shutil.copyfile(file, native / ('ss_ai' + file.name[len(binding['ai']):]))
        imported = json.loads(json.dumps(original))
        imported.update(projectId='json-missing-assets', name='JSON graph fixture')
        imported['roomBinding'] = dict(region='PL', ai='PL_IMPORT_AI', entry='PL_IMPORT_ENTRY',
                                       oracleId='json_import_oracle', entryMode='copy', aiNode=1, entryNode=0)
        imported['roomConnections'] = dict(version=2, ownedRegions=['PL'], rows=[
            dict(name='PL_IMPORT_AI', region='PL', connections=['DISCONNECTED', 'PL_IMPORT_ENTRY'],
                 tags='', owned=True, kind='ai'),
            dict(name='PL_IMPORT_ENTRY', region='PL', connections=['PL_IMPORT_AI'],
                 tags='', owned=True, kind='entry')])
        result = self.request('/api/import-project', imported)
        self.assertEqual(result['project']['roomConnections'], imported['roomConnections'])
        before = self.protected()
        for language in ('zh-CN', 'en'):
            failure = self.request('/api/deploy', result['project'], status=400, language=language)
            self.assertTrue(failure['code'].startswith('rooms.error.'), failure)
            self.assertIn('missing', failure['code'].lower(), failure)
            self.assertIn('PL_IMPORT_AI', failure['error'])
            if language == 'en':
                self.assertFalse(any('\u3400' <= char <= '\u9fff' for char in failure['error']))
            self.assertEqual(self.protected(), before)
        self.assertFalse((self.data / 'runtime/json_import_oracle.json').exists())
        self.assertFalse((self.data / 'local-mod/world/pl-rooms').exists())


if __name__ == '__main__':
    unittest.main()
