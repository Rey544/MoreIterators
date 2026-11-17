import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DiagnosticsExportUITests(unittest.TestCase):
    def test_editor_game_downloads_missing_files_failures_localization_and_races(self):
        chrome = shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        node = shutil.which('node')
        if not Path(chrome).is_file() or not node:
            self.skipTest('Chrome and Node required')
        catalogs = {language: json.loads((ROOT / 'editor/locales' / (language + '.json')).read_text('utf-8')) for language in ('zh-CN', 'en')}
        script = 'const CATALOGS=' + json.dumps(catalogs) + ';\n'
        for name in ('tests/diagnostics_export_fixture.js', 'editor/i18n.js', 'tests/diagnostics_export_browser.js'):
            script += '\n' + (ROOT / name).read_text('utf-8')
        document = '<!doctype html><html><head><meta charset="utf-8"></head><body><header></header><pre id="result">PENDING</pre><script>' + script + '</script></body></html>'
        with tempfile.TemporaryDirectory(prefix='mi-diagnostics-export-ui-') as temporary:
            root = Path(temporary)
            page = root / 'test.html'
            page.write_text(document, 'utf-8')
            result = subprocess.run([node, str(ROOT / 'tests/await_browser_result.mjs'), chrome, str(page), str(root / 'profile')], capture_output=True, encoding='utf-8', timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr[-4000:])
            report = json.loads(result.stdout)
            self.assertTrue(report['ok'], report)
            self.assertGreaterEqual(report['checks'], 40)
            self.assertEqual(report['downloads'], 10)


if __name__ == '__main__':
    unittest.main()
