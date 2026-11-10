from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import playable_world


class PlayableWorldTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.stage=Path(temporary.name)

    def world(self,rows,conditions='',region='ZX',tail=''):
        path=self.stage/'world'/region.lower()/('world_'+region.lower()+'.txt');path.parent.mkdir(parents=True,exist_ok=True)
        text='ROOMS\n'+rows+'\nEND ROOMS\n'
        if conditions:text+='CONDITIONAL LINKS\n'+conditions+'\nEND CONDITIONAL LINKS\n'
        path.write_text(text+tail,'utf-8');return path

    def validate(self,start='ZX_ENTRY',required=('ZX_AI',),regions=('ZX',)):
        return playable_world.validate(self.stage,regions,start,required)

    def test_simple_graph_preserves_world_bytes(self):
        file=self.world('ZX_ENTRY : ZX_AI : SHELTER\nZX_AI : ZX_ENTRY')
        before=file.read_bytes();rows=self.validate()
        self.assertEqual([row['name'] for row in rows],['ZX_ENTRY','ZX_AI'])
        self.assertEqual(file.read_bytes(),before)

    def test_white_conditional_disconnect_is_not_declared_reachable(self):
        self.world('ZX_ENTRY : ZX_AI\nZX_AI : ZX_ENTRY','White : ZX_ENTRY : ZX_AI : DISCONNECTED')
        with self.assertRaisesRegex(ValueError,'无法通往'):self.validate()

    def test_white_conditional_reconnect_uses_final_graph(self):
        self.world('ZX_ENTRY : DISCONNECTED\nZX_AI : ZX_ENTRY','White : ZX_ENTRY : 1 : ZX_AI')
        self.assertEqual(self.validate()[0]['connections'],['ZX_AI'])

    def test_named_replacements_run_in_order(self):
        self.world('ZX_ENTRY : ZX_OLD\nZX_OLD : ZX_ENTRY\nZX_NEXT : ZX_ENTRY\nZX_AI : ZX_ENTRY',
                   'White : ZX_ENTRY : ZX_OLD : ZX_NEXT\nWhite : ZX_ENTRY : ZX_NEXT : ZX_AI')
        self.assertEqual(self.validate()[0]['connections'],['ZX_AI'])

    def test_numeric_replacements_are_queued_not_applied_eagerly(self):
        self.world('ZX_ENTRY : DISCONNECTED, DISCONNECTED\nZX_FIRST : ZX_ENTRY\nZX_AI : ZX_ENTRY',
                   'White : ZX_ENTRY : 1 : ZX_FIRST\nWhite : ZX_ENTRY : 1 : ZX_AI')
        self.assertEqual(self.validate()[0]['connections'],['ZX_AI','DISCONNECTED'])

    def test_numeric_queue_commits_after_named_replacements(self):
        self.world('ZX_ENTRY : DISCONNECTED, DISCONNECTED\nZX_OTHER : ZX_ENTRY\nZX_AI : ZX_ENTRY',
                   'White : ZX_ENTRY : 1 : ZX_AI\nWhite : ZX_ENTRY : DISCONNECTED : ZX_OTHER')
        self.assertEqual(self.validate()[0]['connections'],['ZX_AI','DISCONNECTED'])

    def test_other_timeline_conditions_do_not_change_white_graph(self):
        self.world('ZX_ENTRY : ZX_AI\nZX_AI : ZX_ENTRY','Yellow : ZX_ENTRY : ZX_AI : DISCONNECTED')
        self.assertEqual(self.validate()[0]['connections'],['ZX_AI'])

    def test_prefix_timeline_alternatives_select_only_white(self):
        self.world('(White)ZX_ENTRY : ZX_AI\n(X-White)ZX_ENTRY : ZX_YELLOW\nZX_AI : ZX_ENTRY\n(Yellow)ZX_YELLOW : ZX_ENTRY')
        self.assertEqual([row['name'] for row in self.validate()],['ZX_ENTRY','ZX_AI'])

    def test_current_timeline_missing_start_or_required_is_rejected(self):
        self.world('ZX_ENTRY : DISCONNECTED\n(Yellow)ZX_AI : ZX_ENTRY')
        with self.assertRaisesRegex(ValueError,'演算室未'):self.validate()
        with self.assertRaisesRegex(ValueError,'起始房间未'):self.validate('ZX_AI',())

    def test_unknown_live_custom_condition_is_not_silently_ignored(self):
        self.world('ZX_ENTRY : ZX_AI\n{MySaveFlag}ZX_AI : ZX_ENTRY')
        with self.assertRaisesRegex(ValueError,'存档条件'):self.validate()

    def test_inactive_custom_condition_and_creature_conditions_do_not_block_room_graph(self):
        self.world('ZX_ENTRY : ZX_AI\nZX_AI : ZX_ENTRY\n(Yellow){MySaveFlag}ZX_YELLOW : ZX_ENTRY',
                   tail='CREATURES\n{OtherModCreatureFlag}ZX_AI : 0-Lizard\nEND CREATURES\n')
        self.assertEqual(len(self.validate()),2)

    def test_hidden_map_room_remains_a_physical_room(self):
        self.world('ZX_ENTRY : ZX_AI\nZX_AI : ZX_ENTRY : SWARMROOM : SCAVOUTPOST : SHELTER',
                   'White : HIDEROOM : ZX_AI')
        ai=self.validate()[1]
        self.assertTrue(ai['hidden']);self.assertEqual(ai['connections'],['ZX_ENTRY']);self.assertEqual(ai['tags'],'SHELTER')

    def test_exclusive_room_selectors_are_combined_before_hiding(self):
        self.world('ZX_ENTRY : ZX_AI\nZX_AI : ZX_ENTRY',
                   'Yellow : EXCLUSIVEROOM : ZX_AI\nWhite : EXCLUSIVEROOM : ZX_AI')
        self.assertFalse(self.validate()[1]['hidden'])
        self.world('ZX_ENTRY : ZX_AI\nZX_AI : ZX_ENTRY','Yellow : EXCLUSIVEROOM : ZX_AI')
        self.assertTrue(self.validate()[1]['hidden'])

    def test_replace_room_retains_logical_identity_and_reports_asset_alias(self):
        self.world('ZX_ENTRY : ZX_AI\nZX_AI : ZX_ENTRY','White : REPLACEROOM : ZX_AI : ZX_ALTERNATE')
        ai=self.validate()[1]
        self.assertEqual(ai['name'],'ZX_AI');self.assertEqual(ai['replacement'],'ZX_ALTERNATE')

    def test_isolated_start_is_rejected_even_without_selected_iterators(self):
        self.world('ZX_ENTRY : DISCONNECTED\nZX_AI : DISCONNECTED')
        with self.assertRaisesRegex(ValueError,'不连通'):self.validate(required=())

    def test_all_selected_iterators_must_be_reachable(self):
        self.world('ZX_ENTRY : ZX_AI\nZX_AI : ZX_ENTRY\nZX_OTHER : DISCONNECTED')
        self.validate()
        with self.assertRaisesRegex(ValueError,'ZX_OTHER'):self.validate(required=('ZX_AI','ZX_OTHER'))

    def test_multiple_regions_do_not_invent_cross_region_travel(self):
        self.world('ZX_ENTRY : ZX_AI\nZX_AI : ZX_ENTRY')
        self.world('ZY_ENTRY : ZY_AI\nZY_AI : ZY_ENTRY',region='ZY')
        self.assertEqual(len(self.validate(regions=('ZX','ZY'))),4)
        with self.assertRaisesRegex(ValueError,'ZY_AI'):self.validate(required=('ZX_AI','ZY_AI'),regions=('ZX','ZY'))
        self.world('ZX_ENTRY : ZY_AI\nZX_AI : ZX_ENTRY')
        with self.assertRaisesRegex(ValueError,'未加载'):self.validate(regions=('ZX','ZY'))

    def test_unknown_white_syntax_and_unloaded_destinations_fail_closed(self):
        for condition in ('White : FUTURE_RULE : ZX_AI','White : ZX_ENTRY : ZX_AI',
                          'White : ZX_ENTRY : ZX_AI : ZX_MISSING'):
            with self.subTest(condition=condition):
                self.world('ZX_ENTRY : ZX_AI\nZX_AI : ZX_ENTRY',condition)
                with self.assertRaises(ValueError):self.validate()

    def test_gate_tag_is_rejected_as_start_even_with_nonstandard_name(self):
        self.world('ZX_ENTRY : ZX_AI : GATE\nZX_AI : ZX_ENTRY')
        with self.assertRaisesRegex(ValueError,'业力门'):self.validate()

    def test_missing_end_and_unsupported_numeric_timeline_fail_explicitly(self):
        path=self.world('ZX_ENTRY : ZX_AI\nZX_AI : ZX_ENTRY')
        path.write_text('ROOMS\nZX_ENTRY : ZX_AI\nZX_AI : ZX_ENTRY\n','utf-8')
        with self.assertRaisesRegex(ValueError,'未结束'):self.validate()
        self.world('(0)ZX_ENTRY : ZX_AI\nZX_AI : ZX_ENTRY')
        with self.assertRaisesRegex(ValueError,'暂不支持'):self.validate()


if __name__=='__main__':unittest.main()
