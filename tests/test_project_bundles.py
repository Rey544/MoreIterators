import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'editor'))
import test_project_packages as fixtures
import project_bundles as bundles
import project_packages as packages
import room_bindings
import room_migration
import storage


class ProjectBundleTests(unittest.TestCase):
    setUp = fixtures.ProjectPackageTests.setUp
    validate = fixtures.ProjectPackageTests.validate
    palette = fixtures.ProjectPackageTests.palette
    render = fixtures.ProjectPackageTests.render
    unpack = fixtures.ProjectPackageTests.unpack
    archive = fixtures.ProjectPackageTests.archive
    def second(self, region='YY'):
        project = copy.deepcopy(self.project);project.update(projectId='second', name='第二个作品')
        project['roomBinding'].update(region=region, ai=region+'_AI', entry=region+'_ENTRY', oracleId='second_oracle')
        file = storage.project_file('second');file.parent.mkdir(parents=True);file.write_text(json.dumps(project), 'utf-8')
        for suffix in ('AI', 'ENTRY'):self.render(self.local / ('world/'+region.lower()+'-rooms/'+region+'_'+suffix), region+'_'+suffix)
        folder = self.local / ('world/'+region.lower());folder.mkdir(parents=True)
        (folder / ('world_'+region.lower()+'.txt')).write_text('ROOMS\n'+region+'_AI : DISCONNECTED, '+region+'_ENTRY\n'+region+'_ENTRY : '+region+'_AI, DISCONNECTED : SHELTER\nEND ROOMS\n', 'utf-8')
        (folder / 'properties.txt').write_text('Palette: 9100\n', 'utf-8')
        return project

    def export(self, **kwargs):
        result = bundles.export_package(dict(projects=['selected', 'second'], **kwargs), self.server)
        return result, (storage.EXPORTS / unquote(Path(result['url']).name)).read_bytes()

    def snapshot(self):
        return {path.relative_to(self.root).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in self.root.rglob('*') if path.is_file() and not path.is_relative_to(storage.EXPORTS)}

    def test_multi_including_test_keeps_two_editable_projects_and_original_data(self):
        self.second('TEST');before = self.snapshot()
        result, payload = self.export()
        self.assertEqual(before, self.snapshot())
        inspected = bundles.inspect_import(payload, self.server)
        self.assertEqual([row['projectId'] for row in inspected['projects']], ['selected', 'second'])
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertEqual(set(archive.namelist()), {'bundle.json', 'projects/selected.zip', 'projects/second.zip'})
            with zipfile.ZipFile(io.BytesIO(archive.read('projects/second.zip'))) as inner:
                self.assertEqual(json.loads(inner.read('project.json'))['roomBinding']['region'], 'TEST')
        self.assertFalse(bundles.import_package(payload, self.server)['ok'])
        self.assertEqual(before, self.snapshot())
        result = bundles.import_package(payload, self.server, choices={'project/selected':'replace', 'project/second':'replace'})
        self.assertTrue(result['ok']);self.assertEqual(len(result['projects']), 2)

    def test_single_without_associations_remains_old_v1(self):
        result = bundles.export_package(dict(projects=['selected']), self.server)
        payload = (storage.EXPORTS / unquote(Path(result['url']).name)).read_bytes()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertIn('project.json', archive.namelist());self.assertNotIn('bundle.json', archive.namelist())
        self.assertEqual(bundles.inspect_import(payload, self.server)['projectId'], 'selected')

    def test_pending_and_valid_projects_roundtrip_without_changing_originals(self):
        self.second()
        world=self.local/'world/xx/world_xx.txt'
        world.write_text('ROOMS\nXX_AI : DISCONNECTED, XX_ENTRY\nXX_ENTRY : XX_AI\nEND ROOMS\n','utf-8')
        before=self.snapshot()
        result,payload=self.export()
        self.assertTrue(result['connectionsPending'])
        self.assertEqual(result['pendingConnectionProjects'],['selected'])
        self.assertEqual(self.snapshot(),before)
        inspected=bundles.inspect_import(payload,self.server)
        self.assertTrue(inspected['connectionsPending'])
        self.assertEqual(inspected['pendingConnectionProjects'],['selected'])
        outer=self.unpack(payload)
        inner={pid:self.unpack(outer['projects/'+pid+'.zip']) for pid in ('selected','second')}
        fixtures.ProjectPackageTests.target(self)
        imported=bundles.import_package(payload,self.server)
        self.assertTrue(imported['connectionsPending'])
        self.assertEqual(imported['pendingConnectionProjects'],['selected'])
        self.assertFalse(storage.RUNTIME.exists());self.assertFalse(self.installed.exists())
        receiver_before=self.snapshot()
        exported,second_payload=self.export()
        self.assertEqual(exported['pendingConnectionProjects'],['selected'])
        self.assertEqual(self.snapshot(),receiver_before)
        second_outer=self.unpack(second_payload)
        for pid in ('selected','second'):
            second_inner=self.unpack(second_outer['projects/'+pid+'.zip'])
            self.assertEqual({k:v for k,v in inner[pid].items() if k!='manifest.json'},
                             {k:v for k,v in second_inner.items() if k!='manifest.json'})
            original_rows=json.loads(inner[pid]['manifest.json'])['rooms'];reexported_rows=json.loads(second_inner['manifest.json'])['rooms']
            self.assertEqual([{k:v for k,v in row.items() if k not in ('sourceOrigin','settingsOrigin')} for row in original_rows],
                             [{k:v for k,v in row.items() if k not in ('sourceOrigin','settingsOrigin')} for row in reexported_rows])

    def test_failure_in_later_project_rolls_back_every_earlier_write(self):
        self.second();_, payload = self.export()
        old = json.loads(self.project_file.read_text('utf-8'));old['name']='原作品必须保留';self.project_file.write_text(json.dumps(old), 'utf-8')
        before = self.snapshot();original = room_migration.Files.write;failed = False
        def failing(transaction, file, content):
            nonlocal failed
            if not failed and Path(file) == storage.project_file('second'):
                failed = True;raise OSError('injected disk failure')
            return original(transaction, file, content)
        with patch.object(room_migration.Files, 'write', failing):
            with self.assertRaisesRegex(OSError, 'injected'):
                bundles.import_package(payload, self.server, choices={'project/selected':'replace', 'project/second':'replace'})
        self.assertEqual(before, self.snapshot())

    def test_corrupt_second_project_preflight_never_writes_first(self):
        self.second();_, payload = self.export();files = self.unpack(payload)
        files['projects/second.zip'] = b'broken';payload = self.archive(files);before = self.snapshot()
        with self.assertRaises(ValueError):bundles.import_package(payload, self.server, choices={'project/selected':'replace', 'project/second':'replace'})
        self.assertEqual(before, self.snapshot())

    def prepare_external(self):
        self.external.mkdir(parents=True, exist_ok=True)
        (self.external / 'world').mkdir(exist_ok=True)
        (self.external / 'modinfo.json').write_text(json.dumps(dict(id='author.map', name='地图项目', version='1.0.0')), 'utf-8')
        for name, data in {'world/region.txt':b'rooms', 'plugins/Author.dll':b'assembly', 'src/Runtime.cs':b'class Runtime {}', 'data/pearl.json':b'{}', 'config.json':b'{}', 'bin/runtime.dll':b'library', 'logs/private.log':b'private', 'obj/build.cs':b'private'}.items():
            file = self.external/name;file.parent.mkdir(parents=True, exist_ok=True);file.write_bytes(data)

    def test_selected_external_map_preserves_metadata_runtime_structure_and_safe_copy(self):
        self.prepare_external()
        with patch.object(room_bindings, 'enabled_asset_roots', return_value=[self.external]):
            self.assertEqual(bundles.mod_choices()['mods'][0]['id'], 'author.map')
            result = bundles.export_package(dict(projects=[], externalMods=['author.map']), self.server)
        payload = (storage.EXPORTS / unquote(Path(result['url']).name)).read_bytes()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
            self.assertIn('external-mods/author.map/plugins/Author.dll', names)
            self.assertIn('external-mods/author.map/src/Runtime.cs', names)
            self.assertIn('external-mods/author.map/data/pearl.json', names)
            self.assertIn('external-mods/author.map/config.json', names)
            self.assertIn('external-mods/author.map/bin/runtime.dll', names)
            self.assertFalse(any('private' in name or '/obj/' in name for name in names))
            manifest = json.loads(archive.read('bundle.json'))
            self.assertEqual(manifest['externalMods'][0]['excluded'], ['logs/private.log', 'obj/'])
        first = bundles.import_package(payload, self.server);self.assertTrue(first['ok'])
        target = Path(first['externalMods'][0]['directory']);self.assertTrue(target.is_relative_to(storage.DATA/'imported-mods'))
        self.assertFalse(bundles.import_package(payload, self.server)['ok'])
        second = bundles.import_package(payload, self.server, choices={'external/author.map':'copy'})
        other = Path(second['externalMods'][0]['directory'])
        self.assertNotEqual(target, other);self.assertTrue(target.exists());self.assertEqual((other/'plugins/Author.dll').read_bytes(), b'assembly')

    def test_external_rejects_paths_disabled_ids_and_links(self):
        self.prepare_external()
        with patch.object(room_bindings, 'enabled_asset_roots', return_value=[self.external]):
            for value in ('../private', 'C:/private', 'disabled.map'):
                with self.assertRaises(ValueError):bundles.export_package(dict(projects=[], externalMods=[value]), self.server)
            original = Path.is_symlink
            with patch.object(Path, 'is_symlink', lambda path: path == self.external/'plugins/Author.dll' or original(path)):
                with self.assertRaisesRegex(ValueError, '链接'):bundles.export_package(dict(projects=[], externalMods=['author.map']), self.server)

    def test_projection_roundtrip_keeps_raw_image_metadata(self):
        import projections
        value = projections.default('selected');value['name']='投影原名'
        file = projections.path(value['uid']);file.parent.mkdir(parents=True);file.write_text(json.dumps(value), 'utf-8')
        result = bundles.export_package(dict(projects=['selected'], projections=True), self.server)
        payload = (storage.EXPORTS / unquote(Path(result['url']).name)).read_bytes();before = self.snapshot()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertEqual(archive.read('content/projections/'+value['uid']+'/projection.json'), file.read_bytes())
        self.assertEqual(before, self.snapshot())
        imported = bundles.import_package(payload, self.server, choices={'project/selected':'replace'})
        self.assertTrue(imported['ok']);self.assertEqual(json.loads(file.read_text('utf-8')), value)

    def test_package_name_and_version_do_not_rename_project(self):
        before = self.snapshot()
        result = bundles.export_package(dict(projects=['selected'], packageName='泳池项目', packageVersion='0.4.3'), self.server)
        self.assertIn('泳池项目-0.4.3-', unquote(result['url']))
        payload = (storage.EXPORTS / unquote(Path(result['url']).name)).read_bytes()
        info = bundles.inspect_import(payload, self.server)
        self.assertEqual((info['name'], info['version']), ('泳池项目', '0.4.3'))
        self.assertEqual(info['projects'][0]['name'], self.project['name'])
        self.assertEqual(before, self.snapshot())
        for name in ('../private', 'NUL', 'wrong/name', 'bad:', 'bad.'):
            with self.assertRaises(ValueError):bundles.package_info(dict(packageName=name))
        for version in ('0.1', '01.2.3', '../../x'):
            with self.assertRaises(ValueError):bundles.package_info(dict(packageName='包名', packageVersion=version))

    def test_related_pearl_collection_and_broadcast_preserve_authored_json(self):
        import pearls, pearl_projects, broadcasts
        cid='a'*32;catalog=storage.DATA/'pearl-projects.json'
        catalog.parent.mkdir(parents=True, exist_ok=True)
        catalog.write_text(json.dumps(dict(schema=pearl_projects.SCHEMA, projects=[dict(id=cid, name='原珍珠项目', createdAt='2026-01-01')], activeId=cid)), 'utf-8')
        pearl=pearls.default(cid);pearl.update(name='原珍珠', notes='作者备注', spawnProjects=['selected'])
        pearl_file=pearls.path(pearl['id'], cid);pearl_file.parent.mkdir(parents=True);pearl_file.write_text(json.dumps(pearl), 'utf-8')
        unrelated=copy.deepcopy(pearl);unrelated.update(id='A99', uid='b'*32, spawnProjects=['other'])
        other=pearls.path('A99', cid);other.parent.mkdir(parents=True);other.write_text(json.dumps(unrelated), 'utf-8')
        broadcast=broadcasts.default();broadcast.update(room='XX_ENTRY', region='XX', name='原广播')
        file=storage.DATA/'broadcasts'/broadcast['id']/'broadcast.json';file.parent.mkdir(parents=True);file.write_text(json.dumps(broadcast), 'utf-8')
        before=self.snapshot()
        with patch.object(broadcasts, 'room_index', side_effect=AssertionError('Should not need applied room catalogue')):
            result=bundles.export_package(dict(projects=['selected'], pearls=True, pearlCollectionId=cid, broadcasts=True), self.server)
            payload=(storage.EXPORTS/unquote(Path(result['url']).name)).read_bytes()
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                self.assertNotIn('content/pearl-projects/'+cid+'/pearls/A99/pearl.json', archive.namelist())
                self.assertEqual(json.loads(archive.read('content/pearl-projects/'+cid+'/pearls/'+pearl['id']+'/pearl.json')), pearl)
                self.assertEqual(archive.read('content/broadcasts/'+broadcast['id']+'/broadcast.json'), file.read_bytes())
        self.assertEqual(before, self.snapshot())
        summary=bundles.inspect_import(payload, self.server)
        choices={item['key']:'replace' for item in summary['collisions']}
        result=bundles.import_package(payload, self.server, choices=choices)
        self.assertTrue(result['ok']);self.assertEqual(json.loads(other.read_text('utf-8')), unrelated)

    def test_preferences_store_package_and_external_selection_without_modifying_project(self):
        import playable_export, standalone
        before=self.project_file.read_bytes()
        request=dict(settingsProject='selected', projects=['selected'], externalMods=['author.map'], packageName='分享包', packageVersion='0.4.3')
        playable_export.save_preferences(request, self.server)
        stored=standalone.preferences('selected')
        self.assertEqual(stored['externalMods'], ['author.map'])
        self.assertEqual((stored['packageName'],stored['packageVersion']), ('分享包','0.4.3'))
        self.assertEqual(before,self.project_file.read_bytes())
        playable_export.save_preferences(dict(request, packageName='',packageVersion='0.'),self.server)
        self.assertEqual(standalone.preferences('selected')['packageName'],'')

    def test_external_private_information_stops_before_package_and_reports_file(self):
        self.prepare_external()
        config=self.external/'config.json';config.write_text(json.dumps({'path':r'C:\Users\Someone\Private\project'}), 'utf-8')
        with patch.object(room_bindings,'enabled_asset_roots',return_value=[self.external]):
            with self.assertRaisesRegex(ValueError, 'config.json'):bundles.inspect_mods(dict(externalMods=['author.map']))
            with self.assertRaisesRegex(ValueError, 'config.json'):bundles.export_package(dict(projects=[],externalMods=['author.map']),self.server)
        self.assertFalse(storage.EXPORTS.exists())

    def test_named_package_with_custom_audio_keeps_content_addressed_asset(self):
        import audio_assets
        frame=bytes.fromhex('fffb9000')+b'\x00'*413;audio=frame*3
        audio_assets.parse_mp3(audio);digest=hashlib.sha256(audio).hexdigest()
        file=storage.DATA/'audio'/(digest+'.mp3');file.parent.mkdir(parents=True);file.write_bytes(audio)
        project=json.loads(self.project_file.read_text('utf-8'))
        project['design']['musicWork']=dict(mode='custom',asset=digest,name='Music',volume=.5,loop=True)
        self.project_file.write_text(json.dumps(project),'utf-8')
        result=bundles.export_package(dict(projects=['selected']),self.server)
        payload=(storage.EXPORTS/unquote(Path(result['url']).name)).read_bytes()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:self.assertEqual(archive.read('content/audio/'+digest+'.mp3'),audio)
        file.unlink()
        result=bundles.import_package(payload,self.server,choices={'project/selected':'replace'})
        self.assertTrue(result['ok']);self.assertEqual(file.read_bytes(),audio)

    def test_legacy_migration_copy_does_not_conflict_but_distinct_live_uid_does(self):
        import pearls, pearl_projects
        catalog=storage.DATA/'pearl-projects.json';catalog.parent.mkdir(parents=True,exist_ok=True)
        catalog.write_text(json.dumps(dict(schema=pearl_projects.SCHEMA,projects=[dict(id='legacy',name='Legacy')],activeId='legacy')),'utf-8')
        value=pearls.default('legacy');value['spawnProjects']=['selected']
        canonical=pearls.path(value['id'],'legacy');canonical.parent.mkdir(parents=True);canonical.write_text(json.dumps(value),'utf-8')
        original=storage.DATA/'pearls'/value['id']/'pearl.json';original.parent.mkdir(parents=True);original.write_bytes(canonical.read_bytes())
        result=bundles.export_package(dict(projects=['selected'],pearls=True,pearlCollectionId='legacy'),self.server)
        payload=(storage.EXPORTS/unquote(Path(result['url']).name)).read_bytes()
        choices={row['key']:'replace' for row in bundles.inspect_import(payload,self.server)['collisions']}
        self.assertTrue(bundles.import_package(payload,self.server,choices=choices)['ok'])
        second=storage.DATA/'pearl-projects'/('b'*32)/'pearls'/'A99'/'pearl.json';second.parent.mkdir(parents=True)
        duplicate=copy.deepcopy(value);duplicate.update(id='A99',collectionId='b'*32);second.write_text(json.dumps(duplicate),'utf-8')
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'内部编号已用于其他文件'):bundles.import_package(payload,self.server,choices=choices)
        self.assertEqual(before,self.snapshot())

    def test_external_device_and_unsafe_filenames_are_rejected_before_writing(self):
        for relative in ('external/NUL','external/CON.json','external/COM1/world.txt','external/bad?.txt','external/bad\nname.txt'):
            with self.subTest(relative=relative),self.assertRaises(ValueError):bundles._safe(storage.DATA,relative)
        self.assertFalse((storage.DATA/'external').exists())

    def test_keep_all_existing_projects_changes_no_files_or_timestamps(self):
        self.second();_,payload=self.export()
        for identifier in ('selected','second'):
            file=storage.project_file(identifier);value=json.loads(file.read_text('utf-8'))
            value['name']='本地修改 '+identifier;file.write_text(json.dumps(value),'utf-8')
        before=self.snapshot();times={file:file.stat().st_mtime_ns for file in storage.PROJECTS.rglob('*') if file.is_file()}
        result=bundles.import_package(payload,self.server,choices={'project/selected':'keep','project/second':'keep'})
        self.assertTrue(result['ok']);self.assertEqual(result['projects'],[])
        self.assertEqual(before,self.snapshot())
        self.assertEqual(times,{file:file.stat().st_mtime_ns for file in storage.PROJECTS.rglob('*') if file.is_file()})

    def test_mixed_import_only_replaces_the_explicit_project_and_preserves_local_notes(self):
        second=self.second();_,payload=self.export()
        for identifier in ('selected','second'):
            file=storage.project_file(identifier);value=json.loads(file.read_text('utf-8'))
            value['name']='本地修改 '+identifier;file.write_text(json.dumps(value),'utf-8')
            (file.parent/'notes.txt').write_text('未列入包清单的本地文件','utf-8')
        kept=storage.project_file('selected').read_bytes()
        result=bundles.import_package(payload,self.server,choices={'project/selected':'keep','project/second':'replace'})
        self.assertTrue(result['ok']);self.assertEqual([value['projectId'] for value in result['projects']],['second'])
        self.assertEqual(storage.project_file('selected').read_bytes(),kept)
        self.assertEqual(json.loads(storage.project_file('second').read_text('utf-8'))['name'],second['name'])
        for identifier in ('selected','second'):
            self.assertEqual((storage.project_file(identifier).parent/'notes.txt').read_text('utf-8'),'未列入包清单的本地文件')

    def test_child_validation_receives_only_the_explicit_bundle_room_set(self):
        self.second()
        expected={'XX_AI','XX_ENTRY','YY_AI','YY_ENTRY'}
        with patch.object(packages,'_inspect',wraps=packages._inspect) as inspect:
            _,payload=self.export()
            self.assertGreaterEqual(inspect.call_count,4)
            for call in inspect.call_args_list:self.assertEqual(set(call.kwargs.get('available_rooms',call.args[2] if len(call.args)>2 else ())),expected)
        with patch.object(packages,'_inspect',wraps=packages._inspect) as inspect:
            summary=bundles.inspect_import(payload,self.server)
            self.assertEqual(len(summary['projects']),2)
            self.assertEqual(inspect.call_count,2)
            for call in inspect.call_args_list:self.assertEqual(set(call.kwargs['available_rooms']),expected)


if __name__ == '__main__':unittest.main()
