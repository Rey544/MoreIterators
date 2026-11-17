import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import room_bindings as rooms
import storage


class RoomBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.p = dict(projectId='one', name='One')
        self.projects = [self.p]
        for name, value in [('DATA', self.root), ('RUNTIME', self.root / 'runtime'), ('GAME', self.root / 'game'), ('PROJECTS', self.root / 'projects'), ('LINKS', [])]:
            mocking = patch.object(storage, name, value)
            mocking.start()
            self.addCleanup(mocking.stop)
        storage.GAME.mkdir(parents=True);(storage.GAME/'RainWorld.exe').touch()
        for target, value in [('_projects', lambda: self.projects), ('_asset_roots', lambda: [self.root / 'assets']), ('_options_paths', lambda game: [self.root / 'options'])]:
            mocking = patch.object(rooms, target, value)
            mocking.start()
            self.addCleanup(mocking.stop)
        self.base = self.root / 'template'
        self.geometry_file(self.base, (0, 0, 1))
        mocking = patch.object(rooms, 'source_for', return_value=self.base)
        mocking.start()
        self.addCleanup(mocking.stop)
        self.cat = dict(source='live', fresh=True, complete=True, generation='abc', regions=[], reservedRooms=[], reservedRegions=[])
        self.b = dict(region='XX', ai='XX_AI', entry='XX_A01', oracleId='my_oracle', entryMode='copy', aiNode=1, entryNode=0)

    def geometry_file(self, base, types):
        base.parent.mkdir(parents=True, exist_ok=True)
        base.with_suffix('.txt').write_text('ROOM\n48*36|-1|0\n\n0,0\n\n\n\n\n\n20|' + str(len(types)) + '|15|' + '|'.join(str(t) + ',1,0,0,1,' for t in types) + '|\n', 'utf-8')

    def existing(self, connections=None):
        row = dict(name='XX_A01', region='XX', connections=connections or ['DISCONNECTED', 'XX_B01'], exitCount=2, verified=True, conditional=False, oracle=False, tags='SHELTER')
        self.cat['regions'] = [dict(name='XX', rooms=[row])]
        self.b['entryMode'] = 'existing'
        return row

    def record(self, binding=None, pid='one'):
        b = binding or self.b
        return dict(projectId=pid, ownerMod='moreiterators.local', ai=b['ai'], entry=b['entry'], oracleId=b['oracleId'], roomBinding=b)

    def test_default_preserves_previous_hashed_names(self):
        value = rooms.binding(self.p)
        self.assertEqual(value['ai'], 'TEST_7692C3AD35_AI')
        self.assertEqual(value['oracleId'], 'test_7692c3ad35')

    def test_copy_plan_uses_real_geometry_exit_count_and_zero_based_nodes(self):
        result = rooms.plan(self.p, self.b, self.cat)
        text = result['worldFiles']['world/xx/world_xx.txt']
        self.assertIn('XX_AI : DISCONNECTED, XX_A01', text)
        self.assertIn('XX_A01 : XX_AI, DISCONNECTED', text)
        self.assertEqual([v['kind'] for v in result['roomCopies']], ['ai', 'entry'])
        self.assertTrue(result['requiresRestart'])

    def test_rename_preview_reports_existing_ai_destination(self):
        self.p['roomBinding'] = dict(self.b, entry='XX_OLD')
        value = rooms.plan(self.p, self.b, self.cat)
        self.assertIn(dict(room='XX_AI', node=1, fromRoom='XX_OLD', to='XX_A01'), value['connectionChanges'])
        self.assertIn(dict(room='XX_A01', node=0, fromRoom='DISCONNECTED', to='XX_AI'), value['connectionChanges'])

    def test_moving_copied_nodes_lists_old_and_new_slots(self):
        self.p['roomBinding'] = dict(self.b, aiNode=0, entryNode=1)
        value = rooms.plan(self.p, self.b, self.cat)
        changes = value['connectionChanges']
        self.assertIn(dict(room='XX_AI', node=0, fromRoom='XX_A01', to='DISCONNECTED'), changes)
        self.assertIn(dict(room='XX_A01', node=1, fromRoom='XX_AI', to='DISCONNECTED'), changes)
        self.assertIn('XX_AI : DISCONNECTED, XX_A01', next(iter(value['worldFiles'].values())))

    def test_switching_external_room_previews_previous_unbinding(self):
        self.existing()
        self.p['roomBinding'] = dict(self.b, entry='XX_OLD', entryNode=1)
        value = rooms.plan(self.p, self.b, self.cat)
        self.assertIn(dict(room='XX_OLD', node=1, fromRoom='XX_AI', to='DISCONNECTED'), value['connectionChanges'])
        self.assertIn(dict(room='XX_A01', node=0, fromRoom='DISCONNECTED', to='XX_AI'), value['connectionChanges'])

    def test_same_existing_slot_reports_previous_actual_connection(self):
        self.existing(['XX_OLD_AI', 'DISCONNECTED'])
        self.p['roomBinding'] = dict(self.b, ai='XX_OLD_AI')
        value = rooms.plan(self.p, self.b, self.cat)
        self.assertIn(dict(room='XX_A01', node=0, fromRoom='XX_OLD_AI', to='XX_AI'), value['connectionChanges'])

    def test_uppercase_room_ids_but_oracle_id_unchanged(self):
        self.b.update(region='xy', ai='xy_ai', entry='xy_a01')
        result = rooms.validate(self.p, self.b, self.cat)
        self.assertEqual(result['ai'], 'XY_AI')
        self.assertEqual(result['oracleId'], 'my_oracle')

    def test_invalid_ids_paths_or_nodes_rejected(self):
        for change in [dict(region='../X'), dict(ai='YY_AI'), dict(ai='XX_A01'), dict(oracleId='../abc'), dict(aiNode=True), dict(aiNode=2), dict(entryNode=-1), dict(replaceConnection={})]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                rooms.validate(self.p, dict(self.b, **change), self.cat)

    def test_fixed_ownership_is_readonly(self):
        with patch.object(rooms, '_fixed', return_value=dict(ai='EOE_AI', entry='EOE_A01', oracleId='eoe')):
            self.assertFalse(rooms.describe(self.p)['editable'])
            with self.assertRaises(ValueError):
                rooms.validate(self.p, self.b, self.cat)

    def test_other_project_names_and_oracle_id_cannot_be_reused(self):
        self.projects.append(dict(projectId='two', roomBinding=dict(self.b, region='YY', ai='YY_AI', entry='YY_A01')))
        with self.assertRaisesRegex(ValueError, '内部编号'):
            rooms.validate(self.p, self.b, self.cat)
        self.projects[1]['roomBinding'].update(oracleId='different', ai='XX_AI')
        with self.assertRaises(ValueError):
            rooms.validate(self.p, self.b, self.cat)

    def test_no_second_oracle_in_custom_region(self):
        self.projects.append(dict(projectId='two', roomBinding=dict(self.b, ai='XX_SECOND', entry='XX_B01', oracleId='other')))
        with self.assertRaises(rooms.RoomBindingError) as caught:
            rooms.validate(self.p, self.b, self.cat)
        self.assertEqual(caught.exception.code, 'rooms.error.regionProject')
        self.assertEqual(caught.exception.params, {'region': 'XX', 'name': 'two'})

    def test_disk_collision_rejected_even_when_not_in_live_catalog(self):
        self.cat['reservedRooms'] = ['XX_AI']
        with self.assertRaises(rooms.RoomBindingError) as caught:
            rooms.validate(self.p, self.b, self.cat)
        self.assertEqual(caught.exception.code, 'rooms.error.roomTaken')
        self.assertEqual(caught.exception.params, {'room': 'XX_AI'})

    def test_external_entry_cannot_be_another_creator_project_room(self):
        self.existing()
        self.projects.append(dict(projectId='two', roomBinding=dict(self.b, ai='XY_OTHER', oracleId='other')))
        with self.assertRaises(rooms.RoomBindingError) as caught:
            rooms.validate(self.p, self.b, self.cat)
        self.assertEqual(caught.exception.code, 'rooms.error.roomTaken')
        self.assertEqual(caught.exception.params, {'room': 'XX_A01'})

    def test_native_and_active_mod_oracle_ids_are_reserved(self):
        self.b['oracleId'] = 'lttm_spear'
        with self.assertRaises(ValueError):
            rooms.validate(self.p, self.b, self.cat)
        self.b['oracleId'] = 'foreign_internal'
        self.cat['oracles'] = [dict(projectId='foreign-project', oracleId='FOREIGN_INTERNAL')]
        with self.assertRaises(ValueError):
            rooms.validate(self.p, self.b, self.cat)

    def test_existing_region_copy_rejected(self):
        self.cat['reservedRegions'] = ['XX']
        with self.assertRaises(rooms.RoomBindingError) as caught:
            rooms.validate(self.p, self.b, self.cat)
        self.assertEqual(caught.exception.code, 'rooms.error.regionTaken')
        self.assertEqual(caught.exception.params, {'region': 'XX'})

    def test_existing_entry_requires_fresh_complete_live_and_verified_geometry(self):
        row = self.existing()
        for field, value in [('fresh', False), ('complete', False), ('source', 'offline')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                rooms.validate(self.p, self.b, dict(self.cat, **{field: value}))
        for field, value in [('verified', False), ('conditional', True), ('oracle', True), ('exitCount', 3)]:
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                rooms.validate(self.p, self.b, self.cat)
            row = self.existing()

    def test_occupied_exit_never_implicitly_disconnected(self):
        self.existing(['XX_B01', 'DISCONNECTED'])
        with self.assertRaisesRegex(ValueError, '已连接到 XX_B01'):
            rooms.plan(self.p, self.b, self.cat)

    def test_existing_entry_plan_is_overlay_preserves_other_links_and_tags(self):
        self.existing()
        value = rooms.plan(self.p, self.b, self.cat)
        text = value['worldFiles']['modify/world/xx/world_xx.txt']
        self.assertTrue(text.startswith('[FINDLINESTART]XX_A01 :\n[REPLACE]'))
        self.assertIn('XX_A01 : XX_AI, XX_B01 : SHELTER', text)
        self.assertNotIn('XX_A01 :', text.split('[MERGE]\n')[1])
        self.assertEqual([v['kind'] for v in value['roomCopies']], ['ai'])
        self.assertEqual(value['connectionChanges'][1]['fromRoom'], 'DISCONNECTED')

    def test_move_existing_connection_clears_previous_owned_node(self):
        self.existing(['XX_OLD_AI', 'DISCONNECTED'])
        self.p['roomBinding'] = dict(self.b, ai='XX_OLD_AI', entryNode=0)
        self.b['entryNode'] = 1
        value = rooms.plan(self.p, self.b, self.cat)
        self.assertIn('XX_A01 : DISCONNECTED, XX_AI', next(iter(value['worldFiles'].values())))
        self.assertIn(dict(room='XX_A01', node=0, fromRoom='XX_OLD_AI', to='DISCONNECTED'), value['connectionChanges'])

    def test_plan_roundtrip_and_managed_world_cleanup(self):
        first = rooms.plan(self.p, self.b, self.cat)
        rooms.remember_plan('one', first)
        result = rooms.write_worlds([self.record()])
        root = self.root / 'local-mod'
        self.assertIn('world/xx/world_xx.txt', result['files'])
        foreign = root / 'world/foreign/keep.txt'
        foreign.parent.mkdir(parents=True)
        foreign.write_text('keep', 'utf-8')
        self.b.update(region='YY', ai='YY_AI', entry='YY_A01')
        second = rooms.plan(self.p, self.b, self.cat)
        rooms.remember_plan('one', second)
        result = rooms.write_worlds([self.record()])
        self.assertIn('world/xx/world_xx.txt', result['removed'])
        self.assertFalse((root / 'world/xx/world_xx.txt').exists())
        self.assertEqual(foreign.read_text('utf-8'), 'keep')

    def test_unmanaged_world_file_never_overwritten(self):
        target = self.root / 'local-mod/world/xx/world_xx.txt'
        target.parent.mkdir(parents=True)
        target.write_text('external', 'utf-8')
        value = rooms.plan(self.p, self.b, self.cat)
        with self.assertRaisesRegex(ValueError, '不能覆盖'):
            rooms.write_worlds([self.record()], {'one': value})
        self.assertEqual(target.read_text('utf-8'), 'external')

    def test_manifest_traversal_does_not_delete_outside_output(self):
        root = self.root / 'local-mod'
        root.mkdir()
        outside = self.root / 'precious'
        outside.write_text('keep', 'utf-8')
        (root / '.mi-room-bindings.json').write_text(json.dumps(dict(files=['../precious'])), 'utf-8')
        with self.assertRaises(ValueError):
            rooms.write_worlds([])
        self.assertEqual(outside.read_text('utf-8'), 'keep')

    def test_write_failure_rolls_back_previous_world_files(self):
        first = rooms.plan(self.p, self.b, self.cat)
        rooms.write_worlds([self.record()], {'one': first})
        root = self.root / 'local-mod'
        before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        self.b.update(aiNode=0)
        second = rooms.plan(self.p, self.b, self.cat)
        with patch.object(rooms, '_atomic', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                rooms.write_worlds([self.record()], {'one': second})
        after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_conditional_world_names_still_listed_but_cannot_be_edited(self):
        text = 'CONDITIONAL LINKS\nWhite : XX_A01 : XX_B01\nEND CONDITIONAL LINKS\nROOMS\n(White)XX_A01 : DISCONNECTED\nXX_B01 : XX_A01\nEND ROOMS\n'
        result = rooms.parse_world(text, 'XX')
        self.assertEqual([v['name'] for v in result], ['XX_A01', 'XX_B01'])
        self.assertTrue(all(v['conditional'] for v in result))

    def test_bad_or_unbaked_geometry_rejected(self):
        self.geometry_file(self.base, (0, 1, 0))
        with self.assertRaises(ValueError):
            rooms.geometry(self.base.with_suffix('.txt'))
        self.base.with_suffix('.txt').write_text('unbaked', 'utf-8')
        with self.assertRaises(ValueError):
            rooms.geometry(self.base.with_suffix('.txt'))

    def test_syntax_validation_has_no_catalog_or_disk_dependency(self):
        with patch.object(rooms, 'catalog', side_effect=AssertionError('read')), patch.object(rooms, 'geometry', side_effect=AssertionError('read')):
            self.assertEqual(rooms.normalize(self.b), self.b)

    def test_generation_zero_requires_complete_metadata_matching_actual_exits(self):
        fields = '0,1,0,0,1,' + ','.join(['-1 -1'] * 2) + ','
        lines = ['ROOM', '2*2|-1|0', '', '0,0', '', '', '', '', '', '0|2|1|' + fields + '|' + fields + '|', '', '1,4|1|1|1,4|']
        self.base.with_suffix('.txt').write_text('\n'.join(lines), 'utf-8')
        self.assertEqual(rooms.geometry(self.base.with_suffix('.txt'))['exitCount'], 2)
        lines[11] = '1,4|1|1|1|'
        self.base.with_suffix('.txt').write_text('\n'.join(lines), 'utf-8')
        with self.assertRaises(ValueError):
            rooms.geometry(self.base.with_suffix('.txt'))
        lines[11] = '1,4|1|1|1,4|'
        lines[9] = '0|2|1|0,1,0,0,1,|0,1,0,0,1,|'
        self.base.with_suffix('.txt').write_text('\n'.join(lines), 'utf-8')
        with self.assertRaises(ValueError):
            rooms.geometry(self.base.with_suffix('.txt'))

    def test_actual_demo_entry_generation_zero_is_readonly_valid_geometry(self):
        source = Path(__file__).resolve().parents[1] / 'data/local-mod/world/test-rooms/TEST_F9229C7FFD_ENTRY.txt'
        if not source.exists():
            self.skipTest('Local authored demo room is not present')
        before = source.read_bytes()
        self.assertEqual(rooms.geometry(source)['exitCount'], 2)
        self.assertEqual(source.read_bytes(), before)

    def test_repeat_compile_rechecks_changed_owned_geometry(self):
        value = rooms.plan(self.p, self.b, self.cat)
        self.geometry_file(self.base, (0, 0, 0))
        text = rooms.compile_worlds([self.record()], {'one': value})['world/xx/world_xx.txt']
        self.assertIn('XX_AI : DISCONNECTED, XX_A01, DISCONNECTED', text)
        self.geometry_file(self.base, (0,))
        with self.assertRaisesRegex(ValueError, '出口已改变'):
            rooms.compile_worlds([self.record()], {'one': value})

    def test_compile_worlds_is_readonly_and_preserves_explicit_entry_replacement(self):
        self.existing()
        value = rooms.plan(self.p, self.b, self.cat)
        files = rooms.compile_worlds([self.record()], {'one': value})
        self.assertFalse((self.root / 'local-mod').exists())
        text = files['modify/world/xx/world_xx.txt']
        self.assertIn('[REPLACE]XX_A01 : XX_AI, XX_B01 : SHELTER', text)
        self.assertEqual(len(rooms.parse_world(text, 'XX')), 1)

    def test_geometry_source_cannot_escape_game_or_impersonate_other_room(self):
        source = storage.GAME / 'RainWorld_Data/StreamingAssets/world/xx-rooms/xx_a01.txt'
        source.parent.mkdir(parents=True)
        source.write_text('actual game data', 'utf-8')
        row = dict(name='XX_A01', geometryPath=str(source))
        with patch.object(rooms, 'catalog', return_value=dict(regions=[dict(rooms=[row])])):
            self.assertEqual(rooms.resolve_room_source('XX_A01'), source.with_suffix(''))
            row['geometryPath'] = str(self.base.with_suffix('.txt'))
            with self.assertRaises(ValueError):
                rooms.resolve_room_source('XX_A01')

    def test_native_game_parser_accepts_exact_node_replacement(self):
        
        import os
        import subprocess
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        game = Path(os.environ['MI_TEST_NATIVE_GAME_ROOT']) if os.environ.get('MI_TEST_NATIVE_GAME_ROOT') else storage.locate_game()
        assembly = game / 'RainWorld_Data/Managed/Assembly-CSharp.dll'
        if not compiler.exists() or not assembly.exists():
            self.skipTest('Native Windows game parser unavailable')
        self.existing()
        overlay = self.root / 'overlay.txt'
        overlay.write_text(next(iter(rooms.plan(self.p, self.b, self.cat)['worldFiles'].values())), 'utf-8')
        source = self.root / 'NativeRoomParserCheck.cs'
        source.write_text(r'''
using System; using System.IO; using System.Reflection; using System.Collections;
class Program {
 static void Main(string[] args){
  string managed=Path.GetDirectoryName(args[0]);
  AppDomain.CurrentDomain.AssemblyResolve+=(s,e)=>{string p=Path.Combine(managed,new AssemblyName(e.Name).Name+".dll");return File.Exists(p)?Assembly.LoadFrom(p):null;};
  var asm=Assembly.LoadFrom(args[0]); var t=asm.GetType("ModManager+ModMerger+PendingApply",true);
  ConstructorInfo ctor=null;foreach(var c in t.GetConstructors())if(c.GetParameters().Length==4&&c.GetParameters()[3].ParameterType==typeof(string[]))ctor=c;
  object pending=ctor.Invoke(new object[]{null,"world_xx.txt",new string[0],File.ReadAllLines(args[1])});
  var replacements=(IList)t.GetField("replacements",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(pending);
  if(replacements.Count!=1)throw new Exception("Replacement not parsed");
  object op=replacements[0];Type o=op.GetType();
  if((string)o.GetField("findMatchStart").GetValue(op)!="XX_A01 :" || !(bool)o.GetField("findLine").GetValue(op))throw new Exception("Wrong match semantics");
  string replacement=(string)o.GetField("replaceWith").GetValue(op);
  string actual=(string)t.GetMethod("ApplyLineReplacement",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(pending,new object[]{"XX_A01 : DISCONNECTED, XX_B01 : SHELTER",replacement,o.GetField("replaceType").GetValue(op)});
  if(actual!="XX_A01 : XX_AI, XX_B01 : SHELTER")throw new Exception("Selected exit was moved");
  var merged=(IList)t.GetField("mergeLines").GetValue(pending);
  foreach(object line in merged)if(((string)line).StartsWith("XX_A01 :"))throw new Exception("Entry must not enter native connection merge");
  Console.WriteLine("Native room replacement parser passed");
 }
}
''', 'utf-8')
        executable = self.root / 'NativeRoomParserCheck.exe'
        built = subprocess.run([str(compiler), '/nologo', '/out:' + str(executable), str(source)], text=True, capture_output=True)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        result = subprocess.run([str(executable), str(assembly), str(overlay)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_catalog_distinguishes_stale_from_live(self):
        import datetime
        import os
        options = self.root / 'options'
        options.write_text('EnabledMods<optB><optA>', 'utf-8')
        os.utime(options, (0, 0))
        path = storage.RUNTIME / 'creator/room-catalog.json'
        path.parent.mkdir(parents=True)
        value = dict(schema=rooms.SCHEMA, activeMods=[], regions=[], capturedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(), generation='one', complete=True)
        with patch.object(rooms, 'offline_catalog', return_value=dict(regions=[], reservedRooms=[], reservedRegions=[])):
            path.write_text(json.dumps(value), 'utf-8')
            self.assertEqual(rooms.catalog()['source'], 'live')
            value['capturedAt'] = '2000-01-01T00:00:00+00:00'
            path.write_text(json.dumps(value), 'utf-8')
            self.assertEqual(rooms.catalog()['source'], 'stale')


if __name__ == '__main__':
    unittest.main()
