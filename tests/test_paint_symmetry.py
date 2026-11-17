import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

EDITOR = Path(__file__).resolve().parents[1] / 'editor'
sys.path.insert(0, str(EDITOR))
import paint_layers


class PaintSymmetryTests(unittest.TestCase):
    def test_legacy_texture_is_not_rewritten(self):
        for legacy in ({'layers': [{}]}, {'symmetry': True, 'layers': [{}]}, {'symmetry': False, 'layers': [{}]}):
            before = copy.deepcopy(legacy)
            paint_layers.validate(legacy, 'face')
            self.assertEqual(legacy, before)

    def test_each_combination_survives_json_validation(self):
        for x in (False, True):
            for y in (False, True):
                texture = {'symmetry': x, 'symmetryY': y, 'layers': [{}]}
                result = paint_layers.validate(json.loads(json.dumps(texture)), 'face')
                self.assertEqual(result, texture)

    def test_invalid_axis_flags_are_rejected(self):
        for name in ('symmetry', 'symmetryY'):
            for value in (0, 1, 'true', None, [], {}):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, '对称'):
                    paint_layers.validate({name: value, 'layers': [{}]}, 'face')

    def test_symmetry_flags_do_not_change_existing_composited_artwork(self):
        texture = {'layers': [{'png': '', 'visible': True, 'opacity': 1}]}
        original = paint_layers.compose(texture, (7, 5)).tobytes()
        for x in (False, True):
            for y in (False, True):
                self.assertEqual(paint_layers.compose(dict(texture, symmetry=x, symmetryY=y), (7, 5)).tobytes(), original)

    def test_project_zip_roundtrip_preserves_both_axes(self):
        from test_project_packages import ProjectPackageTests
        import project_packages
        import storage
        fixture = ProjectPackageTests(methodName='runTest')
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        textures = {'face': {'symmetry': True, 'symmetryY': True, 'layers': [{'name': 'authored layer', 'png': ''}]}}
        fixture.project['textures'] = textures
        fixture.project_file.write_text(json.dumps(fixture.project), 'utf-8')
        payload = fixture.payload()
        self.assertEqual(json.loads(fixture.unpack(payload)['project.json'])['textures'], textures)
        fixture.target()
        project_packages.import_package(payload, fixture.server)
        self.assertEqual(json.loads(storage.project_file('selected').read_text('utf-8'))['textures'], textures)

    def test_browser_strokes_gradients_and_history(self):
        chrome = shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        node = shutil.which('node')
        self.assertTrue(Path(chrome).is_file(), 'Chrome is required for the Canvas regression')
        self.assertIsNotNone(node, 'Node is required for the Canvas regression')
        app = (EDITOR / 'app.js').read_text('utf-8')
        scripts = (EDITOR / 'paint-layers.js').read_text('utf-8')
        scripts += '\n' + app[app.index('function paintMirrorPoints('):app.index('function paintStrokeGuard(')]
        scripts += '\n' + app[app.index('function clipPaintSegment('):app.index('function initializePaintStroke(')]
        scripts += '\n' + app[app.index('function drawPaintSegment('):app.index('function previewLine(')]
        scripts += '\n' + Path(__file__).with_name('paint_symmetry_browser.js').read_text('utf-8')
        document = '<!doctype html><html><head><meta charset="utf-8"></head><body><pre id="result">PENDING</pre><script>' + scripts + '</script></body></html>'
        with tempfile.TemporaryDirectory(prefix='mi-symmetry-test-') as temporary:
            root = Path(temporary)
            page = root / 'test.html'
            page.write_text(document, 'utf-8')
            result = subprocess.run([node, str(Path(__file__).with_name('await_browser_result.mjs')), chrome, str(page), str(root / 'profile')], capture_output=True, encoding='utf-8', timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr[-3000:])
            report = json.loads(result.stdout)
            self.assertTrue(report['ok'], report)
            self.assertGreaterEqual(report['checks'], 25)


if __name__ == '__main__':
    unittest.main()
