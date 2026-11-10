import concurrent.futures
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import room_source_choices as choices
import storage


class RoomSourceChoiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.local = self.root / 'local'
        self.installed = self.root / 'installed'
        self.project = dict(projectId='selected', editor={'externalRoomTools': True},
                            design=dict(roomPaletteMode='room',roomGravityMode='room',entryGravityMode='room'),
                            roomBinding=dict(region='XX', ai='XX_AI', entry='YY_EXISTING', oracleId='test', entryMode='existing', aiNode=1, entryNode=0))
        for context in (patch.object(storage, 'PROJECTS', self.root / 'projects'),
                        patch.object(storage, 'LINKS', []),
                        patch.object(storage, 'target_mod', return_value=self.local),
                        patch.object(storage, 'installed_mod', return_value=self.installed),
                        patch.object(choices.room_bindings, 'enabled_asset_roots', return_value=[])):
            context.start()
            self.addCleanup(context.stop)
        self.cache = storage.project_file('selected').parent / 'rooms/rendered/XX_AI'
        self.output = self.local / 'world/xx-rooms/XX_AI'
        self.live = self.installed / 'world/xx-rooms/XX_AI'
        self.render(self.cache)

    def render(self, base, name='XX_AI', cameras=2, color='white', settings='Palette: 9100\n'):
        base.parent.mkdir(parents=True, exist_ok=True)
        text = name + '\n48*36|-1|0\n\n' + '|'.join('0,0' for _ in range(cameras)) + '\n\n\n\n\n\n20|3|15|0,1,0,0,1,|0,1,0,0,1,|1,1,0,0,1,|\n'
        base.with_suffix('.txt').write_text(text, 'utf-8')
        base.with_name(name + '_settings.txt').write_text(settings, 'utf-8')
        for index in range(1, cameras + 1):
            Image.new('RGB', (8, 8), color).save(base.with_name(name + '_' + str(index) + '.png'))

    def source(self):
        path = self.cache.parent.parent / 'XX_AI.txt'
        path.write_text('[[[authored source]]]', 'utf-8')
        return path

    def report(self):
        return choices.preflight([self.project])

    def pick(self, report, origin='project', setting_origin=None):
        row = report['rooms'][0]
        source = next(value['id'] for value in row['renderVersions'] if origin in value['origins'] and value['complete'])
        setting = next(value['id'] for value in row['settingsVersions'] if (setting_origin or origin) in value['origins'] and value['complete'])
        return dict(snapshotToken=report['snapshotToken'], choices={'selected/XX_AI': dict(source=source, settings=setting)})

    def assertCode(self, code, call):
        with self.assertRaises(choices.RoomChoiceError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def enter(self, payload=None):
        with choices.resolution_scope([self.project], payload):
            return choices.selected_source('selected', 'XX_AI')

    def snapshot(self):
        return {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in self.root.rglob('*') if path.is_file()}

    def test_unflagged_projects_keep_old_behavior_without_scanning(self):
        self.project['editor']['externalRoomTools'] = False
        with patch.object(choices, '_candidate', side_effect=AssertionError('scanned')):
            report = self.report()
            self.assertEqual(report['rooms'], [])
            self.assertFalse(report['requiresChoices'])
            self.assertIsNone(self.enter())

    def test_single_complete_version_selects_without_payload_and_does_not_write(self):
        before = self.snapshot()
        self.assertEqual(self.enter(), self.cache)
        self.assertIsNone(choices.selected_source('selected', 'XX_AI'))
        self.assertEqual(self.snapshot(), before)

    def test_equal_bytes_deduplicate_across_three_origins(self):
        self.render(self.output)
        self.render(self.live)
        report = self.report()
        row = report['rooms'][0]
        self.assertFalse(report['requiresChoices'])
        self.assertEqual(len(row['renderVersions']), 1)
        self.assertEqual(set(row['renderVersions'][0]['origins']), {'project', 'local', 'installed'})
        self.assertEqual(len(row['settingsVersions']), 1)

    def test_whole_camera_set_conflicts_and_chooses_without_mixing(self):
        self.render(self.output, cameras=1, color='blue')
        report = self.report()
        self.assertTrue(report['requiresChoices'])
        self.assertCode('room_choices_required', self.enter)
        before = self.snapshot()
        with choices.resolution_scope([self.project], self.pick(report, 'project')):
            self.assertEqual(choices.selected_source('selected', 'XX_AI'), self.cache)
            self.assertEqual(choices.selected_version('selected', 'XX_AI')['cameraCount'], 2)
        self.assertEqual(self.snapshot(), before)

    def test_settings_choose_independently(self):
        self.render(self.output, settings='Palette: 9200\n')
        report = self.report()
        self.assertFalse(report['rooms'][0]['sourceConflict'])
        self.assertTrue(report['rooms'][0]['settingsConflict'])
        with choices.resolution_scope([self.project], self.pick(report, 'project', 'local')):
            self.assertEqual(choices.selected_settings('selected', 'XX_AI'), self.output.with_name('XX_AI_settings.txt'))

    def test_incomplete_version_cannot_be_selected(self):
        self.render(self.output, color='blue')
        self.output.with_name('XX_AI_2.png').unlink()
        report = self.report()
        bad = next(value for value in report['rooms'][0]['renderVersions'] if value['origin'] == 'local')
        self.assertFalse(bad['complete'])
        self.assertFalse(report['requiresChoices'])
        payload = self.pick(report)
        payload['choices']['selected/XX_AI']['source'] = bad['id']
        self.assertCode('room_choices_incomplete', lambda: self.enter(payload))

    def test_missing_all_complete_versions_blocks_export(self):
        self.cache.with_name('XX_AI_1.png').unlink()
        self.assertEqual(self.report()['issues'][0]['code'], 'room_choices_missing')
        self.assertCode('room_choices_missing', self.enter)

    def test_unbaked_geometry_is_not_selectable(self):
        path = self.cache.with_suffix('.txt')
        rows = path.read_text('utf-8').splitlines()
        rows[9] = '0'
        path.write_text('\n'.join(rows), 'utf-8')
        self.assertIn('invalid_geometry', self.report()['rooms'][0]['renderVersions'][0]['issues'])
        self.assertCode('room_choices_missing', self.enter)

    def test_corrupt_camera_and_settings_are_incomplete(self):
        self.cache.with_name('XX_AI_1.png').write_bytes(b'not png')
        self.cache.with_name('XX_AI_settings.txt').write_bytes(b'\x00')
        row = self.report()['rooms'][0]
        self.assertFalse(row['renderVersions'][0]['complete'])
        self.assertFalse(row['settingsVersions'][0]['complete'])

    def test_stale_bytes_rejected_even_when_mtime_is_restored(self):
        report = self.report()
        path = self.cache.with_name('XX_AI_settings.txt')
        stamp = path.stat()
        path.write_text('Palette: 9200\n', 'utf-8')
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertCode('room_choices_stale', lambda: self.enter(self.pick(report)))

    def test_changes_during_scope_rejected_on_exit_and_context_reset(self):
        def action():
            with choices.resolution_scope([self.project]):
                self.cache.with_name('XX_AI_2.png').write_bytes(b'changed')
        self.assertCode('room_choices_stale', action)
        self.assertIsNone(choices.selected_source('selected', 'XX_AI'))

    def test_scope_resets_after_export_failure(self):
        with self.assertRaisesRegex(RuntimeError, 'failed'):
            with choices.resolution_scope([self.project]):
                raise RuntimeError('failed')
        self.assertIsNone(choices.selected_settings('selected', 'XX_AI'))

    def test_scopes_are_nested_and_thread_local(self):
        self.render(self.output, color='blue')
        report = self.report()
        barrier = threading.Barrier(2)
        def worker(origin, expected):
            with choices.resolution_scope([self.project], self.pick(report, origin)):
                barrier.wait(timeout=5)
                self.assertEqual(choices.selected_source('selected', 'XX_AI'), expected)
                with choices.resolution_scope([]):
                    self.assertIsNone(choices.selected_source('selected', 'XX_AI'))
                self.assertEqual(choices.selected_source('selected', 'XX_AI'), expected)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [pool.submit(worker, 'project', self.cache), pool.submit(worker, 'local', self.output)]
            for task in tasks:
                task.result(timeout=10)

    def test_no_manifest_source_is_available_but_not_paired(self):
        self.source()
        version = self.report()['rooms'][0]['renderVersions'][0]
        self.assertTrue(version['sourceAvailable'])
        self.assertFalse(version['pairedSource'])

    def test_explicit_pairing_fingerprint_requires_exact_source_and_render(self):
        source = self.source()
        before = self.snapshot()
        certificate = choices.pairing_record('selected', 'XX_AI')
        self.assertEqual(self.snapshot(), before)
        path = self.cache.with_name('XX_AI.source.json')
        path.write_text(json.dumps(certificate), 'utf-8')
        self.assertTrue(self.report()['rooms'][0]['renderVersions'][0]['pairedSource'])
        source.write_text('[[[changed source]]]', 'utf-8')
        self.assertFalse(self.report()['rooms'][0]['renderVersions'][0]['pairedSource'])

    def test_import_manifest_pairs_only_exact_set_and_digests(self):
        source = self.source()
        files = [source, self.cache.with_suffix('.txt'), self.cache.with_name('XX_AI_1.png'), self.cache.with_name('XX_AI_2.png')]
        root = storage.project_file('selected').parent
        manifest = dict(schema=choices.LOCAL_SCHEMA, projectId='selected', rooms=[dict(name='XX_AI', sourceAvailable=True)],
                        files=[dict(path=path.relative_to(root).as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in files])
        path = root / 'room-package.json'
        path.write_text(json.dumps(manifest), 'utf-8')
        self.assertTrue(self.report()['rooms'][0]['renderVersions'][0]['pairedSource'])
        manifest['files'].pop()
        path.write_text(json.dumps(manifest), 'utf-8')
        self.assertFalse(self.report()['rooms'][0]['renderVersions'][0]['pairedSource'])

    def test_imported_extra_room_only_scanned_with_manifest_evidence(self):
        extra = self.cache.with_name('XX_EXTRA')
        self.render(extra, name='XX_EXTRA')
        report = choices.preflight([self.project], extraRooms=['XX_EXTRA', 'ZZ_FOREIGN'])
        self.assertEqual(len(report['rooms']), 1)
        manifest = dict(schema=choices.LOCAL_SCHEMA, projectId='selected', rooms=[dict(name='XX_EXTRA', sourceAvailable=False)], files=[])
        (storage.project_file('selected').parent / 'room-package.json').write_text(json.dumps(manifest), 'utf-8')
        report = choices.preflight([self.project], extraRooms=['XX_EXTRA', 'ZZ_FOREIGN'])
        self.assertEqual([row['room'] for row in report['rooms']], ['XX_AI', 'XX_EXTRA'])

    def test_unknown_choices_and_missing_tokens_are_rejected(self):
        report = self.report()
        payload = self.pick(report)
        payload.pop('snapshotToken')
        self.assertCode('room_choices_required', lambda: self.enter(payload))
        payload = self.pick(report)
        payload['choices']['selected/XX_AI']['source'] = 'render-unknown'
        self.assertCode('room_choices_invalid', lambda: self.enter(payload))
        self.assertCode('room_choices_invalid', lambda: self.enter({'paths': ['outside']}))

    def test_report_contains_no_absolute_paths_or_authored_source(self):
        self.source()
        data = json.dumps(self.report())
        self.assertNotIn(str(self.root), data)
        self.assertNotIn('authored source', data)
        self.assertNotIn('path', data.lower())

    def test_project_input_and_returned_metadata_are_not_mutated(self):
        before = copy.deepcopy(self.project)
        with choices.resolution_scope([self.project]):
            value = choices.selected_version('selected', 'XX_AI')
            value['pairedSource'] = True
            self.assertFalse(choices.selected_version('selected', 'XX_AI')['pairedSource'])
        self.assertEqual(self.project, before)

    def test_referenced_palette_conflict_can_choose_without_writing(self):
        for root, color in ((self.local, 'blue'), (self.installed, 'red')):
            path = root / 'palettes/palette9100.png'
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB', (8, 8), color).save(path)
        report = self.report()
        asset = report['assets'][0]
        self.assertTrue(asset['conflict'])
        self.assertTrue(report['requiresChoices'])
        self.assertCode('room_choices_required', lambda: self.enter(self.pick(report)))
        payload = self.pick(report)
        payload['assetChoices'] = {asset['key']: next(value['id'] for value in asset['versions'] if value['origin'] == 'installed')}
        before = self.snapshot()
        with choices.resolution_scope([self.project], payload):
            self.assertEqual(choices.selected_asset('selected', 'palettes/palette9100.png'), self.installed / 'palettes/palette9100.png')
        self.assertEqual(self.snapshot(), before)
        self.assertIsNone(choices.selected_asset('selected', 'palettes/palette9100.png'))

    def test_asset_scan_includes_settings_union_but_no_unreferenced_files(self):
        self.render(self.output, settings='Palette: 9200\n')
        root = self.local / 'palettes'
        root.mkdir(parents=True)
        for index in (9100, 9200, 9300):
            Image.new('RGB', (8, 8), 'blue').save(root / ('palette' + str(index) + '.png'))
        self.assertEqual({row['relative'] for row in self.report()['assets']}, {'palettes/palette9100.png', 'palettes/palette9200.png'})

    def test_asset_changes_stale_and_invalid_version_cannot_be_selected(self):
        path = self.local / 'palettes/palette9100.png'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'invalid png')
        report = self.report()
        asset = report['assets'][0]
        self.assertTrue(asset['missing'])
        payload = self.pick(report)
        payload['assetChoices'] = {asset['key']: asset['versions'][0]['id']}
        self.assertCode('room_choices_incomplete', lambda: self.enter(payload))
        Image.new('RGB', (8, 8), 'blue').save(path)
        self.assertCode('room_choices_stale', lambda: self.enter(payload))

    def test_referenced_decal_and_enabled_asset_candidates(self):
        data = '~'.join(['0'] * 11 + ['my-decal'])
        self.cache.with_name('XX_AI_settings.txt').write_text('PlacedObjects: CustomDecal><0><0><' + data + '\n', 'utf-8')
        path = self.root / 'enabled/decals/my-decal.png'
        path.parent.mkdir(parents=True)
        Image.new('RGB', (8, 8), 'blue').save(path)
        with patch.object(choices.room_bindings, 'enabled_asset_roots', return_value=[path.parent.parent]):
            report = self.report()
            self.assertEqual([row['relative'] for row in report['assets']], ['decals/my-decal.png'])
            self.assertEqual(report['assets'][0]['versions'][0]['origin'], 'enabled')
            with choices.resolution_scope([self.project]):
                self.assertEqual(choices.selected_asset('selected', 'decals/my-decal.png'), path)

    def test_same_asset_path_across_projects_is_one_choice(self):
        second = copy.deepcopy(self.project)
        second['projectId'] = 'second'
        second['roomBinding']['ai'] = 'XX_SECOND'
        second_cache = storage.project_file('second').parent / 'rooms/rendered/XX_SECOND'
        self.render(second_cache, name='XX_SECOND')
        for pid, color in (('selected', 'red'), ('second', 'blue')):
            path = storage.project_file(pid).parent / 'rooms/palettes/palette9100.png'
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB', (8, 8), color).save(path)
        report = choices.preflight([self.project, second])
        self.assertEqual(len(report['assets']), 1)
        asset = report['assets'][0]
        self.assertEqual(asset['key'], 'palettes/palette9100.png')
        self.assertEqual(asset['projectIds'], ['second', 'selected'])
        payload = dict(snapshotToken=report['snapshotToken'], assetChoices={asset['key']: asset['versions'][0]['id']})
        with choices.resolution_scope([self.project, second], payload):
            self.assertEqual(choices.selected_asset('selected', asset['relative']), choices.selected_asset('second', asset['relative']))

    def test_export_policies_change_only_an_export_copy(self):
        self.project['design'] = dict(roomPaletteMode='mi', roomGravityMode='mi', entryGravityMode='zero', roomGravity=0.8)
        original = copy.deepcopy(self.project)
        with choices.resolution_scope([self.project], {'snapshotToken':self.report()['snapshotToken'],'policies': {'selected': {'palette': 'room', 'gravity': {'XX_AI':'room','YY_EXISTING':'room'}}}}):
            exported = choices.export_project(self.project)
            self.assertEqual(exported['design']['roomPaletteMode'], 'room')
            self.assertEqual(exported['design']['roomGravityMode'], 'room')
            self.assertEqual(exported['design']['entryGravityMode'], 'room')
            self.assertEqual(exported['design']['roomGravity'], 0.8)
        self.assertEqual(choices.export_project(self.project), original)
        self.assertEqual(self.project, original)

    def test_export_policy_rejects_unknown_project_field_and_value(self):
        for policy in ({'unknown': {'palette': 'room'}}, {'selected': {'palette': 'wrong'}}, {'selected': {'unknown': 'room'}}):
            self.assertCode('room_choices_invalid', lambda: self.enter({'policies': policy}))
        self.project['editor']['externalRoomTools'] = False
        self.assertCode('room_choices_invalid', lambda: self.enter({'policies': {'selected': {'palette': 'room'}}}))

    def test_settings_variants_and_properties_are_selected_as_one_set(self):
        self.render(self.output)
        variant = self.output.with_name('XX_AI_settings-White.txt')
        variant.write_text('Palette: 9200\n', 'utf-8')
        self.output.with_name('XX_AI_properties.txt').write_text('SomeRoomProperty: 1\n', 'utf-8')
        report = self.report()
        settings = report['rooms'][0]['settingsVersions']
        selected = next(value for value in settings if value['origin'] == 'local')
        self.assertEqual(selected['variantCount'], 2)
        self.assertTrue(report['rooms'][0]['settingsConflict'])
        self.assertIn('palettes/palette9200.png', {row['relative'] for row in report['assets']})
        with choices.resolution_scope([self.project], self.pick(report, 'project', 'local')):
            files = choices.selected_settings_files('selected', 'XX_AI')
            self.assertEqual(set(files), {'XX_AI_settings.txt', 'XX_AI_settings-White.txt', 'XX_AI_properties.txt'})
            self.assertEqual(files['XX_AI_settings-White.txt'], variant)

    def test_variant_change_invalidates_snapshot(self):
        path = self.cache.with_name('XX_AI_settings-White.txt')
        path.write_text('Palette: 9100\n', 'utf-8')
        report = self.report()
        path.write_text('Palette: 9200\n', 'utf-8')
        self.assertCode('room_choices_stale', lambda: self.enter(self.pick(report)))

    def test_enabled_asset_versions_have_public_provider_names(self):
        enabled=self.root/'public-mod'
        path=enabled/'palettes/palette9100.png';path.parent.mkdir(parents=True)
        Image.new('RGB',(8,8),'blue').save(path)
        (enabled/'modinfo.json').write_text(json.dumps(dict(id='author.map',name='Author map')),'utf-8')
        with patch.object(choices.room_bindings,'enabled_asset_roots',return_value=[enabled]):
            version=self.report()['assets'][0]['versions'][0]
        self.assertEqual(version['providers'],[dict(id='author.map',name='Author map')])
        self.assertNotIn(str(enabled),json.dumps(version))

    def test_base_game_asset_origin_is_distinct(self):
        game=self.root/'game';assets=game/'RainWorld_Data/StreamingAssets'
        path=assets/'palettes/palette9100.png';path.parent.mkdir(parents=True)
        Image.new('RGB',(8,8),'blue').save(path)
        with patch.object(storage,'available_game_root',return_value=game),patch.object(choices.room_bindings,'enabled_asset_roots',return_value=[assets]):
            version=self.report()['assets'][0]['versions'][0]
        self.assertEqual(version['origin'],'game')
        self.assertEqual(version['providers'],[])

    def test_palette_control_conflict_requires_an_explicit_export_policy(self):
        self.project['design']['roomPaletteMode']='mi'
        report=self.report();conflict=report['parameterConflicts'][0]
        self.assertEqual((conflict['projectId'],conflict['room'],conflict['kind'],conflict['sourceMode'],conflict['certainty']),('selected','XX_AI','palette','mi','potential'))
        payload=self.pick(report)
        self.assertCode('room_choices_required',lambda:self.enter(payload))
        payload['policies']={'selected':{'palette':'project'}}
        self.assertEqual(self.enter(payload),self.cache)
        payload['policies']['selected']['palette']='room'
        before=copy.deepcopy(self.project)
        with choices.resolution_scope([self.project],payload):
            self.assertEqual(choices.export_project(self.project)['design']['roomPaletteMode'],'room')
        self.assertEqual(self.project,before)

    def test_only_the_selected_settings_version_requires_a_policy(self):
        self.project['design']['roomPaletteMode']='mi'
        self.render(self.output,settings='Template: NONE\n')
        report=self.report()
        conflict=report['parameterConflicts'][0]
        safe=next(value for value in report['rooms'][0]['settingsVersions'] if value['origin']=='local')
        self.assertNotIn(safe['id'],conflict['settingsVersionIds'])
        payload=self.pick(report,'project','local')
        self.assertEqual(self.enter(payload),self.output)

    def test_variant_gravity_and_region_template_inheritance_are_detected(self):
        self.project['design'].update(roomPaletteMode='mi',roomGravityMode='mi')
        self.cache.with_name('XX_AI_settings.txt').write_text('Template: XX_SettingsTemplate_Storm\n','utf-8')
        self.cache.with_name('XX_AI_settings-White.txt').write_text('Template: NONE\nEffects: BrokenZeroG-0.5-0-0,\n','utf-8')
        folder=self.local/'world/xx';folder.mkdir(parents=True)
        (folder/'xx_settingstemplate_storm.txt').write_text('Palette: 9100\n','utf-8')
        report=self.report()
        self.assertEqual({value['kind'] for value in report['parameterConflicts']},{'palette','gravity'})
        payload=self.pick(report);payload['policies']={'selected':{'palette':'room','gravity':'project'}}
        self.enter(payload)
        (folder/'xx_settingstemplate_storm.txt').write_text('Palette: 9200\n','utf-8')
        self.assertCode('room_choices_stale',lambda:self.enter(payload))

    def test_implicit_region_template_and_palette_are_detected(self):
        self.project['design'].update(roomPaletteMode='mi',roomGravityMode='mi')
        self.cache.with_name('XX_AI_settings.txt').write_text('Effects: Rain-0.2-0-0,\n','utf-8')
        folder=self.cache.parent.parent/'regions/XX';folder.mkdir(parents=True)
        (folder/'properties.txt').write_text('Palette: 9100\nRoom Setting Templates: Storm\n','utf-8')
        (folder/'xx_settingstemplate_storm.txt').write_text('Effects: ZeroG-1-0-0,\n','utf-8')
        self.assertEqual({value['kind'] for value in self.report()['parameterConflicts']},{'palette','gravity'})

    def test_entry_palette_and_unrelated_project_colors_do_not_conflict(self):
        self.project['design'].update(roomPaletteMode='mi',entryGravityMode='zero',roomWorkColor='#ff0000')
        self.cache.with_name('XX_AI_settings.txt').write_text('Template: NONE\n','utf-8')
        binding=self.project['roomBinding'];binding.update(entry='XX_ENTRY',entryMode='copy')
        self.render(self.cache.with_name('XX_ENTRY'),name='XX_ENTRY',settings='Palette: 9100\nEffects: ZeroG-1-0-0,\n')
        conflicts=self.report()['parameterConflicts']
        self.assertEqual([(value['room'],value['kind'],value['sourceMode']) for value in conflicts],[('XX_ENTRY','gravity','zero')])
        self.project['design']['entryGravityMode']='room'
        second=copy.deepcopy(self.project);second['projectId']='second';second['design']['roomWorkColor']='#00ff00'
        second['roomBinding'].update(ai='XX_SECOND',entryMode='existing')
        self.render(storage.project_file('second').parent/'rooms/rendered/XX_SECOND',name='XX_SECOND',settings='Template: NONE\n')
        self.assertEqual(choices.preflight([self.project,second])['parameterConflicts'],[])

    def test_saved_mode_changes_invalidate_the_parameter_snapshot(self):
        report=self.report()
        self.project['design']['roomPaletteMode']='mi'
        self.assertCode('room_choices_stale',lambda:self.enter(self.pick(report)))

    def test_gravity_policy_changes_only_the_named_room(self):
        self.project['design'].update(roomGravityMode='mi',entryGravityMode='zero')
        before=copy.deepcopy(self.project)
        with choices.resolution_scope([self.project],{'policies':{'selected':{'gravity':{'YY_EXISTING':'room'}}}}):
            exported=choices.export_project(self.project)
            self.assertEqual(exported['design']['roomGravityMode'],'mi')
            self.assertEqual(exported['design']['entryGravityMode'],'room')
        self.assertEqual(self.project,before)

    def test_legacy_gravity_policy_does_not_guess_between_two_rooms(self):
        self.project['roomBinding'].update(entry='XX_ENTRY',entryMode='copy')
        self.project['design'].update(roomGravityMode='mi',entryGravityMode='zero')
        for name in ('XX_AI','XX_ENTRY'):
            self.render(self.cache.with_name(name),name=name,settings='Template: NONE\nEffects: ZeroG-1-0-0,\n')
        report=self.report();payload={'snapshotToken':report['snapshotToken'],'policies':{'selected':{'gravity':'room'}}}
        self.assertCode('room_choices_required',lambda:self.enter(payload))
        payload['policies']['selected']['gravity']={'XX_AI':'project','XX_ENTRY':'room'}
        with choices.resolution_scope([self.project],payload):
            exported=choices.export_project(self.project)
            self.assertEqual(exported['design']['roomGravityMode'],'mi')
            self.assertEqual(exported['design']['entryGravityMode'],'room')

    def test_legacy_gravity_policy_accepts_one_unambiguous_room(self):
        self.project['design'].update(roomGravityMode='mi',entryGravityMode='zero')
        self.cache.with_name('XX_AI_settings.txt').write_text('Template: NONE\nEffects: ZeroG-1-0-0,\n','utf-8')
        payload={'snapshotToken':self.report()['snapshotToken'],'policies':{'selected':{'gravity':'room'}}}
        with choices.resolution_scope([self.project],payload):
            exported=choices.export_project(self.project)
            self.assertEqual(exported['design']['roomGravityMode'],'room')
            self.assertEqual(exported['design']['entryGravityMode'],'zero')


if __name__ == '__main__':
    unittest.main()
