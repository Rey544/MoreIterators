import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


EDITOR = Path(__file__).resolve().parents[1] / 'editor'


class PaintLayerRenameTests(unittest.TestCase):
    def test_rename_dialog_history_and_layer_styles_in_browser(self):
        chrome = shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        node = shutil.which('node')
        if not Path(chrome).is_file() or not node:
            self.skipTest('Chrome and Node are required for isolated browser verification')
        catalogs = {language: json.loads((EDITOR / 'locales' / (language + '.json')).read_text('utf-8')) for language in ('zh-CN', 'en')}
        css = '\n'.join((EDITOR / name).read_text('utf-8') for name in ('style.css', 'studio-theme.css'))
        scripts = '\n'.join((EDITOR / name).read_text('utf-8') for name in ('studio-undo.js', 'head-segments.js', 'paint-composite.js', 'paint-layers.js'))
        app = (EDITOR / 'app.js').read_text('utf-8')
        scripts += '\n' + app[app.index('const paintDesignFlags='):app.index('window.MIUndo?.register(')]
        test = Path(__file__).with_name('paint_layer_rename_browser.js').read_text('utf-8')
        document = '<!doctype html><html><head><meta charset="utf-8"><style>' + css + '</style></head><body class="mi-studio appearance-studio"><main><aside class="paint-layers"><div id="layerList"></div></aside></main><pre id="result">PENDING</pre><script>const catalogs=' + json.dumps(catalogs) + ';\n' + scripts + '\n' + test + '</script></body></html>'
        with tempfile.TemporaryDirectory(prefix='mi-layer-rename-test-') as temporary:
            root = Path(temporary)
            page = root / 'test.html'
            page.write_text(document, 'utf-8')
            run = subprocess.run([node, str(Path(__file__).with_name('await_browser_result.mjs')), chrome, str(page), str(root / 'profile'), '[data-layer-id="layer0"] .layer-name'], capture_output=True, encoding='utf-8', timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr[-5000:])
            result = json.loads(run.stdout)
            self.assertTrue(result['ok'], result)
            self.assertGreaterEqual(result['checks'], 35)


if __name__ == '__main__':
    unittest.main()
