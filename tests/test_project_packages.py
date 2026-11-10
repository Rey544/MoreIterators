import copy
import io
import json
import os
from pathlib import Path
import stat
import shutil
import sys
import tempfile
import threading
import types
import unittest
import zipfile
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import project_packages as packages
import room_bindings
import room_editor
import room_migration
import storage
import project_worlds
import project_lifecycle
import project_purge
import room_cleanup
import room_source_choices


class ProjectPackageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / 'game';self.game.mkdir();(self.game / 'RainWorld.exe').touch()
        self.local = self.root / 'data/local-mod'
        self.installed = self.game / 'RainWorld_Data/StreamingAssets/mods/more_iterators_local'
        self.external = self.root / 'enabled-map'
        self.catalogue = dict(source='live', fresh=True, complete=True, generation='fixture', regions=[], reservedRooms=[], reservedRegions=[])
        for context in (
            patch.object(storage, 'DATA', self.root / 'data'),
            patch.object(storage, 'PROJECTS', self.root / 'data/projects'),
            patch.object(storage, 'EXPORTS', self.root / 'data/exports'),
            patch.object(storage, 'RUNTIME', self.root / 'data/runtime'),
            patch.object(storage, 'GAME', self.game),
            patch.object(storage, 'LINKS', []),
            patch.object(storage, 'settings', {}),
            patch.object(room_bindings, 'catalog', side_effect=lambda: copy.deepcopy(self.catalogue)),
            patch.object(room_bindings, '_asset_roots', side_effect=lambda: [self.local, self.installed, self.external]),
            patch.object(room_bindings, 'resolve_room_source', side_effect=lambda name: self.external / 'world/yy-rooms' / name),
        ):
            context.start();self.addCleanup(context.stop)
        self.project = dict(schema='moreiterators.project.v1', projectId='selected', name='房间分享',
                            design={}, textures={}, dialogue={'first': [{'text': 'keep authored dialogue'}]},
                            roomBinding=dict(region='XX', ai='XX_AI', entry='XX_ENTRY', oracleId='selected_oracle', entryMode='copy', aiNode=1, entryNode=0))
        self.server = types.SimpleNamespace(LOCK=threading.RLock(), validate=self.validate, atomic=room_bindings._atomic)
        self.project_file = storage.project_file('selected');self.project_file.parent.mkdir(parents=True)
        self.project_file.write_text(json.dumps(self.project), 'utf-8')
        self.render(self.local / 'world/xx-rooms/XX_AI', 'XX_AI', 2)
        self.render(self.local / 'world/xx-rooms/XX_ENTRY', 'XX_ENTRY', 1)
        folder = self.local / 'world/xx';folder.mkdir(parents=True)
        (folder / 'world_xx.txt').write_text('ROOMS\nXX_AI : DISCONNECTED, XX_ENTRY\nXX_ENTRY : XX_AI, DISCONNECTED : SHELTER\nEND ROOMS\n', 'utf-8')
        (folder / 'properties.txt').write_text('Palette: 9100\nClouds: 0.4\n', 'utf-8')
        (folder / 'displayname.txt').write_text('Custom region\n', 'utf-8')
        (folder / 'map_xx.txt').write_text('XX_AI: 1><2\nXX_ENTRY: 3><4\nXX_PRIVATE: 5><6\n', 'utf-8')
        self.palette(self.local / 'palettes/palette9100.png', 'red')

    def validate(self, value):
        if value.get('schema') != 'moreiterators.project.v1':raise ValueError('schema')
        storage.valid_id(value.get('projectId'))
        if not isinstance(value.get('name'), str):raise ValueError('name')
        return copy.deepcopy(value)

    def palette(self, path, color):
        path.parent.mkdir(parents=True, exist_ok=True);Image.new('RGB', (32, 16), color).save(path)

    def render(self, base, name, cameras=1, color='white'):
        base.parent.mkdir(parents=True, exist_ok=True)
        text = name + '\n48*36|-1|0\n\n' + '|'.join('0,0' for _ in range(cameras)) + '\n\n\n\n\n\n20|3|15|0,1,0,0,1,|0,1,0,0,1,|1,1,0,0,1,|\n'
        base.with_suffix('.txt').write_text(text, 'utf-8')
        Path(str(base) + '_settings.txt').write_text('Template: NONE\nPalette: 9100\nEffects: ZeroG-0.25-1-1,\n', 'utf-8')
        for i in range(1, cameras + 1):Image.new('RGB', (16, 16), color).save(Path(str(base) + '_' + str(i) + '.png'))
        return base

    def payload(self, extras=None):
        result = packages.export_package('selected', extras or [], self.server)
        return (storage.EXPORTS / result['url'].split('/')[-1]).read_bytes()

    def target(self):
        
        target = self.root / 'receiver'
        for name, path in (('DATA', target / 'data'), ('PROJECTS', target / 'data/projects'),
                           ('EXPORTS', target / 'data/exports'), ('RUNTIME', target / 'data/runtime')):
            context = patch.object(storage, name, path)
            context.start();self.addCleanup(context.stop)
        self.local = storage.DATA / 'local-mod'
        return target

    def unpack(self, payload):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:return {name: archive.read(name) for name in archive.namelist()}

    def archive(self, files):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, value in files.items():archive.writestr(name, value)
        return buffer.getvalue()

    def test_roundtrip_preserves_room_source_settings_cameras_palette_and_plan(self):
        source = self.project_file.parent / 'rooms/XX_AI.txt';source.parent.mkdir()
        source.write_text('[[[authored geometry]]]', 'utf-8')
        Image.new('RGB', (8, 8), 'black').save(source.with_suffix('.png'))
        cache = self.project_file.parent / 'rooms/rendered/XX_AI'
        self.render(cache, 'XX_AI', 2)
        payload = self.payload();files = self.unpack(payload)
        self.assertEqual(files['rooms/XX_AI/source/XX_AI.txt'], source.read_bytes())
        self.assertEqual(files['regions/XX/map_xx.txt'], b'XX_AI: 1><2\nXX_ENTRY: 3><4\n')
        self.target();summary = packages.inspect_import(payload, self.server)
        self.assertFalse(summary['collision']);self.assertEqual(summary['missingSources'], ['XX_ENTRY'])
        result = packages.import_package(payload, self.server)
        self.assertTrue(result['ok']);self.assertTrue(result['requiresApply'])
        root = storage.project_file('selected').parent
        for relative in ('XX_AI.txt', 'XX_AI_settings.txt', 'XX_AI_1.png', 'XX_AI_2.png', 'XX_ENTRY.txt'):
            name = 'XX_ENTRY' if relative.startswith('XX_ENTRY') else 'XX_AI'
            self.assertEqual((root / 'rooms/rendered' / relative).read_bytes(), files['rooms/' + name + '/rendered/' + relative])
        self.assertEqual((root / 'rooms/XX_AI.txt').read_bytes(), files['rooms/XX_AI/source/XX_AI.txt'])
        self.assertEqual(packages.palette_source('selected', 9100).read_bytes(), files['palettes/palette9100.png'])
        self.assertEqual(packages.region_file('selected', 'XX', 'properties.txt').read_bytes(), files['regions/XX/properties.txt'])
        room_editor.ensure_synced('selected', 'XX_AI')
        self.assertEqual(result['project']['dialogue'], self.project['dialogue'])
        self.assertTrue((root / 'room-binding-plan.json').is_file())
        
        b = result['project']['roomBinding']
        record = dict(projectId='selected', ownerMod='moreiterators.local', roomBinding=b,
                      ai=b['ai'], entry=b['entry'], oracleId=b['oracleId'])
        worlds = room_bindings.compile_worlds([record])
        self.assertIn('XX_AI : DISCONNECTED, XX_ENTRY', worlds['world/xx/world_xx.txt'])
        self.assertFalse(storage.RUNTIME.exists());self.assertFalse(self.installed.exists())

    def test_collision_never_overwrites_without_confirmation(self):
        payload = self.payload();before = self.project_file.read_bytes()
        result = packages.import_package(payload, self.server)
        self.assertFalse(result['ok']);self.assertTrue(result['collision'])
        self.assertEqual(self.project_file.read_bytes(), before)
        self.assertFalse((self.project_file.parent / 'room-package.json').exists())

    def test_latest_render_is_selected_as_one_set_but_installed_settings_win(self):
        cache = self.project_file.parent / 'rooms/rendered/XX_AI';self.render(cache, 'XX_AI', 2, 'red')
        current = self.installed / 'world/xx-rooms/XX_AI';self.render(current, 'XX_AI', 2, 'blue')
        for file in (self.local / 'world/xx-rooms').iterdir():os.utime(file, (1000, 1000))
        for file in cache.parent.iterdir():os.utime(file, (1000, 1000))
        for file in current.parent.iterdir():os.utime(file, (2000, 2000))
        settings = Path(str(current) + '_settings.txt');settings.write_text('Template: NONE\nPalette: 9100\nEffects: ZeroG-0.61-1-1,\n', 'utf-8')
        self.palette(self.installed / 'palettes/palette9100.png', 'red')
        files = self.unpack(self.payload())
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_1.png'], Path(str(current) + '_1.png').read_bytes())
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_2.png'], Path(str(current) + '_2.png').read_bytes())
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_settings.txt'], settings.read_bytes())
        manifest = json.loads(files['manifest.json'])
        self.assertEqual(manifest['rooms'][0]['sourceOrigin'], 'installed')
        self.assertEqual(manifest['rooms'][0]['settingsOrigin'], 'installed')

    def test_latest_cached_settings_survive_newer_installed_geometry(self):
        cached = self.render(self.project_file.parent / 'rooms/rendered/XX_AI', 'XX_AI', 2, 'red')
        installed = self.render(self.installed / 'world/xx-rooms/XX_AI', 'XX_AI', 2, 'blue')
        self.palette(self.installed / 'palettes/palette9100.png', 'red')
        for folder, modified in ((self.local / 'world/xx-rooms', 1000), (cached.parent, 1000), (installed.parent, 2000)):
            for file in folder.iterdir():os.utime(file, (modified, modified))
        settings = Path(str(cached) + '_settings.txt')
        settings.write_text('Template: NONE\nPalette: 9100\nEffectColorA: 9\nEffectColorB: 10\nFadePalette: 9100, 0.2, 0.8\nEffects: ZeroG-0.61-1-1,\n', 'utf-8')
        os.utime(settings, (3000, 3000))
        
        os.utime(installed.with_suffix('.txt'), (4000, 4000))
        files = self.unpack(self.payload())
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_1.png'], Path(str(installed) + '_1.png').read_bytes())
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_settings.txt'], settings.read_bytes())
        manifest = json.loads(files['manifest.json'])
        self.assertEqual(manifest['rooms'][0]['sourceOrigin'], 'installed')
        self.assertEqual(manifest['rooms'][0]['settingsOrigin'], 'project')

    def test_external_room_settings_ignore_unregistered_project_cache(self):
        source = self.render(self.external / 'world/yy-rooms/YY_ONE', 'YY_ONE')
        cached = self.render(self.project_file.parent / 'rooms/rendered/YY_ONE', 'YY_ONE')
        os.utime(Path(str(cached) + '_settings.txt'), (2000000000, 2000000000))
        self.assertEqual(packages.selected_room_settings(self.project, 'YY_ONE', source), Path(str(source) + '_settings.txt'))

    def test_missing_camera_or_settings_blocks_export_without_default_fallback(self):
        for suffix in ('_2.png', '_settings.txt'):
            with self.subTest(suffix=suffix):
                file = self.local / ('world/xx-rooms/XX_AI' + suffix);data = file.read_bytes();file.unlink()
                with self.assertRaisesRegex(ValueError, '缺少房间文件'):self.payload()
                file.write_bytes(data)

    def test_missing_authored_room_never_uses_default_chamber(self):
        (self.local / 'world/xx-rooms/XX_AI.txt').unlink()
        with self.assertRaisesRegex(ValueError, '不会使用默认模板'):self.payload()

    def test_pending_rained_changes_block_export(self):
        source = self.project_file.parent / 'rooms/XX_AI.txt';source.parent.mkdir()
        source.write_text('[[[new unsynced work]]]', 'utf-8')
        with self.assertRaisesRegex(ValueError, '尚未同步'):self.payload()

    def test_only_explicit_extra_room_is_included_without_other_project_content(self):
        self.render(self.external / 'world/yy-rooms/YY_ONE', 'YY_ONE')
        self.render(self.external / 'world/yy-rooms/YY_TWO', 'YY_TWO')
        self.palette(self.external / 'palettes/palette9100.png', 'red')
        self.catalogue['regions'] = [dict(name='YY', rooms=[dict(name=name, region='YY', connections=['DISCONNECTED', 'DISCONNECTED'], conditional=False,
                                           geometryPath=str(self.external / 'world/yy-rooms' / (name + '.txt'))) for name in ('YY_ONE', 'YY_TWO')])]
        (self.project_file.parent / 'history').mkdir();(self.project_file.parent / 'history/private.json').write_text('secret')
        (self.project_file.parent / 'diagnostics.log').write_text('secret')
        files = self.unpack(self.payload(['YY_ONE']))
        self.assertTrue(any('/YY_ONE/' in name for name in files))
        self.assertFalse(any('YY_TWO' in name or 'history' in name or 'log' in name for name in files))
        self.target();packages.import_package(self.archive(files), self.server)
        self.assertEqual(packages.rendered_source('selected', 'YY_ONE').name, 'YY_ONE')

    def test_import_rejects_path_traversal_duplicate_names_symlinks_and_code(self):
        files = self.unpack(self.payload());self.target()
        for name in ('../escape.txt', 'C:/escape.txt', 'rooms\\escape.txt', 'plugin.dll', 'evil.py'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                packages.inspect_import(self.archive(dict(files, **{name: b'not allowed'})), self.server)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            for name, value in files.items():archive.writestr(name, value)
            archive.writestr('PROJECT.JSON', files['project.json'])
        with self.assertRaisesRegex(ValueError, '重复文件'):packages.inspect_import(buffer.getvalue(), self.server)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            for name, value in files.items():archive.writestr(name, value)
            entry = zipfile.ZipInfo('link.txt');entry.create_system = 3;entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(entry, '../elsewhere')
        with self.assertRaisesRegex(ValueError, '链接'):packages.inspect_import(buffer.getvalue(), self.server)
        self.assertFalse(storage.PROJECTS.exists())

    def test_hash_and_missing_camera_validation_happens_before_writes(self):
        files = self.unpack(self.payload());self.target()
        changed = dict(files);changed['rooms/XX_AI/rendered/XX_AI_settings.txt'] = b'Palette: 9100\n'
        with self.assertRaisesRegex(ValueError, '校验失败'):packages.import_package(self.archive(changed), self.server)
        del files['rooms/XX_AI/rendered/XX_AI_2.png']
        with self.assertRaisesRegex(ValueError, '缺少相机'):packages.import_package(self.archive(files), self.server)
        self.assertFalse(storage.PROJECTS.exists())

    def test_compressed_and_expanded_limits_are_separate(self):
        payload = self.payload()
        with patch.object(packages, 'MAX_COMPRESSED', len(payload) - 1), self.assertRaisesRegex(ValueError, '压缩体积'):packages.inspect_import(payload, self.server)
        with patch.object(packages, 'MAX_UNCOMPRESSED', 100), self.assertRaisesRegex(ValueError, '解压后体积'):packages.inspect_import(payload, self.server)

    def test_transaction_failure_restores_existing_project_and_room_bytes(self):
        payload = self.payload();self.target()
        packages.import_package(payload, self.server)
        base = storage.project_file('selected').parent
        before = {path.relative_to(base).as_posix(): path.read_bytes() for path in base.rglob('*') if path.is_file()}
        original = room_migration.Files.json
        def fail(transaction, file, value):
            if Path(file).name == 'room-package.json':raise OSError('simulated write failure')
            return original(transaction, file, value)
        with patch.object(room_migration.Files, 'json', fail), self.assertRaisesRegex(OSError, 'simulated'):
            packages.import_package(payload, self.server, replace=True)
        after = {path.relative_to(base).as_posix(): path.read_bytes() for path in base.rglob('*') if path.is_file()}
        self.assertEqual(after, before)

    def test_failed_connection_plan_rolls_back_new_import(self):
        payload = self.payload();self.target()
        with patch.object(room_bindings, 'plan', side_effect=ValueError('connection rejected')), \
             self.assertRaisesRegex(ValueError, 'connection rejected'):
            packages.import_package(payload, self.server)
        self.assertFalse(storage.project_file('selected').exists())
        self.assertFalse(any(path.is_file() for path in storage.PROJECTS.rglob('*')))

    def test_imported_extra_can_deploy_with_world_registration_and_authored_settings(self):
        extra = self.external / 'world/yy-rooms/YY_ONE';self.render(extra, 'YY_ONE', color='green')
        self.palette(self.external / 'palettes/palette9100.png', 'red')
        self.catalogue['regions'] = [dict(name='YY', rooms=[dict(name='YY_ONE', region='YY', connections=['DISCONNECTED', 'DISCONNECTED'], conditional=False, geometryPath=str(extra.with_suffix('.txt')))])]
        payload = self.payload(['YY_ONE']);self.target()
        
        self.catalogue['regions'] = []
        packages.import_package(payload, self.server)
        project = storage.load_project('selected')
        prepared = packages.before_deploy(project, self.server)
        self.assertIn('world/yy-rooms/YY_ONE_1.png', prepared['files'])
        self.assertIn('YY_ONE : DISCONNECTED, DISCONNECTED', prepared['worldFiles']['world/yy/world_yy.txt'])
        self.assertIn('[ADD]YY', prepared['worldFiles']['modify/world/regions.txt'])
        self.assertEqual(prepared['worldFiles']['world/xx/properties.txt'], 'Palette: 9100\nClouds: 0.4\n')
        result = packages.write_deploy_assets(prepared)
        self.assertIn('world/yy-rooms/YY_ONE_1.png', result['files'])
        self.assertEqual((self.local / 'world/yy-rooms/YY_ONE_1.png').read_bytes(), Path(str(extra) + '_1.png').read_bytes())
        self.assertIn('ZeroG-0.25', (self.local / 'world/xx-rooms/XX_AI_settings.txt').read_text())
        self.assertTrue((self.local / '.mi-project-package-assets.json').is_file())
        self.assertFalse(self.installed.exists())

    def test_external_extra_conflict_blocks_apply_without_writing(self):
        extra = self.external / 'world/yy-rooms/YY_ONE';self.render(extra, 'YY_ONE')
        self.palette(self.external / 'palettes/palette9100.png', 'red')
        self.catalogue['regions'] = [dict(name='YY', rooms=[dict(name='YY_ONE', region='YY', connections=['DISCONNECTED', 'DISCONNECTED'], conditional=False, geometryPath=str(extra.with_suffix('.txt')))])]
        payload = self.payload(['YY_ONE']);self.target();packages.import_package(payload, self.server)
        with self.assertRaisesRegex(ValueError, '已启用内容重名'):packages.before_deploy(storage.load_project('selected'), self.server)
        self.assertFalse((self.local / 'world/yy-rooms').exists())
        self.assertFalse((self.local / '.mi-project-package-assets.json').exists())

    def test_import_cannot_claim_an_enabled_external_chamber(self):
        payload = self.payload();self.target()
        external = self.external / 'world/xx-rooms/XX_AI';self.render(external, 'XX_AI')
        self.catalogue['regions'] = [dict(name='XX', rooms=[dict(name='XX_AI', region='XX', connections=['DISCONNECTED', 'XX_ENTRY'], conditional=False, geometryPath=str(external.with_suffix('.txt')))])]
        with self.assertRaisesRegex(ValueError, '已启用内容重名'):packages.import_package(payload, self.server)
        self.assertFalse(storage.project_file('selected').exists())

    def test_replace_prunes_only_files_from_prior_manifest(self):
        payload = self.payload();self.target();packages.import_package(payload, self.server)
        root = storage.project_file('selected').parent
        unrelated = root / 'notes.txt';unrelated.write_text('keep')
        files = self.unpack(payload)
        geometry = files['rooms/XX_AI/rendered/XX_AI.txt'].replace(b'0,0|0,0', b'0,0')
        files['rooms/XX_AI/rendered/XX_AI.txt'] = geometry
        del files['rooms/XX_AI/rendered/XX_AI_2.png']
        manifest = json.loads(files['manifest.json']);manifest['files'] = packages._records({name: content for name, content in files.items() if name != 'manifest.json'})
        files['manifest.json'] = packages._json(manifest)
        packages.import_package(self.archive(files), self.server, replace=True)
        self.assertFalse((root / 'rooms/rendered/XX_AI_2.png').exists())
        self.assertEqual(unrelated.read_text(), 'keep')

    def deployed_extra(self):
        extra = self.external / 'world/yy-rooms/YY_ONE';self.render(extra, 'YY_ONE')
        self.palette(self.external / 'palettes/palette9100.png', 'red')
        self.catalogue['regions'] = [dict(name='YY', rooms=[dict(name='YY_ONE', region='YY', connections=['DISCONNECTED', 'DISCONNECTED'], conditional=False, geometryPath=str(extra.with_suffix('.txt')))])]
        payload = self.payload(['YY_ONE']);self.target();self.catalogue['regions'] = []
        project = packages.import_package(payload, self.server)['project']
        prepared = packages.before_deploy(project, self.server);packages.write_deploy_assets(prepared)
        for relative, text in prepared['worldFiles'].items():
            path = self.local / relative;path.parent.mkdir(parents=True, exist_ok=True);path.write_text(text, 'utf-8')
        (self.local / project_worlds.MANIFEST).write_text(json.dumps(dict(schema='moreiterators.room-bindings.v1', files=sorted(prepared['worldFiles']))), 'utf-8')
        binding = room_bindings.binding(project)
        record = storage.registry_record(project, binding['ai'], binding['entry'], binding['oracleId'])
        registry = storage.RUNTIME / 'creator/registry.json';registry.parent.mkdir(parents=True)
        registry.write_text(json.dumps([record]), 'utf-8')
        return project, record

    def test_recoverable_delete_and_restore_include_extra_and_unique_palette(self):
        self.deployed_extra()
        extra = self.local / 'world/yy-rooms/YY_ONE_1.png';palette = self.local / 'palettes/palette9100.png'
        original = extra.read_bytes()
        with patch.object(room_cleanup, '_running_game', return_value=False):
            deleted = project_lifecycle.delete(dict(projectId='selected'), self.server)
            self.assertFalse(extra.exists());self.assertFalse(palette.exists())
            self.assertNotIn('selected', packages.output_manifest(self.local)['projects'])
            restored = project_lifecycle.restore(deleted['token'], self.server)
        self.assertEqual(restored['project']['projectId'], 'selected')
        self.assertEqual(extra.read_bytes(), original);self.assertTrue(palette.exists())
        self.assertIn('selected', packages.output_manifest(self.local)['projects'])
        self.assertIn('YY_ONE', (self.local / 'world/yy/world_yy.txt').read_text())

    def test_permanent_delete_removes_extra_outputs_and_package_ownership(self):
        self.deployed_extra()
        unrelated = self.local / 'palettes/palette9999.png';self.palette(unrelated, 'blue')
        with patch.object(room_cleanup, '_running_game', return_value=False):
            planned = project_purge.plan(dict(source=dict(projectId='selected')), self.server)
            self.assertFalse(planned.get('conflicts'))
            result = project_purge.apply(dict(planToken=planned['planToken']), self.server)
        self.assertTrue(result['ok'])
        self.assertFalse((self.local / 'world/yy-rooms/YY_ONE_1.png').exists())
        self.assertFalse((self.local / 'palettes/palette9100.png').exists())
        self.assertTrue(unrelated.exists())
        self.assertNotIn('selected', packages.output_manifest(self.local)['projects'])

    def test_shared_palette_and_other_project_room_survive_ownership_removal(self):
        project, record = self.deployed_extra()
        marker = packages.output_manifest(self.local)
        marker['projects']['other'] = ['palettes/palette9100.png', 'world/zz-rooms/ZZ_KEEP_1.png']
        (self.local / packages.OUTPUT_MANIFEST).write_text(json.dumps(marker), 'utf-8')
        other_room = self.local / 'world/zz-rooms/ZZ_KEEP_1.png';self.palette(other_room, 'green')
        files = project_worlds.owned_files('selected', project, [record], [record])
        names = {file.relative_to(self.local).as_posix() for file, item in files if item['kind'] == 'local-room'}
        self.assertNotIn('palettes/palette9100.png', names)
        self.assertNotIn('world/zz-rooms/ZZ_KEEP_1.png', names)
        self.assertIn('world/yy-rooms/YY_ONE_1.png', names)

    def test_unsupported_template_blocks_export_without_modifying_settings(self):
        file = self.local / 'world/xx-rooms/XX_AI_settings.txt'
        text = 'Template: xx_settingsTemplate_custom\nPalette: 9100\n';file.write_text(text, 'utf-8')
        before = file.read_bytes()
        with self.assertRaisesRegex(ValueError, '模板依赖'):self.payload()
        self.assertEqual(file.read_bytes(), before)

    def test_reapply_reduced_package_removes_installed_old_extra_only(self):
        self.deployed_extra();shutil.copytree(self.local, self.installed)
        preserved = self.installed / 'world/zz-rooms/ZZ_OTHER_1.png';self.palette(preserved, 'green')
        payload = self.payload([])
        packages.import_package(payload, self.server, replace=True)
        prepared = packages.before_deploy(storage.load_project('selected'), self.server)
        result = packages.write_deploy_assets(prepared)
        self.assertIn('world/yy-rooms/YY_ONE_1.png', result['installedRemoved'])
        self.assertFalse((self.installed / 'world/yy-rooms/YY_ONE_1.png').exists())
        self.assertFalse((self.local / 'world/yy-rooms/YY_ONE_1.png').exists())
        self.assertTrue(preserved.exists())

    def test_preexisting_identical_unowned_palette_is_not_claimed_or_deleted(self):
        payload = self.payload();self.target();packages.import_package(payload, self.server)
        palette = self.local / 'palettes/palette9100.png';self.palette(palette, 'red')
        project = storage.load_project('selected');prepared = packages.before_deploy(project, self.server)
        self.assertIn('palettes/palette9100.png', prepared['borrowed'])
        packages.write_deploy_assets(prepared)
        self.assertNotIn('palettes/palette9100.png', packages.deployed_paths('selected'))
        binding = room_bindings.binding(project)
        record = storage.registry_record(project, binding['ai'], binding['entry'], binding['oracleId'])
        files = project_worlds.owned_files('selected', project, [record], [record])
        self.assertNotIn(palette, [file for file, _ in files])

    def test_later_world_settings_and_connections_are_not_replayed_from_old_import(self):
        project, record = self.deployed_extra()
        world = self.local / 'world/xx/world_xx.txt'
        world.write_text('ROOMS\nXX_AI : YY_ONE, XX_ENTRY\nXX_ENTRY : XX_AI, DISCONNECTED\nEND ROOMS\n', 'utf-8')
        properties = self.local / 'world/xx/properties.txt';properties.write_text('Palette: 9100\nClouds: 0.9\n', 'utf-8')
        mapping = self.local / 'world/xx/map_xx.txt';mapping.write_text('XX_AI: 50><60\nXX_ENTRY: 70><80\nUNSELECTED: 1><2\n', 'utf-8')
        settings = self.local / 'world/xx-rooms/XX_AI_settings.txt';settings.write_text('Template: NONE\nPalette: 9100\nEffects: ZeroG-0.7-1-1,\n', 'utf-8')
        before = packages.load_metadata('selected')['importedAtNs']
        prepared = packages.before_deploy(project, self.server)
        packages.write_deploy_assets(prepared)
        self.assertEqual(packages.load_metadata('selected')['importedAtNs'], before)
        after = room_bindings.compile_worlds([record])
        self.assertIn('XX_AI : YY_ONE, XX_ENTRY', after['world/xx/world_xx.txt'])
        self.assertIn('Clouds: 0.9', after['world/xx/properties.txt'])
        self.assertIn('XX_AI: 50><60', after['world/xx/map_xx.txt'])
        self.assertNotIn('UNSELECTED', after['world/xx/map_xx.txt'])
        self.assertIn(b'ZeroG-0.7', prepared['files']['world/xx-rooms/XX_AI_settings.txt'])

    def test_actual_server_deploy_uses_package_rooms_and_installs_extra(self):
        import server
        payload = self.payload();self.target();project = packages.import_package(payload, self.server)['project']
        with patch.object(server, 'save', side_effect=copy.deepcopy), \
             patch.object(server, 'compile_design', return_value=dict(projectId='selected')), \
             patch.object(server, 'MOD', self.local), \
             patch.object(server, 'DESIGNS', storage.RUNTIME), \
             patch.object(server, 'ASSETS', self.game / 'RainWorld_Data/StreamingAssets'), \
             patch.object(server, 'installation_paths', return_value={}), \
             patch.object(server.audio_assets, 'copy_referenced'), \
             patch.object(server.local_content, 'status', return_value={}), \
             patch.object(server.waiting_room, 'prepare', side_effect=AssertionError('must not replace imported room')), \
             patch.object(server, 'copy_room', side_effect=AssertionError('must not copy older default room')):
            result = server.deploy(project)
        self.assertTrue(result['ok'])
        self.assertIn('Palette: 9100', (self.installed / 'world/xx-rooms/XX_AI_settings.txt').read_text())
        self.assertIn('ZeroG-0.25', (self.installed / 'world/xx-rooms/XX_ENTRY_settings.txt').read_text())
        self.assertIn('XX_AI : DISCONNECTED, XX_ENTRY', (self.installed / 'world/xx/world_xx.txt').read_text())
        self.assertTrue((self.installed / 'world/xx-rooms/XX_AI_2.png').is_file())

    def test_renamed_binding_cannot_replay_old_room_package(self):
        payload = self.payload();self.target();project = packages.import_package(payload, self.server)['project']
        project['roomBinding']['ai'] = 'XX_RENAMED'
        storage.project_file('selected').write_text(json.dumps(project), 'utf-8')
        with self.assertRaisesRegex(ValueError, '清单尚未迁移'):packages.before_deploy(project, self.server)
        self.assertFalse((self.local / 'world/xx-rooms').exists())

    def variant_fixture(self):
        self.project['editor']={'externalRoomTools':True}
        self.project['design'].update(roomPaletteMode='room',roomGravityMode='room',entryGravityMode='room')
        self.project_file.write_text(json.dumps(self.project),'utf-8')
        variant=self.local/'world/xx-rooms/XX_AI_settings-White.txt'
        data='~'.join(['0']*11+['variant-decal'])
        variant.write_text('Template: NONE\nMorePalette0: 9200\nPlacedObjects: CustomDecal><0><0><'+data+'\n','utf-8')
        properties=variant.with_name('XX_AI_properties.txt');properties.write_text('SomeRoomProperty: 1\n','utf-8')
        self.palette(self.local/'palettes/palette9200.png','blue')
        self.palette(self.local/'decals/variant-decal.png','green')
        return variant,properties

    def test_selected_variants_roundtrip_and_deploy_keep_dependencies(self):
        variant,properties=self.variant_fixture();content=variant.read_bytes()
        with patch.object(room_bindings,'enabled_asset_roots',return_value=[]):
            with room_source_choices.resolution_scope([self.project]):payload=self.payload()
        files=self.unpack(payload)
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_settings-White.txt'],content)
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_properties.txt'],properties.read_bytes())
        self.assertIn('palettes/palette9200.png',files)
        self.assertIn('assets/decals/variant-decal.png',files)
        self.target();project=packages.import_package(payload,self.server)['project']
        local=storage.project_file('selected').parent/'rooms/rendered/XX_AI_settings-White.txt'
        self.assertEqual(local.read_bytes(),content)
        again=self.unpack(self.payload())
        self.assertEqual(again['rooms/XX_AI/rendered/XX_AI_settings-White.txt'],content)
        prepared=packages.before_deploy(project,self.server)
        self.assertEqual(prepared['files']['world/xx-rooms/XX_AI_settings-White.txt'],content)
        self.assertIn('decals/variant-decal.png',prepared['files'])
        packages.write_deploy_assets(prepared)
        self.assertEqual((self.local/'world/xx-rooms/XX_AI_settings-White.txt').read_bytes(),content)
        self.assertEqual(self.unpack(self.payload())['rooms/XX_AI/rendered/XX_AI_settings-White.txt'],content)

    def test_unregistered_variants_export_and_local_copy_use_selected_settings_folder(self):
        import standalone,room_controls,server
        variant,properties=self.variant_fixture()
        self.project['editor']={};self.project_file.write_text(json.dumps(self.project),'utf-8')
        self.assertIsNone(packages.load_metadata('selected'))
        source=self.local/'world/xx-rooms/XX_AI'
        files=self.unpack(self.payload())
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_settings-White.txt'],variant.read_bytes())
        self.assertEqual(files['rooms/XX_AI/rendered/XX_AI_properties.txt'],properties.read_bytes())
        self.assertIn('palettes/palette9200.png',files)
        self.assertIn('assets/decals/variant-decal.png',files)
        stage=self.root/'native-standalone';directory=stage/'world/zz-rooms'
        settings=standalone.copy_selected_room(self.project,source,'XX_AI','ZZ_NEW',directory,self.server)
        standalone.copy_selected_room_palettes(self.project,settings,'XX_AI','ZZ_NEW',directory,stage)
        self.assertEqual((directory/'ZZ_NEW_settings-White.txt').read_bytes(),variant.read_bytes())
        self.assertTrue((stage/'decals/variant-decal.png').is_file())
        local_copy=self.root/'local-copy'
        room_controls.copy_owned_room(self.project,source,local_copy,'XX_AI','ai',server,replace=True)
        self.assertEqual((local_copy/variant.name).read_bytes(),variant.read_bytes())
        self.assertEqual((local_copy/properties.name).read_bytes(),properties.read_bytes())

    def test_variant_collection_does_not_mix_settings_origins_or_room_prefixes(self):
        variant,properties=self.variant_fixture()
        selected=self.project_file.parent/'rooms/rendered/XX_AI_settings.txt'
        selected.parent.mkdir(parents=True);selected.write_text('Template: NONE\nPalette: 9100\n','utf-8')
        white=selected.with_name('XX_AI_settings-white.txt');white.write_text('Palette: 9100\n','utf-8')
        for filename in ('XX_AIX_settings-red.txt','XX_AI_settings-red.txt.bak','XX_AI_other.txt'):
            selected.with_name(filename).write_text('ignored','utf-8')
        result=packages.room_settings_files(self.project,'XX_AI',selected)
        self.assertEqual(result,{'XX_AI_settings.txt':selected,'XX_AI_settings-white.txt':white})
        self.assertNotIn(properties.name,result)
        external=self.external/'world/yy-rooms/YY_ONE_settings.txt';external.parent.mkdir(parents=True)
        external.write_text('Template: NONE\n','utf-8')
        lower=external.with_name('yy_one_settings-red.txt');lower.write_text('Palette: 9100\n','utf-8')
        self.assertEqual(packages.room_settings_files(self.project,'YY_ONE',external),{'YY_ONE_settings.txt':external,'YY_ONE_settings-red.txt':lower})

    def test_missing_registered_variant_cannot_fall_back_to_another_version(self):
        variant,_=self.variant_fixture();payload=self.payload();self.target()
        project=packages.import_package(payload,self.server)['project']
        cache=storage.project_file('selected').parent/'rooms/rendered'
        missing=cache/variant.name;missing.unlink()
        other=self.local/'world/xx-rooms';other.mkdir(parents=True)
        (other/variant.name).write_text('Template: NONE\nPalette: 9100\n','utf-8')
        with self.assertRaisesRegex(ValueError,'缺少房间设置变体'):
            packages.room_settings_files(project,'XX_AI',cache/'XX_AI_settings.txt')

    def test_standalone_copy_maps_variants_and_carries_their_dependencies(self):
        import standalone
        variant,properties=self.variant_fixture()
        source=self.local/'world/xx-rooms/XX_AI'
        stage=self.root/'standalone-stage';directory=stage/'world/zz-rooms'
        with patch.object(room_bindings,'enabled_asset_roots',return_value=[]):
            with room_source_choices.resolution_scope([self.project]):
                settings=standalone.copy_selected_room(self.project,source,'XX_AI','ZZ_NEW',directory,self.server)
                standalone.copy_selected_room_palettes(self.project,settings,'XX_AI','ZZ_NEW',directory,stage)
        self.assertEqual((directory/'ZZ_NEW_settings-White.txt').read_bytes(),variant.read_bytes())
        self.assertEqual((directory/'ZZ_NEW_properties.txt').read_bytes(),properties.read_bytes())
        self.assertEqual((directory/'ZZ_NEW.txt').read_text('utf-8').splitlines()[0],'ZZ_NEW')
        self.assertTrue((stage/'decals/variant-decal.png').is_file())
        self.assertIn('world/zz-rooms/ZZ_NEW_settings-White.txt',standalone._room_files(stage,'ZZ_NEW'))
        self.assertEqual(standalone.room_palette_requirements(stage,['ZZ_NEW']),{'regionkit':'RegionKit'})

    def test_standalone_independent_settings_do_not_require_geometry_origin_settings(self):
        import standalone
        self.project['editor']={'externalRoomTools':True}
        self.project['design'].update(roomPaletteMode='room',roomGravityMode='room',entryGravityMode='room')
        source=self.local/'world/xx-rooms/XX_AI'
        settings=self.installed/'world/xx-rooms/XX_AI_settings.txt';settings.parent.mkdir(parents=True)
        settings.write_text('Template: NONE\nPalette: 9100\n','utf-8')
        source.with_name('XX_AI_settings.txt').unlink()
        stage=self.root/'separate-settings'
        with patch.object(room_bindings,'enabled_asset_roots',return_value=[]):
            with room_source_choices.resolution_scope([self.project]):
                chosen=standalone.copy_selected_room(self.project,source,'XX_AI','ZZ_NEW',stage,self.server)
                self.assertEqual(chosen,settings)
        self.assertTrue((stage/'ZZ_NEW_2.png').is_file())

    def test_room_reference_files_keep_selected_variants_and_assets(self):
        import server
        variant,properties=self.variant_fixture()
        with patch.object(room_bindings,'enabled_asset_roots',return_value=[]):
            with room_source_choices.resolution_scope([self.project]):files=dict(server.room_reference_files('selected'))
        self.assertEqual(files['XX_AI_settings-White.txt'],variant.read_bytes())
        self.assertEqual(files['XX_AI_properties.txt'],properties.read_bytes())
        self.assertIn('palettes/palette9200.png',files)
        self.assertIn('decals/variant-decal.png',files)

    def test_room_reference_files_without_conflict_keep_variants_and_assets(self):
        import server
        variant,properties=self.variant_fixture()
        self.project['editor']={}
        self.project_file.write_text(json.dumps(self.project),'utf-8')
        original=self.project_file.read_bytes()
        with patch.object(room_bindings,'enabled_asset_roots',return_value=[]):
            self.assertIsNone(room_source_choices.selected_version('selected','XX_AI'))
            files=dict(server.room_reference_files('selected'))
        self.assertEqual(files['XX_AI_settings-White.txt'],variant.read_bytes())
        self.assertEqual(files['XX_AI_properties.txt'],properties.read_bytes())
        self.assertEqual(files['palettes/palette9100.png'],(self.local/'palettes/palette9100.png').read_bytes())
        self.assertEqual(files['palettes/palette9200.png'],(self.local/'palettes/palette9200.png').read_bytes())
        self.assertEqual(files['decals/variant-decal.png'],(self.local/'decals/variant-decal.png').read_bytes())
        self.assertEqual(self.project_file.read_bytes(),original)


if __name__ == '__main__':
    unittest.main()
