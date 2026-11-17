import json
import unittest
import urllib.parse
from unittest.mock import patch

import test_room_identity_workflow as workflow


class RoomDraftApplyTests(unittest.TestCase):
    start = workflow.RoomIdentityWorkflowTests.start
    stop = workflow.RoomIdentityWorkflowTests.stop
    request = workflow.RoomIdentityWorkflowTests.request
    protected = workflow.RoomIdentityWorkflowTests.protected

    def setUp(self):
        injection = '''
import room_cleanup
original_record_migration=room_cleanup.record_migration
def record_migration(*args,**kwargs):
    if (storage.DATA/'fail-after-draft.fixture').exists():raise ValueError('fixture failure after draft write')
    return original_record_migration(*args,**kwargs)
room_cleanup.record_migration=record_migration
server.server_lifecycle'''
        boot = workflow.BOOT.replace(';server.server_lifecycle', injection)
        replacement = patch.object(workflow, 'BOOT', boot)
        replacement.start()
        self.addCleanup(replacement.stop)
        workflow.RoomIdentityWorkflowTests.setUp(self)
        self.pid = next(project['projectId'] for project in self.request('/api/projects') if project['name'] == 'PL workflow fixture')
        self.query = urllib.parse.urlencode({'projectId': self.pid})
        self.original = self.request('/api/room-binding?' + self.query)['binding']
        self.target = dict(self.original, region='PL', ai='PL_AI', entry='PL_POOL', entryMode='copy')
        self.draft_file = self.data / 'projects' / self.pid / 'editor-drafts/room-binding.json'

    def save_draft(self, value, revision):
        return self.request('/api/room-draft', {'projectId': self.pid, 'binding': value, 'revision': revision})

    def apply(self, revision=None, status=200):
        request = {'projectId': self.pid, 'binding': self.target}
        plan = self.request('/api/room-binding/preview', request)
        request['token'] = plan['token']
        if revision is not None:
            request['draftRevision'] = revision
        return self.request('/api/room-binding/apply', request, status=status)

    def test_applied_rename_consumes_matching_older_draft_atomically(self):
        older = dict(self.original, region='PL_', ai='AI', entry='POOL')
        saved = self.save_draft(older, 0)
        applied = self.apply(saved['revision'])
        self.assertEqual(applied['draftRevision'], saved['revision'] + 1)
        self.assertFalse(applied['draftPreserved'])
        disk = json.loads(self.draft_file.read_text('utf-8'))
        self.assertEqual(disk['binding'], self.target)
        self.assertEqual(disk['revision'], applied['draftRevision'])
        self.stop()
        self.start()
        self.assertEqual(self.request('/api/room-binding?' + self.query)['binding'], self.target)
        reopened = self.request('/api/room-draft?' + self.query)
        self.assertIsNone(reopened['binding'])
        self.assertEqual(reopened['revision'], applied['draftRevision'])
        next_draft = self.save_draft(dict(self.target, entry='PL_OTHER'), reopened['revision'])
        self.assertEqual(next_draft['revision'], reopened['revision'] + 1)

    def test_other_page_newer_draft_is_preserved_byte_for_byte(self):
        first = self.save_draft(dict(self.original, region='PL_'), 0)
        other = dict(self.original, region='QQ', ai='QQ_AI', entry='QQ_ENTRY')
        latest = self.save_draft(other, first['revision'])
        before = self.draft_file.read_bytes()
        applied = self.apply(first['revision'])
        self.assertEqual(applied['binding'], self.target)
        self.assertTrue(applied['draftPreserved'])
        self.assertEqual(applied['draftRevision'], latest['revision'])
        self.assertEqual(self.draft_file.read_bytes(), before)
        reopened = self.request('/api/room-draft?' + self.query)
        self.assertEqual(reopened['binding'], other)
        self.assertEqual(reopened['revision'], latest['revision'])

    def test_failed_apply_rolls_back_both_world_and_draft(self):
        saved = self.save_draft(dict(self.original, region='PL_'), 0)
        before = self.protected()
        (self.data / 'fail-after-draft.fixture').write_text('fail', 'utf-8')
        error = self.apply(saved['revision'], status=400)
        self.assertIn('fixture failure after draft write', error['error'])
        self.assertEqual(self.protected(), before)
        self.assertEqual(self.request('/api/room-binding?' + self.query)['binding'], self.original)
        self.assertEqual(self.request('/api/room-draft?' + self.query)['revision'], saved['revision'])

    def test_legacy_client_without_revision_keeps_existing_draft_behavior(self):
        self.save_draft(dict(self.original, region='PL_'), 0)
        before = self.draft_file.read_bytes()
        applied = self.apply()
        self.assertTrue(applied['ok'])
        self.assertNotIn('draftRevision', applied)
        self.assertNotIn('draftPreserved', applied)
        self.assertEqual(self.draft_file.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
