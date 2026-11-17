import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


EDITOR = Path(__file__).resolve().parents[1] / 'editor'


class RoomIdentityUITests(unittest.TestCase):
    def test_identity_validation_and_applied_preview_stay_separate(self):
        chrome = shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        node = shutil.which('node')
        if not Path(chrome).is_file() or not node:
            self.skipTest('Chrome and Node are required for isolated browser verification')
        body = re.search(r'<body[^>]*>([\s\S]*?)</body>', (EDITOR / 'rooms.html').read_text('utf-8'))[1]
        body = re.sub(r'<script[^>]*>[\s\S]*?</script>|<link[^>]*>', '', body)
        styles = '\n'.join((EDITOR / name).read_text('utf-8') for name in ('dialogue.css', 'rooms.css', 'room-picker.css', 'studio-theme.css'))
        catalogs = {locale: json.loads((EDITOR / 'locales' / (locale + '.json')).read_text('utf-8')) for locale in ('zh-CN', 'en')}
        fixture = Path(__file__).with_name('room_picker_fixture.js').read_text('utf-8').replace('ZZ', 'TEST')
        fixture += '\n' + Path(__file__).with_name('room_workflow_fixture.js').read_text('utf-8')
        script = 'const CATALOGS=' + json.dumps(catalogs) + ';\n' + fixture
        script += '\n' + '\n'.join((EDITOR / name).read_text('utf-8') for name in ('i18n.js', 'room-picker.js', 'rooms.js'))
        script += '\n' + Path(__file__).with_name('room_identity_browser.js').read_text('utf-8')
        document = '<!doctype html><html><head><meta charset="utf-8"><style>' + styles + '</style></head><body class="mi-studio">' + body + '<pre id="result">PENDING</pre><script>' + script + '</script></body></html>'
        with tempfile.TemporaryDirectory(prefix='mi-room-identity-test-') as temporary:
            root = Path(temporary)
            page = root / 'test.html'
            page.write_text(document, 'utf-8')
            run = subprocess.run([node, str(Path(__file__).with_name('await_browser_result.mjs')), chrome, str(page), str(root / 'profile')], capture_output=True, encoding='utf-8', timeout=60)
            evidence = os.environ.get('MI_ROOM_IDENTITY_EVIDENCE')
            if evidence:
                destination = Path(evidence)
                destination.mkdir(parents=True, exist_ok=True)
                (destination / 'room-identity.html').write_text(document, 'utf-8')
                (destination / 'browser-result.json').write_text(run.stdout or run.stderr, 'utf-8')
            self.assertEqual(run.returncode, 0, run.stderr[-5000:])
            result = json.loads(run.stdout)
            self.assertTrue(result['ok'], result)
            self.assertGreaterEqual(result['checks'], 30)


if __name__ == '__main__':
    unittest.main()
