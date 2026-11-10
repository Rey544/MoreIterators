import json
import hashlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT.parent / 'evidence/hierarchy-20261109'


def changed_paths(before, after, prefix=''):
    if isinstance(before, dict) and isinstance(after, dict):
        return [path for key in sorted(before.keys() | after.keys()) for path in changed_paths(before.get(key), after.get(key), prefix + '.' + key if prefix else key)]
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [path for index, (left, right) in enumerate(zip(before, after)) for path in changed_paths(left, right, prefix + '.' + str(index))]
    return [] if before == after else [prefix]


class FullHierarchyBrowserTests(unittest.TestCase):
    def test_full_appearance_with_isolated_real_server(self):
        chrome = shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        with tempfile.TemporaryDirectory(prefix='mi-hierarchy-full-') as temporary:
            folder = Path(temporary)
            data = folder / 'data'
            game = folder / 'game'
            data.mkdir()
            game.mkdir()
            legacy = Path(os.environ['MI_HIERARCHY_LEGACY_PROJECT']) if os.environ.get('MI_HIERARCHY_LEGACY_PROJECT') else None
            raw_default = os.environ.get('MI_HIERARCHY_RAW_DEFAULT') == '1'
            evidence_kind = 'legacy' if legacy else 'raw-default' if raw_default else 'full'
            project_id = 'hierarchy-fixture'
            fingerprint = lambda root: {str(file.relative_to(root)): hashlib.sha256(file.read_bytes()).hexdigest() for file in root.rglob('*') if file.is_file()}
            original_hashes = None
            if legacy:
                legacy_value = json.loads(legacy.read_text('utf-8'))
                project_id = legacy_value['projectId']
                original_hashes = fingerprint(legacy.parent)
                shutil.copytree(legacy.parent, data / 'projects' / project_id)
            (game / 'RainWorld.exe').write_bytes(b'isolated fixture, never executed')
            (game / 'Rained.exe').write_bytes(b'isolated fixture, never executed')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            (data / 'config.json').write_text(json.dumps({'studioPort': port, 'gameRoot': str(game), 'rainedExecutable': str(game / 'Rained.exe')}), 'utf-8')
            environment = {**os.environ, 'MORE_ITERATORS_DATA': str(data), 'RAIN_WORLD_ROOT': str(game), 'PYTHONDONTWRITEBYTECODE': '1'}
            boot = "import sys;sys.path.insert(0,sys.argv[1]);import server;p=server.project_templates.create(server.default());p['projectId']='hierarchy-fixture';p['name']='层级验证';p['editor']['externalRoomTools']=True;p['design'].update(roomPaletteMode='room',roomGravityMode='mi',entryGravityMode='room',puppetSleeveSyncSeparated=True);p['design'].update({key+'Mode':('solid' if key in ('antennaInner','antennaOuter') else 'original') for key in ('antennaInner','antennaOuter','antennaLowerInner','antennaLowerOuter','earInner','earOuter','earDecorationInner','earDecorationOuter')});server.save(p);server.server_lifecycle.EditorServer(('127.0.0.1',server.PORT),server.Handler).run()"
            if legacy:
                boot = "import sys;sys.path.insert(0,sys.argv[1]);import server;server.server_lifecycle.EditorServer(('127.0.0.1',server.PORT),server.Handler).run()"
            elif raw_default:
                boot = "import sys;sys.path.insert(0,sys.argv[1]);import server;p=server.project_templates.create(server.default());p['projectId']='hierarchy-fixture';p['name']='层级验证';p['editor']['externalRoomTools']=True;p['design'].update(roomPaletteMode='room',roomGravityMode='mi',entryGravityMode='room');server.save(p);server.server_lifecycle.EditorServer(('127.0.0.1',server.PORT),server.Handler).run()"
            with (folder / 'server.log').open('w', encoding='utf-8') as log:
                server = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', '-c', boot, str(ROOT / 'editor')], env=environment, stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                try:
                    base = 'http://127.0.0.1:' + str(port)
                    for _ in range(200):
                        try:
                            with urllib.request.urlopen(base + '/api/health', timeout=.5):
                                break
                        except OSError:
                            if server.poll() is not None:
                                self.fail((folder / 'server.log').read_text('utf-8'))
                            time.sleep(.05)
                    original = (data / 'projects' / project_id / 'project.json').read_bytes()
                    EVIDENCE.mkdir(parents=True, exist_ok=True)
                    run = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('hierarchy_full_browser.mjs')), chrome, base, str(folder / 'profile'), str(EVIDENCE), project_id, evidence_kind], capture_output=True, encoding='utf-8', timeout=90)
                    self.assertEqual(run.returncode, 0, run.stderr[-5000:])
                    result = json.loads(run.stdout)
                    self.assertTrue(result['ok'], result)
                    saved = json.loads((data / 'projects' / project_id / 'project.json').read_text('utf-8'))
                    before = json.loads(original)
                    result['savedFieldChanges'] = changed_paths(before, saved)
                    if raw_default:
                        for key in result['normalizedFields']:
                            before['design'][key] = saved['design'][key]
                    self.assertEqual(saved['design'], before['design'])
                    self.assertEqual(saved['name'], before['name'])
                    self.assertEqual(saved['editor'].get('externalRoomTools'), before['editor'].get('externalRoomTools'))
                    self.assertFalse((data / 'local-mod').exists())
                    if legacy:
                        self.assertEqual(original_hashes, fingerprint(legacy.parent))
                        result['originalFilesUnchanged'] = len(original_hashes)
                    (EVIDENCE / (evidence_kind + '-appearance-result.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
                    print(json.dumps(result, ensure_ascii=False))
                finally:
                    server.terminate()
                    server.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()
