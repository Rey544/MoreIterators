import base64
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

EDITOR = Path(__file__).resolve().parents[1] / 'editor'
sys.path.insert(0, str(EDITOR))
import paint_layers


def png(image):
    out = io.BytesIO()
    image.save(out, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode()


def layer(color, **changes):
    image = Image.new('RGBA', (3, 2), color)
    result = dict(name='layer', png=png(image), visible=True, opacity=1)
    result.update(changes)
    return result


def legacy_composite(texture, size):
    result = Image.new('RGBA', size)
    for item in texture['layers']:
        if not item.get('visible', True) or not item.get('png'):
            continue
        image = Image.open(io.BytesIO(base64.b64decode(item['png'].split(',', 1)[1]))).convert('RGBA')
        image.putalpha(image.getchannel('A').point(lambda value: round(value * item.get('opacity', 1))))
        result = Image.alpha_composite(result, image)
    return result


class PaintClippingTests(unittest.TestCase):
    def test_old_stacks_have_identical_pixels(self):
        stack = {'layers': [layer((100, 20, 70, 128), opacity=.67), layer((40, 130, 90, 210), opacity=.43), layer((0, 0, 255, 255), visible=False)]}
        self.assertEqual(paint_layers.compose(stack, (3, 2)).tobytes(), legacy_composite(stack, (3, 2)).tobytes())

    def test_clipping_preserves_parent_alpha_and_never_leaks(self):
        base = Image.new('RGBA', (3, 2), (255, 0, 0, 128))
        base.putpixel((0, 0), (0, 0, 0, 0))
        stack = {'layers': [layer((0, 0, 0, 0), png=png(base)), layer((0, 0, 255, 255), clipToBelow=True)]}
        output = paint_layers.compose(stack, (3, 2))
        self.assertEqual(output.getchannel('A').tobytes(), base.getchannel('A').tobytes())
        self.assertEqual(output.getpixel((1, 0)), (0, 0, 255, 128))
        self.assertEqual(output.getpixel((0, 0))[3], 0)

    def test_hidden_parent_hides_all_clipped_layers(self):
        stack = {'layers': [layer((255, 0, 0, 255), visible=False), layer((0, 0, 255, 255), clipToBelow=True)]}
        self.assertIsNone(paint_layers.compose(stack, (3, 2)).getbbox())

    def test_child_opacity_and_parent_opacity_are_independent(self):
        stack = {'layers': [layer((255, 0, 0, 255), opacity=.5), layer((0, 0, 255, 255), opacity=.5, clipToBelow=True)]}
        self.assertEqual(paint_layers.compose(stack, (3, 2)).getpixel((0, 0)), (127, 0, 128, 128))

    def test_release_keeps_source_pixels(self):
        stack = {'layers': [layer((255, 0, 0, 0)), layer((0, 0, 255, 255), clipToBelow=True)]}
        before = copy.deepcopy(stack)
        self.assertIsNone(paint_layers.compose(stack, (3, 2)).getbbox())
        del stack['layers'][1]['clipToBelow']
        self.assertEqual(paint_layers.compose(stack, (3, 2)).getpixel((0, 0)), (0, 0, 255, 255))
        self.assertEqual(stack['layers'][1]['png'], before['layers'][1]['png'])

    def test_native_base_split_matches_whole_material(self):
        raw = Image.new('RGBA', (3, 2), (240, 100, 30, 128))
        stack = {'layers': [layer((0, 0, 0, 0)), layer((0, 0, 255, 255), clipToBelow=True), layer((255, 255, 255, 100)), layer((0, 255, 0, 120), clipToBelow=True)]}
        base, overlay = paint_layers.split(stack, (3, 2), raw)
        expected = copy.deepcopy(stack)
        expected['layers'][0]['png'] = png(raw)
        self.assertEqual(Image.alpha_composite(base, overlay).tobytes(), paint_layers.compose(expected, (3, 2)).tobytes())
        self.assertEqual(paint_layers.compose(paint_layers.overlay_texture(stack), (3, 2)).tobytes(), overlay.tobytes())

    def test_missing_old_texture_retains_native_material(self):
        native = Image.new('RGBA', (3, 2), (80, 90, 100, 255))
        base, overlay = paint_layers.split({}, (3, 2), native)
        self.assertEqual(base.tobytes(), native.tobytes())
        self.assertIsNone(overlay.getbbox())

    def test_compiled_and_exported_materials_include_clipping(self):
        from test_standalone_extra_rooms import ExtraRoomExportTests
        import server
        fixture = ExtraRoomExportTests('test_default_still_exports_only_current_two')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        project = server.validate(fixture.project)
        keys = ['face', 'forehead', 'gown', 'sleeve', 'sleeveR', 'collar', 'scarf', 'legThigh', 'puppetHand0', 'puppetSleeve2', 'antennaL', 'earL', 'antennaLowerL', 'earDecorationL']
        keys.extend(item['id'] for item in project['design']['frontPanels'])
        for key in keys:
            size = server.texture_size(project, key)
            image = Image.new('RGBA', size, (170, 50, 30, 128))
            image.putpixel((0, 0), (0, 0, 0, 0))
            layers = [dict(name='Base', png=png(image), opacity=.8, visible=True),
                      dict(name='Clip', png=png(Image.new('RGBA', size, (0, 30, 255, 255))), opacity=.6, visible=True, clipToBelow=True),
                      dict(name='Paint', png=png(Image.new('RGBA', size, (0, 200, 30, 90))), opacity=.4, visible=True),
                      dict(name='Clip 2', png=png(Image.new('RGBA', size, (200, 50, 100, 255))), opacity=.7, visible=True, clipToBelow=True)]
            if paint_layers.hardware(key):
                for i, item in enumerate(layers):
                    item['surface'] = 'inner' if i < 2 else 'outer'
            project['textures'][key] = dict(layers=layers)
        project['design']['frontSymmetry'] = False
        server.validate(project)
        before = copy.deepcopy(project)
        compiled = server.compile_design(project)
        def decode(value):
            return Image.open(io.BytesIO(base64.b64decode(value.split(',', 1)[1]))).convert('RGBA')
        for key in ['gown', 'sleeve', 'sleeveR', 'collar', 'scarf', 'legThigh']:
            with self.subTest(material=key):
                actual = Image.alpha_composite(decode(compiled[key+'BasePng']), decode(compiled[key+'Png']))
                expected = Image.open(io.BytesIO(server.material(project, key))).convert('RGBA')
                self.assertEqual(actual.tobytes(), expected.tobytes())
        for key, field in [('face', 'cheekPng'), ('forehead', 'facePng')]:
            self.assertEqual(decode(compiled[field]).tobytes(), paint_layers.compose(project['textures'][key], server.texture_size(project, key)).tobytes())
        self.assertEqual(decode(compiled['puppetArms'][0]['handPng']).tobytes(), paint_layers.compose(project['textures']['puppetHand0'], (32, 32)).tobytes())
        sleeve = compiled['puppetArms'][2]
        self.assertEqual(Image.alpha_composite(decode(sleeve['sleeveBasePng']), decode(sleeve['sleevePng'])).tobytes(), Image.open(io.BytesIO(server.material(project, 'puppetSleeve2'))).tobytes())
        for key in ('antennaL', 'earL', 'antennaLowerL', 'earDecorationL'):
            prefix = server.head_segments.prefix(key)
            for index, suffix in ((0, 'InnerPng'), (1, 'Png')):
                self.assertEqual(decode(compiled[prefix+'Left'+suffix]).tobytes(), server.antenna_layer(project, key, index).tobytes())
        for item in compiled['frontPanels']:
            self.assertEqual(Image.alpha_composite(decode(item['basePng']), decode(item['patternPng'])).tobytes(), Image.open(io.BytesIO(server.material(project, item['id']))).tobytes())
        self.assertEqual(before, project, 'Compilation mutated editable source data')
        
        
        with fixture.archive() as archive:
            name = next(name for name in archive.namelist() if '/designs/' in name and name.endswith('.json'))
            exported = json.loads(archive.read(name))
            for key in ('facePng', 'cheekPng', 'gownBasePng', 'gownPng', 'antennaLeftInnerPng', 'antennaLeftPng'):
                self.assertEqual(decode(exported[key]).tobytes(), decode(compiled[key]).tobytes())
            self.assertEqual(exported['puppetArms'][2]['sleeveBasePng'], compiled['puppetArms'][2]['sleeveBasePng'])
            self.assertFalse(any('clipToBelow' in name for name in archive.namelist()))
        self.assertEqual(before, project, 'Export mutated editable source data')

    def test_hardware_materials_never_clip_across_surfaces(self):
        stack = {'layers': [layer((255, 0, 0, 128), surface='inner'), layer((0, 255, 0, 255), surface='outer'), layer((0, 0, 255, 255), surface='inner', clipToBelow=True)]}
        inner = {'layers': paint_layers.select_surface(stack, False)}
        outer = {'layers': paint_layers.select_surface(stack, True)}
        self.assertEqual(paint_layers.compose(inner, (3, 2)).getpixel((0, 0)), (0, 0, 255, 128))
        self.assertEqual(paint_layers.compose(outer, (3, 2)).getpixel((0, 0)), (0, 255, 0, 255))

    def test_validate_clip_metadata(self):
        paint_layers.validate({'layers': [layer((0, 0, 0, 0), clipToBelow=True)]}, 'face')
        with self.assertRaises(ValueError):
            paint_layers.validate({'layers': [layer((0, 0, 0, 0), clipToBelow='true')]}, 'face')

    def test_actual_browser_canvas_and_layer_operations(self):
        chrome = shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        if not Path(chrome).is_file():
            self.skipTest('Chrome is unavailable for actual Canvas verification')
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is unavailable for browser protocol verification')
        fixture = {'layers': [layer((255, 0, 0, 128)), layer((0, 0, 255, 255), opacity=.5, clipToBelow=True), layer((0, 255, 0, 160)), layer((255, 255, 255, 255), clipToBelow=True, opacity=.25)]}
        expected = list(paint_layers.compose(fixture, (3, 2)).tobytes())
        scripts = '\n'.join((EDITOR / name).read_text('utf-8') for name in ('paint-composite.js', 'paint-layers.js'))
        app = (EDITOR / 'app.js').read_text('utf-8')
        scripts += '\n' + app[app.index('async function restoreAppearanceHistory(value)'):app.index('window.MIUndo?.register(')]
        test = Path(__file__).with_name('paint_clipping_browser.js').read_text('utf-8')
        document = '<!doctype html><html><head><meta charset="utf-8"><style>body{height:1800px}#layerList{width:170px}</style></head><body><div id="layerList"></div><button id="layerAdd"></button><button id="layerDelete"></button><pre id="result">PENDING</pre><script>const fixture=' + json.dumps(fixture) + ';const expected=' + json.dumps(expected) + ';\n' + scripts + '\n' + test + '</script></body></html>'
        with tempfile.TemporaryDirectory(prefix='mi-layer-test-') as temporary:
            root = Path(temporary)
            page = root / 'test.html'
            page.write_text(document, 'utf-8')
            run = subprocess.run([node, str(Path(__file__).with_name('await_browser_result.mjs')), chrome, str(page), str(root / 'profile')], capture_output=True, encoding='utf-8', timeout=60)
            self.assertEqual(run.returncode, 0, run.stderr[-5000:])
            result = json.loads(run.stdout)
            self.assertTrue(result['ok'], result)
            self.assertGreaterEqual(result['checks'], 25)


if __name__ == '__main__':
    unittest.main()
