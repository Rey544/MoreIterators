"""Previewed, recoverable edits to one iterator's authoring associations.

Shared pearls are edited by reader/spawn only. Transfers never apply target drafts
to the game, reuse identities, or replace another project's rooms.
"""
import copy, datetime, hashlib, json, time, uuid
from pathlib import Path
import storage, room_bindings, room_migration, project_lifecycle as life
import pearl_projects, pearl_suspension, projections, project_worlds

_plans={}
SCHEMA='moreiterators.association-operation.v1'

def _json(file):return json.loads(file.read_text('utf-8'))
def _digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
def _hash(file):return hashlib.sha256(file.read_bytes()).hexdigest() if file.exists() else None
def _projection_snapshot(pid):return {str(file):_hash(file) for file in projections.root().glob('*/projection.json') if _json(file).get('projectId')==pid}
def _pearl_files():
    marker=pearl_projects.metadata_path()
    if not marker.exists():return sorted((storage.DATA/'pearls').glob('*/pearl.json'))
    catalog=pearl_projects._validate_catalog(_json(marker))
    return [file for entry in catalog['projects'] for file in sorted(pearl_projects._directory(entry['id']).glob('*/pearl.json'))]
def _cid(file,p):
    if p.get('collectionId'):return p['collectionId']
    return 'legacy' if file.is_relative_to(storage.DATA/'pearls') else file.parents[2].name

def _source(data):
    source=data.get('source') or {}
    if not isinstance(source,dict):raise ValueError('关联内容来源无效')
    token=source.get('token');archive=None
    if token:
        archive=life._read(life._token(token))
        if archive['state'] not in life.ACTIVE_STATES:raise ValueError('此删除记录已恢复，请重新选择项目')
        pid=archive['projectId'];project=copy.deepcopy(archive['project'])
        for item in archive['files']:life._blob(archive,item)
    else:
        pid=storage.valid_id(source.get('projectId'));life.assert_active(pid)
        project=storage.load_project(pid)
        if data.get('project') is not None:
            draft=copy.deepcopy(data['project'])
            if not isinstance(draft,dict) or draft.get('projectId')!=pid:raise ValueError('关联内容与当前项目不一致')
            # Appearance's page may have an older independent editor snapshot.
            for key in ('dialogue','dialogueRevision','overseer','overseerRevision','roomBinding'):
                if key in project:draft[key]=copy.deepcopy(project[key])
                else:draft.pop(key,None)
            project=draft
    life._editable(pid,project)
    return pid,project,archive

def _gather(data):
    pid,project,archive=_source(data);items=[];payload={};evidence={}
    def item(id,type,label,detail,actions,value,shared=False):
        items.append(dict(id=id,type=type,label=label,detail=detail,allowedActions=actions,shared=shared))
        payload[id]=value
    item('appearance','appearance','外观与贴图','包含声音设置',['keep','move'],{k:copy.deepcopy(project[k]) for k in ('design','textures','editor') if k in project})
    if 'dialogue' in project:item('dialogue','dialogue','剧情对话','见面剧情与通用读取对话',['keep','move'],copy.deepcopy(project['dialogue']))
    if 'overseer' in project:item('overseer','overseer','监视器设置','',['keep','move'],copy.deepcopy(project['overseer']))
    item('rooms','rooms','房间工程','房间输出随本体删除；工程源与快照保留在最近删除',['keep'],None)
    source_projections=[]
    if archive:
        evidence[str(life._manifest(archive['token']))]=_hash(life._manifest(archive['token']))
        for entry in archive['files']:
            if entry['kind']=='projection' and entry['path']=='projection.json':
                _,content=life._blob(archive,entry);source_projections.append((None,json.loads(content)))
    else:
        for file,entry in life._owned_files(pid,project):evidence[str(file)]=_hash(file)
        for file in sorted(projections.root().glob('*/projection.json')):
            p=_json(file)
            if p.get('projectId')==pid:source_projections.append((file,p))
    for file,p in source_projections:
        item('projection:'+p['uid'],'projection',p.get('name',p['uid']),'投影动画',['keep','move'] if archive else ['keep','delete','move'],dict(file=file,value=p))
    settings=projections.settings_path(pid)
    if settings.exists():
        p=_json(settings);evidence[str(settings)]=_hash(settings)
        item('projectionSettings','projectionSettings','投影蒙版','',['keep','move'],p)
    elif archive:
        entry=next((e for e in archive['files'] if e['kind']=='projection-settings'),None)
        if entry:
            _,content=life._blob(archive,entry);item('projectionSettings','projectionSettings','投影蒙版','',['keep','move'],json.loads(content))
    binding=room_bindings.binding(project);rooms=pearl_suspension.owned_rooms(project)
    collection_names={p['id']:p['name'] for p in _json(pearl_projects.metadata_path()).get('projects',[])} if pearl_projects.metadata_path().exists() else {}
    for file in _pearl_files():
        p=_json(file);cid=_cid(file,p);base=cid+':'+p['id'];evidence[str(file)]=_hash(file);label=collection_names.get(cid,cid)+' / '+p['name']
        for r in p.get('readers',[]):
            if r.get('projectId')==pid:item('reader:'+base,'reader',label,'仅此迭代器的珍珠读取文本',['keep','delete','move'],dict(file=file,pearl=p,reader=r),True)
        if pid in p.get('spawnProjects',[]):item('spawn:'+base+':project','spawn',label,'本迭代器等待房间的生成位置',['keep','delete','move'],dict(file=file,pearl=p,mode='project',room=binding['entry']),True)
        for room in p.get('spawnRooms',[]):
            if room in rooms:item('spawn:'+base+':room:'+room,'spawn',label,room,['keep','delete','move'],dict(file=file,pearl=p,mode='room',room=room),True)
    evidence[str(storage.RUNTIME/'creator/registry.json')]=_hash(storage.RUNTIME/'creator/registry.json')
    for file in storage.project_files():evidence[str(file)]=_hash(file)
    source=dict(projectId=pid,name=project['name'],archived=bool(archive))
    if archive:source['token']=archive['token']
    snapshot=_digest(dict(source=source,project=project,items=items,evidence=evidence))
    return dict(source=source,snapshot=snapshot,items=items,project=project,payload=payload,archive=archive,evidence=evidence)

def inspect(data,server=None):
    g=_gather(data);targets=[]
    for file in storage.project_files():
        p=_json(file)
        if p['projectId']==g['source']['projectId']:continue
        try:life._editable(p['projectId'],p);life.assert_active(p['projectId'])
        except ValueError:continue
        targets.append(dict(projectId=p['projectId'],name=p['name']))
    return {k:g[k] for k in ('source','snapshot','items')}|dict(targets=targets,notes=['共享珍珠只处理本迭代器的文本与生成位置，独立广播保持不变。','迁移内容保存到目标项目，应用到游戏需在目标工作室操作。'])

def _projection_runtime(uid,pid):
    file=storage.RUNTIME/'projections'/(uid+'.json')
    if file.exists():
        p=_json(file)
        if p.get('projectId')!=pid or p.get('uid')!=uid:raise ValueError('投影运行文件归属冲突，已停止操作')
    return file

def _runtime_pearl_changes(selected,pid):
    marker,manifest,published=pearl_suspension._published();changes={}
    if manifest is None:return changes
    for file,p,entry in published:
        before=copy.deepcopy(p)
        for value,action,type in selected:
            authored=value['pearl']
            if authored.get('uid')!=p.get('uid'):continue
            if type=='reader':p['readers']=[r for r in p.get('readers',[]) if r.get('projectId')!=pid]
            else:
                for key in ('spawns','suspendedSpawns'):
                    p[key]=[s for s in p.get(key,[]) if not (s.get('projectId')==pid if value['mode']=='project' else s.get('entry')==value['room'] and not s.get('projectId'))]
        if p!=before:
            changes[file]=p;entry['sha256']=hashlib.sha256(json.dumps(p,ensure_ascii=False,indent=2).encode()).hexdigest()
    if changes:manifest['generation']=uuid.uuid4().hex;changes[marker]=manifest
    return changes

def plan(data,server):
    g=_gather(data)
    if data.get('snapshot')!=g['snapshot']:raise ValueError('关联内容已改变，请重新打开清单')
    delete=data.get('deleteProject',False)
    if not isinstance(delete,bool) or delete and g['source']['archived']:raise ValueError('删除项目操作无效')
    choices=data.get('choices',[])
    if not isinstance(choices,list):raise ValueError('关联内容选项无效')
    by_id={x['id']:x for x in g['items']};actions={};replace=data.get('replaceIds',[])
    if not isinstance(replace,list) or any(id not in by_id for id in replace):raise ValueError('替换选项无效')
    for choice in choices:
        id=choice.get('id');action=choice.get('action')
        if id not in by_id or id in actions or action not in by_id[id]['allowedActions']:raise ValueError('关联内容选项无效')
        actions[id]=action
    moving=any(a=='move' for a in actions.values());target=None;target_file=None
    if moving:
        tid=storage.valid_id(data.get('targetProjectId'))
        if tid==g['source']['projectId']:raise ValueError('请选择另一个迁移目标')
        life.assert_active(tid);target=storage.load_project(tid);life._editable(tid,target);target_file=storage.project_file(tid)
    else:tid=None
    conflicts=[];writes={};removes=set();selected_pearls=[];project_changed=False;new_projections=[]
    pid=g['source']['projectId'];target_before=copy.deepcopy(target)
    def conflict(id,message,replaceable=True):
        if id not in replace or not replaceable:conflicts.append(dict(id=id,message=message,canReplace=replaceable))
    def pearl_edit(file):
        if file not in writes:writes[file]=copy.deepcopy(_json(file))
        return writes[file]
    for id,action in actions.items():
        if action=='keep':continue
        type=by_id[id]['type'];value=copy.deepcopy(g['payload'][id])
        if type in ('appearance','dialogue','overseer','projectionSettings'):
            if action!='move':raise ValueError('此内容只能保留或迁移')
            if type=='appearance':
                if any(target.get(k)!=v for k,v in value.items()):conflict(id,'目标已有外观、贴图与声音设置')
                target.update(value);project_changed=True
            elif type in ('dialogue','overseer'):
                if target.get(type) and target[type]!=value:conflict(id,'目标已有'+('对话' if type=='dialogue' else '监视器设置'))
                if type=='overseer':
                    old=room_bindings.binding(g['project']);new=room_bindings.binding(target);mapping={old['ai']:new['ai'],old['entry']:new['entry']}
                    for profile in [value,*value.get('guests',[])]:
                        if isinstance(profile,dict) and isinstance(profile.get('rooms'),list):profile['rooms']=[mapping.get(room,room) for room in profile['rooms']]
                target[type]=value;target[type+'Revision']=target.get(type+'Revision',0)+1;project_changed=True
            else:
                dest=projections.settings_path(tid);old=_json(dest) if dest.exists() else None
                if old and old.get('mask')!=value['mask']:conflict(id,'目标已有投影蒙版')
                writes[dest]=dict(value,projectId=tid,revision=(old or {}).get('revision',0)+1)
        elif type=='projection':
            p=value['value'];source_file=value['file']
            if source_file is not None:removes.add(source_file)
            removes.add(_projection_runtime(p['uid'],pid))
            if action=='move':
                duplicates=[_json(f) for f in projections.root().glob('*/projection.json') if _json(f).get('projectId')==tid and (_json(f).get('name')==p.get('name') or _json(f).get('migratedFrom')==dict(projectId=pid,uid=p['uid']))]
                if duplicates:conflict(id,'目标已有同名或已迁移的投影',False)
                olduid=p['uid'];p.update(uid=uuid.uuid4().hex,projectId=tid,revision=1,migratedFrom=dict(projectId=pid,uid=olduid))
                new_projections.append((id,p));writes[projections.path(p['uid'])]=p
        elif type=='reader':
            file=value['file'];p=pearl_edit(file);reader=value['reader'];p['readers']=[r for r in p['readers'] if r.get('projectId')!=pid]
            if action=='move':
                existing=next((r for r in p['readers'] if r.get('projectId')==tid),None)
                if existing:conflict(id,'目标已为此珍珠编写读取文本')
                p['readers']=[r for r in p['readers'] if r.get('projectId')!=tid]
                reader['projectId']=tid;p['readers'].append(reader)
            selected_pearls.append((value,action,type))
        elif type=='spawn':
            p=pearl_edit(value['file']);mode=value['mode'];room=value['room']
            if mode=='project':p['spawnProjects']=[x for x in p.get('spawnProjects',[]) if x!=pid];p.setdefault('spawnPositions',{}).pop(pid,None)
            else:p['spawnRooms']=[x for x in p.get('spawnRooms',[]) if x!=room];p.setdefault('spawnRoomPositions',{}).pop(room,None)
            if action=='move':
                b=room_bindings.binding(target);dest=b['ai'] if room==room_bindings.binding(g['project'])['ai'] else b['entry']
                if dest==b['entry']:
                    if tid in p.get('spawnProjects',[]) or dest in p.get('spawnRooms',[]):conflict(id,'目标房间已有此珍珠的生成位置')
                    p['spawnRooms']=[room for room in p.get('spawnRooms',[]) if room!=dest];p.setdefault('spawnRoomPositions',{}).pop(dest,None)
                    p['spawnProjects']=list(dict.fromkeys(p.get('spawnProjects',[])+[tid]));p.setdefault('spawnPositions',{}).pop(tid,None)
                else:
                    if dest in p.get('spawnRooms',[]):conflict(id,'目标房间已有此珍珠的生成位置')
                    p['spawnRooms']=list(dict.fromkeys(p.get('spawnRooms',[])+[dest]));p.setdefault('spawnRoomPositions',{}).pop(dest,None)
            selected_pearls.append((value,action,type))
    if project_changed:
        normalized=server.validate(copy.deepcopy(target));normalized['updatedAt']=datetime.datetime.now().isoformat(timespec='seconds');writes[target_file]=normalized
    # Validate projection line ownership against the final target dialogue/readers.
    if moving:
        all_pearls=[writes.get(f,_json(f)) for f in _pearl_files()]
        try:entries=projections.source_entries(tid,target.get('dialogue',{}),all_pearls)
        except ValueError:
            entries=[]
            for id,action in actions.items():
                if action=='move' and by_id[id]['type'] in ('reader','dialogue'):conflict(id,'迁移后的台词编号冲突，请先在目标编辑器检查重复台词',False)
        for id,p in new_projections:
            try:projections.validate(p,resolve_sources=False);projections.resolve_lines(p,entries)
            except ValueError:conflict(id,'此投影绑定的对话未迁移到目标，请同时迁移对应对话或珍珠文本',False)
        for file in _projection_snapshot(tid):
            try:projections.resolve_lines(_json(Path(file)),entries)
            except ValueError:
                for id,action in actions.items():
                    if action=='move' and by_id[id]['type'] in ('reader','dialogue'):conflict(id,'目标的现有投影仍依赖将被替换的台词，请先调整该投影',False)
    if not delete and not g['source']['archived']:
        source_entries=projections.source_entries(pid,g['project'].get('dialogue',{}),[writes.get(f,_json(f)) for f in _pearl_files()])
        for id,value in g['payload'].items():
            if by_id[id]['type']!='projection' or actions.get(id,'keep')!='keep':continue
            try:projections.resolve_lines(value['value'],source_entries)
            except ValueError:
                for changed,action in actions.items():
                    if action!='keep' and by_id[changed]['type']=='reader':conflict(changed,'源项目的投影仍依赖此珍珠文本，请同时处理对应投影',False)
    for file,p in writes.items():
        if file.name=='pearl.json':p['revision']=p.get('revision',0)+1
    runtime_changes=_runtime_pearl_changes(selected_pearls,pid)
    writes.update(runtime_changes)
    if delete:
        records=life._registry();owned=[r for r in records if r.get('projectId')==pid]
        room_files=project_worlds.owned_files(pid,g['project'],owned,records)
        if room_files or owned and project_worlds.plan([r for r in records if r.get('projectId')!=pid],pid):project_worlds.require_closed()
    if not delete and not any(a!='keep' for a in actions.values()):raise ValueError('请选择要处理的关联内容')
    summary=[]
    if delete:summary.append('删除迭代器本体与其游戏房间输出，工程源归档。')
    summary.append('独立广播及其他迭代器的珍珠文本保持不变。')
    if moving:summary.append('迁移到目标项目草稿；不会自动应用到游戏。')
    if moving and not delete and any(actions.get(k)=='move' for k in ('appearance','dialogue','overseer','projectionSettings')):summary.append('外观、对话与设置复制到目标；源项目的参数保留。')
    if any(by_id[id]['type']=='spawn' and a=='move' for id,a in actions.items()):summary.append('生成位置迁入目标对应房间，具体坐标重置为房间默认位置。')
    if g['source']['archived']:summary.append('原始删除归档保留，仍可完整恢复。')
    token=uuid.uuid4().hex
    fingerprints={str(file):_hash(file) for file in set(writes)|removes}
    if target_file:fingerprints[str(target_file)]=_hash(target_file)
    for file in fingerprints:_resolve(_location(Path(file)))
    _plans[token]=dict(at=time.monotonic(),data=copy.deepcopy(data),snapshot=g['snapshot'],g=g,writes=writes,removes=removes,fingerprints=fingerprints,conflicts=conflicts,delete=delete,target=tid,targetProjections=_projection_snapshot(tid) if tid else None)
    for key,p in list(_plans.items()):
        if time.monotonic()-p['at']>900:_plans.pop(key,None)
    return dict(planToken=token,summary=summary,conflicts=conflicts,canApply=not conflicts)

def _location(file):
    file=Path(file).absolute()
    for key,base in [('data',storage.DATA),('installed',storage.installed_mod('association-operation')),('history',storage.archive_root()/'project-history')]:
        base=base.absolute()
        if file.is_relative_to(base):return dict(root=key,path=file.relative_to(base).as_posix())
    raise ValueError('关联操作文件不在本地项目范围内')
def _operation_root():return storage.DATA/'association-operations'
def _op_path(token):return life._safe_path(_operation_root(),life._token(token)+'/manifest.json')
def _resolve(item):
    roots=dict(data=storage.DATA,installed=storage.installed_mod('association-operation'),history=storage.archive_root()/'project-history')
    if item.get('root') not in roots:raise ValueError('关联操作恢复路径无效')
    return life._safe_path(roots[item['root']],item.get('path'))

def apply(data,server):
    token=life._token(data.get('planToken'));p=_plans.pop(token,None)
    if not p or time.monotonic()-p['at']>900:raise ValueError('操作预览已过期，请重新检查')
    if p['conflicts']:raise ValueError('请先处理目标内容冲突')
    if _gather(p['data'])['snapshot']!=p['snapshot'] or any(_hash(Path(file))!=digest for file,digest in p['fingerprints'].items()):raise ValueError('预览后内容已改变，请重新检查')
    if p['target'] and _projection_snapshot(p['target'])!=p['targetProjections']:raise ValueError('预览后目标投影已改变，请重新检查')
    g=p['g'];pid=g['source']['projectId'];transaction=room_migration.Files();deleted=None
    for file in set(p['writes'])|p['removes']:_resolve(_location(file))
    if not g['source']['archived']:_resolve(_location(storage.project_file(pid)))
    _op_path(token)
    try:
        # Preserve the source's pending appearance before the normal lifecycle
        # archives it. Independent editor fields were merged in _source().
        if not g['source']['archived'] and p['data'].get('project') is not None:
            saved=server.validate(copy.deepcopy(g['project']));transaction.json(storage.project_file(pid),saved)
        if p['delete']:deleted=life.delete(dict(projectId=pid),server,transaction=transaction)
        for file in p['removes']:
            if file.exists():transaction.remove(file)
        # Recompute the narrow published pearl edit after lifecycle suspension,
        # so it cannot accidentally reactivate preserved deleted-room spawns.
        for file,value in p['writes'].items():
            if file.is_relative_to(storage.RUNTIME):continue
            transaction.json(file,value)
        selected=[]
        by_id={i['id']:i for i in g['items']}
        for choice in p['data'].get('choices',[]):
            if choice['action']!='keep' and by_id[choice['id']]['type'] in ('reader','spawn'):selected.append((g['payload'][choice['id']],choice['action'],by_id[choice['id']]['type']))
        for file,value in _runtime_pearl_changes(selected,pid).items():transaction.json(file,value)
        # A separate operation archive covers shared-file edits and overwritten
        # target drafts. Its restore refuses changes made after this operation.
        entries=[];folder=life._safe_path(_operation_root(),token)
        for i,(file,before) in enumerate(transaction.original.items()):
            item=dict(_location(file),beforeHash=hashlib.sha256(before).hexdigest() if before is not None else None,afterHash=_hash(file))
            if before is not None:
                blob=life._safe_path(folder,'blobs/'+format(i,'08x'));blob.parent.mkdir(parents=True,exist_ok=True);blob.write_bytes(before);item['blob']=blob.name
            entries.append(item)
        value=dict(schema=SCHEMA,token=token,state='applied',sourceProjectId=pid,targetProjectId=p['target'],sourceName=g['source']['name'],createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=entries,trashToken=(deleted or {}).get('token'))
        server.atomic(_op_path(token),value)
    except Exception:transaction.rollback();raise
    return dict(ok=True,deletedProject=bool(deleted),sourceProjectId=pid,targetProjectId=p['target'],trashToken=(deleted or {}).get('token'),operationToken=token,requiresApply=bool(p['target']))

def operations():
    return [{k:p.get(k) for k in ('token','sourceProjectId','targetProjectId','sourceName','createdAt')} for file in sorted(_operation_root().glob('*/manifest.json'),reverse=True) if (p:=_json(file)).get('schema')==SCHEMA and p.get('state')=='applied']

def restore(data,server):
    token=life._token(data.get('operationToken'));file=_op_path(token);value=_json(file)
    if value.get('schema')!=SCHEMA or value.get('token')!=token or value.get('state')!='applied':raise ValueError('此关联操作已恢复或记录无效')
    staged=[]
    for item in value['files']:
        target=_resolve(item)
        if _hash(target)!=item['afterHash']:raise ValueError('操作后内容已有新修改，未覆盖恢复：'+target.name)
        content=None
        if item['beforeHash'] is not None:
            blob=life._safe_path(_operation_root(),token+'/blobs/'+item['blob']);content=blob.read_bytes()
            if hashlib.sha256(content).hexdigest()!=item['beforeHash']:raise ValueError('关联操作归档校验失败')
        staged.append((target,content))
    if any(i['root']=='installed' for i in value['files']):project_worlds.require_closed()
    transaction=room_migration.Files()
    try:
        for target,content in staged:
            if content is None:transaction.remove(target)
            else:transaction.write(target,content)
        value['state']='restored';transaction.json(file,value)
    except Exception:transaction.rollback();raise
    return dict(ok=True,sourceProjectId=value['sourceProjectId'])
