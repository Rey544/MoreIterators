import copy
import io
import json
from contextlib import contextmanager
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import unquote
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import test_standalone_extra_rooms as fixtures
import project_bundles
import project_packages
import playable_export
import server
import standalone
import storage


class MultiProjectExportTests(unittest.TestCase):
    @contextmanager
    def fixture(self,count,connected=True):
        fixture=fixtures.ExtraRoomExportTests();fixture.setUp()
        try:
            projects={};graph={}
            for index in range(count):
                ai=f'ZX_I{index}_AI';entry=f'ZX_I{index}_ENTRY'
                graph[ai]=[entry,f'ZX_I{index-1}_ENTRY' if connected and index else 'DISCONNECTED']
                graph[entry]=[ai,f'ZX_I{index+1}_AI' if connected and index+1<count else 'DISCONNECTED']
                for name in (ai,entry):
                    fixture.render(fixture.source(name),name)
                    fixture.render(fixture.local/'world/zx-rooms'/name,name)
            for index in range(count):
                pid='iterator-'+str(index);project=copy.deepcopy(fixture.project)
                project.update(projectId=pid,name='Iterator '+str(index))
                project['roomBinding'].update(ai=f'ZX_I{index}_AI',entry=f'ZX_I{index}_ENTRY',oracleId=pid)
                owned={project['roomBinding']['ai']:'ai',project['roomBinding']['entry']:'entry'}
                project['roomConnections']=dict(version=2,ownedRegions=['ZX'],rows=[dict(name=name,region='ZX',connections=links,tags='',owned=name in owned,**({'kind':owned[name]} if name in owned else {})) for name,links in graph.items()])
                file=storage.project_file(pid);file.parent.mkdir(parents=True,exist_ok=True);file.write_text(json.dumps(project),'utf-8')
                projects[pid]=project
            rows=[dict(name=name,region='ZX',connections=links,tags='',kind='extra',sourceAvailable=True) for name,links in graph.items()]
            (fixture.local/'world/zx/world_zx.txt').write_text('ROOMS\n'+'\n'.join(name+' : '+', '.join(links) for name,links in graph.items())+'\nEND ROOMS\n','utf-8')
            request={**fixture.request,'projects':list(projects),'name':'Several iterators','description':'','settingsProject':'iterator-0','startRoom':'ZX_I0_ENTRY'}
            def metadata(pid):
                if pid not in projects:return copy.deepcopy(fixture.package)
                owned=projects[pid]['roomBinding']
                selected=[dict(row,kind='ai' if row['name']==owned['ai'] else 'entry') for row in rows if row['name'] in (owned['ai'],owned['entry'])]
                return dict(schema=project_packages.LOCAL_SCHEMA,projectId=pid,rooms=selected,regions=[],palettes=[],files=[])
            with patch.object(storage,'load_project',side_effect=lambda pid:copy.deepcopy(projects[pid])),patch.object(project_packages,'load_metadata',side_effect=metadata):
                yield fixture,request,graph
        finally:fixture.doCleanups()

    def build(self,request,kind):
        if kind=='project':reply=project_bundles.export_package({**request,'packageName':'Several iterators','packageVersion':'0.1.0'},server)
        elif kind=='mod':reply=standalone.build(request,server,save_preferences=False)
        else:reply=playable_export.build({**request,'scope':'project'},server)
        return zipfile.ZipFile(storage.EXPORTS/unquote(Path(reply['url']).name))

    def graph(self,archive,request):
        text=archive.read(request['id']+'/world/zx/world_zx.txt').decode()
        return {line.split(' : ')[0]:line.split(' : ')[1].split(', ') for line in text.splitlines() if ' : ' in line}

    def test_three_five_and_ten_projects_retain_every_work_and_authored_connection(self):
        for count in (3,5,10):
            with self.fixture(count) as (fixture,request,graph):
                before={path:path.read_bytes() for path in fixture.data.rglob('*') if path.is_file()}
                for kind in ('project','mod','playable'):
                    with self.subTest(count=count,kind=kind),self.build(request,kind) as archive:
                        if kind=='project':
                            manifest=json.loads(archive.read('bundle.json'))
                            self.assertEqual([row['projectId'] for row in manifest['projects']],request['projects'])
                            for row in manifest['projects']:
                                with zipfile.ZipFile(io.BytesIO(archive.read(row['path']))) as inner:
                                    project=json.loads(inner.read('project.json'))
                                    self.assertEqual(project['projectId'],row['projectId'])
                                    self.assertEqual(len(project['roomConnections']['rows']),count*2)
                        else:
                            records=json.loads(archive.read(request['id']+'/moreiterators/registry.json'))
                            self.assertEqual([row['projectId'] for row in records],request['projects'])
                            self.assertEqual(self.graph(archive,request),graph)
                self.assertEqual(before,{path:path.read_bytes() for path in fixture.data.rglob('*') if path.is_file()})

    def test_project_order_does_not_change_links_or_playable_reachability(self):
        with self.fixture(5) as (fixture,request,graph):
            ids=request['projects']
            for ordered in (ids,list(reversed(ids)),ids[2:]+ids[:2]):
                for kind in ('mod','playable'):
                    with self.subTest(order=ordered,kind=kind),self.build(dict(request,projects=ordered),kind) as archive:
                        self.assertEqual(self.graph(archive,request),graph)

    def test_disconnected_projects_stay_disconnected_and_playable_export_reports_them(self):
        with self.fixture(3,False) as (fixture,request,graph):
            with self.build(request,'mod') as archive:self.assertEqual(self.graph(archive,request),graph)
            with self.assertRaisesRegex(ValueError,'起始房间无法通往所选演算室'):self.build(request,'playable')


if __name__=='__main__':unittest.main()
