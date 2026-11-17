import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

EDITOR = Path(__file__).resolve().parents[1] / 'editor'
TESTS = Path(__file__).resolve().parent


class ExportFailureUITests(unittest.TestCase):
    def test_error_sources_retry_and_pending_project_notices(self):
        chrome = shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        node = shutil.which('node')
        if not Path(chrome).is_file() or not node:
            self.skipTest('Chrome and Node are required')
        body = re.search(r'<dialog id="exportDialog"[\s\S]*?</dialog>', (EDITOR / 'index.html').read_text('utf-8'))[0]
        catalogs = {locale: json.loads((EDITOR / 'locales' / (locale + '.json')).read_text('utf-8')) for locale in ('zh-CN', 'en')}
        script = 'const CATALOGS=' + json.dumps(catalogs) + ';\n'
        script += (TESTS / 'export_ui_fixture.js').read_text('utf-8')
        script += '\n' + (EDITOR / 'i18n.js').read_text('utf-8')
        script += '\n' + (EDITOR / 'standalone.js').read_text('utf-8')
        application = (EDITOR / 'app.js').read_text('utf-8')
        script += '\n' + application[application.index("$('import').onclick="):application.index("$('dialogueEditor').onclick=")]
        script += '\n' + (TESTS / 'export_failure_browser.js').read_text('utf-8')
        document = '<!doctype html><html><head><meta charset="utf-8"></head><body><button id="export"></button><button id="import"></button><a id="roomStudio"></a>' + body + '<pre id="result">PENDING</pre><script>' + script + '</script></body></html>'
        with tempfile.TemporaryDirectory(prefix='mi-export-failure-test-') as temporary:
            root = Path(temporary)
            page = root / 'test.html'
            page.write_text(document, 'utf-8')
            run = subprocess.run([node, str(TESTS / 'await_browser_result.mjs'), chrome, str(page), str(root / 'profile')], capture_output=True, encoding='utf-8', timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr[-5000:])
            result = json.loads(run.stdout)
            self.assertTrue(result['ok'], result)
            self.assertGreaterEqual(result['checks'], 15)


if __name__ == '__main__':
    unittest.main()
