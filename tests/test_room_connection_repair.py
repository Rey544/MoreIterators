import json
import unittest
from test_room_workflow import RoomWorkflowTests


class RoomConnectionRepairTests(unittest.TestCase):
    setUp=RoomWorkflowTests.setUp
    start=RoomWorkflowTests.start
    stop=RoomWorkflowTests.stop
    request=RoomWorkflowTests.request
    protected=RoomWorkflowTests.protected
    get=RoomWorkflowTests.get

    def save_connections(self, ai_links, entry_links):
        path=self.data/'projects'/self.pid/'project.json'
        project=json.loads(path.read_text('utf-8'))
        project['roomBinding']=self.binding
        project['roomConnections']=dict(version=2,ownedRegions=['TEST'],rows=[
            dict(name=self.binding['ai'],region='TEST',connections=ai_links,tags='',owned=True,kind='ai'),
            dict(name=self.binding['entry'],region='TEST',connections=entry_links,tags='',owned=True,kind='entry')])
        path.write_text(json.dumps(project),'utf-8')

    def reconcile(self, room, status=200):
        return self.request('/api/room-workflow/apply',dict(projectId=self.pid,revision=self.get()['revision'],connections=[],reconcileRooms=[room]),status=status)

    def test_known_mismatch_remains_visible_and_explicit_append_preserves_edge(self):
        ai=self.binding['ai'];entry=self.binding['entry']
        self.save_connections([entry],[ai]);before=self.protected()
        state=self.get();self.assertEqual(self.protected(),before)
        row=next(row for row in state['rooms'] if row['name']==ai)
        self.assertEqual(row['connections'],[entry]);self.assertEqual(row['actualExitCount'],2)
        self.assertFalse(row['verified']);self.assertTrue(row['issues'][0]['canReconcile'])
        result=self.reconcile(ai);row=next(row for row in result['rooms'] if row['name']==ai)
        self.assertEqual(row['connections'],[entry,'DISCONNECTED']);self.assertTrue(row['verified'])
        self.assertEqual(next(row for row in result['rooms'] if row['name']==entry)['connections'],[ai])

    def test_explicit_trim_only_removes_unused_slots(self):
        ai=self.binding['ai'];entry=self.binding['entry']
        self.save_connections(['DISCONNECTED',entry],[ai,'DISCONNECTED'])
        result=self.reconcile(entry)
        self.assertEqual(next(row for row in result['rooms'] if row['name']==entry)['connections'],[ai])
        self.assertEqual(next(row for row in result['rooms'] if row['name']==ai)['connections'],['DISCONNECTED',entry])

    def test_connected_removed_exit_is_preserved_and_not_reconcilable(self):
        ai=self.binding['ai'];entry=self.binding['entry']
        self.save_connections(['DISCONNECTED',entry],[ai,'TEST_OTHER']);before=self.protected()
        row=next(row for row in self.get()['rooms'] if row['name']==entry)
        self.assertFalse(row['issues'][0]['canReconcile'])
        result=self.reconcile(entry,status=400)
        self.assertEqual(result['code'],'rooms.error.workflowConnectedExitMissing')
        self.assertEqual(self.protected(),before)


if __name__=='__main__':unittest.main()
