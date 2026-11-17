import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

EDITOR = Path(__file__).resolve().parents[1] / 'editor'
TESTS = Path(__file__).resolve().parent


class RoomLoadingUITests(unittest.TestCase):
    def test_partial_failure_recovery_and_explicit_exit_repair(self):
        chrome = shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        node = shutil.which('node')
        if not Path(chrome).is_file() or not node:
            self.skipTest('Chrome and Node are required')
        body = re.search(r'<body[^>]*>([\s\S]*?)</body>', (EDITOR / 'rooms.html').read_text('utf-8'))[1]
        body = re.sub(r'<script[^>]*>[\s\S]*?</script>|<link[^>]*>', '', body)
        catalogs = {locale: json.loads((EDITOR / 'locales' / (locale + '.json')).read_text('utf-8')) for locale in ('zh-CN', 'en')}
        script = 'const CATALOGS=' + json.dumps(catalogs) + ';\n'
        script += (TESTS / 'room_picker_fixture.js').read_text('utf-8').replace('ZZ', 'TEST')
        script += '\n' + (TESTS / 'room_workflow_fixture.js').read_text('utf-8')
        script += '\n' + (TESTS / 'room_loading_fixture.js').read_text('utf-8')
        script += '\n' + '\n'.join((EDITOR / name).read_text('utf-8') for name in ('i18n.js', 'room-picker.js', 'rooms.js'))
        script += '\n' + (TESTS / 'room_loading_browser.js').read_text('utf-8')
        document = '<!doctype html><html><head><meta charset="utf-8"></head><body>' + body + '<pre id="result">PENDING</pre><script>' + script + '</script></body></html>'
        with tempfile.TemporaryDirectory(prefix='mi-room-loading-test-') as temporary:
            root = Path(temporary)
            page = root / 'test.html'
            page.write_text(document, 'utf-8')
            run = subprocess.run([node, str(TESTS / 'await_browser_result.mjs'), chrome, str(page), str(root / 'profile')], capture_output=True, encoding='utf-8', timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr[-5000:])
            result = json.loads(run.stdout)
            self.assertTrue(result['ok'], result)
            self.assertGreaterEqual(result['checks'], 26)


if __name__ == '__main__':
    unittest.main()
