"""Recoverable project deletion: archive owned rooms and rebuild shared world indices.

Shared pearl/broadcast authoring stays intact; runtime pearl suspension is transactional.
"""
from pathlib import Path, PurePosixPath
import copy, datetime, hashlib, json, os, re, uuid
import storage, room_bindings, room_migration, pearl_suspension, project_worlds

SCHEMA='moreiterators.deleted-project.v1'
ACTIVE_STATES=('deleting','deleted','restoring')

def root():return storage.DATA/'deleted-projects'
def _token(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):raise ValueError('删除记录编号无效')
    return value

def _safe_path(base,relative=''):
    base=Path(base).absolute()
    if base.resolve()!=base:raise ValueError('项目文件路径存在链接，已停止操作')
    if not isinstance(relative,str) or '\\' in relative or ':' in relative or (relative and (PurePosixPath(relative).is_absolute() or any(part in ('.','..') for part in relative.split('/')))):raise ValueError('项目文件路径无效')
    path=base/relative
    if not path.resolve().is_relative_to(base):raise ValueError('项目文件路径越界')
    for parent in [path,*path.parents]:
        if parent==base.parent:break
        if parent.is_symlink() or parent.exists() and parent.resolve()!=parent.absolute():raise ValueError('项目文件路径存在链接，已停止操作')
    return path

def _manifest(token):return _safe_path(root(),_token(token)+'/manifest.json')
def _read(token):
    value=json.loads(_manifest(token).read_text('utf-8'))
    if value.get('schema')!=SCHEMA or value.get('token')!=token or not isinstance(value.get('files'),list):raise ValueError('删除记录损坏，无法恢复')
    pid=storage.valid_id(value.get('projectId'))
    if not isinstance(value.get('project'),dict) or value['project'].get('projectId')!=pid or not isinstance(value.get('registry'),list) or any(not isinstance(v,dict) or v.get('projectId')!=pid for v in value['registry']):raise ValueError('删除记录损坏，无法恢复')
    return value

def _records():
    if not root().exists():return []
    result=[]
    for file in sorted(root().glob('*/manifest.json')):
        value=_read(file.parent.name)
        if value.get('state') in ACTIVE_STATES:result.append(value)
    return result

def listing():
    return [dict(token=v['token'],projectId=v['projectId'],name=v['name'],deletedAt=v['deletedAt'],rooms=sorted(pearl_suspension.owned_rooms(v['project']))) for v in sorted(_records(),key=lambda v:v['deletedAt'],reverse=True)]

def archived(pid):
    storage.valid_id(pid)
    return next((v for v in _records() if v['projectId']==pid),None)

def assert_active(pid):
    storage.assert_not_purged(pid)
    if archived(pid):raise ValueError('此项目已删除，请先从最近删除中恢复')

def reference_project(pid):
    """Read-only metadata for shared pearls; never re-add a deleted project."""
    storage.valid_id(pid)
    value=archived(pid)
    if value:return copy.deepcopy(value['project'])
    return storage.load_project(pid)

def _blob(value,item):
    digest=item.get('sha256');blob=item.get('blob')
    if not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest) or not isinstance(blob,str) or not re.fullmatch('[a-f0-9]{8}',blob):raise ValueError('删除记录损坏，无法恢复')
    file=_safe_path(root(),value['token']+'/blobs/'+blob);content=file.read_bytes()
    if hashlib.sha256(content).hexdigest()!=digest or len(content)!=item.get('size'):raise ValueError('归档文件校验失败，无法恢复')
    return file,content

def reference_file(pid,relative):
    """Return a verified read-only source, without recreating an active project."""
    storage.valid_id(pid);file=_safe_path(storage.project_file(pid).parent,relative);value=archived(pid)
    if not value:return file if file.is_file() else None
    item=next((item for item in value['files'] if item.get('kind')=='project' and item.get('path')==relative),None)
    return _blob(value,item)[0] if item else None

def _editable(pid,project=None):
    storage.valid_id(pid)
    if storage.binding(pid) or storage.link(pid) or project and (project.get('legacyOracle') or project.get('fixedProject')):raise ValueError('原版与关联模组的固定项目不能删除')

def _registry():
    file=storage.RUNTIME/'creator/registry.json'
    value=json.loads(file.read_text('utf-8')) if file.exists() else []
    if not isinstance(value,list) or any(not isinstance(v,dict) for v in value):raise ValueError('运行项目目录损坏，已停止操作')
    return value

def _base(pid,item):
    kind=item.get('kind')
    if kind=='project':return storage.PROJECTS/pid
    if kind=='history':return storage.history_directory(pid)
    if kind=='projection':
        return storage.DATA/'projections'/_token(item.get('owner'))
    if kind=='projection-settings':return storage.DATA/'projections/project-settings'
    if kind=='runtime':return storage.RUNTIME
    if kind=='local-room':return storage.DATA/'local-mod'
    if kind=='installed-room':return storage.installed_mod(pid)
    raise ValueError('删除记录的文件类型无效')

def _destination(pid,item):
    relative=item.get('path')
    if item.get('kind')=='runtime' and (not isinstance(relative,str) or not re.fullmatch(r'(?:projections/[a-f0-9]{32}|[A-Za-z0-9_-]+)\.json',relative)):raise ValueError('运行项目文件路径无效')
    if item.get('kind')=='projection-settings' and relative!=pid+'.json':raise ValueError('投影设置归属无效')
    if item.get('kind') in ('local-room','installed-room') and (not isinstance(relative,str) or not project_worlds.ROOM_PATH.fullmatch(relative)):raise ValueError('房间运行文件路径无效')
    return _safe_path(_base(pid,item),relative)

def _tree(base,kind,owner=None):
    base=_safe_path(base)
    if not base.exists():return []
    result=[]
    for folder,dirs,files in os.walk(base,followlinks=False):
        for name in dirs:_safe_path(base,(Path(folder)/name).relative_to(base).as_posix())
        for name in files:
            relative=(Path(folder)/name).relative_to(base).as_posix();file=_safe_path(base,relative)
            item=dict(kind=kind,path=relative)
            if owner:item['owner']=owner
            result.append((file,item))
    return result

def _owned_files(pid,project):
    result=_tree(storage.PROJECTS/pid,'project')+_tree(storage.history_directory(pid),'history')
    settings=storage.DATA/'projections/project-settings'/(pid+'.json')
    if settings.is_file():result.append((settings,dict(kind='projection-settings',path=pid+'.json')))
    for file in sorted((storage.DATA/'projections').glob('*/projection.json')):
        value=json.loads(file.read_text('utf-8'))
        if value.get('projectId')==pid:result+=_tree(file.parent,'projection',file.parent.name)
    oid=room_bindings.binding(project)['oracleId']
    for file in [*sorted(storage.RUNTIME.glob('*.json')),*sorted((storage.RUNTIME/'projections').glob('*.json'))]:
        try:value=json.loads(file.read_text('utf-8'))
        except (ValueError,UnicodeError):
            if file.name!=oid+'.json':continue
            value={'projectId':pid}
        if isinstance(value,dict) and value.get('projectId')==pid:
            relative=file.relative_to(storage.RUNTIME).as_posix();item=dict(kind='runtime',path=relative)
            result.append((_destination(pid,item),item))
    seen=set();unique=[]
    for file,item in result:
        if file not in seen:unique.append((file,item));seen.add(file)
    return unique

def delete(data,server,transaction=None):
    """Called under the server lock; save latest draft, snapshot, then deactivate."""
    draft=data.get('project');pid=storage.valid_id((draft or {}).get('projectId',data.get('projectId')))
    _editable(pid,draft);assert_active(pid)
    existing=storage.load_project(pid) if storage.project_file(pid).exists() else None
    _editable(pid,existing)
    pearl_suspension.verify_runtime()
    records=_registry();owned=[copy.deepcopy(v) for v in records if v.get('projectId')==pid]
    remaining=[v for v in records if v.get('projectId')!=pid]
    room_files=project_worlds.owned_files(pid,existing or draft,owned,records)
    world_changes=project_worlds.plan(remaining,pid) if owned else {}
    if room_files or world_changes:project_worlds.require_closed()
    if draft is not None:project=server._save(copy.deepcopy(draft))
    elif existing is not None:project=existing
    else:raise ValueError('项目不存在')
    pearl_changes=pearl_suspension.runtime_changes(pid)
    token=uuid.uuid4().hex;folder=_safe_path(root(),token);folder.mkdir(parents=True)
    items=[]
    for index,(file,item) in enumerate(_owned_files(pid,project)+room_files):
        content=file.read_bytes();digest=hashlib.sha256(content).hexdigest();blob_id=format(index,'08x');blob=_safe_path(folder,'blobs/'+blob_id);blob.parent.mkdir(exist_ok=True);blob.write_bytes(content)
        items.append(dict(item,blob=blob_id,sha256=digest,size=len(content)))
    value=dict(schema=SCHEMA,token=token,state='deleting',projectId=pid,name=project['name'],project=project,deletedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=items,registry=owned)
    external=transaction is not None
    transaction=transaction or room_migration.Files()
    if external:transaction.json(_manifest(token),value)
    else:server.atomic(_manifest(token),value)
    try:
        if room_files:project_worlds.require_closed()
        # Removing the manifest first prevents discovery after an interrupted delete.
        ordered=sorted(items,key=lambda item:0 if item['kind']=='project' and item['path']=='project.json' else 1)
        for item in ordered:
            target=_destination(pid,item)
            if item['kind'] in ('local-room','installed-room') and hashlib.sha256(target.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('删除期间房间文件已改变，已停止操作')
            transaction.remove(target)
        transaction.json(storage.RUNTIME/'creator/registry.json',remaining)
        project_worlds.apply(transaction,world_changes)
        for file,content in pearl_changes.items():transaction.json(file,content)
        value['state']='deleted'
        if external:transaction.json(_manifest(token),value)
        else:server.atomic(_manifest(token),value)
    except Exception:
        transaction.rollback();value['state']='failed'
        if not external:server.atomic(_manifest(token),value)
        raise
    return dict(ok=True,token=token,projectId=pid,name=project['name'])

def restore(token,server):
    value=_read(_token(token));pid=value['projectId'];_editable(pid,value['project'])
    storage.assert_not_purged(pid)
    if value.get('state') not in ACTIVE_STATES:raise ValueError('此删除记录已恢复')
    current=storage.project_file(pid)
    if current.exists() and value['state']=='deleted':raise ValueError('同名项目编号已被占用，不能覆盖恢复')
    binding=room_bindings.binding(value['project']);records=_registry()
    for file in storage.project_files():
        if file.parent.name==pid:continue
        other=room_bindings.binding(json.loads(file.read_text('utf-8')))
        if other['oracleId']==binding['oracleId'] or other['ai']==binding['ai'] or binding['entryMode']=='copy' and binding['entry'] in (other['ai'],other['entry']):raise ValueError('原项目的房间或迭代器编号已被其他项目占用')
    for item in records:
        if item.get('projectId')==pid and item not in value['registry']:raise ValueError('运行目录已有不同的同名项目，不能覆盖恢复')
        if item.get('projectId')!=pid and (item.get('oracleId')==binding['oracleId'] or item.get('ai')==binding['ai']):raise ValueError('原项目的房间或迭代器编号已被其他项目占用')
    staged=[]
    for item in value['files']:
        _,content=_blob(value,item)
        target=_destination(pid,item)
        if target.exists() and target.read_bytes()!=content:raise ValueError('恢复位置存在不同文件，已停止以免覆盖')
        staged.append((target,content))
    pearl_changes=pearl_suspension.runtime_changes(pid,restoring=True)
    if any(item.get('kind') in ('local-room','installed-room') for item in value['files']):project_worlds.require_closed()
    transaction=room_migration.Files();previous=value['state']
    try:
        value['state']='restoring';server.atomic(_manifest(token),value)
        for file,content in staged:transaction.write(file,content)
        restored_records=[v for v in records if v.get('projectId')!=pid]+value['registry']
        transaction.json(storage.RUNTIME/'creator/registry.json',restored_records)
        if value['registry']:project_worlds.apply(transaction,project_worlds.plan(restored_records,pid))
        for file,content in pearl_changes.items():transaction.json(file,content)
        value['state']='restored';server.atomic(_manifest(token),value)
    except Exception:
        transaction.rollback();value['state']=previous;server.atomic(_manifest(token),value);raise
    return dict(ok=True,project=storage.load_project(pid))

def reconcile_deleted(token,server):
    """One-time upgrade of old tombstones; archive outputs before removing them."""
    value=_read(_token(token));pid=value['projectId'];_editable(pid,value['project'])
    if value['state']!='deleted':raise ValueError('此删除记录不能清理运行残留')
    for item in value['files']:_blob(value,item)
    records=_registry()
    if any(v.get('projectId')==pid for v in records):raise ValueError('已删除项目仍在运行目录，请先检查项目状态')
    files=project_worlds.owned_files(pid,value['project'],value['registry'],records,value['deletedAt'])
    world_changes=project_worlds.plan(records,pid) if value['registry'] else {}
    pearl_changes=pearl_suspension.runtime_changes(pid)
    if files or world_changes:project_worlds.require_closed()
    updated=copy.deepcopy(value);known={(item['kind'],item['path']) for item in value['files']}
    for file,item in files:
        if (item['kind'],item['path']) in known:raise ValueError('删除记录已有同名房间快照，未覆盖')
        content=file.read_bytes();blob_id=format(len(updated['files']),'08x')
        blob=_safe_path(root(),value['token']+'/blobs/'+blob_id);blob.parent.mkdir(parents=True,exist_ok=True);blob.write_bytes(content)
        updated['files'].append(dict(item,blob=blob_id,sha256=hashlib.sha256(content).hexdigest(),size=len(content)))
    transaction=room_migration.Files()
    try:
        if files:project_worlds.require_closed()
        for file,item in files:
            snapshot=next(x for x in updated['files'] if x['kind']==item['kind'] and x['path']==item['path'])
            if hashlib.sha256(file.read_bytes()).hexdigest()!=snapshot['sha256']:raise ValueError('清理期间房间文件已改变，已停止操作')
            transaction.remove(file)
        project_worlds.apply(transaction,world_changes)
        for file,content in pearl_changes.items():transaction.json(file,content)
        transaction.json(_manifest(token),updated)
    except Exception:
        transaction.rollback();raise
    return dict(ok=True,projectId=pid,removed=[str(file) for file,_ in files],worldFiles=[str(file) for file in world_changes])
