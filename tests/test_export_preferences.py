import copy
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import playable_export
import server
import storage
import standalone
import test_standalone_extra_rooms as fixtures
from test_scene_assets import draft


class ExportPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ExtraRoomExportTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.request={**self.fixture.request,'settingsProject':'selected','startRoom':'ZX_ENTRY','scene':draft()}
        self.file=storage.project_file('selected').parent/'export-settings.json'

    def test_draft_only_writes_current_export_settings_and_preserves_author_content(self):
        before={path:path.read_bytes() for path in self.fixture.data.rglob('*') if path.is_file()}
        playable_export.save_preferences(self.request,server)
        saved=json.loads(self.file.read_text('utf-8'))
        self.assertEqual(saved['scene'],self.request['scene'])
        self.assertEqual(saved['projects'],['selected'])
        self.assertEqual({path:path.read_bytes() for path in before},before)
        self.assertEqual(set(self.fixture.data.rglob('*'))-set(before),{path for path in self.fixture.data.rglob('*') if path.is_dir()}|{self.file})
        self.assertEqual(standalone.preferences('selected')['scene'],self.request['scene'])

    def test_incomplete_metadata_can_be_saved_without_exporting(self):
        playable_export.save_preferences({**self.request,'id':'','name':'','authors':'','version':''},server)
        self.assertEqual(json.loads(self.file.read_text('utf-8'))['name'],'')
        self.assertFalse(storage.EXPORTS.exists())

    def test_content_scope_parts_and_format_survive_preference_roundtrip(self):
        request={**self.request,'scope':'region','region':'ZX','parts':['textures','room'],'format':'project','dialogue':False}
        playable_export.save_preferences(request,server)
        saved=standalone.preferences('selected')
        for key in ('scope','region','parts','format','dialogue','startRoom','scene'):
            self.assertEqual(saved[key],request[key])
        before=self.file.read_bytes()
        for changes in ({'parts':['room','room']},{'parts':['unknown']},{'parts':'room'},{'format':'unknown'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):playable_export.save_preferences({**request,**changes},server)
            self.assertEqual(self.file.read_bytes(),before)

    def test_bad_identity_or_scene_cannot_replace_saved_draft(self):
        playable_export.save_preferences(self.request,server);before=self.file.read_bytes()
        bad_scene=draft();bad_scene['scenes'][0]['images'][0]['name']='../escape'
        for changes in ({'settingsProject':'../other'},{'settingsProject':'missing'},{'scene':bad_scene},{'scene':{'schema':'unknown'}},{'startRoom':'../escape'},{'cover':'not-image'},{'pearls':'false'}):
            with self.subTest(changes=list(changes)),self.assertRaises(ValueError):playable_export.save_preferences({**self.request,**changes},server)
            self.assertEqual(self.file.read_bytes(),before)

    def test_old_standalone_export_keeps_saved_scene(self):
        playable_export.save_preferences(self.request,server)
        standalone.build({key:value for key,value in self.request.items() if key!='scene'},server)
        self.assertEqual(json.loads(self.file.read_text('utf-8'))['scene'],self.request['scene'])


class ExportPreferenceHttpTests(unittest.TestCase):
    def setUp(self):
        ExportPreferenceTests.setUp(self)
        self.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.port=self.http.server_address[1]
        change=patch.object(server,'PORT',self.port);change.start();self.addCleanup(change.stop)
        threading.Thread(target=self.http.serve_forever,daemon=True).start()
        self.addCleanup(self.http.server_close);self.addCleanup(self.http.shutdown)

    def post(self,body,origin=True,length=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=10)
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']='http://127.0.0.1:'+str(self.port)
        if length:headers['Content-Length']=str(length)
        try:
            connection.request('POST','/api/export-settings',body,headers)
            response=connection.getresponse();return response.status,json.loads(response.read())
        finally:connection.close()

    def test_loopback_required_and_scene_envelope_exceeds_old_limit_safely(self):
        body=json.dumps(self.request).encode()
        status,_=self.post(body,origin=False);self.assertEqual(status,403);self.assertFalse(self.file.exists())
        status,result=self.post(body+b' '*16_000_000)
        self.assertEqual(status,200,result);self.assertEqual(json.loads(self.file.read_text('utf-8'))['scene'],self.request['scene'])
        before=self.file.read_bytes();status,_=self.post(b'',length=128*1024*1024)
        self.assertEqual(status,400);self.assertEqual(self.file.read_bytes(),before)

    def test_static_scene_files_are_available(self):
        for path in ('/scene-assets.js','/scene-assets.css'):
            connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=10)
            try:
                connection.request('GET',path);response=connection.getresponse()
                self.assertEqual(response.status,200);self.assertTrue(response.read())
            finally:connection.close()


if __name__=='__main__':unittest.main()
