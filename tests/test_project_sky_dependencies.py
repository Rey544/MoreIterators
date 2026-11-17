import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import project_packages
import room_bindings
import room_migration
import room_package_dependencies
import storage


class ProjectSkyDependencyTests(unittest.TestCase):
    def fixture(self):
        from test_project_packages import ProjectPackageTests
        value = ProjectPackageTests();value.setUp();self.addCleanup(value.doCleanups)
        return value

    def sky(self, fixture, value='1', variant=''):
        file = fixture.local / 'world/xx-rooms' / ('XX_ENTRY_settings' + variant + '.txt')
        file.write_text('Template: NONE\nPalette: 9100\nEffects: AboveCloudsView-' + value + '-369-321,\n', 'utf-8')
        return file

    def context(self, files, room='XX_ENTRY'):
        return json.loads(files['rooms/' + room + '/rendered/' + room + '_mi_background.json'])

    def test_active_sky_exports_coordinates_without_other_rooms(self):
        f = self.fixture();source = self.sky(f)
        before = source.read_bytes();files = f.unpack(f.payload())
        value = self.context(files)
        self.assertEqual(value['mapPosition'], [74.0, 56.0])
        self.assertEqual(value['size'], [48, 36])
        self.assertEqual(files['rooms/XX_ENTRY/rendered/XX_ENTRY_settings.txt'], before)
        self.assertNotIn(b'XX_PRIVATE', files['regions/XX/map_xx.txt'])
        self.assertFalse(any('XX_PRIVATE' in path for path in files))
        self.assertEqual(source.read_bytes(), before)

    def test_native_missing_map_keeps_zero_position(self):
        f = self.fixture();self.sky(f)
        (f.local / 'world/xx/map_xx.txt').unlink()
        files = f.unpack(f.payload())
        self.assertEqual(self.context(files)['mapPosition'], [0.0, 0.0])
        self.assertNotIn('regions/XX/map_xx.txt', files)

    def test_zero_and_removed_effect_do_not_require_coordinates(self):
        f = self.fixture();file = self.sky(f, '0')
        (f.local / 'world/xx/map_xx.txt').unlink()
        for text in [file.read_text('utf-8'), 'Template: NONE\nPalette: 9100\nEffects: ZeroG-1-0-0,\n']:
            file.write_text(text, 'utf-8');files = f.unpack(f.payload())
            self.assertFalse(any(path.endswith('_mi_background.json') for path in files))

    def test_world_origin_reads_other_room_dimensions_without_exporting_them(self):
        f = self.fixture();self.sky(f)
        f.render(f.local / 'world/xx-rooms/XX_PRIVATE', 'XX_PRIVATE')
        path = f.local / 'world/xx-rooms/XX_PRIVATE.txt'
        path.write_text(path.read_text('utf-8').replace('48*36', '96*200'), 'utf-8')
        world = f.local / 'world/xx/world_xx.txt'
        world.write_text(world.read_text('utf-8').replace('END ROOMS', 'XX_PRIVATE : DISCONNECTED, DISCONNECTED\nEND ROOMS'), 'utf-8')
        (f.local / 'world/xx/map_xx.txt').write_text('XX_AI: 1><2\nXX_ENTRY: 3><4\nXX_PRIVATE: -1000><-2000\n', 'utf-8')
        files = f.unpack(f.payload())
        self.assertEqual(self.context(files)['mapPosition'], [1147.0, 2304.0])
        self.assertFalse(any('XX_PRIVATE' in path for path in files))
        self.assertNotIn(b'XX_PRIVATE', files['regions/XX/map_xx.txt'])

    def test_invalid_coordinates_name_room_settings_and_source(self):
        f = self.fixture();self.sky(f)
        (f.local / 'world/xx/map_xx.txt').write_text('XX_AI: 1><2\nXX_ENTRY: nan><4\n', 'utf-8')
        with self.assertRaises(ValueError) as raised:f.payload()
        message = str(raised.exception)
        self.assertIn('XX_ENTRY_settings.txt', message);self.assertIn('本地模组/world/xx-rooms', message)
        self.assertNotIn(str(f.root), message)

    def test_character_variant_is_preserved_and_produces_context(self):
        f = self.fixture();self.sky(f, '0');variant = self.sky(f, '0.3913043', '-Saint')
        files = f.unpack(f.payload())
        self.assertEqual(files['rooms/XX_ENTRY/rendered/XX_ENTRY_settings-Saint.txt'], variant.read_bytes())
        self.assertEqual(self.context(files)['mapPosition'], [74.0, 56.0])

    def test_scientific_notation_and_native_template_lookup(self):
        self.assertTrue(room_package_dependencies.sky_enabled('Effects: AboveCloudsView-1e-05-0-0,'))
        self.assertFalse(room_package_dependencies.sky_enabled('Effects: AboveCloudsView-0e-05-0-0,', 'Effects: AboveCloudsView-1-0-0,'))
        self.assertIsNone(room_package_dependencies.parent_template('XX', 'Template: SS_SettingsTemplate_Missing', ''))
        self.assertEqual(room_package_dependencies.parent_template('XX', 'Template: SS_SettingsTemplate_Outside', 'Room Setting Templates: Outside'), 'xx_settingstemplate_outside.txt')

    def test_timeline_map_is_named_instead_of_using_base_coordinates(self):
        f = self.fixture();self.sky(f)
        (f.local / 'world/xx/map_xx-Saint.txt').write_text('XX_ENTRY: 900><800\n', 'utf-8')
        with self.assertRaisesRegex(ValueError, 'map_xx-Saint.txt'):f.payload()

    def template(self, fixture):
        folder = fixture.local / 'world/xx'
        (folder / 'properties.txt').write_text('Room Setting Templates: Outside\nCloudsStart: 100\n', 'utf-8')
        template = folder / 'xx_settingstemplate_outside.txt'
        template.write_text('Palette: 9100\nMorePalette0: 9101, 0.5\nEffects: AboveCloudsView-1-0-0,\n', 'utf-8')
        fixture.palette(fixture.local / 'palettes/palette9101.png', 'blue')
        (fixture.local / 'world/xx-rooms/XX_ENTRY_settings.txt').write_text('Template: XX_SettingsTemplate_Outside\n', 'utf-8')
        return template

    def test_template_sky_and_regionkit_palette_roundtrip(self):
        f = self.fixture();template = self.template(f);expected = template.read_bytes()
        payload = f.payload();files = f.unpack(payload)
        self.assertEqual(files['regions/XX/xx_settingstemplate_outside.txt'], expected)
        self.assertIn('palettes/palette9101.png', files)
        self.assertEqual(self.context(files)['mapPosition'], [74.0, 56.0])
        f.target();project_packages.import_package(payload, f.server)
        prepared = project_packages.before_deploy(storage.load_project('selected'), f.server)
        self.assertEqual(prepared['worldFiles']['world/xx/xx_settingstemplate_outside.txt'].splitlines(), expected.decode().splitlines())
        self.assertIn('palettes/palette9101.png', prepared['files'])
        self.assertIn('world/xx-rooms/XX_ENTRY_mi_background.json', prepared['files'])

    def test_zero_overrides_inherited_sky(self):
        f = self.fixture();self.template(f)
        (f.local / 'world/xx-rooms/XX_ENTRY_settings.txt').write_text('Template: XX_SettingsTemplate_Outside\nEffects: AboveCloudsView-0-0-0,\n', 'utf-8')
        files = f.unpack(f.payload())
        self.assertFalse(any(path.endswith('_mi_background.json') for path in files))

    def test_empty_registered_template_roundtrip_remains_empty(self):
        f = self.fixture();template = self.template(f);template.write_bytes(b'')
        payload = f.payload();files = f.unpack(payload)
        relative = 'regions/XX/xx_settingstemplate_outside.txt'
        self.assertEqual(files[relative], b'')
        self.assertNotIn('palettes/palette9101.png', files)
        self.assertFalse(any(path.endswith('_mi_background.json') for path in files))
        f.target();project = project_packages.import_package(payload, f.server)['project']
        prepared = project_packages.before_deploy(project, f.server)
        self.assertEqual(prepared['worldFiles']['world/xx/xx_settingstemplate_outside.txt'], '')
        for invalid in (b'\x00', b'\xff'):
            with self.assertRaises(ValueError):project_packages._region_text(invalid, template.name)
        with self.assertRaises(ValueError):project_packages._text(b'', 'XX_ENTRY.txt')

    def test_import_rejects_missing_or_invalid_background_context(self):
        f = self.fixture();self.sky(f);files = f.unpack(f.payload())
        path = 'rooms/XX_ENTRY/rendered/XX_ENTRY_mi_background.json'
        for missing in [True, False]:
            changed = dict(files)
            if missing:changed.pop(path)
            else:
                value = json.loads(changed[path]);value['size'] = [1, 1];changed[path] = json.dumps(value).encode()
            manifest = json.loads(changed['manifest.json']);manifest['files'] = project_packages._records({key:value for key,value in changed.items() if key != 'manifest.json'})
            changed['manifest.json'] = json.dumps(manifest).encode()
            with self.assertRaisesRegex(ValueError, '背景坐标|天空远景坐标'):project_packages.inspect_import(f.archive(changed), f.server)

    def test_actual_apply_installs_context_templates_and_map(self):
        import server
        f = self.fixture();self.template(f);payload = f.payload();files = f.unpack(payload);f.target()
        project = project_packages.import_package(payload, f.server)['project']
        with patch.object(server, 'save', side_effect=copy.deepcopy), patch.object(server, 'compile_design', return_value={'projectId':'selected'}), \
             patch.object(server, 'MOD', f.local), patch.object(server, 'DESIGNS', storage.RUNTIME), patch.object(server, 'ASSETS', f.game / 'RainWorld_Data/StreamingAssets'), \
             patch.object(server, 'installation_paths', return_value={}), patch.object(server.audio_assets, 'copy_referenced'), patch.object(server.local_content, 'status', return_value={}), \
             patch.object(server.waiting_room, 'prepare', side_effect=AssertionError('no template replacement')), patch.object(server, 'copy_room', side_effect=AssertionError('no default replacement')):
            self.assertTrue(server.deploy(project)['ok'])
        self.assertEqual((f.installed / 'world/xx-rooms/XX_ENTRY_mi_background.json').read_bytes(), files['rooms/XX_ENTRY/rendered/XX_ENTRY_mi_background.json'])
        self.assertEqual((f.installed / 'world/xx/xx_settingstemplate_outside.txt').read_bytes(), files['regions/XX/xx_settingstemplate_outside.txt'])
        self.assertEqual((f.installed / 'world/xx/map_xx.txt').read_text('utf-8').splitlines(), files['regions/XX/map_xx.txt'].decode().splitlines())

    def test_reexport_keeps_original_context(self):
        f = self.fixture();self.sky(f);payload = f.payload();before = self.context(f.unpack(payload));f.target()
        project_packages.import_package(payload, f.server)
        exported = project_packages.export_package('selected', [], f.server)
        after = self.context(f.unpack((storage.EXPORTS / exported['url'].split('/')[-1]).read_bytes()))
        self.assertEqual(before, after)

    def test_dev_map_change_recalculates_existing_context(self):
        f = self.fixture();self.sky(f);files = f.unpack(f.payload());before = self.context(files)
        sidecar = f.local / 'world/xx-rooms/XX_ENTRY_mi_background.json'
        sidecar.write_text(json.dumps(before), 'utf-8')
        (f.local / 'world/xx/map_xx.txt').write_text('XX_AI: 1><2\nXX_ENTRY: 300><400\n', 'utf-8')
        after = self.context(f.unpack(f.payload()))
        self.assertEqual(after['mapPosition'], [371.0, 452.0])
        self.assertNotEqual(before['mapFingerprint'], after['mapFingerprint'])
        self.assertEqual(json.loads(sidecar.read_text('utf-8')), before)

    def test_deleted_map_row_in_registered_world_overrides_imported_old_row(self):
        f = self.fixture();self.sky(f);payload = f.payload();before = self.context(f.unpack(payload))
        project_packages.import_package(payload, f.server, replace=True)
        (f.local / 'world/xx/map_xx.txt').write_text('XX_AI: 1><2\n', 'utf-8')
        after = self.context(f.unpack(f.payload()))
        self.assertEqual(after['mapPosition'], [72.0, 54.0])
        self.assertNotEqual(before['mapFingerprint'], after['mapFingerprint'])

    def oe(self, fixture):
        fixture.project['roomBinding'].update(region='OE', ai='OE_AI', entry='OE_ENTRY')
        fixture.project_file.write_text(json.dumps(fixture.project), 'utf-8')
        for name in ('OE_AI', 'OE_ENTRY'):fixture.render(fixture.local / 'world/oe-rooms' / name, name)
        settings = fixture.local / 'world/oe-rooms/OE_ENTRY_settings.txt'
        settings.write_text('Template: NONE\nPalette: 9100\nEffects: AboveCloudsView-1-0-0,\n', 'utf-8')
        folder = fixture.local / 'world/oe';folder.mkdir(parents=True)
        (folder / 'properties.txt').write_text('Palette: 9100\n', 'utf-8')
        (folder / 'world_oe.txt').write_text('ROOMS\nOE_AI : DISCONNECTED, OE_ENTRY\nOE_ENTRY : OE_AI, DISCONNECTED\nEND ROOMS\n', 'utf-8')
        (folder / 'map_oe.txt').write_text('OE_AI: 1><2\nOE_ENTRY: 3><4\n', 'utf-8')
        return settings

    def test_oe_sky_names_missing_reference_rooms_before_export(self):
        f = self.fixture();settings = self.oe(f);original = settings.read_bytes()
        with self.assertRaisesRegex(ValueError, r'OE_ENTRY.*OE_ENTRY_settings.txt.*GATE_SB_OE.*OE_RUIN02'):f.payload()
        self.assertEqual(settings.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, 'OE_RUIN02'):
            project_packages.export_package('selected', [], f.server, available_rooms={'GATE_SB_OE'})

    def test_oe_sky_bundle_scope_is_respected_but_single_import_rechecks(self):
        f = self.fixture();self.oe(f);references = {'GATE_SB_OE', 'OE_RUIN02'}
        result = project_packages.export_package('selected', [], f.server, available_rooms=references)
        payload = (storage.EXPORTS / result['url'].split('/')[-1]).read_bytes()
        with self.assertRaisesRegex(ValueError, '天空远景缺少参照房间'):project_packages.inspect_import(payload, f.server)
        project, manifest, files = project_packages._inspect(payload, f.server, available_rooms=references)
        self.assertEqual(project['projectId'], 'selected')
        self.assertEqual({row['name'] for row in manifest['rooms']}, {'OE_AI', 'OE_ENTRY'})
        self.assertIn('rooms/OE_ENTRY/rendered/OE_ENTRY_mi_background.json', files)

    def test_oe_deploy_requires_references_in_compiled_world_not_just_bundle_names(self):
        import project_bundles
        f = self.fixture();self.oe(f);references = {'GATE_SB_OE', 'OE_RUIN02'}
        result = project_packages.export_package('selected', [], f.server, available_rooms=references)
        payload = (storage.EXPORTS / result['url'].split('/')[-1]).read_bytes()
        project, manifest, files = project_packages._inspect(payload, f.server, available_rooms=references)
        f.target()
        writes, _ = project_bundles._project_writes(project, manifest, files)
        for target, content in writes.items():target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(content)
        room_bindings._atomic(storage.project_file('selected').parent / 'room-binding-plan.json', room_bindings.plan(project, project['roomBinding']))
        before = {str(path.relative_to(storage.DATA)):path.read_bytes() for path in storage.DATA.rglob('*') if path.is_file()}
        with self.assertRaisesRegex(ValueError, '天空远景缺少参照房间'):project_packages.before_deploy(project, f.server)
        self.assertEqual(before, {str(path.relative_to(storage.DATA)):path.read_bytes() for path in storage.DATA.rglob('*') if path.is_file()})
        real_compile = room_bindings.compile_worlds
        def compile_with_references(records):
            worlds = real_compile(records)
            worlds['world/oe/world_oe.txt'] = worlds['world/oe/world_oe.txt'].replace('END ROOMS', 'GATE_SB_OE : DISCONNECTED\nOE_RUIN02 : DISCONNECTED\nEND ROOMS')
            return worlds
        with patch.object(room_bindings, 'compile_worlds', compile_with_references):
            prepared = project_packages.before_deploy(project, f.server)
            self.assertIn('GATE_SB_OE', prepared['worldFiles']['world/oe/world_oe.txt'])

    def test_package_migration_renames_context_and_templates(self):
        f = self.fixture();self.template(f);payload = f.payload();f.target()
        project = project_packages.import_package(payload, f.server)['project'];old = room_bindings.binding(project)
        new = dict(old, region='YY', ai='YY_AI', entry='YY_ENTRY');project['roomBinding'] = new
        f.project_file = storage.project_file('selected');f.project_file.write_text(json.dumps(project), 'utf-8')
        transaction = room_migration.Files()
        room_migration._package_references(transaction, 'selected', old, new, None)
        root = f.project_file.parent
        value = json.loads((root / 'rooms/rendered/YY_ENTRY_mi_background.json').read_text('utf-8'))
        self.assertEqual(value['room'], 'YY_ENTRY');self.assertEqual(value['sourceRegion'], 'XX')
        self.assertEqual(value['mapPosition'], [74.0, 56.0])
        self.assertTrue((root / 'rooms/regions/YY/yy_settingstemplate_outside.txt').is_file())
        self.assertIn('YY_SettingsTemplate_Outside', (root / 'rooms/rendered/YY_ENTRY_settings.txt').read_text('utf-8'))


if __name__ == '__main__':unittest.main()
