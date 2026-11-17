import copy
import hashlib
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import test_room_identity_workflow as workflow


class RainedSyncTransactionTests(unittest.TestCase):
    start=workflow.RoomIdentityWorkflowTests.start
    stop=workflow.RoomIdentityWorkflowTests.stop
    request=workflow.RoomIdentityWorkflowTests.request

    def setUp(self):
        injection='''
import room_editor
def fixture_render(pid,kind,roomnames,source_hashes=None):
    p=storage.load_project(pid);ai,entry,_=roomnames(p)
    return storage.DATA/'render-output'/(ai if kind=='ai' else entry)
room_editor.render=fixture_render
original_sync_local_world=server.sync_local_world
def fixture_sync_local_world():
    original_sync_local_world()
    if (storage.DATA/'fail-sync.fixture').is_file():raise ValueError('fixture failed after installation')
server.sync_local_world=fixture_sync_local_world
server.server_lifecycle'''
        boot=workflow.BOOT.replace(';server.server_lifecycle',injection)
        replacement=patch.object(workflow,'BOOT',boot);replacement.start();self.addCleanup(replacement.stop)
        workflow.RoomIdentityWorkflowTests.setUp(self)
        self.project=self.request('/api/projects')[0];self.pid=self.project['projectId']
        self.binding=self.project['roomBinding']
        self.directory=self.data/'projects'/self.pid

    def protected(self):
        roots=[self.data/'projects',self.data/'runtime',self.data/'local-mod',self.data/'archive/project-history',self.assets/'mods']
        return {path.relative_to(self.folder).as_posix():(hashlib.sha256(path.read_bytes()).hexdigest(),path.stat().st_mtime_ns)
                for root in roots for path in root.rglob('*') if path.is_file()}

    def output(self,kind='entry'):
        name=self.binding[kind];output=self.data/'render-output'/name;output.parent.mkdir(exist_ok=True)
        data=(Path(__file__).parent/'fixtures/rained/unbaked-entry.txt').read_text('utf-8-sig').splitlines()
        data[0]=name;output.with_suffix('.txt').write_text('\n'.join(data)+'\n','utf-8')
        shutil.copyfile(self.directory/'rooms/rendered'/(name+'_1.png'),output.with_name(name+'_1.png'))
        return output

    def sync(self,kind='entry',status=200):
        return self.request('/api/sync-room',dict(projectId=self.pid,kind=kind),status=status)

    def test_unbaked_rained_render_syncs_and_keeps_connections(self):
        output=self.output();before=self.project
        editable=self.directory/'rooms'/(self.binding['entry']+'.txt');source=editable.read_bytes()
        result=self.sync();self.assertEqual(result['cameras'],1)
        after=self.request('/api/projects')[0]
        self.assertEqual(after['roomBinding'],before['roomBinding'])
        self.assertEqual(after.get('roomConnections'),before.get('roomConnections'))
        for root in (self.directory/'rooms/rendered',self.data/'local-mod/world/test-rooms',self.assets/'mods/more_iterators_local/world/test-rooms'):
            self.assertEqual((root/output.with_suffix('.txt').name).read_bytes(),output.with_suffix('.txt').read_bytes())
        self.assertEqual(editable.read_bytes(),source)
        world=(self.data/'local-mod/world/test/world_test.txt').read_text('utf-8')
        self.assertIn(self.binding['ai']+' : DISCONNECTED, '+self.binding['entry'],world)
        self.assertIn(self.binding['entry']+' : '+self.binding['ai'],world)

    def test_corrupt_render_does_not_replace_cache_or_deploy(self):
        output=self.output();rows=output.with_suffix('.txt').read_text('utf-8').splitlines()
        rows[11]=rows[11][:-2];output.with_suffix('.txt').write_text('\n'.join(rows)+'\n','utf-8')
        before=self.protected();error=self.sync(status=400)
        self.assertIn(self.binding['entry'],error['error']);self.assertEqual(self.protected(),before)

    def test_valid_geometry_with_removed_connected_node_preserves_all_files(self):
        self.output('ai');before=self.protected()
        self.sync('ai',status=400)
        self.assertEqual(self.protected(),before)

    def test_failure_after_installation_restores_every_output_and_timestamp(self):
        self.output();(self.data/'fail-sync.fixture').touch();before=self.protected()
        error=self.sync(status=400)
        self.assertIn('fixture failed after installation',error['error'])
        self.assertEqual(self.protected(),before)

    def test_deploy_preflight_uses_saved_binding_when_old_page_submits_stale_names(self):
        self.assertNotIn('roomConnections',self.project)
        (self.directory/'room-package.json').unlink(missing_ok=True)
        incoming=copy.deepcopy(self.project)
        incoming['roomBinding']=dict(self.binding,region='ZZ',ai='ZZ_OLD_AI',entry='ZZ_OLD_ENTRY',oracleId='old_oracle')
        incoming['design']['headColor']='#123456'
        result=self.request('/api/deploy',incoming)
        self.assertEqual(result['project']['roomBinding'],self.binding)
        self.assertEqual(result['project']['design']['headColor'],'#123456')
        self.assertFalse((self.data/'local-mod/world/zz').exists())
        saved=self.request('/api/projects')[0]
        self.assertEqual(saved['roomBinding'],self.binding)
        self.assertNotIn('roomConnections',saved)


if __name__=='__main__':unittest.main()
