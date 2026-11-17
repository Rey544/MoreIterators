import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import unquote
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import project_packages
import project_bundles
import room_bindings
import room_source_choices
import storage
import test_project_packages as fixtures


class RtmExportIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ProjectPackageTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.project = self.f.project
        self.project['editor'] = {'externalRoomTools': True}
        self.project['design'].update(roomPaletteMode='room', roomGravityMode='room', entryGravityMode='room')
        self.f.project_file.write_text(json.dumps(self.project), 'utf-8')
        self.rtm = self.f.root / 'rtm'
        self.template = self.rtm / 'templates/ct'
        self.base = self.template / 'rooms/CT_A01'
        self.f.render(self.base, 'CT_A01')
        Image.new('RGB', (1400, 800), 'green').save(self.base.with_name('CT_A01_1.png'))
        self.settings = self.base.with_name('CT_A01_settings.txt')
        self.settings.write_text('Template: NONE\nPalette: 9200\nEffects: ZeroG-0.7-1-1,\n', 'utf-8')
        self.f.palette(self.template / 'palettes/palette9200.png', 'blue')
        (self.rtm / 'modinfo.json').write_text(json.dumps(dict(id='octooltestmod', name='RainocTool Map', version='1.1.3')), 'utf-8')
        self.registration = dict(schemaVersion=1, enabled=True, id='ct', name='CT', code='CT', entryRoom='CT_A01',
            rooms=[dict(name='CT_A01', label='CT_A01', connections=['DISCONNECTED', 'DISCONNECTED'], tags=[], spawn=dict(x=4, y=11))])
        self.manifest = self.template / 'region.json'
        self.manifest.write_text(json.dumps(self.registration), 'utf-8')
        self.region = self.template / 'world/ct'
        self.region.mkdir(parents=True)
        (self.region / 'properties.txt').write_text('Palette: 9200\n', 'utf-8')
        (self.region / 'displayname.txt').write_text('Authored region\n', 'utf-8')
        (self.region / 'world_ct.txt').write_text('ROOMS\nCT_A01 : DISCONNECTED, DISCONNECTED\nEND ROOMS\n', 'utf-8')
        (self.region / 'map_ct.txt').write_text('CT_A01: 7><8><7><8><0\n', 'utf-8')
        self.maps = self.template / 'maps'
        self.maps.mkdir()
        (self.maps / 'map_ct.txt').write_text('CT_A01: 9><10><9><10><0\n', 'utf-8')
        self.f.catalogue['regions'] = [dict(name='CT', rooms=[dict(name='CT_A01', region='CT',
            connections=['DISCONNECTED', 'DISCONNECTED'], tags='', conditional=False, geometryPath=str(self.base.with_suffix('.txt')))])]
        self.enabled_roots = [self.f.local, self.f.installed, self.rtm]
        for context in (patch.object(room_source_choices, '_rained_levels', return_value=None),
                        patch.object(room_bindings, 'enabled_asset_roots', side_effect=lambda: list(self.enabled_roots))):
            context.start()
            self.addCleanup(context.stop)

    def report(self):
        return room_source_choices.preflight([storage.load_project('selected')], ['CT_A01'])

    def export_zip(self):
        report = self.report()
        with room_source_choices.resolution_scope([storage.load_project('selected')],
                {'snapshotToken': report['snapshotToken'], 'extraRooms': ['CT_A01']}):
            return self.f.unpack(self.f.payload(['CT_A01']))

    def room(self, report):
        return next(row for row in report['rooms'] if row['room'] == 'CT_A01')

    def original_files(self):
        return {path: path.read_bytes() for path in self.f.root.rglob('*') if path.is_file()}

    def test_registered_settings_camera_palette_and_latest_region_map_reach_zip(self):
        files = self.export_zip()
        for suffix in ('.txt', '_settings.txt', '_1.png'):
            filename = 'CT_A01' + suffix
            self.assertEqual(files['rooms/CT_A01/rendered/' + filename], self.base.with_name(filename).read_bytes())
        self.assertEqual(files['palettes/palette9200.png'], (self.template / 'palettes/palette9200.png').read_bytes())
        self.assertEqual(files['regions/CT/properties.txt'], (self.region / 'properties.txt').read_bytes())
        self.assertEqual(files['regions/CT/map_ct.txt'].decode('utf-8').splitlines(), (self.maps / 'map_ct.txt').read_text('utf-8').splitlines())

    def test_settings_variants_and_their_dependencies_reach_zip(self):
        variant = self.base.with_name('CT_A01_settings-Red.txt')
        variant.write_text('Palette: 9201\nEffects: ZeroG-0.2-1-1,\n', 'utf-8')
        self.f.palette(self.template / 'palettes/palette9201.png', 'yellow')
        files = self.export_zip()
        self.assertEqual(files['rooms/CT_A01/rendered/' + variant.name], variant.read_bytes())
        self.assertEqual(files['palettes/palette9201.png'], (self.template / 'palettes/palette9201.png').read_bytes())

    def test_stale_world_mirror_cannot_replace_authoritative_settings_by_newer_timestamp(self):
        mirror = self.rtm / 'world/ct-rooms/CT_A01'
        self.f.render(mirror, 'CT_A01')
        mirror_settings = mirror.with_name('CT_A01_settings.txt')
        mirror_settings.write_text('Palette: 9999\nEffects: ZeroG-0-1-1,\n', 'utf-8')
        os.utime(self.settings, ns=(1000000000, 1000000000))
        os.utime(mirror_settings, ns=(9000000000, 9000000000))
        report = self.report()
        self.assertFalse(self.room(report)['settingsConflict'])
        files = self.export_zip()
        self.assertEqual(files['rooms/CT_A01/rendered/CT_A01_settings.txt'], self.settings.read_bytes())
        self.assertNotIn('palettes/palette9999.png', files)

    def test_template_asset_precedes_stale_shared_mod_asset(self):
        shared = self.rtm / 'palettes/palette9200.png'
        self.f.palette(shared, 'red')
        files = self.export_zip()
        self.assertEqual(files['palettes/palette9200.png'], (self.template / 'palettes/palette9200.png').read_bytes())
        self.assertNotEqual(files['palettes/palette9200.png'], shared.read_bytes())

    def test_scan_and_export_leave_authored_files_and_connections_unchanged(self):
        before = self.original_files()
        project = copy.deepcopy(self.project)
        self.export_zip()
        self.assertEqual(self.project, project)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content, str(path))

    def test_disabled_rtm_mod_does_not_supply_settings(self):
        self.enabled_roots.remove(self.rtm)
        report = self.report()
        self.assertFalse(any(row['complete'] for row in self.room(report)['settingsVersions']))

    def test_disabled_rtm_region_does_not_supply_settings(self):
        self.registration['enabled'] = False
        self.manifest.write_text(json.dumps(self.registration), 'utf-8')
        report = self.report()
        self.assertFalse(any(row['complete'] for row in self.room(report)['settingsVersions']))

    def test_deleted_settings_stays_missing_instead_of_using_old_mirror(self):
        mirror = self.rtm / 'world/ct-rooms/CT_A01'
        self.f.render(mirror, 'CT_A01')
        self.settings.unlink()
        report = self.report()
        self.assertTrue(any(row['name'] == 'CT_A01_settings.txt' for row in self.room(report)['missingFiles']))

    def test_new_rtm_save_invalidates_export_snapshot(self):
        first = self.report()
        self.settings.write_text('Template: NONE\nPalette: 9200\nEffects: ZeroG-0.1-1-1,\n', 'utf-8')
        second = self.report()
        self.assertNotEqual(first['snapshotToken'], second['snapshotToken'])
        self.assertEqual(self.export_zip()['rooms/CT_A01/rendered/CT_A01_settings.txt'], self.settings.read_bytes())

    def test_rtm_map_seed_is_used_only_when_no_persisted_map_exists(self):
        (self.maps / 'map_ct.txt').unlink()
        files = self.export_zip()
        self.assertEqual(files['regions/CT/map_ct.txt'].decode('utf-8').splitlines(), (self.region / 'map_ct.txt').read_text('utf-8').splitlines())

    def test_unrelated_mi_room_source_keeps_its_existing_region_files(self):
        selected = project_packages._region_source(self.project, 'XX', self.f.local / 'world/xx-rooms/XX_AI', 'properties.txt')
        self.assertEqual(selected, self.f.local / 'world/xx/properties.txt')

    def test_same_region_mi_cache_and_rtm_extra_share_latest_region_map(self):
        self.project['roomBinding'].update(region='CT', ai='CT_AI', entry='CT_ENTRY')
        self.f.project_file.write_text(json.dumps(self.project), 'utf-8')
        for name, cameras in (('CT_AI', 2), ('CT_ENTRY', 1)):
            self.f.render(self.f.local / 'world/ct-rooms' / name, name, cameras)
        own = self.f.local / 'world/ct'
        own.mkdir()
        (own / 'world_ct.txt').write_text('ROOMS\nCT_AI : DISCONNECTED, CT_ENTRY\nCT_ENTRY : CT_AI, DISCONNECTED\nEND ROOMS\n', 'utf-8')
        (own / 'properties.txt').write_text('Palette: 9100\n', 'utf-8')
        (own / 'map_ct.txt').write_text('CT_AI: 0><0\nCT_ENTRY: 1><1\n', 'utf-8')
        current_map = 'CT_AI: 20><30\nCT_ENTRY: 40><50\nCT_A01: 60><70\n'
        (self.maps / 'map_ct.txt').write_text(current_map, 'utf-8')
        files = self.export_zip()
        self.assertEqual(files['regions/CT/map_ct.txt'].decode('utf-8'), current_map)
        self.assertEqual(files['regions/CT/properties.txt'], (self.region / 'properties.txt').read_bytes())

    def test_sky_context_uses_rtm_persisted_map_and_template_world(self):
        self.settings.write_text('Template: NONE\nPalette: 9200\nEffects: AboveCloudsView-1-1-1,\n', 'utf-8')
        files = self.export_zip()
        context = json.loads(files['rooms/CT_A01/rendered/CT_A01_mi_background.json'])
        self.assertEqual(context['mapPosition'], [72.0, 54.0])
        self.assertEqual(context['sourceRegion'], 'CT')

    def test_exporting_existing_room_does_not_run_import_destination_collision_check(self):
        self.f.catalogue['regions'].append(dict(name='XX', rooms=[dict(name='XX_AI', region='XX',
            connections=['DISCONNECTED', 'XX_ENTRY'], tags='', conditional=False,
            geometryPath=str(self.f.external / 'world/xx-rooms/XX_AI.txt'))]))
        before = self.original_files()
        files = self.export_zip()
        payload = self.f.archive(files)
        with self.assertRaisesRegex(ValueError, '已启用内容重名'):
            project_packages.inspect_import(payload, self.f.server)
        for path, content in before.items():self.assertEqual(path.read_bytes(), content)

    def test_export_self_check_still_rejects_invalid_camera_bytes(self):
        files = self.export_zip()
        files['rooms/CT_A01/rendered/CT_A01_1.png'] = b'not a png'
        with self.assertRaisesRegex(ValueError, '房间图片无效'):
            project_packages._inspect(self.f.archive(files), self.f.server, check_destination=False)

    def test_named_bundle_export_keeps_rtm_files_but_import_still_rejects_destination_collision(self):
        self.f.catalogue['regions'].append(dict(name='XX', rooms=[dict(name='XX_AI', region='XX',
            connections=['DISCONNECTED', 'XX_ENTRY'], tags='', conditional=False,
            geometryPath=str(self.f.external / 'world/xx-rooms/XX_AI.txt'))]))
        report = self.report()
        request = dict(projects=['selected'], extraRooms=['CT_A01'], packageName='RTM export check', packageVersion='0.5.0')
        before = self.original_files()
        with room_source_choices.resolution_scope([storage.load_project('selected')],
                {'snapshotToken': report['snapshotToken'], 'extraRooms': ['CT_A01']}):
            result = project_bundles.export_package(request, self.f.server)
        payload = (storage.EXPORTS / unquote(Path(result['url']).name)).read_bytes()
        bundle = self.f.unpack(payload)
        manifest = json.loads(bundle['bundle.json'])
        self.assertEqual(manifest['package'], dict(name='RTM export check', version='0.5.0'))
        files = self.f.unpack(bundle['projects/selected.zip'])
        self.assertEqual(files['rooms/CT_A01/rendered/CT_A01_settings.txt'], self.settings.read_bytes())
        self.assertEqual(files['palettes/palette9200.png'], (self.template / 'palettes/palette9200.png').read_bytes())
        with self.assertRaisesRegex(ValueError, '已启用内容重名'):
            project_bundles.inspect_import(payload, self.f.server)
        for path, content in before.items():self.assertEqual(path.read_bytes(), content)


if __name__ == '__main__':
    unittest.main()
