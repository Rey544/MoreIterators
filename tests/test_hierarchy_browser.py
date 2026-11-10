import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / 'editor'
EVIDENCE = ROOT.parent / 'evidence/hierarchy-20261109'


class HierarchyBrowserTests(unittest.TestCase):
    def page(self, name, markup, styles, scripts, fixture, checks, code=''):
        catalogs = {language: json.loads((EDITOR / 'locales' / (language + '.json')).read_text('utf-8')) for language in ('zh-CN', 'en')}
        bootstrap = 'const PEARL_CATALOGS=' + json.dumps(catalogs) + ';\n' + fixture
        js = bootstrap + '\n' + '\n'.join((EDITOR / script).read_text('utf-8') for script in scripts) + '\n' + code + '\n' + checks
        css = '\n'.join((EDITOR / style).read_text('utf-8') for style in styles)
        markup = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', markup)
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        target = EVIDENCE / (name + '-fixture.html')
        target.write_text('<!doctype html><html><head><meta charset="utf-8"><style>' + css + '</style></head><body class="mi-studio ' + name + '-studio">' + markup + '<pre id="result" hidden>PENDING</pre><script>' + js.replace('</script>', '<\\/script>') + '</script></body></html>', 'utf-8')
        chrome = shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        with tempfile.TemporaryDirectory(prefix='mi-hierarchy-test-') as temporary:
            run = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('hierarchy_browser_runner.mjs')), chrome, str(target), temporary, str(EVIDENCE / name)], capture_output=True, encoding='utf-8', timeout=90)
            self.assertEqual(run.returncode, 0, run.stderr[-5000:])
            result = json.loads(run.stdout)
            self.assertTrue(result['ok'], result)
            self.assertGreaterEqual(result['checks'], 10)
            print(name, json.dumps(result, ensure_ascii=False))

    def test_pearls_scope_and_history(self):
        markup = re.search(r'<body[^>]*>([\s\S]*?)</body>', (EDITOR / 'pearls.html').read_text('utf-8')).group(1)
        fixture = Path(__file__).with_name('pearl_native_fixture.js').read_text('utf-8')
        fixture += '\nfixturePearl.appearance.effect="halcyon";fixturePearl.appearance.music=true;'
        checks = Path(__file__).with_name('hierarchy_pearls_browser.js').read_text('utf-8')
        self.page('pearl', markup, ['pearls.css', 'studio-theme.css', 'room-picker.css'], ['i18n.js', 'line-actions.js', 'audio-settings.js', 'pearl-icons.js', 'pearl-workspace.js', 'studio-undo.js', 'room-picker.js', 'pearls.js'], fixture, checks)

    def test_dialogue_preview_and_shared_switch(self):
        markup = re.search(r'<body[^>]*>([\s\S]*?)</body>', (EDITOR / 'dialogue.html').read_text('utf-8')).group(1)
        fixture = Path(__file__).with_name('hierarchy_dialogue_fixture.js').read_text('utf-8')
        checks = Path(__file__).with_name('hierarchy_dialogue_browser.js').read_text('utf-8')
        self.page('dialogue', markup, ['dialogue.css', 'studio-theme.css'], ['i18n.js', 'line-actions.js', 'studio-undo.js', 'dialogue.js'], fixture, checks)

    def test_appearance_hierarchy_and_sleeve_binding(self):
        app = (EDITOR / 'app.js').read_text('utf-8')
        wardrobe = (EDITOR / 'wardrobe.js').read_text('utf-8')
        html = (EDITOR / 'index.html').read_text('utf-8')
        markup = '<main>' + html[html.index('<aside id="settings"'):html.index('</aside>') + 8] + '<section><select id="target"><option value="forehead">Forehead</option></select></section></main>'
        code = wardrobe[wardrobe.index('function garmentField('):wardrobe.index('function garmentPaint(')]
        code += '\n' + wardrobe[wardrobe.index('let settingsConditions='):wardrobe.index('function wardrobeSettings(')]
        code += '\n' + app[app.index('const sections='):app.index('function composite(')]
        fixture = Path(__file__).with_name('hierarchy_appearance_fixture.js').read_text('utf-8')
        checks = Path(__file__).with_name('hierarchy_appearance_browser.js').read_text('utf-8')
        self.page('appearance', markup, ['style.css', 'studio-theme.css'], ['i18n.js', 'studio-undo.js', 'puppet-arms.js', 'voice-settings.js', 'color-gradients.js'], fixture, checks, code)


if __name__ == '__main__':
    unittest.main()
