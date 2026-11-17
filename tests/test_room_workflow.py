import copy
import json
import os
import shutil
import time
import unittest
import urllib.parse
from unittest.mock import patch
import test_room_identity_workflow as workflow


class RoomWorkflowTests(unittest.TestCase):
    start=workflow.RoomIdentityWorkflowTests.start
    stop=workflow.RoomIdentityWorkflowTests.stop
    request=workflow.RoomIdentityWorkflowTests.request
    protected=workflow.RoomIdentityWorkflowTests.protected

    def setUp(self):
        injection='''
import json,room_workflow,room_migration
original_catalog=room_workflow._catalog
room_workflow._catalog=lambda:json.loads((storage.DATA/'catalog.fixture').read_text('utf-8')) if (storage.DATA/'catalog.fixture').exists() else original_catalog()
original_json=room_migration.Files.json
def fixture_json(self,path,value):
    original_json(self,path,value)
    if path.name=='room-workflow.json' and value.get('pending') is None and (storage.DATA/'fail-workflow.fixture').exists():raise ValueError('fixture failed after pending consumption')
room_migration.Files.json=fixture_json
server.server_lifecycle'''
        boot=workflow.BOOT.replace(';server.server_lifecycle',injection)
        replacement=patch.object(workflow,'BOOT',boot);replacement.start();self.addCleanup(replacement.stop)
        workflow.RoomIdentityWorkflowTests.setUp(self)
        self.pid=next(p['projectId'] for p in self.request('/api/projects') if p['name']=='PL workflow fixture')
        self.query='?'+urllib.parse.urlencode({'projectId':self.pid})
        self.state=self.get()
        self.binding=self.state['binding']

    def get(self):return self.request('/api/room-workflow'+self.query if hasattr(self,'query') else '/api/room-workflow?projectId='+self.pid)

    def stage(self,names=None,state=None):
        state=state or self.get()
        return self.request('/api/room-workflow/names',dict(projectId=self.pid,revision=state['revision'],names=names or dict(region='PL',ai='PL_AI',entry='PL_POOL')))

    def connect_pending(self,state,status=200):
        return self.request('/api/room-workflow/apply',dict(projectId=self.pid,revision=state['revision'],connections=[{'from':dict(room=row['room'],node=row['node']),'to':dict(room=row['toRoom'],node=row['toNode']),'replaces':row['id']} for row in state['pending']['required']]),status=status)

    def live_files(self):
        return {k:v for k,v in self.protected().items() if '/editor-drafts/' not in k}

    def test_names_are_durable_copies_until_explicit_connection_and_cancel_keeps_old_work(self):
        before=self.live_files();state=self.stage()
        self.assertEqual(self.live_files(),before)
        self.assertEqual(state['binding'],self.binding)
        self.assertEqual({r['name'] for r in state['rooms'] if r['owned']},{'PL_AI','PL_POOL'})
        self.assertTrue(all(r['original'] in (self.binding['ai'],self.binding['entry']) for r in state['rooms'] if r['owned']))
        self.assertEqual(len(state['pending']['required']),1)
        self.stop();self.start();reopened=self.get();self.assertEqual(reopened['pending'],state['pending'])
        result=self.request('/api/room-workflow/cancel',dict(projectId=self.pid,revision=reopened['revision']))
        self.assertIsNone(result['pending']);self.assertEqual(self.live_files(),before)
        self.assertEqual(result['binding'],self.binding)

    def test_connection_commits_rename_and_graph_survives_ordinary_deploy(self):
        state=self.stage();result=self.connect_pending(state)
        self.assertIsNone(result['pending']);self.assertEqual(result['binding']['ai'],'PL_AI');self.assertEqual(result['binding']['entry'],'PL_POOL')
        project=self.request('/api/projects')[0]
        self.assertEqual(project['roomConnections']['version'],2)
        self.assertEqual({r['name'] for r in project['roomConnections']['rows'] if r['owned']},{'PL_AI','PL_POOL'})
        for old in (self.binding['ai'],self.binding['entry']):
            self.assertFalse((self.data/'projects'/self.pid/'rooms/rendered'/(old+'.txt')).exists())
        self.assertTrue(list((self.data/'projects'/self.pid/'room-backups').rglob(self.binding['ai']+'.txt')))
        plan=self.data/'projects'/self.pid/'room-binding-plan.json'
        self.assertEqual(json.loads(plan.read_text('utf-8'))['connectionVersion'],2)
        legacy=copy.deepcopy(project);legacy.pop('roomConnections')
        self.request('/api/save',legacy)
        self.assertEqual(self.request('/api/projects')[0]['roomConnections'],project['roomConnections'])
        self.request('/api/deploy',legacy)
        after=self.get();self.assertEqual(after['connections'],result['connections'])

    def test_apply_without_explicit_connection_or_stale_page_preserves_pending_and_old_outputs(self):
        state=self.stage();before=self.protected()
        self.request('/api/room-workflow/apply',dict(projectId=self.pid,revision=state['revision'],connections=[]),status=400)
        self.assertEqual(self.protected(),before)
        self.request('/api/room-workflow/cancel',dict(projectId=self.pid,revision=state['revision']-1),status=400)
        self.assertEqual(self.protected(),before)

    def test_transaction_failure_after_pending_consumption_restores_every_file(self):
        state=self.stage();before=self.protected();(self.data/'fail-workflow.fixture').write_text('fail','utf-8')
        error=self.connect_pending(state,status=400)
        self.assertIn('fixture failed after pending consumption',error['error'])
        self.assertEqual(self.protected(),before);self.assertEqual(self.get()['pending'],state['pending'])

    def fixture_catalog(self):
        ai=self.binding['ai'];entry=self.binding['entry']
        rows=[dict(name=ai,region='TEST',connections=['DISCONNECTED',entry],exitCount=2,verified=True,conditional=False),dict(name=entry,region='TEST',connections=[ai],exitCount=1,verified=True,conditional=False),dict(name='TEST_MAP',region='TEST',connections=['DISCONNECTED','TEST_OTHER'],exitCount=2,verified=True,conditional=False),dict(name='TEST_OTHER',region='TEST',connections=['TEST_MAP'],exitCount=1,verified=True,conditional=False)]
        value=dict(source='live',fresh=True,complete=True,regions=[dict(name='TEST',rooms=rows)],reservedRooms=[],reservedRegions=[],generation='fixture')
        (self.data/'catalog.fixture').write_text(json.dumps(value),'utf-8')
        world=self.assets/'world/test/world_test.txt';world.parent.mkdir(parents=True,exist_ok=True)
        world.write_text('ROOMS\nTEST_MAP : DISCONNECTED, TEST_OTHER\nTEST_OTHER : TEST_MAP\nEND ROOMS\n','utf-8')
        return value

    def test_connecting_map_room_keeps_waiting_room_and_unrelated_connections(self):
        self.fixture_catalog();before=self.get();entry=self.binding['entry'];entry_file=self.data/'projects'/self.pid/'rooms/rendered'/(entry+'.txt');entry_bytes=entry_file.read_bytes()
        result=self.request('/api/room-workflow/apply',dict(projectId=self.pid,revision=before['revision'],ownedRoom=self.binding['ai'],ownedNode=0,targetRoom='TEST_MAP',targetNode=0))
        self.assertEqual(result['binding']['entry'],entry);self.assertEqual(result['binding']['entryMode'],'copy')
        self.assertEqual(entry_file.read_bytes(),entry_bytes)
        project=self.request('/api/projects')[0];rows={r['name']:r for r in project['roomConnections']['rows']}
        self.assertEqual(rows[self.binding['ai']]['connections'],['TEST_MAP',entry])
        self.assertEqual(rows['TEST_MAP']['connections'],[self.binding['ai'],'TEST_OTHER'])
        self.assertEqual(rows[entry]['connections'],[self.binding['ai']])
        self.request('/api/deploy',project)
        local=self.data/'local-mod/modify/world/test/world_test.txt'
        self.assertIn('TEST_MAP : '+self.binding['ai']+', TEST_OTHER',local.read_text('utf-8'))
        self.assertEqual(self.get()['binding']['entry'],entry)

    def test_occupied_and_cross_region_targets_do_not_change_files(self):
        value=self.fixture_catalog();before=self.get();files=self.protected()
        result=self.request('/api/room-workflow/apply',dict(projectId=self.pid,revision=before['revision'],ownedRoom=self.binding['ai'],ownedNode=0,targetRoom='TEST_MAP',targetNode=1),status=400)
        self.assertEqual(result['code'],'rooms.error.workflowOccupied');self.assertEqual(self.protected(),files)
        value['regions'].append(dict(name='SU',rooms=[dict(name='SU_A01',region='SU',connections=['DISCONNECTED'],exitCount=1,verified=True)]));(self.data/'catalog.fixture').write_text(json.dumps(value),'utf-8')
        result=self.request('/api/room-workflow/apply',dict(projectId=self.pid,revision=before['revision'],ownedRoom=self.binding['ai'],ownedNode=0,targetRoom='SU_A01',targetNode=0),status=400)
        self.assertEqual(result['code'],'rooms.error.workflowCrossRegion');self.assertEqual(self.protected(),files)

    def connect_map(self):
        self.fixture_catalog()
        return self.request('/api/room-workflow/apply',dict(projectId=self.pid,revision=self.get()['revision'],ownedRoom=self.binding['ai'],ownedNode=0,targetRoom='TEST_MAP',targetNode=0))

    def test_deploy_rebases_unselected_external_ports_from_disk_not_own_overlay(self):
        self.connect_map();project=self.request('/api/projects')[0]
        native=self.assets/'world/test/world_test.txt'
        native.write_text('ROOMS\nTEST_MAP : DISCONNECTED, TEST_NEW\nTEST_NEW : TEST_MAP\nEND ROOMS\n','utf-8')
        merged=self.assets/'mergedmods/world/test/world_test.txt';merged.parent.mkdir(parents=True)
        merged.write_text('ROOMS\nTEST_MAP : '+self.binding['ai']+', TEST_STALE\nEND ROOMS\n','utf-8')
        self.request('/api/deploy',project)
        text=(self.data/'local-mod/modify/world/test/world_test.txt').read_text('utf-8')
        self.assertIn('TEST_MAP : '+self.binding['ai']+', TEST_NEW',text)
        self.assertNotIn('TEST_STALE',text);self.assertNotIn('TEST_OTHER',text)

    def test_deploy_from_newest_local_room_preserves_camera_bytes_and_timestamps(self):
        self.connect_map();project=self.request('/api/projects')[0]
        rooms=self.data/'local-mod/world/test-rooms'
        cameras=[path for name in (self.binding['ai'],self.binding['entry']) for path in rooms.glob(name+'_*.png')]
        self.assertTrue(cameras)
        newest=time.time_ns()+10_000_000_000
        for path in cameras:os.utime(path,ns=(newest,newest))
        before={path:(path.read_bytes(),path.stat().st_mtime_ns) for path in cameras}
        cache=self.data/'projects'/self.pid/'rooms/rendered'
        sources={path.name:path.read_bytes() for path in cache.iterdir() if path.is_file()}
        for _ in range(2):self.request('/api/deploy',project)
        self.assertEqual({path:(path.read_bytes(),path.stat().st_mtime_ns) for path in cameras},before)
        self.assertEqual({path.name:path.read_bytes() for path in cache.iterdir() if path.is_file()},sources)
        self.assertEqual(self.request('/api/projects')[0]['roomConnections'],project['roomConnections'])
        installed=self.assets/'mods/more_iterators_local/world/test-rooms'
        for path,(content,_) in before.items():self.assertEqual((installed/path.name).read_bytes(),content)

    def test_deploy_external_port_taken_rejects_before_any_output(self):
        self.connect_map();project=self.request('/api/projects')[0]
        (self.assets/'world/test/world_test.txt').write_text('ROOMS\nTEST_MAP : TEST_FOREIGN, TEST_OTHER\nTEST_OTHER : TEST_MAP\nEND ROOMS\n','utf-8')
        before=self.protected();error=self.request('/api/deploy',project,status=400)
        self.assertEqual(error['code'],'rooms.error.workflowOccupied');self.assertEqual(self.protected(),before)

    def test_reconnecting_removes_only_previous_external_override(self):
        self.connect_map();value=json.loads((self.data/'catalog.fixture').read_text('utf-8'))
        value['regions'][0]['rooms'].append(dict(name='TEST_NEXT',region='TEST',connections=['DISCONNECTED'],exitCount=1,verified=True,conditional=False))
        (self.data/'catalog.fixture').write_text(json.dumps(value),'utf-8')
        native=self.assets/'world/test/world_test.txt';native.write_text(native.read_text('utf-8').replace('END ROOMS','TEST_NEXT : DISCONNECTED\nEND ROOMS'),'utf-8')
        self.request('/api/room-workflow/apply',dict(projectId=self.pid,revision=self.get()['revision'],ownedRoom=self.binding['ai'],ownedNode=0,targetRoom='TEST_NEXT',targetNode=0))
        text=(self.data/'local-mod/modify/world/test/world_test.txt').read_text('utf-8')
        self.assertNotIn('[FINDLINESTART]TEST_MAP',text)
        self.assertIn('[REPLACE]TEST_NEXT : '+self.binding['ai'],text)
        self.assertIn('TEST_MAP : DISCONNECTED, TEST_OTHER',native.read_text('utf-8'))

    def test_json_graph_without_room_files_never_fabricates_default_rooms(self):
        source=copy.deepcopy(self.request('/api/projects')[0]);source['projectId']='json-import';source['name']='JSON fixture'
        source['roomBinding']=dict(self.binding,region='ZZ',ai='ZZ_AI',entry='ZZ_ENTRY',oracleId='json_import')
        source['roomConnections']=dict(version=2,ownedRegions=['ZZ'],rows=[dict(name='ZZ_AI',region='ZZ',connections=['DISCONNECTED','ZZ_ENTRY'],tags='',owned=True,kind='ai'),dict(name='ZZ_ENTRY',region='ZZ',connections=['ZZ_AI'],tags='',owned=True,kind='entry')])
        imported=self.request('/api/import-project',source)['project'];pid=imported['projectId']
        self.assertEqual(imported['roomConnections'],source['roomConnections'])
        before=self.protected();error=self.request('/api/deploy',imported,status=400)
        self.assertEqual(error['code'],'rooms.error.workflowSourceMissing');self.assertEqual(self.protected(),before)
        destination=self.data/'projects'/pid/'rooms/rendered';destination.mkdir(parents=True)
        for kind in ('ai','entry'):
            old=self.binding[kind];new=imported['roomBinding'][kind]
            for original in (self.data/'projects'/self.pid/'rooms/rendered').glob(old+'*'):
                if original.name.endswith('.source.json'):continue
                target=destination/(new+original.name[len(old):]);shutil.copyfile(original,target)
                if target.name==new+'.txt':
                    lines=target.read_text('utf-8').splitlines();lines[0]=new;target.write_text('\n'.join(lines)+'\n','utf-8')
        state=self.request('/api/room-workflow?projectId='+pid)
        self.request('/api/room-workflow/apply',dict(projectId=pid,revision=state['revision'],ownedRoom='ZZ_AI',ownedNode=1,targetRoom='ZZ_ENTRY',targetNode=0))
        self.assertTrue((self.data/'local-mod/world/zz-rooms/ZZ_AI.txt').is_file())


if __name__=='__main__':unittest.main()
