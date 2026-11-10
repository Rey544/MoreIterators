import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import test_project_packages as fixtures
import project_packages
import server
import storage
import copy
import hashlib
import zipfile
from pathlib import Path


class PackageHttpTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ProjectPackageTests('test_roundtrip_preserves_room_source_settings_cameras_palette_and_plan')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        context=patch.object(server,'validate',self.fixture.validate);context.start();self.addCleanup(context.stop)
        self.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.port=self.http.server_address[1]
        context=patch.object(server,'PORT',self.port);context.start();self.addCleanup(context.stop)
        thread=threading.Thread(target=self.http.serve_forever,daemon=True);thread.start()
        self.addCleanup(self.http.server_close);self.addCleanup(self.http.shutdown)

    def request(self,path,value,origin=True,**headers):
        headers={'Content-Type':'application/json' if isinstance(value,dict) else 'application/zip',**headers}
        if origin:headers['Origin']='http://127.0.0.1:'+str(self.port)
        body=json.dumps(value).encode() if isinstance(value,dict) else value
        client=http.client.HTTPConnection('127.0.0.1',self.port,timeout=10)
        try:
            client.request('POST',path,body,headers);response=client.getresponse()
            return response.status,json.loads(response.read())
        finally:client.close()

    def test_binary_inspect_and_explicit_replace(self):
        status,export=self.request('/api/export-project-package',{'projectId':'selected','extraRooms':[]})
        self.assertEqual(status,200,export)
        payload=(storage.EXPORTS/export['url'].split('/')[-1]).read_bytes()
        status,preview=self.request('/api/project-package-inspect',payload)
        self.assertEqual(status,200,preview);self.assertTrue(preview['collision'])
        before=self.fixture.project_file.read_bytes()
        status,result=self.request('/api/import-project-package',payload)
        self.assertEqual(status,200,result);self.assertFalse(result['ok']);self.assertTrue(result['collision'])
        self.assertEqual(self.fixture.project_file.read_bytes(),before)
        status,result=self.request('/api/import-project-package',payload,**{'X-MI-Replace-Project':'1'})
        self.assertEqual(status,200,result);self.assertTrue(result['ok']);self.assertTrue(result['requiresApply'])

    def test_zip_still_requires_loopback_origin(self):
        before=self.fixture.project_file.read_bytes()
        status,_=self.request('/api/import-project-package',b'not-a-zip',origin=False)
        self.assertEqual(status,403);self.assertEqual(self.fixture.project_file.read_bytes(),before)

    def test_invalid_archive_does_not_overwrite(self):
        before=self.fixture.project_file.read_bytes()
        status,result=self.request('/api/import-project-package',b'not-a-zip',**{'X-MI-Replace-Project':'1'})
        self.assertEqual(status,400,result);self.assertEqual(self.fixture.project_file.read_bytes(),before)

    def test_explicit_conflict_choice_exports_selected_version_without_source_writes(self):
        project=copy.deepcopy(self.fixture.project);project['editor']={'externalRoomTools':True}
        self.fixture.project_file.write_text(json.dumps(project),'utf-8')
        current=self.fixture.installed/'world/xx-rooms/XX_AI'
        self.fixture.render(current,'XX_AI',2,'blue')
        settings=Path(str(current)+'_settings.txt')
        settings.write_text('Template: NONE\nPalette: 9100\nEffects: ZeroG-0.61-1-1,\n','utf-8')
        self.fixture.palette(self.fixture.installed/'palettes/palette9100.png','red')
        roots=(self.fixture.project_file.parent,self.fixture.local,self.fixture.installed)
        def snapshot():
            return {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for root in roots for path in root.rglob('*') if path.is_file()}
        before=snapshot()
        status,report=self.request('/api/export-room-check',{'projects':['selected']})
        self.assertEqual(status,200,report);self.assertTrue(report['requiresChoices'])
        status,error=self.request('/api/export-project-package',{'projectId':'selected'})
        self.assertEqual(status,400);self.assertEqual(error['code'],'room_choices_required')
        choices={}
        for room in report['rooms']:
            choices['selected/'+room['room']]={kind:next((value['id'] for value in room[field] if value['complete'] and 'installed' in value['origins']),room[field][0]['id'])
                                              for kind,field in (('source','renderVersions'),('settings','settingsVersions'))}
        policies={'selected':{}}
        for conflict in report['parameterConflicts']:
            if conflict['kind']=='gravity':policies['selected'].setdefault('gravity',{})[conflict['room']]='project'
            else:policies['selected'][conflict['kind']]='project'
        payload={'snapshotToken':report['snapshotToken'],'choices':choices,'policies':policies}
        status,result=self.request('/api/export-project-package',{'projectId':'selected','roomSourceChoices':payload})
        self.assertEqual(status,200,result)
        with zipfile.ZipFile(storage.EXPORTS/result['url'].split('/')[-1]) as archive:
            self.assertEqual(archive.read('rooms/XX_AI/rendered/XX_AI_1.png'),Path(str(current)+'_1.png').read_bytes())
            self.assertEqual(archive.read('rooms/XX_AI/rendered/XX_AI_settings.txt'),settings.read_bytes())
        self.assertEqual(snapshot(),before)
        settings.write_text(settings.read_text('utf-8')+'Clouds: 0.3\n','utf-8')
        status,error=self.request('/api/export-project-package',{'projectId':'selected','roomSourceChoices':payload})
        self.assertEqual(status,400);self.assertEqual(error['code'],'room_choices_stale')


if __name__=='__main__':unittest.main()
