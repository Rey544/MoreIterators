import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import unittest
import urllib.parse
import urllib.request
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_room_identity_workflow as workflow


class RoomRenameCleanupTests(unittest.TestCase):
    start=workflow.RoomIdentityWorkflowTests.start
    stop=workflow.RoomIdentityWorkflowTests.stop
    request=workflow.RoomIdentityWorkflowTests.request

    def setUp(self):
        injection='''
import room_cleanup
original_retire=room_cleanup.retire_migration
def retire(*args,**kwargs):
    original_retire(*args,**kwargs)
    if (storage.DATA/'fail-after-retire.fixture').is_file():raise ValueError('fixture failure after retirement')
room_cleanup.retire_migration=retire
server.server_lifecycle'''
        replacement=patch.object(workflow,'BOOT',workflow.BOOT.replace(';server.server_lifecycle',injection))
        replacement.start();self.addCleanup(replacement.stop)
        workflow.RoomIdentityWorkflowTests.setUp(self)
        self.pid=next(project['projectId'] for project in self.request('/api/projects') if project['name']=='PL workflow fixture')
        self.query=urllib.parse.urlencode({'projectId':self.pid})
        self.original=self.request('/api/room-binding?'+self.query)['binding']
        self.target=dict(self.original,region='PL',ai='PL_AI',entry='PL_POOL',entryMode='copy')
        self.project_root=self.data/'projects'/self.pid
        self.local=self.data/'local-mod'
        self.installed=self.assets/'mods/more_iterators_local'
        ambient=self.assets/'soundeffects/ambient';ambient.mkdir(parents=True)
        for name in ('am_ind-superstructure.ogg','am_win-strongwnd2.ogg','so_sfx-datatrans2.ogg'):
            (ambient/name).write_bytes(b'OggS'+bytes(60))

    def apply(self,binding=None,revision=None,status=200,language='zh-CN'):
        data={'projectId':self.pid,'binding':binding or self.target}
        plan=self.request('/api/room-binding/preview',data)
        data['token']=plan['token']
        if revision is not None:data['draftRevision']=revision
        return self.request('/api/room-binding/apply',data,status=status,language=language)

    def files(self):
        result={}
        for root in (self.data,self.assets/'mods'):
            for file in root.rglob('*'):
                if not file.is_file() or '/archive/logs/' in file.as_posix():continue
                result[file.relative_to(self.folder).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
        return result

    def old_files(self):
        names=(self.original['ai'],self.original['entry']);result={}
        for scope,root in (('source',self.project_root/'rooms'),('rendered',self.project_root/'rooms/rendered'),('local',self.local),('installed',self.installed)):
            folder=root if scope in ('source','rendered') else root/'world/test-rooms'
            for file in folder.iterdir():
                if file.is_file() and any(re.fullmatch(re.escape(name)+r'(?:\.txt|\.png|_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|_[1-9][0-9]*\.png|\.source\.json)',file.name) for name in names):
                    result[(scope,file.relative_to(root).as_posix())]=(file,file.read_bytes())
        return result

    def test_legacy_outputs_all_versions_are_backed_up_and_removed(self):
        self.apply(self.original)
        (self.project_root/'room-ownership.json').unlink()
        old_ai=self.original['ai'];old_entry=self.original['entry']
        for scope,root in (('local',self.local),('installed',self.installed)):
            file=root/'world/test-rooms'/(old_ai+'_settings.txt')
            file.write_text(file.read_text('utf-8')+'\nRainIntensity: '+('0.33' if scope=='local' else '0.66')+'\n','utf-8')
        variant=self.project_root/'rooms/rendered'/(old_ai+'_settings-Saint.txt')
        variant.write_text('Palette: 26\nRainIntensity: 0.7\n','utf-8')
        near=self.local/'world/test-rooms'/(old_ai+'_OTHER.txt');near.write_text('unrelated similarly named room','utf-8')
        old=self.old_files()
        self.assertNotEqual(old[('local','world/test-rooms/'+old_ai+'_settings.txt')][1],old[('installed','world/test-rooms/'+old_ai+'_settings.txt')][1])
        pearl=self.data/'pearl-projects/fixture/pearls/A01/pearl.json';pearl.parent.mkdir(parents=True)
        original_text='台词必须保留 '+old_ai+' '+old_entry
        pearl.write_text(json.dumps(dict(schema='moreiterators.pearl.v1',revision=4,spawnRooms=[old_ai,old_entry],spawnRoomPositions={old_ai:dict(x=.4,y=.5)},readers=[dict(text=original_text)])),'utf-8')
        unrelated=pearl.parent.parent/'A02/pearl.json';unrelated.parent.mkdir(parents=True)
        unrelated_bytes=json.dumps(dict(schema='moreiterators.pearl.v1',revision=9,readers=[dict(text='另一颗珍珠')])).encode('utf-8')
        unrelated.write_bytes(unrelated_bytes)
        runtime=self.data/'runtime/pearls/A01.json';runtime.parent.mkdir(parents=True)
        runtime.write_text(json.dumps(dict(schema='moreiterators.pearl.v1',readers=[],spawns=[dict(projectId='',entry=old_ai)],text=original_text)),'utf-8')
        self.apply()
        backup=next((self.project_root/'room-backups').iterdir())
        manifest=json.loads((backup/'manifest.json').read_text('utf-8'))
        self.assertEqual(len(manifest['files']),len(old))
        for (scope,relative),(file,content) in old.items():
            self.assertFalse(file.exists(),str(file))
            self.assertEqual((backup/scope/relative).read_bytes(),content)
        self.assertEqual(near.read_text('utf-8'),'unrelated similarly named room')
        self.assertTrue((self.installed/'world/pl-rooms/PL_AI_settings-Saint.txt').is_file())
        authored=json.loads(pearl.read_text('utf-8'));applied=json.loads(runtime.read_text('utf-8'))
        self.assertEqual(authored['spawnRooms'],['PL_AI','PL_POOL'])
        self.assertEqual(authored['spawnRoomPositions'],{'PL_AI':dict(x=.4,y=.5)})
        self.assertEqual(authored['readers'][0]['text'],original_text)
        self.assertEqual(applied['spawns'][0]['entry'],'PL_AI')
        self.assertEqual(applied['text'],original_text)
        self.assertEqual(unrelated.read_bytes(),unrelated_bytes)
        self.assertFalse((self.local/'world/test/world_test.txt').exists())
        self.assertFalse((self.installed/'world/test/world_test.txt').exists())
        ledger=json.loads((self.project_root/'room-ownership.json').read_text('utf-8'))
        self.assertEqual({row['name'] for row in ledger['rooms']},{'PL_AI','PL_POOL'})
        for room in ('PL_AI','PL_POOL'):
            sidecar=json.loads((self.project_root/'rooms/rendered'/(room+'.source.json')).read_text('utf-8'))
            self.assertEqual(sidecar['room'],room)
            self.assertEqual(sidecar['projectId'],self.pid)
            self.assertTrue((self.project_root/'rooms'/(room+'.txt')).is_file())

    def test_rollback_after_old_files_deleted_restores_every_file_and_timestamp(self):
        self.apply(self.original)
        draft=self.request('/api/room-draft',dict(projectId=self.pid,binding=dict(self.original,region='PL_'),revision=0))
        (self.data/'fail-after-retire.fixture').write_text('fail','utf-8')
        before=self.files();times={file:file.stat().st_mtime_ns for file,_ in self.old_files().values()}
        result=self.apply(revision=draft['revision'],status=400)
        self.assertIn('fixture failure after retirement',result['error'])
        self.assertEqual(self.files(),before)
        self.assertTrue(all(file.stat().st_mtime_ns==mtime for file,mtime in times.items()))
        self.assertEqual(self.request('/api/room-binding?'+self.query)['binding'],self.original)
        self.assertEqual(self.request('/api/room-draft?'+self.query)['revision'],draft['revision'])

    def test_external_reference_blocks_entire_rename(self):
        self.apply(self.original)
        world=self.assets/'mods/foreign/world/zz/world_zz.txt';world.parent.mkdir(parents=True)
        world.write_text('ROOMS\nZZ_TEST : '+self.original['ai']+'\nEND ROOMS\n','utf-8')
        before=self.files();result=self.apply(status=400,language='en')
        self.assertIn(self.original['ai'],result['error'])
        self.assertEqual(result['code'],'rooms.error.migrationWorldReference')
        self.assertEqual(result['params']['room'],self.original['ai'])
        self.assertEqual(Path(result['params']['file']),world)
        self.assertNotRegex(result['error'],r'[\u3400-\u9fff]')
        self.assertEqual(self.files(),before)
        self.assertTrue(world.is_file())

    def test_extra_rooms_with_core_prefix_never_overwrite_unowned_files(self):
        exported=self.request('/api/export-project-package',dict(projectId=self.pid,extraRooms=[]))
        archive=self.data/'exports'/exported['url'].rsplit('/',1)[-1]
        req=urllib.request.Request(self.base+'/api/import-project-package',data=archive.read_bytes(),headers={'Origin':self.base,'X-MI-Replace-Project':'1','X-MI-Language':'zh-CN','Content-Type':'application/zip'})
        with urllib.request.urlopen(req,timeout=45) as response:self.assertTrue(json.load(response)['ok'])
        metadata_file=self.project_root/'room-package.json';metadata=json.loads(metadata_file.read_text('utf-8'))
        for name in ('PL_AI2','PL_AI_SIDE'):
            metadata['rooms'].append(dict(name=name,region='PL',kind='extra',connections=['DISCONNECTED','DISCONNECTED'],tags='',sourceAvailable=False,sourceOrigin='project',settingsOrigin='project'))
            for suffix in ('.txt','_settings.txt','_1.png'):
                content=(self.project_root/'rooms/rendered'/(self.original['ai']+suffix)).read_bytes()
                if suffix=='.txt':
                    lines=content.decode('utf-8-sig').splitlines();lines[0]=name;content=('\n'.join(lines)+'\n').encode('utf-8')
                path='rooms/rendered/'+name+suffix;(self.project_root/path).write_bytes(content)
                metadata['files'].append(dict(path=path,size=len(content),sha256=hashlib.sha256(content).hexdigest()))
        metadata_file.write_text(json.dumps(metadata,ensure_ascii=False),'utf-8')
        for root in (self.local,self.installed):
            for name in ('PL_AI2','PL_AI_SIDE'):
                with self.subTest(root=str(root),name=name):
                    file=root/'world/pl-rooms'/(name+'.txt');file.parent.mkdir(parents=True,exist_ok=True)
                    content=b'unowned room must not be overwritten';file.write_bytes(content)
                    future=time.time_ns()+60_000_000_000
                    os.utime(self.project_root/'rooms/rendered'/(name+'.txt'),ns=(future,future))
                    try:
                        before=self.files();result=self.apply(status=400,language='en')
                        self.assertIn(name,result['error'])
                        self.assertEqual(result['code'],'rooms.error.migrationUnownedFile')
                        self.assertEqual(result['params']['file'],'world/pl-rooms/'+name+'.txt')
                        self.assertNotRegex(result['error'],r'[\u3400-\u9fff]')
                        self.assertEqual(file.read_bytes(),content)
                        self.assertEqual(self.files(),before)
                    finally:file.unlink(missing_ok=True)

    def test_existing_target_source_reports_filename_in_english_without_writes(self):
        file=self.project_root/'rooms/PL_AI.txt';file.write_bytes(b'another authored source project')
        before=self.files();result=self.apply(status=400,language='en')
        self.assertEqual(result['code'],'rooms.error.migrationTargetExists')
        self.assertIn('PL_AI',result['params']['file'])
        self.assertIn('PL_AI',result['error'])
        self.assertNotRegex(result['error'],r'[\u3400-\u9fff]')
        self.assertEqual(self.files(),before)

    def test_imported_package_rename_can_be_saved_and_exported_again(self):
        exported=self.request('/api/export-project-package',dict(projectId=self.pid,extraRooms=[]))
        archive=self.data/'exports'/exported['url'].rsplit('/',1)[-1]
        req=urllib.request.Request(self.base+'/api/import-project-package',data=archive.read_bytes(),headers={'Origin':self.base,'X-MI-Replace-Project':'1','X-MI-Language':'zh-CN','Content-Type':'application/zip'})
        with urllib.request.urlopen(req,timeout=45) as response:self.assertTrue(json.load(response)['ok'])
        metadata_file=self.project_root/'room-package.json'
        metadata=json.loads(metadata_file.read_text('utf-8'))
        metadata['rooms'].append(dict(name='TEST_EXTRA',region='TEST',kind='extra',connections=[self.original['ai'],'DISCONNECTED'],tags='',sourceAvailable=False,sourceOrigin='project',settingsOrigin='project'))
        for suffix in ('.txt','_settings.txt','_1.png'):
            content=(self.project_root/'rooms/rendered'/(self.original['ai']+suffix)).read_bytes()
            if suffix=='.txt':
                lines=content.decode('utf-8-sig').splitlines();lines[0]='TEST_EXTRA';content=('\n'.join(lines)+'\n').encode('utf-8')
            path='rooms/rendered/TEST_EXTRA'+suffix
            (self.project_root/path).write_bytes(content)
            metadata['files'].append(dict(path=path,size=len(content),sha256=hashlib.sha256(content).hexdigest()))
        metadata_file.write_text(json.dumps(metadata,ensure_ascii=False),'utf-8')
        self.apply(self.original)
        palette=next((self.local/'palettes').glob('palette*.png'))
        relative=palette.relative_to(self.local).as_posix();palette_bytes=palette.read_bytes()
        for target in (self.local,self.installed):
            marker=target/'.mi-project-package-assets.json';manifest=json.loads(marker.read_text('utf-8'))
            manifest['projects'][self.pid].remove(relative);marker.write_text(json.dumps(manifest),'utf-8')
        (self.installed/relative).unlink()
        self.apply()
        self.assertEqual(palette.read_bytes(),palette_bytes)
        self.assertEqual((self.installed/relative).read_bytes(),palette_bytes)
        metadata=json.loads((self.project_root/'room-package.json').read_text('utf-8'))
        self.assertEqual({room['name'] for room in metadata['rooms']},{'PL_AI','PL_POOL','TEST_EXTRA'})
        self.assertEqual(next(room['connections'] for room in metadata['rooms'] if room['name']=='TEST_EXTRA'),['PL_AI','DISCONNECTED'])
        self.assertIn('TEST_EXTRA : PL_AI, DISCONNECTED',(self.local/'world/test/world_test.txt').read_text('utf-8'))
        for item in metadata['files']:
            file=self.project_root/item['path']
            self.assertTrue(file.is_file(),item['path'])
            self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),item['sha256'])
        project=json.loads((self.project_root/'project.json').read_text('utf-8'))
        self.request('/api/save',project)
        exported=self.request('/api/export-project-package',dict(projectId=self.pid,extraRooms=['TEST_EXTRA']))
        with zipfile.ZipFile(self.data/'exports'/exported['url'].rsplit('/',1)[-1]) as archive:
            manifest=json.loads(archive.read('manifest.json'))
            self.assertEqual({room['name'] for room in manifest['rooms']},{'PL_AI','PL_POOL','TEST_EXTRA'})
            self.assertTrue(all(self.original['ai'] not in name and self.original['entry'] not in name for name in archive.namelist()))
        self.apply()


if __name__=='__main__':unittest.main()
