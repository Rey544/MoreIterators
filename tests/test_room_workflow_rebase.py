import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import room_bindings
import storage


class RoomWorkflowRebaseTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.assets=self.root/'assets';self.foreign=self.root/'foreign';self.local=self.root/'data/local-mod';self.installed=self.assets/'mods/more_iterators_local'
        self.world=self.assets/'world/xx/world_xx.txt';self.world.parent.mkdir(parents=True)
        self.world.write_text('ROOMS\nXX_MAP : DISCONNECTED, DISCONNECTED, XX_OTHER\nXX_OTHER : XX_MAP\nEND ROOMS\n','utf-8')
        state=dict(roots=[self.assets/'mergedmods',self.installed,self.foreign/'newest',self.foreign,self.assets],assets=self.assets,installed={'foreign':self.foreign,'moreiterators.local':self.installed})
        for context in (patch.object(storage,'DATA',self.root/'data'),patch.object(storage,'PROJECTS',self.root/'data/projects'),patch.object(storage,'LINKS',[]),patch.object(storage,'installed_mod',return_value=self.installed),patch.object(room_bindings,'_selection',return_value=state)):
            context.start();self.addCleanup(context.stop)

    def plan(self,pid='first',node=0):
        name='XX_'+pid.upper();links=['DISCONNECTED','DISCONNECTED','XX_STALE'];links[node]=name
        return (pid,dict(connectionRows=[dict(name=name,region='XX',connections=['XX_MAP'],owned=True,kind='ai'),dict(name='XX_MAP',region='XX',connections=links,tags='',owned=False)]))

    def test_two_projects_same_external_room_merge_once_without_losing_native_port(self):
        result=room_bindings.rebase_external_rows([self.plan(),self.plan('second',1)])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['connections'],['XX_FIRST','XX_SECOND','XX_OTHER'])

    def test_projects_cannot_claim_same_external_port(self):
        with self.assertRaises(room_bindings.RoomBindingError) as caught:room_bindings.rebase_external_rows([self.plan(),self.plan('second')])
        self.assertEqual(caught.exception.code,'rooms.error.workflowOccupied')

    def test_own_overlay_and_merged_cache_are_not_native_baseline(self):
        for root in (self.local,self.installed,self.assets/'mergedmods'):
            file=root/'world/xx/world_xx.txt';file.parent.mkdir(parents=True)
            file.write_text('ROOMS\nXX_MAP : XX_BAD, XX_BAD, XX_BAD\nEND ROOMS\n','utf-8')
        self.assertEqual(room_bindings.rebase_external_rows([self.plan()])[0]['connections'],['XX_FIRST','DISCONNECTED','XX_OTHER'])

    def test_enabled_third_party_modify_preserves_unselected_exit(self):
        file=self.foreign/'modify/world/xx/world_xx.txt';file.parent.mkdir(parents=True)
        file.write_text('[FINDLINESTART]XX_MAP :\n[REPLACE]XX_MAP : DISCONNECTED, DISCONNECTED, XX_NEW\n[MERGE]\nROOMS\nEND ROOMS\n','utf-8')
        self.assertEqual(room_bindings.rebase_external_rows([self.plan()])[0]['connections'],['XX_FIRST','DISCONNECTED','XX_NEW'])
        file.write_text('[UNKNOWN]XX_MAP\n','utf-8')
        with self.assertRaises(room_bindings.RoomBindingError) as caught:room_bindings.rebase_external_rows([self.plan()])
        self.assertEqual(caught.exception.code,'rooms.error.workflowExternalUnavailable')

    def test_old_external_rows_without_any_project_edge_emit_no_override(self):
        pid,plan=self.plan();plan=copy.deepcopy(plan);plan['connectionRows'][1]['connections']=['DISCONNECTED','DISCONNECTED','XX_STALE']
        self.assertEqual(room_bindings.rebase_external_rows([(pid,plan)]),[])


if __name__=='__main__':unittest.main()
