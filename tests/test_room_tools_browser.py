import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


EDITOR = Path(__file__).resolve().parents[1] / 'editor'


class RoomToolsBrowserTests(unittest.TestCase):
    def test_independent_room_tools_control_and_history(self):
        chrome = shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        node = shutil.which('node')
        if not Path(chrome).is_file() or not node:
            self.skipTest('Chrome and Node are required for isolated browser verification')
        app = (EDITOR / 'app.js').read_text('utf-8')
        wardrobe = (EDITOR / 'wardrobe.js').read_text('utf-8')
        html = (EDITOR / 'index.html').read_text('utf-8')
        aside = html[html.index('<aside id="settings"'):html.index('</aside>') + 8]
        styles = '\n'.join((EDITOR / name).read_text('utf-8') for name in ('style.css', 'studio-theme.css'))
        catalogs = {language: json.loads((EDITOR / 'locales' / (language + '.json')).read_text('utf-8')) for language in ('zh-CN', 'en')}
        overlay = EDITOR.parent.parent / 'evidence/hierarchy-20261109/appearance-locales.json'
        if overlay.is_file():
            for language, entries in json.loads(overlay.read_text('utf-8')).items():
                catalogs[language].update(entries)
        script = 'const catalogs=' + json.dumps(catalogs) + ';window.fetch=async url=>({ok:true,json:async()=>catalogs[String(url).includes("zh-CN")?"zh-CN":"en"]});\n'
        script += (EDITOR / 'i18n.js').read_text('utf-8') + '\n' + (EDITOR / 'studio-undo.js').read_text('utf-8')
        script += '\n' + wardrobe[wardrobe.index('function garmentField('):wardrobe.index('function garmentButton(')]
        script += '\n' + wardrobe[wardrobe.index('let settingsConditions='):wardrobe.index('function wardrobeSettings(')]
        script += '\n' + app[app.index('const sections='):app.index('function composite(')]
        script += '\n' + app[app.index('function appearanceHistoryData('):app.index('function appearanceView(')]
        script += '\n' + app[app.index('function syncProjectControls('):app.index('function snapshot(')]
        script += '\n' + app[app.index('function refreshChamberPresetPreview('):app.index('async function listProjects(')]
        script += '\n' + app[app.index('async function changeProject('):app.index("$('externalRoomTools').onchange=")]
        script += '\n' + app[app.index("$('externalRoomTools').onchange="):app.index("$('projectName').oninput=")]
        script += '\n' + Path(__file__).with_name('room_tools_browser.js').read_text('utf-8')
        controls = '<header>' + ''.join('<button id="' + name + '"></button>' for name in ('projects', 'new', 'import', 'save', 'apply', 'history', 'export')) + '</header>'
        document = '<!doctype html><html><head><meta charset="utf-8"><style>' + styles + '</style></head><body class="mi-studio appearance-studio">' + controls + '<main>' + aside + '</main><pre id="result">PENDING</pre><script>const $=id=>document.getElementById(id);\n' + script + '</script></body></html>'
        with tempfile.TemporaryDirectory(prefix='mi-room-tools-test-') as temporary:
            root = Path(temporary)
            page = root / 'test.html'
            page.write_text(document, 'utf-8')
            run = subprocess.run([node, str(Path(__file__).with_name('await_browser_result.mjs')), chrome, str(page), str(root / 'profile')], capture_output=True, encoding='utf-8', timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr[-5000:])
            result = json.loads(run.stdout)
            self.assertTrue(result['ok'], result)
            self.assertGreaterEqual(result['checks'], 50)


if __name__ == '__main__':
    unittest.main()
