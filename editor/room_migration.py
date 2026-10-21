"""Previewed room migrations with explicit ownership and file rollback."""
import copy
import hashlib
import json
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
import broadcasts
import pearls
import room_bindings
import room_cleanup
import room_editor
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
    def __init__(self):self.original={}
    def watch(self,file):
        file=Path(file)
        if file not in self.original:self.original[file]=file.read_bytes() if file.exists() else None
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
                else:self.write(file,value)
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
    for file in pearls.runtime().glob('*.json'):
        if file.name=='spawn-request.json':continue
        value=json.loads(file.read_text('utf-8'));changed=False
        for reader in value.get('readers',[]):
            if reader.get('projectId')==pid:reader['oracleId']=new['oracleId'];changed=True
        for spawn in value.get('spawns',[]):
            if spawn.get('projectId')==pid:spawn['entry']=new['entry'];changed=True
        if changed:
            transaction.watch(file);transaction.watch(storage.RUNTIME/'pearl-project.json')
            pearls.migrate_runtime_lines(file,value)
    rooms={old['ai']:new['ai']}
    if old['entryMode']=='copy':rooms[old['entry']]=new['entry']
    _overseer_references(transaction, rooms)
    for folder in (storage.DATA/'broadcasts',storage.RUNTIME/'broadcasts'):
        for file in folder.rglob('*.json'):
            value=json.loads(file.read_text('utf-8'))
            if value.get('schema')==broadcasts.SCHEMA and value.get('room') in rooms:
                value['room']=rooms[value['room']];value['region']=new['region']
                transaction.json(file,value)


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


def apply(project_id,raw,token,server):
    planned=preview(project_id,raw)
    if not isinstance(token,str) or token!=planned['token']:
        raise ValueError('项目、房间或连接已改变，请重新预览后再应用。')
    project=storage.load_project(project_id);old=room_bindings.binding(project);new=planned['binding']
    project=copy.deepcopy(project);project['roomBinding']=new;server.validate(project)
    record=storage.registry_record(project,new['ai'],new['entry'],new['oracleId'])
    registry=storage.RUNTIME/'creator/registry.json'
    records=json.loads(registry.read_text('utf-8')) if registry.exists() else []
    records=[item for item in records if item['projectId']!=project_id]+[record]
    records.sort(key=lambda item:item['projectId'])
    plan={key:value for key,value in planned.items() if key not in ('token','projectId','name')}
    worlds=room_bindings.compile_worlds(records,{project_id:plan})
    local=storage.DATA/'local-mod';installed=storage.installed_mod(project_id)
    marker=local/'.mi-room-bindings.json'
    managed=json.loads(marker.read_text('utf-8')).get('files',[]) if marker.exists() else []
    for relative in [*managed,*worlds]:
        path=(local/relative).resolve()
        if not path.is_relative_to(local.resolve()):raise ValueError('世界输出路径越界')
    transaction=Files()
    with staging_directory() as staged:
        # Finish camera validation and copies before changing the active project.
        for item in plan['roomCopies']:server.copy_room(Path(item['source']),staged,item['name'],replace=True)
        if new['entryMode']=='copy':server.zero_gravity(staged/(new['entry']+'_settings.txt'))
        try:
            for relative in set(managed)|set(worlds):transaction.watch(local/relative)
            transaction.watch(marker)
            room_bindings.write_worlds(records,{project_id:plan})
            room_folder=Path('world')/(new['region'].lower()+'-rooms')
            for file in staged.iterdir():
                transaction.write(local/room_folder/file.name,file.read_bytes())
                transaction.write(storage.project_file(project_id).parent/'rooms/rendered'/file.name,file.read_bytes())
            for item in plan['roomCopies']:
                previous=old[item['kind']];current=item['name']
                if previous==current:continue
                for suffix in ('.txt','.png'):
                    source=storage.project_file(project_id).parent/'rooms'/(previous+suffix)
                    destination=source.with_name(current+suffix)
                    if source.is_file():
                        if destination.exists():raise ValueError('目标 Rained 源工程已存在，请先核对：'+current)
                        transaction.write(destination,source.read_bytes())
                        # A renamed source still corresponds to the staged render.
                        cache=storage.project_file(project_id).parent/'rooms/rendered'/(current+'.txt')
                        if cache.exists():cache.touch()
            transaction.json(storage.project_file(project_id),project)
            transaction.json(storage.project_file(project_id).parent/'room-binding-plan.json',plan)
            transaction.json(storage.design_path(project_id,new['oracleId']),_migrated_design(project,old,new,server))
            transaction.json(registry,records)
            runtime_references(transaction,project_id,old,new)
            if old['oracleId']!=new['oracleId']:
                previous=storage.design_path(project_id,old['oracleId'])
                if previous.exists() and json.loads(previous.read_text('utf-8')).get('projectId')==project_id:transaction.remove(previous)
            info=local/'modinfo.json'
            if not info.exists():transaction.json(info,dict(id='moreiterators.local',name='更多迭代器 · 本地作品',version='0.1.0',authors='Local',description='本机作品。不要上传。',requirements=['moreiterators.core'],requirements_names=['更多迭代器'],tags=['Regions'],target_game_version='v1.11.8',checksum_override_version=False))
            # Synchronize only known generated outputs; never mirror foreign rooms.
            for relative in set(managed)|set(worlds):
                if relative not in worlds:transaction.remove(installed/relative)
            for relative in [*worlds,'modinfo.json',*(str(room_folder/file.name) for file in staged.iterdir())]:
                transaction.write(installed/relative,(local/relative).read_bytes())
            generated=[]
            for file in staged.iterdir():
                relative=(room_folder/file.name).as_posix()
                generated.extend([('local',relative),('installed',relative),('rendered',file.name)])
            room_cleanup.record_migration(transaction,project_id,old,new,generated)
        except Exception:
            transaction.rollback();raise
    return dict(ok=True,project=storage.load_project(project_id),binding=new,requiresRestart=True,warnings=planned['warnings'])
