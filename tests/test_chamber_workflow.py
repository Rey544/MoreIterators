import copy,hashlib,json,unittest
from unittest.mock import patch
import test_chamber_presets as presets
import chamber_presets,room_bindings,room_editor,storage,server,chamber_sizes


class ChamberWorkflowTests(presets.ChamberPresetTests):
    def test_replacement_refreshes_imported_file_manifest(self):
        import project_packages
        project=chamber_presets.create({'presetId':'mi-chamber-multi-screen'},server)['project'];pid=project['projectId'];directory=storage.project_file(pid).parent;binding=room_bindings.binding(project)
        metadata=dict(schema=project_packages.LOCAL_SCHEMA,projectId=pid,rooms=[dict(name=binding['ai'],kind='ai',region=binding['region'],connections=[binding['entry']],sourceAvailable=True)],files=project_packages._records({file.relative_to(directory).as_posix():file.read_bytes() for file in chamber_presets.room_files(project) if project_packages._local_file(file.relative_to(directory).as_posix())}))
        (directory/project_packages.LOCAL_MANIFEST).write_text(json.dumps(metadata),'utf-8')
        chamber_presets.replace({'project':project,'presetId':'mi-chamber-moon','token':chamber_presets.state(pid)['token']},server)
        current=project_packages.load_metadata(pid)
        for item in current['files']:
            self.assertEqual(item['sha256'],hashlib.sha256((directory/item['path']).read_bytes()).hexdigest())
        names=[item['path'] for item in current['files']]
        self.assertNotIn('rooms/rendered/'+binding['ai']+'_3.png',names)
        self.assertIn('rooms/rendered/'+binding['ai']+'_settings-red.txt',names)

    def test_replacement_preserves_identity_other_work_and_waiting_room(self):
        project=chamber_presets.create({'presetId':'mi-chamber-multi-screen'},server)['project'];pid=project['projectId'];directory=storage.project_file(pid).parent
        old=copy.deepcopy(project);waiting=room_bindings.binding(project)['entry']
        hashes={str(f.relative_to(directory)):hashlib.sha256(f.read_bytes()).hexdigest() for f in directory.rglob('*') if f.is_file() and waiting in f.name}
        result=chamber_presets.replace({'project':project,'presetId':'mi-chamber-moon','token':chamber_presets.state(pid)['token']},server)
        after=result['project'];room=room_bindings.binding(after)['ai']
        for key in ('projectId','name','textures','dialogue','editor'):self.assertEqual(after.get(key),old.get(key),key)
        self.assertEqual({k:v for k,v in after['design'].items() if k not in ('roomPaletteMode','roomGravityMode')},{k:v for k,v in old['design'].items() if k not in ('roomPaletteMode','roomGravityMode')})
        self.assertEqual({str(f.relative_to(directory)):hashlib.sha256(f.read_bytes()).hexdigest() for f in directory.rglob('*') if f.is_file() and waiting in f.name},hashes)
        self.assertFalse((directory/'rooms/rendered'/(room+'_3.png')).exists())
        self.assertTrue((directory/'rooms/rendered'/(room+'_2.png')).exists())
        from pathlib import Path
        backup=Path(result['backup']);self.assertTrue((backup/'rooms/rendered'/(room+'_3.png')).is_file())
        self.assertEqual(json.loads((backup/'project.json').read_text('utf-8')),old)
        room_editor.ensure_synced(pid,room)
        self.assertEqual(storage.load_project(pid),after)

    def test_stale_replacement_and_failed_write_preserve_every_existing_file(self):
        project=chamber_presets.create({'presetId':'mi-chamber-pebbles'},server)['project'];pid=project['projectId']
        request={'project':project,'presetId':'mi-chamber-moon','token':'wrong'};before=self.snapshot()
        with self.assertRaises(ValueError):chamber_presets.replace(request,server)
        self.assertEqual(before,self.snapshot())
        request['token']=chamber_presets.state(pid)['token']
        with patch.object(room_bindings,'plan',side_effect=OSError('failure')):
            with self.assertRaises(OSError):chamber_presets.replace(request,server)
        self.assertEqual(before,self.snapshot())

    def test_preview_and_size_listing_do_not_write_any_project(self):
        before=self.snapshot()
        for row in chamber_presets.listing()['presets']:
            self.assertTrue(chamber_presets.preview(row['id']).startswith(b'\x89PNG'))
            self.assertIn('original',[v['id'] for v in row['sizes']])
            self.assertTrue(any(v['rows']>1 for v in row['sizes']))
        self.assertEqual(before,self.snapshot())

    def test_replacement_exports_new_connections_before_apply_without_reprioritizing_waiting_room(self):
        import os,time,project_packages,standalone,room_asset_dependencies
        for kind in ('none','imported','legacy'):
            with self.subTest(metadata=kind):
                project=chamber_presets.create({'presetId':'mi-chamber-pebbles'},server)['project']
                pid=project['projectId'];binding=room_bindings.binding(project);room,entry=binding['ai'],binding['entry']
                directory=storage.project_file(pid).parent
                world=storage.target_mod(pid)/'world'/binding['region'].lower()/('world_'+binding['region'].lower()+'.txt')
                world.parent.mkdir(parents=True,exist_ok=True)
                world.write_text('ROOMS\n'+room+' : DISCONNECTED, '+entry+'\n'+entry+' : '+room+'\nEND ROOMS\n','utf-8')
                os.utime(world,ns=(2_000_000_000,2_000_000_000))
                old_world=world.read_bytes()
                if kind!='none':
                    metadata=dict(schema=project_packages.LOCAL_SCHEMA,projectId=pid,files=[],rooms=[dict(name=room,kind='ai',region=binding['region'],sourceAvailable=True,connections=['DISCONNECTED',entry],tags=''),dict(name=entry,kind='entry',region=binding['region'],sourceAvailable=True,connections=['DISCONNECTED'],tags='SHELTER')])
                    if kind=='imported':metadata['importedAtNs']=1_000_000_000
                    manifest=directory/project_packages.LOCAL_MANIFEST;manifest.write_text(json.dumps(metadata),'utf-8');os.utime(manifest,ns=(1_000_000_000,1_000_000_000))
                result=chamber_presets.replace({'project':project,'presetId':'mi-chamber-moon','token':chamber_presets.state(pid)['token']},server)
                after=result['project'];metadata=project_packages.load_metadata(pid)
                ai_row=next(row for row in metadata['rooms'] if row['name']==room)
                self.assertEqual(ai_row['connections'],[entry]);self.assertGreater(ai_row['updatedAtNs'],world.stat().st_mtime_ns)
                self.assertEqual(world.read_bytes(),old_world)
                if kind=='none':self.assertEqual([row['name'] for row in metadata['rooms']],[room])
                else:
                    self.assertEqual(metadata['importedAtNs'],1_000_000_000)
                    waiting=next(row for row in metadata['rooms'] if row['name']==entry)
                    self.assertNotIn('updatedAtNs',waiting);self.assertEqual(waiting['connections'],['DISCONNECTED'])
                self.assertEqual(project_packages.selected_room_connections(after,room,room_editor.cached_source(pid,room),{})[0],[entry])
                self.assertEqual(project_packages.selected_room_connections(after,entry,room_editor.cached_source(pid,entry),{})[0],[room])
                assets=lambda project,source,text:{paths[0]:self.fixture.local/'palettes/palette9100.png' for paths in room_asset_dependencies.references(text) if paths[0].endswith('.png')}
                with patch.object(standalone,'room_palette_source',return_value=self.fixture.local/'palettes/palette9100.png'),patch.object(standalone,'room_settings_assets',side_effect=assets),patch.object(room_asset_dependencies,'has_native_ambient_reference',return_value=True):
                    exported=project_packages.export_package(pid,[],server)
                files=self.fixture.unpack((storage.EXPORTS/exported['url'].split('/')[-1]).read_bytes())
                manifest=json.loads(files['manifest.json'])
                self.assertEqual(next(row['connections'] for row in manifest['rooms'] if row['name']==room),[entry])
                self.assertEqual(next(row['connections'] for row in manifest['rooms'] if row['name']==entry),[room])
                world.write_text('ROOMS\n'+room+' : DISCONNECTED\n'+entry+' : '+room+'\nEND ROOMS\n','utf-8')
                os.utime(world,ns=(time.time_ns()+1_000_000,time.time_ns()+1_000_000))
                self.assertEqual(project_packages.selected_room_connections(after,room,room_editor.cached_source(pid,room),{})[0],['DISCONNECTED'])

    def test_dimensions_preserve_shortcut_flags_and_actual_camera_grid(self):
        from room_lingo import parse
        for name,size in [('pebbles',(140,40)),('broken',(70,80)),('moon',(140,80))]:
            root,spec=chamber_presets.get('mi-chamber-'+name);assets=chamber_presets.validated_assets(root,spec)
            original=parse(assets['source']['.txt'].decode('utf-8-sig').splitlines()[0])
            output,light,shift=chamber_sizes.resize_source(assets['source']['.txt'],assets['source']['.png'],*size)
            values=[parse(v) for v in output.decode().splitlines()]
            flags=lambda g:sorted(flag for col in g for cell in col for flag in cell[0][1] if flag in (4,6))
            self.assertEqual(flags(original),flags(values[0]))
            self.assertEqual(len(values[6]['cameras']),size[0]//70*(size[1]//40))
            self.assertEqual((len(values[0])-24,len(values[0][0])-8),size)
            self.assertTrue(light.startswith(b'\x89PNG'))

    def test_largest_dimensions_keep_every_native_shortcut_cell_and_connection(self):
        from room_lingo import parse
        cases=[(row['id'],'3x3') for row in chamber_presets.listing()['presets']]
        cases.extend([('mi-chamber-pebbles','2x1'),('mi-chamber-broken','1x2'),('mi-chamber-moon','2x2')])
        for preset,size_id in cases:
            with self.subTest(preset=preset,size=size_id):
                root,spec=chamber_presets.get(preset);assets=chamber_presets.validated_assets(root,spec)
                size=next(row for row in chamber_sizes.options(spec) if row['id']==size_id)
                original=[parse(line) for line in assets['source']['.txt'].decode('utf-8-sig').splitlines()[:9]]
                output,light,shift=chamber_sizes.resize_source(assets['source']['.txt'],assets['source']['.png'],size['width'],size['height'])
                changed=[parse(line) for line in output.decode('utf-8').splitlines()]
                left,top,right,bottom=original[5]['extraTiles'];oldw,oldh=len(original[0]),len(original[0][0])
                sx=left+shift['x']//20;sy=oldh-bottom-shift['y']//20
                dx,dy=shift['dx']//20,shift['dy']//20
                transform=lambda point:(point[0]+(dx if point[0]>=sx else 0),point[1]+(dy if point[1]>=sy else 0))
                cells=lambda geometry:{(x,y):cell[0] for x,col in enumerate(geometry) for y,cell in enumerate(col) if cell[0][0]==7 or set(cell[0][1])&{4,5,6,7,8}}
                before,after=cells(original[0]),cells(changed[0])
                self.assertEqual(after,{transform(point):cell for point,cell in before.items()})
                self.assertEqual(sum(cell[0]==7 for cell in before.values()),sum(cell[0]==7 for cell in after.values()))
                self.assertEqual(sum(6 in cell[1] for cell in before.values()),sum(6 in cell[1] for cell in after.values()))
                for point in before:
                    for neighbor in ((point[0]+1,point[1]),(point[0],point[1]+1)):
                        if neighbor not in before:continue
                        a,b=transform(point),transform(neighbor)
                        self.assertEqual(abs(a[0]-b[0])+abs(a[1]-b[1]),1)
                self.assertEqual(len(changed[6]['cameras']),size['cameraCount'])


if __name__=='__main__':unittest.main()
