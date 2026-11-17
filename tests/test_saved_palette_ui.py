import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SavedPaletteUITests(unittest.TestCase):
    def test_project_and_region_choices_are_accessible_without_external_tools(self):
        chrome = shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        node = shutil.which('node')
        if not Path(chrome).is_file() or not node:
            self.skipTest('Chrome and Node required')
        editor = ROOT / 'editor'
        catalogs = {locale: json.loads((editor / 'locales' / (locale + '.json')).read_text('utf-8')) for locale in ('zh-CN', 'en')}
        body = re.search(r'<dialog id="exportDialog"[\s\S]*?</dialog>', (editor / 'index.html').read_text('utf-8'))[0]
        script = 'const CATALOGS=' + json.dumps(catalogs) + ';\n'
        script += (ROOT / 'tests/export_ui_fixture.js').read_text('utf-8')
        script += '\n' + (editor / 'i18n.js').read_text('utf-8')
        script += '\n' + (editor / 'standalone.js').read_text('utf-8')
        script += '\n' + (ROOT / 'tests/saved_palette_browser.js').read_text('utf-8')
        document = '<!doctype html><html><head><meta charset="utf-8"></head><body><button id="export"></button><a id="roomStudio"></a>' + body + '<pre id="result">PENDING</pre><script>' + script + '</script></body></html>'
        with tempfile.TemporaryDirectory(prefix='mi-saved-palette-ui-') as temporary:
            root = Path(temporary)
            page = root / 'test.html'
            page.write_text(document, 'utf-8')
            run = subprocess.run([node, str(ROOT / 'tests/await_browser_result.mjs'), chrome, str(page), str(root / 'profile')], capture_output=True, encoding='utf-8', timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr[-4000:])
            result = json.loads(run.stdout)
            self.assertTrue(result['ok'], result)
            self.assertGreaterEqual(result['checks'], 10)


if __name__ == '__main__':
    unittest.main()
