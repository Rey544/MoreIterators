import copy
import base64
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import project_packages
import projections
import room_bindings
import room_controls
import room_preview
import room_source_choices
import server
import standalone
import storage
import test_project_packages as package_fixture


class ExternalRoomPriorityTests(unittest.TestCase):
    def setUp(self):
        fixture = package_fixture.ProjectPackageTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        project = server.default()
        project.update(projectId='selected', name='External room priority', roomBinding=copy.deepcopy(fixture.project['roomBinding']))
        project['editor']['externalRoomTools'] = True
        project['design'].update(roomPaletteMode='mi', roomGravityMode='mi', entryGravityMode='zero',
                                 roomPalette=26, roomWorkColor='#123456', roomReceptionColor='#abcdef',
                                 roomBrightness=1.25, roomContrast=1.4, roomSaturation=.6)
        fixture.project = server.validate(project)
        self.project = fixture.project
        fixture.project_file.write_text(json.dumps(self.project), 'utf-8')
        for context in (
            patch.object(room_bindings, 'enabled_asset_roots', side_effect=lambda: [fixture.local]),
            patch.object(server, 'MOD', fixture.local),
            patch.object(server, 'DESIGNS', storage.RUNTIME),
            patch.object(server, 'ASSETS', fixture.game / 'RainWorld_Data/StreamingAssets'),
            patch.object(server, 'installation_paths', return_value={}),
            patch.object(server.local_content, 'status', return_value={}),
        ):
            context.start()
            self.addCleanup(context.stop)
        self.room_files = {}
        for name in ('XX_AI', 'XX_ENTRY'):
            base = fixture.local / 'world/xx-rooms' / name
            lines = base.with_suffix('.txt').read_text('utf-8').splitlines()
            while len(lines) < 11:
                lines.append('')
            lines.append('0,0|1,0|')
            base.with_suffix('.txt').write_text('\n'.join(lines) + '\n', 'utf-8')
            decal = '~'.join(['0'] * 11 + ['priority-decal'])
            settings = ('Template: XX_SettingsTemplate_Custom\nPalette: 9100\n'
                        'FadePalette: 9101,0.25,0.75\nMorePalette0: 9102,0.4,0.6\n'
                        'Effects: ZeroG-0.35-1-1, BrokenZeroG-0.1-0-0,\n'
                        'PlacedObjects: CustomDecal><0><0><' + decal + '\n'
                        'FutureRoomField: leave this: value | untouched\n')
            files = {
                name + '_settings.txt': settings,
                name + '_settings-White.txt': 'Template: XX_SettingsTemplate_Custom\nPalette: 9102\nEffects: ZeroG-0.65-0-0,\nRoleField: keep-white\n',
                name + '_properties.txt': 'SomeRoomProperty: 1\nFutureRoomProperty: keep\n',
            }
            for filename, text in files.items():
                (base.parent / filename).write_text(text, 'utf-8')
                self.room_files[filename] = (base.parent / filename).read_bytes()
        region = fixture.local / 'world/xx'
        self.properties = b'Palette: 9103\nRoom Setting Templates: Custom\nClouds: 0.4\nFutureRegionField: keep\n'
        self.template = b'Palette: 9103\nEffects: ZeroG-0.15-1-1,\nTemplateField: keep\n'
        (region / 'properties.txt').write_bytes(self.properties)
        (region / 'xx_settingstemplate_custom.txt').write_bytes(self.template)
        for index, color in ((26, 'gray'), (9101, 'green'), (9102, 'blue'), (9103, 'purple')):
            fixture.palette(fixture.local / ('palettes/palette' + str(index) + '.png'), color)
        fixture.palette(fixture.local / 'decals/priority-decal.png', 'orange')

    def snapshot(self, root):
        return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob('*') if path.is_file()}

    def assert_modes(self, design, expected):
        self.assertEqual({key: design[key] for key in room_controls.MODES}, expected)

    def assert_authored(self, project, original):
        self.assertIs(project['editor']['externalRoomTools'], True)
        self.assertEqual(project['design'], original['design'])
        self.assertEqual(project['roomBinding'], original['roomBinding'])

    def assert_copied_settings(self, filename, actual):
        expected = self.room_files[filename]
        if filename.endswith('_settings.txt'):
            self.assert_same_text(actual, expected)
        else:
            self.assertEqual(actual, expected)

    def assert_same_text(self, actual, expected):
        normalize = lambda content: content.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
        self.assertEqual(normalize(actual), normalize(expected))

    def test_flag_save_and_runtime_modes_preserve_legacy_and_author_presets(self):
        original = copy.deepcopy(self.project)
        old_modes = dict(roomPaletteMode='mi', roomGravityMode='mi', entryGravityMode='zero')
        for value in ('missing', False):
            with self.subTest(flag=value):
                old = copy.deepcopy(self.project)
                if value == 'missing':
                    old['editor'].pop('externalRoomTools')
                else:
                    old['editor']['externalRoomTools'] = value
                before = copy.deepcopy(old)
                self.assert_modes(server.compile_design(old), old_modes)
                self.assertEqual(old, before)
                self.assertFalse(room_controls.room_palette(old))
                self.assertFalse(room_controls.room_gravity(old))
                self.assertFalse(room_controls.entry_gravity(old))
        saved = server.save(copy.deepcopy(self.project))
        self.assert_authored(saved, original)
        loaded = storage.load_project('selected')
        self.assert_authored(loaded, original)
        before = copy.deepcopy(loaded)
        self.assert_modes(server.compile_design(loaded), dict.fromkeys(room_controls.MODES, 'room'))
        self.assertEqual(loaded, before)
        self.assertTrue(room_controls.room_palette(loaded))
        self.assertTrue(room_controls.room_gravity(loaded))
        self.assertTrue(room_controls.entry_gravity(loaded))

    def test_owned_copy_keeps_devtools_settings_and_no_repeated_parameter_choice(self):
        before = self.snapshot(self.fixture.local)
        original = copy.deepcopy(self.project)
        report = room_source_choices.preflight([self.project])
        self.assertEqual(report['parameterModes'], [])
        self.assertFalse(report['requiresChoices'])
        destination = self.fixture.root / 'copy'
        with room_source_choices.resolution_scope([self.project]):
            for kind, name in (('ai', 'XX_AI'), ('entry', 'XX_ENTRY')):
                source = self.fixture.local / 'world/xx-rooms' / name
                room_controls.copy_owned_room(self.project, source, destination, name, kind, server, replace=True)
        for filename, content in self.room_files.items():
            self.assert_copied_settings(filename, (destination / filename).read_bytes())
        self.assertEqual(self.snapshot(self.fixture.local), before)
        self.assertEqual(self.project, original)

    def test_split_geometry_and_settings_keep_selected_region_dependencies(self):
        fixture = self.fixture
        cache = fixture.project_file.parent / 'rooms/rendered'
        for name in ('XX_AI', 'XX_ENTRY'):
            fixture.render(cache / name, name, 2 if name == 'XX_AI' else 1, color='blue')
            (cache / (name + '_settings.txt')).write_text('Template: NONE\nPalette: 26\n', 'utf-8')
        stale_region = fixture.project_file.parent / 'rooms/regions/XX'
        stale_region.mkdir(parents=True)
        (stale_region / 'properties.txt').write_text('Palette: 26\nRoom Setting Templates: Stale\n', 'utf-8')
        (stale_region / 'xx_settingstemplate_stale.txt').write_text('Palette: 26\n', 'utf-8')
        report = room_source_choices.preflight([self.project])
        self.assertEqual(report['parameterModes'], [])
        choices = {}
        for row in report['rooms']:
            choices[row['projectId'] + '/' + row['room']] = dict(
                source=next(value['id'] for value in row['renderVersions'] if 'project' in value['origins'] and value['complete']),
                settings=next(value['id'] for value in row['settingsVersions'] if 'local' in value['origins'] and value['complete']))
        before = self.snapshot(fixture.local)
        with room_source_choices.resolution_scope([self.project], dict(snapshotToken=report['snapshotToken'], choices=choices)):
            exported = fixture.unpack(fixture.payload())
            self.assertEqual(standalone._room_region_file(self.project, cache / 'XX_AI', 'XX_AI', 'properties.txt').read_bytes(), self.properties)
        self.assertEqual(exported['regions/XX/properties.txt'], self.properties)
        self.assertEqual(exported['regions/XX/xx_settingstemplate_custom.txt'], self.template)
        self.assertNotIn('regions/XX/xx_settingstemplate_stale.txt', exported)
        for filename, content in self.room_files.items():
            name = 'XX_ENTRY' if filename.startswith('XX_ENTRY') else 'XX_AI'
            self.assertEqual(exported['rooms/' + name + '/rendered/' + filename], content)
        self.assertEqual(exported['rooms/XX_AI/rendered/XX_AI_1.png'], (cache / 'XX_AI_1.png').read_bytes())
        self.assertEqual(self.snapshot(fixture.local), before)

    def test_project_zip_roundtrip_and_real_apply_keep_author_data_and_room_files(self):
        fixture = self.fixture
        original = copy.deepcopy(self.project)
        source_root = fixture.local
        before = self.snapshot(source_root)
        with room_source_choices.resolution_scope([self.project]):
            payload = fixture.payload()
        exported = fixture.unpack(payload)
        self.assert_authored(json.loads(exported['project.json']), original)
        for index in (9100, 9101, 9102, 9103):
            self.assertIn('palettes/palette' + str(index) + '.png', exported)
        self.assertIn('assets/decals/priority-decal.png', exported)
        fixture.target()
        imported = project_packages.import_package(payload, server)['project']
        self.assert_authored(imported, original)
        with patch.object(server, 'MOD', fixture.local), patch.object(server, 'DESIGNS', storage.RUNTIME):
            result = server.deploy(imported)
        self.assertTrue(result['ok'])
        saved = storage.load_project('selected')
        self.assert_authored(saved, original)
        runtime = json.loads(storage.design_path('selected', original['roomBinding']['oracleId']).read_text('utf-8'))
        self.assert_modes(runtime, dict.fromkeys(room_controls.MODES, 'room'))
        for filename, content in self.room_files.items():
            for base in (fixture.local, fixture.installed):
                self.assertEqual((base / 'world/xx-rooms' / filename).read_bytes(), content)
        self.assert_same_text((fixture.installed / 'world/xx/properties.txt').read_bytes(), self.properties)
        self.assert_same_text((fixture.installed / 'world/xx/xx_settingstemplate_custom.txt').read_bytes(), self.template)
        self.assertEqual(self.snapshot(source_root), before)

    def test_preview_uses_effective_room_mode_without_changing_author_settings(self):
        before = self.snapshot(self.fixture.local)
        original = storage.project_file('selected').read_bytes()
        calls = []
        decode = projections.decode_room_image
        def observe(image, palette, design):
            calls.append(copy.deepcopy(design))
            return decode(image, palette, design)
        with patch.object(projections, 'decode_room_image', side_effect=observe):
            result = room_preview.preview('XX_AI', 'selected')
        self.assertIsNotNone(result['image'])
        self.assertEqual(len(calls), 2)
        for design in calls:
            self.assert_modes(design, dict.fromkeys(room_controls.MODES, 'room'))
            self.assertEqual(design['roomWorkColor'], self.project['design']['roomWorkColor'])
        changed = copy.deepcopy(self.project)
        changed['design'].update(roomBrightness=.25, roomContrast=.25, roomSaturation=0)
        with patch.object(room_preview, '_project', return_value=changed):
            other = room_preview.preview('XX_AI', 'selected')
        self.assertEqual(other['image'], result['image'])
        self.assertEqual(storage.project_file('selected').read_bytes(), original)
        self.assertEqual(self.snapshot(self.fixture.local), before)

    def test_rk_direct_fades_use_numeric_order_camera_factors_and_stop_at_gap(self):
        fixture = self.fixture
        source = fixture.local / 'world/xx-rooms/XX_AI'
        colors = {9200: (16, 32, 48), 9201: (48, 64, 80), 9202: (96, 112, 128),
                  9203: (128, 144, 160), 9204: (32, 64, 96), 9205: (194, 210, 226), 9206: (255, 255, 255)}
        for index, color in colors.items():
            fixture.palette(fixture.local / ('palettes/palette' + str(index) + '.png'), color)
        text = ('Template: NONE\nPalette: 9200\nFadePalette: 9201,0.5,0.25\n'
                'MorePalette10: 9205,0.5,0.25\nMorePalette2: 9204,0.5,0.5\n'
                'MorePalette0: 9202,0.5,0.5\nMorePalette1: 9203,0.5\n'
                + ''.join('MorePalette' + str(index) + ': 9200,0,0\n' for index in reversed(range(3, 10)))
                + 'MorePalette12: 9206,1,1\n')
        Path(str(source) + '_settings.txt').write_text(text, 'utf-8')
        before = copy.deepcopy(self.project)
        expected = ((129, 149, 169), (83, 105, 127), (16, 32, 48))
        for camera, color in enumerate(expected):
            with self.subTest(camera=camera):
                palette = projections.room_palette(self.project, source, camera)
                self.assertEqual(palette.size, (32, 8))
                self.assertEqual(set(palette.getdata()), {color})
        self.assertEqual(self.project, before)

    def test_linked_apply_copies_role_settings_to_installed_mod(self):
        fixture = self.fixture
        workspace = fixture.root / 'linked-workspace'
        link = dict(id='test.linked', folder='linked-priority', workspace=str(workspace),
                    projects={'selected': dict(ai='XX_AI', entry='XX_ENTRY', oracleId='selected_oracle')})
        with patch.object(storage, 'LINKS', [link]):
            project_file = storage.project_file('selected')
            project_file.parent.mkdir(parents=True)
            project_file.write_text(json.dumps(self.project), 'utf-8')
            cache = project_file.parent / 'rooms/rendered'
            shutil.copytree(fixture.local / 'world/xx-rooms', cache)
            target = storage.target_mod('selected')
            shutil.copytree(fixture.local / 'world/xx', target / 'world/xx')
            installed = storage.installed_mod('selected')
            installed.mkdir(parents=True)
            before = self.snapshot(cache)
            original = project_file.read_bytes()
            server.sync_linked_rooms(self.project, 'XX_AI', 'XX_ENTRY')
            for filename, content in self.room_files.items():
                for destination in (target, installed):
                    self.assert_copied_settings(filename, (destination / 'world/xx-rooms' / filename).read_bytes())
            self.assertEqual(self.snapshot(cache), before)
            self.assertEqual(project_file.read_bytes(), original)

    def test_installed_geometry_with_project_settings_uses_same_preview_export_template(self):
        fixture = self.fixture
        cache = fixture.project_file.parent / 'rooms/rendered'
        shutil.copytree(fixture.local / 'world/xx-rooms', cache)
        shutil.copytree(fixture.local / 'world/xx-rooms', fixture.installed / 'world/xx-rooms')
        shutil.copytree(fixture.local / 'world/xx', fixture.installed / 'world/xx')
        project_region = fixture.project_file.parent / 'rooms/regions/XX'
        project_region.mkdir(parents=True)
        properties = b'Palette: 9401\nRoom Setting Templates: Custom\nOrigin: project-settings\n'
        template = b'Palette: 9401\nTemplateOrigin: project-settings\n'
        (project_region / 'properties.txt').write_bytes(properties)
        (project_region / 'xx_settingstemplate_custom.txt').write_bytes(template)
        (fixture.installed / 'world/xx/properties.txt').write_bytes(b'Palette: 9402\nRoom Setting Templates: Custom\nOrigin: installed-geometry\n')
        (fixture.installed / 'world/xx/xx_settingstemplate_custom.txt').write_bytes(b'Palette: 9402\nTemplateOrigin: installed-geometry\n')
        fixture.palette(fixture.project_file.parent / 'rooms/palettes/palette9401.png', (33, 66, 99))
        fixture.palette(fixture.installed / 'palettes/palette9402.png', (210, 180, 150))
        for name in ('XX_AI', 'XX_ENTRY'):
            (cache / (name + '_settings.txt')).write_bytes(b'Template: XX_SettingsTemplate_Custom\nEffects: ZeroG-0.8-1-1,\n')
            (cache / (name + '_settings-White.txt')).write_bytes(b'Template: XX_SettingsTemplate_Custom\nEffects: ZeroG-0.8-1-1,\n')
            for path in (fixture.installed / 'world/xx-rooms').glob(name + '_[0-9]*.png'):
                Image.new('RGB', (16, 16), (1, 0, 0)).save(path)
        report = room_source_choices.preflight([self.project])
        choices = {}
        for row in report['rooms']:
            choices[row['projectId'] + '/' + row['room']] = dict(
                source=next(value['id'] for value in row['renderVersions'] if 'installed' in value['origins'] and value['complete']),
                settings=next(value['id'] for value in row['settingsVersions'] if 'project' in value['origins'] and value['complete']))
        before = self.snapshot(fixture.local), self.snapshot(fixture.installed), self.snapshot(fixture.project_file.parent)
        with room_source_choices.resolution_scope([self.project], dict(snapshotToken=report['snapshotToken'], choices=choices)):
            source = room_bindings.source_for(self.project, 'ai')
            self.assertEqual(source, fixture.installed / 'world/xx-rooms/XX_AI')
            self.assertEqual(room_controls.effective_palette_settings(self.project, source)['palette'], 9401)
            preview = room_preview.preview('XX_AI', 'selected')
            exported = fixture.unpack(fixture.payload())
        with Image.open(io.BytesIO(base64.b64decode(preview['image'].split(',', 1)[1]))) as image:
            self.assertEqual(image.getpixel((0, 0)), (33, 66, 99, 255))
        self.assertEqual(exported['regions/XX/properties.txt'], properties)
        self.assertEqual(exported['regions/XX/xx_settingstemplate_custom.txt'], template)
        self.assertEqual(exported['palettes/palette9401.png'], (fixture.project_file.parent / 'rooms/palettes/palette9401.png').read_bytes())
        self.assertEqual((self.snapshot(fixture.local), self.snapshot(fixture.installed), self.snapshot(fixture.project_file.parent)), before)

    def test_explicit_palette_choice_overrides_same_number_owned_palette_in_preview(self):
        fixture = self.fixture
        other = fixture.external / 'palettes/palette9100.png'
        fixture.palette(other, (4, 80, 120))
        for name in ('XX_AI', 'XX_ENTRY'):
            (fixture.local / 'world/xx-rooms' / (name + '_settings.txt')).write_bytes(b'Template: NONE\nPalette: 9100\n')
        before = self.snapshot(fixture.local), self.snapshot(fixture.external), fixture.project_file.read_bytes()
        with patch.object(room_bindings, 'enabled_asset_roots', return_value=[fixture.local, fixture.external]):
            report = room_source_choices.preflight([self.project])
            asset = next(row for row in report['assets'] if row['relative'] == 'palettes/palette9100.png')
            selected = next(value['id'] for value in asset['versions'] if value['origin'] == 'enabled')
            payload = dict(snapshotToken=report['snapshotToken'], assetChoices={asset['key']: selected})
            with room_source_choices.resolution_scope([self.project], payload):
                self.assertEqual(room_source_choices.selected_asset('selected', 'palettes/palette9100.png'), other)
                preview = room_preview.preview('XX_AI', 'selected')
                exported = fixture.unpack(fixture.payload())
        with Image.open(io.BytesIO(base64.b64decode(preview['image'].split(',', 1)[1]))) as image:
            self.assertEqual(image.getpixel((0, 0)), (4, 80, 120, 255))
        self.assertEqual(exported['palettes/palette9100.png'], other.read_bytes())
        self.assertEqual((self.snapshot(fixture.local), self.snapshot(fixture.external), fixture.project_file.read_bytes()), before)

    def test_standalone_content_keeps_native_settings_with_explicit_stub_dll(self):
        fixture = self.fixture
        request = dict(id='test.external-priority', name='External room priority', authors='Test', description='', version='0.1.0',
                       projects=['selected'], dialogue=False, pearls=False, broadcasts=False, workPearls=False, projections=False)
        def compile_stub(stage, sources, meta, projects):
            suffix = hashlib.sha256(meta['id'].encode()).hexdigest()[:12]
            directory = stage / 'plugins'
            directory.mkdir()
            (directory / ('IteratorContent_' + suffix + '.dll')).write_bytes(b'MZ isolated test fixture, not a compiled DLL')
            return suffix
        before = self.snapshot(fixture.local)
        authored = storage.project_file('selected').read_bytes()
        provider = fixture.root / 'regionkit-fixture'
        provider.mkdir()
        (provider / 'modinfo.json').write_text(json.dumps(dict(id='regionkit', name='RegionKit', requirements=[])), 'utf-8')
        with patch.object(room_bindings, 'enabled_asset_roots', return_value=[fixture.local, provider]), \
             room_source_choices.resolution_scope([self.project]), patch.object(standalone, 'compile_runtime', side_effect=compile_stub):
            result = standalone.build(request, server, save_preferences=False)
        with zipfile.ZipFile(storage.EXPORTS / Path(result['url']).name) as archive:
            prefix = request['id'] + '/'
            registry = json.loads(archive.read(prefix + 'moreiterators/registry.json'))
            self.assertEqual(len(registry), 1)
            runtime = json.loads(archive.read(prefix + registry[0]['design']))
            self.assert_modes(runtime, dict.fromkeys(room_controls.MODES, 'room'))
            suffix = hashlib.sha256(request['id'].encode()).hexdigest()[:12]
            self.assertEqual(archive.read(prefix + 'plugins/IteratorContent_' + suffix + '.dll'), b'MZ isolated test fixture, not a compiled DLL')
            for filename, content in self.room_files.items():
                self.assert_copied_settings(filename, archive.read(prefix + 'world/xx-rooms/' + filename))
            self.assertEqual(archive.read(prefix + 'world/xx/properties.txt'), self.properties)
            self.assertEqual(archive.read(prefix + 'world/xx/xx_settingstemplate_custom.txt'), self.template)
            for index in (9100, 9101, 9102, 9103):
                self.assertIn(prefix + 'palettes/palette' + str(index) + '.png', archive.namelist())
            self.assertIn(prefix + 'decals/priority-decal.png', archive.namelist())
        self.assertEqual(storage.project_file('selected').read_bytes(), authored)
        self.assertEqual(self.snapshot(fixture.local), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
