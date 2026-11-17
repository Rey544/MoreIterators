import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import unquote

import test_project_packages as fixtures
import project_bundles
import project_packages
import pearl_projects
import pearls
import storage


class BundlePearlValidationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ProjectPackageTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.cid='a'*32
        catalog=storage.DATA/'pearl-projects.json'
        catalog.write_text(json.dumps(dict(schema=pearl_projects.SCHEMA,projects=[dict(id=self.cid,name='Pearls')],activeId=self.cid)),'utf-8')
        self.value=pearls.default(self.cid)
        self.value.update(spawnProjects=['selected','external-reader'],spawnPositions={'external-reader':{'x':.5,'y':.6}},spawnRooms=['OTHER_ROOM'],spawnRoomPositions={'OTHER_ROOM':{'x':.4,'y':.3}})
        self.value['readers']=[dict(projectId='external-reader',requireMark=True,repeatEnabled=False,repeatPrependCommon=False,repeat=[],leavePolicy='resume',read=[dict(lineId='b'*32,text='Original line',hold=2.5,gap=.6)],leaving=[],returning=[])]
        self.file=pearls.path(self.value['id'],self.cid)
        self.file.parent.mkdir(parents=True)
        self.file.write_text(json.dumps(self.value),'utf-8')
        self.path='content/pearl-projects/'+self.cid+'/pearls/'+self.value['id']+'/pearl.json'

    def export(self):
        result=project_bundles.export_package(dict(projects=['selected'],pearls=True,pearlCollectionId=self.cid),self.fixture.server)
        return (storage.EXPORTS/unquote(Path(result['url']).name)).read_bytes()

    def snapshot(self):
        return {path.relative_to(self.fixture.root).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in self.fixture.root.rglob('*') if path.is_file() and not path.is_relative_to(storage.EXPORTS)}

    def test_valid_structure_preserves_external_references_and_original_text(self):
        before=self.snapshot()
        with patch.object(pearls,'reference_project',side_effect=AssertionError('Must not resolve another author project')), \
             patch.object(pearls,'destinations',side_effect=AssertionError('Must not require live catalogue')), \
             patch.object(pearls,'spawn_geometry',side_effect=AssertionError('Must not require another project geometry')), \
             patch.object(pearls,'room_geometry',side_effect=AssertionError('Must not require another room geometry')):
            payload=self.export()
            files=self.fixture.unpack(payload)
            self.assertEqual(json.loads(files[self.path]),self.value)
            summary=project_bundles.inspect_import(payload,self.fixture.server)
            result=project_bundles.import_package(payload,self.fixture.server,choices={item['key']:'replace' for item in summary['collisions']})
            self.assertTrue(result['ok'])
            self.assertEqual(json.loads(self.file.read_text('utf-8')),self.value)
        self.assertEqual(self.value['readers'][0]['read'][0]['text'],'Original line')
        self.assertEqual(before[self.file.relative_to(self.fixture.root).as_posix()],hashlib.sha256(self.file.read_bytes()).hexdigest())

    def test_corrupt_pearl_fails_inspection_and_replacement_before_writes(self):
        payload=self.export()
        base=self.fixture.unpack(payload)
        cases={
            'appearance missing':lambda value:value.pop('appearance'),
            'appearance wrong type':lambda value:value.update(appearance=[]),
            'reader invalid':lambda value:value.update(readers=['broken']),
            'line invalid':lambda value:value['readers'][0]['read'][0].update(text=42),
            'duration invalid':lambda value:value['readers'][0]['read'][0].update(hold=-2),
            'repeat invalid':lambda value:value['readers'][0].update(repeatEnabled='true'),
            'position invalid':lambda value:value['spawnPositions']['external-reader'].update(x=2),
            'room position invalid':lambda value:value['spawnRoomPositions']['OTHER_ROOM'].update(y=False),
        }
        before=self.snapshot()
        for label,mutate in cases.items():
            with self.subTest(label=label):
                value=copy.deepcopy(self.value)
                mutate(value)
                files=dict(base)
                files[self.path]=json.dumps(value).encode()
                manifest=json.loads(files['bundle.json'])
                manifest['files']=project_packages._records({name:data for name,data in files.items() if name!='bundle.json'})
                files['bundle.json']=json.dumps(manifest).encode()
                damaged=self.fixture.archive(files)
                for call in (lambda:project_bundles.inspect_import(damaged,self.fixture.server),lambda:project_bundles.import_package(damaged,self.fixture.server,choices={'project/selected':'replace',self.path:'replace'})):
                    with self.assertRaisesRegex(ValueError,'pearl.json'):call()
                self.assertEqual(before,self.snapshot())

    def test_normal_editor_validation_still_resolves_referenced_projects(self):
        before=copy.deepcopy(self.value)
        with patch.object(pearls,'reference_project',side_effect=ValueError('external project unavailable')) as lookup:
            with self.assertRaisesRegex(ValueError,'external project unavailable'):
                pearls.validate(self.value)
            lookup.assert_called_once_with('external-reader')
        self.assertEqual(self.value,before)


if __name__=='__main__':unittest.main()
