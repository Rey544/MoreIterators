import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_room_source_choices as fixtures
import room_source_choices as choices


class RtmAssetConflictTests(unittest.TestCase):
    render = fixtures.RoomSourceChoiceTests.render

    def setUp(self):
        fixtures.RoomSourceChoiceTests.setUp(self)
        self.rtm = self.root / 'rtm'
        self.template = self.rtm / 'templates/ct'
        self.other = self.root / 'ordinary'
        self.render(self.template / 'rooms/CT_A01', name='CT_A01', settings='Palette: 9200\n')
        (self.rtm / 'modinfo.json').write_text(json.dumps(dict(id='octooltestmod', name='RTM')), 'utf-8')
        (self.template / 'region.json').write_text(json.dumps(dict(schemaVersion=1, enabled=True, id='ct', code='CT',
            rooms=[dict(name='CT_A01', connections=['DISCONNECTED', 'DISCONNECTED'])])), 'utf-8')
        self.other.mkdir()
        (self.other / 'modinfo.json').write_text(json.dumps(dict(id='ordinary', name='Ordinary')), 'utf-8')
        context = patch.object(choices.room_bindings, 'enabled_asset_roots', return_value=[self.other, self.rtm])
        context.start()
        self.addCleanup(context.stop)

    def palette(self, root, number, color):
        path = root / 'palettes' / ('palette' + str(number) + '.png')
        path.parent.mkdir(exist_ok=True, parents=True)
        Image.new('RGB', (32, 16), color).save(path)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def report(self):
        return choices.preflight([self.project], ['CT_A01'])

    def asset(self, report, number):
        return next(row for row in report['assets'] if row['key'] == 'palettes/palette' + str(number) + '.png')

    def test_mixed_rooms_keep_template_and_ordinary_palettes_and_exclude_shared_mirror(self):
        self.render(self.cache, settings='Palette: 9200\n')
        blue = self.palette(self.template, 9200, 'blue')
        red = self.palette(self.other, 9200, 'red')
        green = self.palette(self.rtm, 9200, 'green')
        report = self.report()
        asset = self.asset(report, 9200)
        self.assertEqual({row['hash'] for row in asset['versions']}, {blue, red})
        self.assertNotIn(green, {row['hash'] for row in asset['versions']})
        self.assertTrue(asset['conflict'])
        self.assertTrue(report['requiresChoices'])

    def test_unreferenced_template_palette_does_not_replace_ordinary_room_palette(self):
        self.render(self.cache, settings='Palette: 9300\n')
        self.palette(self.template, 9200, 'blue')
        red = self.palette(self.other, 9300, 'red')
        purple = self.palette(self.template, 9300, 'purple')
        report = self.report()
        asset = self.asset(report, 9300)
        self.assertEqual({row['hash'] for row in asset['versions']}, {red})
        self.assertNotIn(purple, {row['hash'] for row in asset['versions']})
        self.assertFalse(asset['conflict'])

    def test_template_only_reference_keeps_runtime_palette_priority(self):
        self.render(self.cache, settings='Effects: \n')
        blue = self.palette(self.template, 9200, 'blue')
        self.palette(self.other, 9200, 'red')
        self.palette(self.rtm, 9200, 'green')
        asset = self.asset(self.report(), 9200)
        self.assertEqual({row['hash'] for row in asset['versions']}, {blue})
        self.assertFalse(asset['conflict'])


if __name__ == '__main__':
    unittest.main()
