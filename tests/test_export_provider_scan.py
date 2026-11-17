import json
import unittest
from unittest.mock import patch
from PIL import Image

import test_room_source_choices as fixtures
import room_source_choices as choices


class ExportProviderScanTests(unittest.TestCase):
    setUp = fixtures.RoomSourceChoiceTests.setUp
    render = fixtures.RoomSourceChoiceTests.render
    report = fixtures.RoomSourceChoiceTests.report
    snapshot = fixtures.RoomSourceChoiceTests.snapshot

    def provider(self, name='Enabled provider'):
        root = self.root / 'enabled'
        root.mkdir(exist_ok=True)
        (root / 'modinfo.json').write_text(json.dumps(dict(id='enabled.provider', name=name)), 'utf-8')
        return root

    def palette(self, root, number=9100, color='blue'):
        path = root / 'palettes' / ('palette' + str(number) + '.png')
        path.parent.mkdir(exist_ok=True)
        Image.new('RGB', (32, 8), color).save(path)
        return path

    def test_missing_asset_does_not_read_unrelated_provider_metadata(self):
        root = self.provider()
        before = self.snapshot()
        with patch.object(choices, '_provider', side_effect=AssertionError('missing asset provider read')):
            versions, records = choices._asset_versions('selected', 'palettes/palette9100.png', [root])
        self.assertEqual(versions, [])
        self.assertTrue(any(record and record.get('missing') and record.get('path') == str(root / 'palettes/palette9100.png') for record in records))
        self.assertEqual(self.snapshot(), before)

    def test_present_asset_keeps_provider_and_metadata_snapshot(self):
        root = self.provider()
        self.palette(root)
        before = self.snapshot()
        versions, records = choices._asset_versions('selected', 'palettes/palette9100.png', [root])
        self.assertEqual(versions[0]['meta']['providers'], [dict(id='enabled.provider', name='Enabled provider')])
        self.assertTrue(any(record and record.get('path') == str(root / 'modinfo.json') and record.get('sha256') for record in records))
        self.assertEqual(self.snapshot(), before)

    def test_newly_created_asset_is_found_by_next_scan(self):
        root = self.provider()
        with patch.object(choices.room_bindings, 'enabled_asset_roots', return_value=[root]):
            first = self.report()
            self.palette(root)
            second = self.report()
        self.assertNotEqual(first['snapshotToken'], second['snapshotToken'])
        self.assertTrue(first['assets'][0]['missing'])
        self.assertFalse(second['assets'][0]['missing'])

    def test_provider_edits_are_reread_by_next_scan(self):
        root = self.provider()
        self.palette(root)
        with patch.object(choices.room_bindings, 'enabled_asset_roots', return_value=[root]):
            first = self.report()
            self.provider('Revised provider')
            second = self.report()
        self.assertNotEqual(first['snapshotToken'], second['snapshotToken'])
        self.assertEqual(second['assets'][0]['versions'][0]['providers'][0]['name'], 'Revised provider')

    def test_disabled_provider_is_not_reused_by_next_scan(self):
        root = self.provider()
        self.palette(root)
        with patch.object(choices.room_bindings, 'enabled_asset_roots', return_value=[root]):
            first = self.report()
        second = self.report()
        self.assertFalse(first['assets'][0]['missing'])
        self.assertTrue(second['assets'][0]['missing'])

    def test_present_corrupt_asset_still_reports_invalid_version(self):
        root = self.provider()
        path = self.palette(root)
        path.write_bytes(b'invalid palette')
        versions, records = choices._asset_versions('selected', 'palettes/palette9100.png', [root])
        self.assertEqual(versions[0]['meta']['issues'], ['invalid_asset'])
        self.assertFalse(versions[0]['meta']['complete'])
        self.assertTrue(versions[0]['meta']['providers'])


if __name__ == '__main__':
    unittest.main()
