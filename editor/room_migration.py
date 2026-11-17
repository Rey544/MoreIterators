"""Previewed room migrations with explicit ownership and file rollback."""
import copy
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
import broadcasts
import pearls
import room_bindings
import room_cleanup
import room_editor
import room_controls
import storage


@contextmanager
def staging_directory():
    """Use writable local data, including machines with restricted system TEMP."""
    root=(storage.DATA/'.staging').resolve()
    root.mkdir(parents=True,exist_ok=True)
    path=(root/('room-'+uuid.uuid4().hex)).resolve()
    if not path.is_relative_to(root):raise ValueError('房间中转目录越界')
    path.mkdir()
    try:yield path
    finally:
        if not path.resolve().is_relative_to(root):raise ValueError('房间中转目录已改变，未清理')
        shutil.rmtree(path)


class Files:
    def __init__(self):self.original={};self.timestamps={}
    def watch(self,file):
        file=Path(file)
        if file not in self.original:
            self.original[file]=file.read_bytes() if file.exists() else None
            if file.is_file():self.timestamps[file]=(file.stat().st_atime_ns,file.stat().st_mtime_ns)
    def write(self,file,content):
        file=Path(file);self.watch(file);file.parent.mkdir(parents=True,exist_ok=True)
        temporary=file.with_name(file.name+'.migration-tmp')
        try:temporary.write_bytes(content);temporary.replace(file)
        finally:temporary.unlink(missing_ok=True)
    def json(self,file,value):self.write(file,json.dumps(value,ensure_ascii=False,indent=2).encode('utf-8'))
    def remove(self,file):self.watch(file);Path(file).unlink(missing_ok=True)
    def rollback(self):
        failures=[]
        for file,value in reversed(list(self.original.items())):
            try:
                if value is None:file.unlink(missing_ok=True)
                else:
                    self.write(file,value)
                    if file in self.timestamps:os.utime(file,ns=self.timestamps[file])
            except OSError as error:failures.append(str(file)+': '+str(error))
        if failures:raise OSError('房间迁移回滚未完成：'+'; '.join(failures))


def preview(project_id,raw):
    project=storage.load_project(storage.valid_id(project_id))
    old=room_bindings.binding(project)
    for kind in ('ai','entry'):
        if kind=='ai' or old['entryMode']=='copy':room_editor.ensure_synced(project_id,old[kind])
    plan=room_bindings.plan(project,raw)
    evidence=[]
    for item in plan['roomCopies']:
        source=Path(item['source'])
        for file in sorted(source.parent.glob(source.name+'*')):
            if file.is_file():evidence.append((str(file),file.stat().st_size,file.stat().st_mtime_ns))
    payload=dict(project=project,plan=plan,sourceFiles=evidence)
    token=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
    return dict(plan,token=token,projectId=project_id,name=project['name'])


def _remap_overseer_rooms(config, rooms):
    """Change only explicit room references; preserve defaults and other settings."""
    if not isinstance(config, dict):
        return False
    changed = False
    for profile in [config, *config.get('guests', [])]:
        if not isinstance(profile, dict) or 'rooms' not in profile:
            continue
        before = profile['rooms']
        after = list(dict.fromkeys(rooms.get(room, room) for room in before))
        if after != before:
            profile['rooms'] = after
            changed = True
    return changed


def _overseer_references(transaction, rooms):
    # Remap saved drafts and applied designs separately, never publish a draft.
    for file in storage.project_files():
        project = json.loads(file.read_text('utf-8'))
        if _remap_overseer_rooms(project.get('overseer'), rooms):
            project['overseerRevision'] = project.get('overseerRevision', 0) + 1
            transaction.json(file, project)
        pid = project['projectId']
        runtime = storage.design_path(pid, room_bindings.binding(project)['oracleId'])
        paths = [runtime]
        if storage.link(pid):
            paths.append(storage.installed_mod(pid) / 'designs' / runtime.name)
        for path in paths:
            if not path.is_file():
                continue
            design = json.loads(path.read_text('utf-8'))
            if design.get('projectId') != pid or 'overseerJson' not in design:
                continue
            config = json.loads(design['overseerJson'])
            if _remap_overseer_rooms(config, rooms):
                design['overseerJson'] = json.dumps(config, ensure_ascii=False)
                transaction.json(path, design)


def runtime_references(transaction,pid,old,new):
    """Rebind already-applied data without publishing unrelated authoring drafts."""
    for file in (storage.RUNTIME/'projections').glob('*.json'):
        value=json.loads(file.read_text('utf-8'))
        if value.get('projectId')==pid:
            value['oracleId']=new['oracleId'];transaction.json(file,value)
    rooms={old['ai']:new['ai']}
    if old['entryMode']=='copy':rooms[old['entry']]=new['entry']
    for file in pearls.runtime().glob('*.json'):
        if file.name=='spawn-request.json':continue
        value=json.loads(file.read_text('utf-8'));changed=False
        for reader in value.get('readers',[]):
            if reader.get('projectId')==pid:reader['oracleId']=new['oracleId'];changed=True
        for spawn in value.get('spawns',[]):
            if spawn.get('projectId')==pid:spawn['entry']=new['entry'];changed=True
            elif spawn.get('entry') in rooms:spawn['entry']=rooms[spawn['entry']];changed=True
        if changed:
            transaction.watch(file);transaction.watch(storage.RUNTIME/'pearl-project.json')
            pearls.migrate_runtime_lines(file,value)
    authored=list((storage.DATA/'pearls').glob('*/pearl.json'))+list((storage.DATA/'pearl-projects').glob('*/pearls/*/pearl.json'))
    for file in authored:
        value=json.loads(file.read_text('utf-8'))
        if value.get('schema')!=pearls.SCHEMA:continue
        before=copy.deepcopy(value)
        if 'spawnRooms' in value:value['spawnRooms']=[rooms.get(name,name) for name in value['spawnRooms']]
        if 'spawnRoomPositions' in value:value['spawnRoomPositions']={rooms.get(name,name):position for name,position in value['spawnRoomPositions'].items()}
        if value!=before:
            value['revision']=value.get('revision',0)+1
            transaction.json(file,value)
    _overseer_references(transaction, rooms)
    for folder in (storage.DATA/'broadcasts',storage.RUNTIME/'broadcasts'):
        for file in folder.rglob('*.json'):
            value=json.loads(file.read_text('utf-8'))
            if value.get('schema')==broadcasts.SCHEMA and value.get('room') in rooms:
                value['room']=rooms[value['room']];value['region']=new['region']
                transaction.json(file,value)


def _package_references(transaction,pid,old,new,backup):
    import project_packages
    metadata=project_packages.load_metadata(pid)
    if not metadata:return
    root=storage.project_file(pid).parent
    names={old['ai']:new['ai']}
    if old['entryMode']=='copy':names[old['entry']]=new['entry']
    owned={new['ai']}
    if new['entryMode']=='copy':owned.add(new['entry'])
    for room in metadata['rooms']:
        before=copy.deepcopy(room)
        if room['kind'] in ('ai','entry'):room['name']=new[room['kind']]
        room['region']=room['name'].split('_')[0]
        room['connections']=[names.get(name,name) for name in room['connections']]
        if room['kind']=='entry' and new['entryMode']=='existing':room['sourceAvailable']=False
        if room!=before:room['updatedAtNs']=time.time_ns()
    def renamed(relative):
        for previous,current in names.items():
            match=re.fullmatch(r'(rooms/(?:rendered/)?|world/[a-z0-9]+-rooms/)'+re.escape(previous)+r'(\.txt|\.png|_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|_mi_background\.json|_[1-9][0-9]*\.png)',relative)
            if match:
                if current not in owned:return None
                prefix=match[1] if match[1].startswith('rooms/') else 'world/'+current.split('_')[0].lower()+'-rooms/'
                return prefix+current+match[2]
        return relative
    files={}
    for item in metadata['files']:
        previous=item['path'];current=renamed(previous)
        if current is None:continue
        source=project_packages._safe(root,previous);destination=project_packages._safe(root,current)
        data = destination.read_bytes() if destination.is_file() else source.read_bytes()
        if current != previous and current.endswith('_mi_background.json'):
            context = json.loads(data.decode('utf-8-sig'));context['room'] = names.get(context['room'], context['room'])
            data = json.dumps(context, ensure_ascii=False, indent=2).encode('utf-8')
        elif current != previous and old['region'] != new['region'] and re.search(r'_settings(?:-[A-Za-z0-9_-]+)?\.txt$', current):
            text = data.decode('utf-8-sig')
            text = re.sub(r'(?mi)^(Template:[ \t]*)' + re.escape(old['region']) + r'(_settingstemplate_)', lambda match: match[1] + new['region'] + match[2], text)
            data = text.encode('utf-8')
        if current != previous or data != destination.read_bytes():transaction.write(destination, data)
        files[current]=destination.read_bytes()
    used_regions={room['region'] for room in metadata['rooms']}
    if old['region']!=new['region']:
        original=next((row for row in metadata.get('regions',[]) if row['code']==old['region']),None)
        if original and not any(row['code']==new['region'] for row in metadata['regions']):
            added=copy.deepcopy(original);added['code']=new['region'];added['files']=[]
            for filename in original['files']:
                new_filename='map_'+new['region'].lower()+'.txt' if filename.startswith('map_') else new['region'].lower()+filename[len(old['region']):] if '_settingstemplate_' in filename else filename
                previous='rooms/regions/'+old['region']+'/'+filename
                current='rooms/regions/'+new['region']+'/'+new_filename
                data=project_packages._safe(root,previous).read_bytes()
                if filename.startswith('map_'):
                    text=data.decode('utf-8-sig')
                    for before,after in names.items():text=re.sub(r'(?<![A-Z0-9_])'+re.escape(before)+r'(?![A-Z0-9_])',after,text)
                    data=project_packages._map_subset(text.encode('utf-8'),{room['name'] for room in metadata['rooms'] if room['region']==new['region']}) or b''
                destination=project_packages._safe(root,current)
                if destination.is_file() and destination.read_bytes()!=data:raise room_bindings.RoomBindingError('migrationTargetExists',file=current)
                transaction.write(destination,data);files[current]=data;added['files'].append(new_filename)
            metadata['regions'].append(added)
        metadata['regions']=[row for row in metadata.get('regions',[]) if row['code'] in used_regions]
        files={name:data for name,data in files.items() if not name.startswith('rooms/regions/') or name.split('/')[2] in used_regions}
    metadata['files']=project_packages._records(files)
    if 'deployedFiles' in metadata:metadata['deployedFiles']=sorted({mapped for item in metadata['deployedFiles'] if (mapped:=renamed(item)) is not None})
    transaction.json(root/project_packages.LOCAL_MANIFEST,metadata)
    for target in (storage.target_mod(pid),storage.installed_mod(pid)):
        marker=target/project_packages.OUTPUT_MANIFEST
        if not marker.is_file():continue
        manifest=project_packages.output_manifest(target)
        if pid in manifest['projects']:
            manifest['projects'][pid]=sorted({mapped for item in manifest['projects'][pid] if (mapped:=renamed(item)) is not None})
            transaction.json(marker,manifest)


def _package_outputs(transaction,project,server):
    import project_packages
    pid=project['projectId'];prepared=project_packages.before_deploy(project,server)
    if not prepared.get('files'):return
    binding=room_bindings.binding(project);core={binding['ai']}
    if binding['entryMode']=='copy':core.add(binding['entry'])
    owned=set()
    for root in (storage.target_mod(pid),storage.installed_mod(pid)):
        manifest=project_packages.output_manifest(root)
        existing=set(manifest['projects'].get(pid,[]))
        shared={name for owner,names in manifest['projects'].items() if owner!=pid for name in names}
        claimed=set()
        for relative,content in prepared['files'].items():
            file=project_packages._safe(root,relative)
            if relative in shared and (not file.is_file() or file.read_bytes()!=content):raise room_bindings.RoomBindingError('migrationSharedFile',file=relative)
            is_core=any(re.fullmatch('world/'+binding['region'].lower()+'-rooms/'+re.escape(name)+r'(?:\.txt|_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|_mi_background\.json|_[1-9][0-9]*\.png)',relative) for name in core)
            if file.is_file() and relative not in existing and relative not in shared and not is_core and file.read_bytes()!=content:
                raise room_bindings.RoomBindingError('migrationUnownedFile',file=relative)
            borrowed=relative in shared or (relative in prepared.get('borrowed',[]) and file.is_file() and relative not in existing)
            if not borrowed:
                transaction.write(file,content);claimed.add(relative)
        manifest['projects'][pid]=sorted(existing|claimed)
        transaction.json(root/project_packages.OUTPUT_MANIFEST,manifest)
        owned.update(claimed)
    metadata=project_packages.load_metadata(pid)
    metadata['deployedFiles']=sorted(set(metadata.get('deployedFiles',[]))|owned)
    transaction.json(storage.project_file(pid).parent/project_packages.LOCAL_MANIFEST,metadata)


def _migrated_design(project, old, new, server):
    source = storage.design_path(project['projectId'], old['oracleId'])
    if source.is_file():
        design = json.loads(source.read_text('utf-8'))
        if not isinstance(design, dict) or design.get('projectId') != project['projectId']:
            raise ValueError('已应用的设计不属于此项目，不能覆盖。')
        design['oracleId'] = new['oracleId']
        return design
    initial = copy.deepcopy(project)
    initial.pop('overseer', None)
    return server.compile_design(initial)


def apply(project_id,raw,token,server,draft_revision=None,_plan=None,_finalize=None):
    if draft_revision is not None and (type(draft_revision) is not int or draft_revision<0):
        raise ValueError('房间草稿已在其他页面更新，请重新打开后再修改')
    planned=preview(project_id,raw) if _plan is None else _plan
    if _plan is None and (not isinstance(token,str) or token!=planned['token']):
        raise ValueError('项目、房间或连接已改变，请重新预览后再应用。')
    project=storage.load_project(project_id);old=room_bindings.binding(project);new=planned['binding']
    if planned.get('connectionVersion')==2:
        project['roomConnections']=dict(version=2,rows=copy.deepcopy(planned['connectionRows']),ownedRegions=list(planned.get('ownedRegions',[])))
    project=copy.deepcopy(project);project['roomBinding']=new;server.validate(project)
    record=storage.registry_record(project,new['ai'],new['entry'],new['oracleId'])
    registry=storage.RUNTIME/'creator/registry.json'
    records=json.loads(registry.read_text('utf-8')) if registry.exists() else []
    previous_records=copy.deepcopy(records)
    records=[item for item in records if item['projectId']!=project_id]+[record]
    records.sort(key=lambda item:item['projectId'])
    plan={key:value for key,value in planned.items() if key not in ('token','projectId','name')}
    local=storage.DATA/'local-mod';installed=storage.installed_mod(project_id)
    marker=local/'.mi-room-bindings.json'
    managed=json.loads(marker.read_text('utf-8')).get('files',[]) if marker.exists() else []
    for relative in managed:
        path=(local/relative).resolve()
        if not path.is_relative_to(local.resolve()):raise ValueError('世界输出路径越界')
    transaction=Files();draft_result={}
    retired=room_cleanup.prepare_migration(project_id,old,new,previous_records,managed)
    root=storage.project_file(project_id).parent
    old_owned={old['ai']}
    if old['entryMode']=='copy':old_owned.add(old['entry'])
    for item in plan['roomCopies']:
        if item['name'] in old_owned:continue
        for folder in (root/'rooms',root/'rooms/rendered'):
            collision=next((file for file in folder.glob(item['name']+'*') if re.fullmatch(re.escape(item['name'])+r'(?:\.txt|\.png|_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|_mi_background\.json|_[1-9][0-9]*\.png|\.source\.json)',file.name)),None)
            if collision is not None:raise room_bindings.RoomBindingError('migrationTargetExists',file=str(collision))
    with staging_directory() as staged:
        # Finish camera validation and copies before changing the active project.
        for item in plan['roomCopies']:
            source=Path(item['source'])
            server.copy_room(source,staged,item['name'],replace=True)
            if _plan is not None and source.name==item['name'] and old[item['kind']]==item['name']:
                for file in staged.glob(item['name']+'*'):
                    original=source.parent/file.name
                    if original.is_file():file.write_bytes(original.read_bytes())
        if _plan is None and new['entryMode']=='copy' and not room_controls.entry_gravity(project):server.zero_gravity(staged/(new['entry']+'_settings.txt'))
        try:
            room_cleanup.backup_migration(transaction,project_id,retired,old,new)
            room_folder=Path('world')/(new['region'].lower()+'-rooms')
            for file in staged.iterdir():
                transaction.write(root/'rooms/rendered'/file.name,file.read_bytes())
            for item in plan['roomCopies']:
                previous=old[item['kind']];current=item['name']
                if previous==current:continue
                for suffix in ('.txt','.png'):
                    source=root/'rooms'/(previous+suffix)
                    destination=source.with_name(current+suffix)
                    if source.is_file():
                        if destination.exists():raise room_bindings.RoomBindingError('migrationTargetExists',file=str(destination))
                        transaction.write(destination,source.read_bytes())
                for source in (root/'rooms/rendered').glob(previous+'*'):
                    if not re.fullmatch(re.escape(previous)+r'(?:_settings-[A-Za-z0-9_-]+\.txt|_properties\.txt)',source.name):continue
                    transaction.write(source.with_name(current+source.name[len(previous):]),source.read_bytes())
            transaction.json(storage.project_file(project_id),project)
            if draft_revision is not None:
                import studio_drafts
                draft_result=studio_drafts.align_applied(project_id,new,draft_revision,transaction.json)
            transaction.json(storage.project_file(project_id).parent/'room-binding-plan.json',plan)
            transaction.json(storage.design_path(project_id,new['oracleId']),_migrated_design(project,old,new,server))
            transaction.json(registry,records)
            runtime_references(transaction,project_id,old,new)
            _package_references(transaction,project_id,old,new,retired.get('backup'))
            for item in plan['roomCopies']:
                name=item['name'];cache=root/'rooms/rendered'/(name+'.txt')
                source=root/'rooms'/(name+'.txt')
                if source.is_file():
                    cache.touch()
                    import room_source_choices
                    transaction.json(root/'rooms/rendered'/(name+'.source.json'),room_source_choices.pairing_record(project_id,name))
            _package_outputs(transaction,project,server)
            worlds=room_bindings.compile_worlds(records,{project_id:plan})
            for relative in set(managed)|set(worlds):transaction.watch(local/relative)
            transaction.watch(marker)
            room_bindings.write_worlds(records,{project_id:plan})
            if old['oracleId']!=new['oracleId']:
                previous=storage.design_path(project_id,old['oracleId'])
                if previous.exists() and json.loads(previous.read_text('utf-8')).get('projectId')==project_id:transaction.remove(previous)
            info=local/'modinfo.json'
            if not info.exists():transaction.json(info,dict(id='moreiterators.local',name='更多迭代器 本地作品',version='0.1.0',authors='Local',description='本机作品。不要上传。',requirements=['moreiterators.core'],requirements_names=['更多迭代器'],tags=['Regions'],target_game_version='v1.11.8',checksum_override_version=False))
            # Synchronize only known generated outputs; never mirror foreign rooms.
            for relative in set(managed)|set(worlds):
                if relative not in worlds:transaction.remove(installed/relative)
            generated=[]
            for item in plan['roomCopies']:
                name=item['name']
                for file in sorted((root/'rooms/rendered').glob(name+'*')):
                    if not re.fullmatch(re.escape(name)+r'(?:\.txt|_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|_mi_background\.json|_[1-9][0-9]*\.png)',file.name):continue
                    relative=(room_folder/file.name).as_posix()
                    transaction.write(local/relative,file.read_bytes())
                    transaction.write(installed/relative,file.read_bytes())
                    generated.extend([('local',relative),('installed',relative),('rendered',file.name)])
            for relative in [*worlds,'modinfo.json']:
                transaction.write(installed/relative,(local/relative).read_bytes())
            room_cleanup.record_migration(transaction,project_id,old,new,generated)
            room_cleanup.retire_migration(transaction,project_id,retired)
            if _finalize is not None:_finalize(transaction)
        except Exception:
            transaction.rollback();raise
    return dict(ok=True,project=storage.load_project(project_id),binding=new,requiresRestart=True,warnings=planned['warnings'],removedRooms=retired['names'],**draft_result)
