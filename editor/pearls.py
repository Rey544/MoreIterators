"""Editable pearl projects, separate from puppet projects and public templates."""
from pathlib import Path
import copy, datetime, hashlib, json, math, os, re, uuid
import storage,dialogue,pearl_projects,audio_assets

SCHEMA='moreiterators.pearl.v1'

def reference_project(pid):
    from project_lifecycle import reference_project as load_reference
    return load_reference(pid)
def root(collection_id=None): return pearl_projects.directory(collection_id)
def runtime(): return storage.RUNTIME/'pearls'
def valid_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Z]{1,4}[0-9]{2,4}',value):raise ValueError('珍珠编号应为 A01、B02 等大写字母与数字组合')
    return value
def path(pid,collection_id=None):
    pid=valid_id(pid);base=root(collection_id);result=base/pid/'pearl.json'
    if not result.resolve().is_relative_to(base.resolve()):raise ValueError('珍珠目录不能指向项目以外')
    return result
def files(collection_id=None):return sorted(root(collection_id).glob('*/pearl.json'))
def _read(file,cid):
    item=json.loads(file.read_text('utf-8'))
    if not isinstance(item,dict) or item.get('id')!=file.parent.name or item.get('collectionId',cid)!=cid:raise ValueError('珍珠编号或项目归属与目录不一致')
    item['collectionId']=cid
    return item
def load(pid,collection_id=None):
    cid=pearl_projects.resolve(collection_id);return _read(path(pid,cid),cid)
def listing(collection_id=None):
    cid=pearl_projects.resolve(collection_id);return [_read(f,cid) for f in files(cid)]
def list_all():
    return [item for project in pearl_projects.catalog()['projects'] for item in listing(project['id'])]
def lines(text):return [dict(lineId=uuid.uuid4().hex,text=s,hold=2.5,gap=.6) for s in text.split('\n') if s.strip()]
def reader(pid):return dict(projectId=pid,requireMark=True,repeatEnabled=False,repeatPrependCommon=False,presentation=dialogue.presentation_defaults(),repeat=[],leavePolicy='resume',read=lines('……让我看看。'),leaving=[],returning=[])
def default(collection_id=None):
    cid=pearl_projects.resolve(collection_id);used={p['id'] for p in listing(cid)}
    pid=next(chr(65+i//99)+str(i%99+1).zfill(2) for i in range(26*99) if chr(65+i//99)+str(i%99+1).zfill(2) not in used)
    return dict(schema=SCHEMA,collectionId=cid,id=pid,name=pid,uid=uuid.uuid4().hex,revision=0,notes='',appearance=dict(baseColor='#000000',highlightColor='#b0d8f0',secondaryColor='#365576',twoTone=False,size=1,effect='none',effectColor='#88bbff',effectOpacity=.4,effectSize=28,pulseSpeed=1,music=False,musicVolume=.16,musicTrack=audio_assets.default_track()),readers=[],spawnProjects=[],spawnRooms=[],spawnRoomPositions={})
def validate(p):
    p=copy.deepcopy(p)
    if not isinstance(p,dict):raise ValueError('珍珠项目格式无效')
    if p.get('schema')!=SCHEMA:raise ValueError('珍珠项目格式无效')
    if 'collectionId' not in p:p['collectionId']=pearl_projects.ensure_legacy()
    else:p['collectionId']=pearl_projects.resolve(p['collectionId'])
    valid_id(p.get('id'))
    if not isinstance(p.get('uid'),str) or not re.fullmatch('[a-f0-9]{32}',p['uid']):raise ValueError('珍珠内部 ID 无效')
    if 'runtimeId' in p and p['runtimeId']!='MoreIterators_'+p['uid']:raise ValueError('珍珠运行编号不可修改')
    if type(p.get('revision',0)) is not int or p.get('revision',0)<0:raise ValueError('珍珠版本号无效')
    for key,limit in [('name',100),('notes',20000)]:
        if not isinstance(p.get(key),str) or len(p[key])>limit or key=='name' and not p[key].strip():raise ValueError('名称或作者备注无效')
    a=p.get('appearance',{})
    for key in ('baseColor','highlightColor','secondaryColor','effectColor'):
        if not re.fullmatch('#[0-9a-fA-F]{6}',a.get(key,'')):raise ValueError('颜色必须为 RGB 十六进制')
    for key,lo,hi in [('size',.5,3),('effectOpacity',0,1),('effectSize',5,120),('pulseSpeed',.1,4),('musicVolume',0,.6)]:
        value=a.get(key)
        if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError(key+' 超出范围')
    if a.get('effect') not in ('none','glow','pulse','halcyon'):raise ValueError('未知珍珠特效')
    if type(a.get('twoTone')) is not bool or type(a.get('music')) is not bool:raise ValueError('特效开关无效')
    a['musicTrack']=audio_assets.validate_track(a.get('musicTrack'))
    line_ids=set()
    def check_lines(arr):
        if not isinstance(arr,list) or len(arr)>200:raise ValueError('一组最多 200 句')
        for line in arr:
            if not isinstance(line,dict) or not isinstance(line.get('text'),str) or len(line['text'])>2000:raise ValueError('台词无效')
            dialogue.ensure_line_id(line,line_ids)
            dialogue.validate_line_actions(line)
            if 'presentation' in line:line['presentation']=dialogue.validate_presentation(line['presentation'])
            for k,lo in [('hold',.1),('gap',0)]:
                v=line.get(k)
                if type(v) not in (float,int) or not math.isfinite(v) or not lo<=v<=60:raise ValueError('台词停留与间隔应为 0—60 秒（停留至少 0.1 秒）')
    def check_pool(pool):
        if not isinstance(pool,list) or len(pool)>40:raise ValueError('随机池最多 40 组')
        for variant in pool:
            if not isinstance(variant,dict):raise ValueError('随机组格式无效')
            if not isinstance(variant.get('name'),str) or len(variant['name'])>80:raise ValueError('随机组名称无效')
            check_lines(variant.get('lines'))
            if 'action' in variant:dialogue.validate_action(variant['action'])
    seen=set()
    if not isinstance(p.get('readers'),list) or len(p['readers'])>200:raise ValueError('读取者列表无效')
    for r in p['readers']:
        if not isinstance(r,dict):raise ValueError('读取者条目无效')
        r['requireMark']=True
        if 'presentation' in r:r['presentation']=dialogue.validate_presentation(r['presentation'])
        r.setdefault('repeatEnabled',False);r.setdefault('repeat',[])
        r.setdefault('repeatPrependCommon',False)
        if type(r['repeatPrependCommon']) is not bool:raise ValueError('先播放通用重复读取开关无效')
        if type(r['repeatEnabled']) is not bool:raise ValueError('单独重复读取开关无效')
        pid=storage.valid_id(r.get('projectId'))
        reference_project(pid)
        if pid in seen:raise ValueError('同一个迭代器不能重复绑定')
        seen.add(pid)
        if r.get('leavePolicy') not in ('resume','restart','cancel') or type(r.get('requireMark')) is not bool:raise ValueError('离开规则或印记开关无效')
        check_lines(r.get('read'))
        if 'readAction' in r:dialogue.validate_action(r['readAction'])
        for key in ('leaving','returning','repeat')+tuple(k for k in ('many',) if k in r):
            check_pool(r.get(key))
        if 'affinity' in r:
            variants=r['affinity']
            if not isinstance(variants,dict) or set(variants)-set(dialogue.AFFINITY_TIERS):raise ValueError('珍珠好感度档位无效')
            for tier,branch in variants.items():
                if not isinstance(branch,dict) or set(branch)-{'read','readAction','repeatEnabled','repeatPrependCommon','repeat','presentation'}:raise ValueError('珍珠好感度台词包含未知字段')
                if 'presentation' in branch:branch['presentation']=dialogue.validate_presentation(branch['presentation'])
                check_lines(branch.get('read'))
                if 'readAction' in branch:dialogue.validate_action(branch['readAction'])
                branch.setdefault('repeatEnabled',False);branch.setdefault('repeat',[])
                branch.setdefault('repeatPrependCommon',False)
                if type(branch['repeatPrependCommon']) is not bool:raise ValueError('先播放通用重复读取开关无效')
                if type(branch['repeatEnabled']) is not bool:raise ValueError('珍珠好感度重复读取开关无效')
                check_pool(branch['repeat'])
    if not isinstance(p.get('spawnProjects'),list) or len(set(p['spawnProjects']))!=len(p['spawnProjects']):raise ValueError('测试房间列表无效')
    for pid in p['spawnProjects']:reference_project(storage.valid_id(pid))
    positions=p.get('spawnPositions',{})
    if not isinstance(positions,dict) or set(positions)-set(p['spawnProjects']):raise ValueError('珍珠生成位置必须属于已选择的房间')
    for pid,position in positions.items():validate_position(position,spawn_geometry(pid),p['appearance']['size'])
    rooms=p.setdefault('spawnRooms',[])
    if not isinstance(rooms,list) or len(rooms)>1000 or any(not isinstance(name,str) or not re.fullmatch(r'[A-Z0-9]+_[A-Z0-9_]+',name) for name in rooms) or len(set(rooms))!=len(rooms):raise ValueError('珍珠生成房间编号无效或重复')
    room_positions=p.setdefault('spawnRoomPositions',{})
    if not isinstance(room_positions,dict) or set(room_positions)-set(rooms):raise ValueError('珍珠生成位置必须属于已选择的房间')
    known={item['entry'] for item in destinations()} if rooms else set()
    for name in rooms:
        if name not in known:raise ValueError('珍珠生成房间不在当前房间目录中：'+name)
        if name in room_positions:validate_position(room_positions[name],room_geometry(name),p['appearance']['size'])
    return p

def destinations(roomnames=None):
    import room_bindings,broadcasts
    result=[];seen=set()
    for file in storage.project_files():
        project=json.loads(file.read_text('utf-8'));pid=project['projectId'];binding=room_bindings.binding(project)
        ai,entry=(roomnames(project)[:2] if roomnames else (binding['ai'],binding['entry']))
        for kind,name in [('entry',entry),('ai',ai)]:
            if name in seen:continue
            seen.add(name);result.append(dict(key=pid if kind=='entry' else 'room:'+name,projectId=pid if kind=='entry' else '',ownerProjectId=pid,name=project['name'],entry=name,kind=kind,priority=True,region=name.split('_')[0]))
    snapshot=room_bindings.catalog()
    if snapshot.get('source') in ('live','stale'):
        available=[(region['name'],row['name']) for region in snapshot.get('regions',[]) for row in region.get('rooms',[])]
    else:available=[(row['region'],row['room']) for row in broadcasts.rooms()]
    for region,name in sorted(available):
        if name in seen:continue
        seen.add(name);result.append(dict(key='room:'+name,projectId='',ownerProjectId='',name=name,entry=name,kind='room',priority=False,region=region))
    return result

def room_geometry(name):
    import room_bindings,broadcasts
    if not isinstance(name,str) or not re.fullmatch(r'[A-Z0-9]+_[A-Z0-9_]+',name):raise ValueError('珍珠生成房间编号无效或重复')
    # Newly created rooms may have a saved authoring copy before a live snapshot.
    for file in storage.project_files():
        project=json.loads(file.read_text('utf-8'));binding=room_bindings.binding(project)
        for kind in ('entry','ai'):
            if binding[kind]==name:
                try:return _geometry_file(room_bindings.source_for(project,kind).with_suffix('.txt'),name)
                except ValueError:break
    try:source=room_bindings.resolve_room_source(name).with_suffix('.txt')
    except ValueError:
        item=broadcasts.room_index().get(name)
        if not item:raise ValueError('珍珠生成房间不在当前房间目录中：'+name)
        source=Path(item['path'])
    return _geometry_file(source,name)

def spawn_geometry(project_id):
    """Use the selected entry's exact authoring geometry; bottom-left coordinates."""
    import room_bindings,broadcasts,native_projects
    project=reference_project(storage.valid_id(project_id));binding=room_bindings.binding(project)
    if storage.link(project_id) or native_projects.binding(project_id):return broadcasts.geometry(binding['entry'])
    from project_lifecycle import reference_file
    source=reference_file(project_id,'rooms/rendered/'+binding['entry']+'.txt')
    if source is None:source=room_bindings.source_for(project,'entry').with_suffix('.txt')
    return _geometry_file(source,binding['entry'])

def _geometry_file(source,room_name):
    try:
        if source.stat().st_size>16*1024*1024:raise ValueError()
        rows=source.read_text('utf-8-sig').splitlines();width,height=map(int,rows[1].split('|')[0].split('*'))
        if not 1<=width<=2048 or not 1<=height<=2048 or width*height>1024*1024:raise ValueError()
        cells=rows[11].split('|')
        if len(cells)<width*height:raise ValueError()
        solids=[];shortcuts=[]
        for index,cell in enumerate(cells[:width*height]):
            x=index//height;y=height-1-index%height;kind=cell.split(',')[0]
            if kind=='1':solids.append([x,y])
            if kind=='4':shortcuts.append([x,y])
        cameras=[]
        for camera in rows[3].split('|'):
            if camera.strip():
                x,y=map(float,camera.split(','))
                if not math.isfinite(x) or not math.isfinite(y):raise ValueError()
                cameras.append([x,height*20-800-y])
        return dict(room=room_name,region=room_name.split('_')[0],width=width,height=height,solids=solids,shortcuts=shortcuts,cameras=cameras)
    except (OSError,ValueError,IndexError,UnicodeError):raise ValueError('珍珠生成房间地形无法读取，请先导入有效房间。')

def validate_position(position,geometry,size):
    if not isinstance(position,dict) or set(position)!={'x','y'}:raise ValueError('珍珠生成位置格式无效')
    if any(type(position[key]) not in (int,float) or not math.isfinite(position[key]) or not 0<=position[key]<=1 for key in ('x','y')):raise ValueError('珍珠生成位置应为 0—1 的有限数值')
    x=position['x']*geometry['width']*20;y=position['y']*geometry['height']*20;radius=5*size
    if not radius<=x<=geometry['width']*20-radius or not radius<=y<=geometry['height']*20-radius:raise ValueError('珍珠生成位置超出房间边界，请向房间内侧移动。')
    if [int(x//20),int(y//20)] in geometry['solids']:raise ValueError('珍珠生成位置位于实体地形内，请选择空闲位置。')
def atomic(file,value):
    pearl_projects.atomic(file,value)
def _prepare_save(p):
    p=validate(p);file=path(p['id'],p['collectionId'])
    for other in list_all():
        if other['uid']==p['uid'] and (other['id']!=p['id'] or other['collectionId']!=p['collectionId']):raise ValueError('已保存珍珠的内部编号、珍珠编号与所属项目固定')
    if file.exists():
        old=load(p['id'],p['collectionId'])
        if old['uid']!=p['uid']:raise ValueError('该珍珠编号已被使用，请换一个编号')
        if p.get('revision')!=old['revision']:raise ValueError('珍珠已在其他页面修改，请重新打开')
    elif p.get('revision',0)!=0:raise ValueError('此珍珠版本没有对应的已保存文件')
    p['revision']=p.get('revision',0)+1;p['updatedAt']=datetime.datetime.now().isoformat(timespec='seconds')
    return p,file

def save(p):
    with pearl_projects.LOCK:
        p,file=_prepare_save(p);atomic(file,p);return p
def compile_project(p,roomnames):
    out=copy.deepcopy(p);out.pop('notes',None);out['runtimeId']='MoreIterators_'+p['uid']
    appearance=out.get('appearance',{})
    if 'musicTrack' in appearance:
        enabled=appearance.get('music') and appearance.get('effect')=='halcyon'
        appearance['musicTrack']=audio_assets.runtime_track(appearance['musicTrack'] if enabled else None)
    out['spawns']=[]
    for pid in p['spawnProjects']:
        project=reference_project(pid);ai,entry,oid=roomnames(project)
        spawn=dict(projectId=pid,entry=entry)
        if pid in p.get('spawnPositions',{}):
            position=p['spawnPositions'][pid];validate_position(position,spawn_geometry(pid),p['appearance']['size']);spawn['position']=copy.deepcopy(position)
        out['spawns'].append(spawn)
    seen={spawn['entry'] for spawn in out['spawns']}
    for room in p.get('spawnRooms',[]):
        if room in seen:continue
        spawn=dict(projectId='',entry=room)
        if room in p.get('spawnRoomPositions',{}):
            position=p['spawnRoomPositions'][room];validate_position(position,room_geometry(room),p['appearance']['size']);spawn['position']=copy.deepcopy(position)
        out['spawns'].append(spawn);seen.add(room)
    for r in out['readers']:
        project=reference_project(r['projectId']);r['oracleId']=roomnames(project)[2];r['name']=project['name']
    return out
def apply(p,roomnames):
    # Applying a pearl publishes only its entire collection, never a mixture.
    with pearl_projects.LOCK:
        p,file=_prepare_save(p)
        publish_collection(p['collectionId'],roomnames,pending=(file,p),request_uid=p['uid'])
        return p


def _managed_runtime(file,known_uids):
    try:
        value=json.loads(file.read_text('utf-8'))
        return (isinstance(value,dict) and value.get('schema')==SCHEMA and value.get('uid') in known_uids
                and value.get('runtimeId')=='MoreIterators_'+value.get('uid','')
                and value.get('ownerMod','') in ('','moreiterators.local')
                and file.name==value.get('id','')+'.json')
    except (OSError,ValueError,TypeError):return False


def _commit(changes):
    """Best-effort transaction with exact byte rollback, all targets preflighted."""
    old={file:file.read_bytes() if file.exists() else None for file in changes}
    completed=[]
    try:
        for file,value in changes.items():
            if value is None:
                if file.exists():file.unlink()
            else:atomic(file,value)
            completed.append(file)
    except Exception:
        for file in reversed(completed):
            if old[file] is None:
                if file.exists():file.unlink()
            else:
                temp=file.with_name(file.name+'.rollback-'+uuid.uuid4().hex)
                try:temp.write_bytes(old[file]);os.replace(temp,file)
                finally:
                    if temp.exists():temp.unlink()
        raise


def publish_collection(collection_id,roomnames,pending=None,request_uid=None):
    """Publish one collection and return its catalog; never touch external mods."""
    with pearl_projects.LOCK:
        cid=pearl_projects.resolve(collection_id)
        data=pearl_projects.catalog();items=listing(cid)
        if pending:
            authored=pending[1]
            items=[p for p in items if p['id']!=authored['id']]+[authored]
        # Compile all before any authoring/runtime mutation.
        import pearl_suspension
        compiled=[pearl_suspension.partition(compile_project(validate(p),roomnames)) for p in items]
        uids={p['uid'] for p in list_all()}
        if pending:uids.add(pending[1]['uid'])
        desired={runtime()/(p['id']+'.json'):p for p in compiled}
        for file in desired:
            if file.exists() and not _managed_runtime(file,uids):raise ValueError('本地运行目录存在非本项目管理的同名珍珠，已停止发布：'+file.name)
        changes={}
        if pending:changes[pending[0]]=pending[1]
        for file in sorted(runtime().glob('*.json')):
            if file not in desired and _managed_runtime(file,uids):changes[file]=None
        changes.update(desired)
        request=runtime()/'spawn-request.json'
        if request_uid:
            if request.exists():
                try:old_request=json.loads(request.read_text('utf-8'))
                except (ValueError,TypeError):old_request=None
                if not isinstance(old_request,dict) or old_request.get('uid') not in uids:raise ValueError('本地生成请求不属于已知珍珠，已停止覆盖')
            changes[request]=dict(uid=request_uid,nonce=uuid.uuid4().hex,collectionId=cid)
        elif request.exists():
            try:
                old_request=json.loads(request.read_text('utf-8'))
                if old_request.get('uid') in uids:changes[request]=None
            except (ValueError,TypeError,AttributeError):pass
        data['activeId']=cid;changes[pearl_projects.metadata_path()]=data
        changes[storage.RUNTIME/'pearl-project.json']=dict(schema='moreiterators.pearl-runtime.v1',collectionId=cid,
            generation=uuid.uuid4().hex,files=[dict(name=p['id']+'.json',uid=p['uid'],sha256=hashlib.sha256(json.dumps(p,ensure_ascii=False,indent=2).encode('utf-8')).hexdigest()) for p in sorted(compiled,key=lambda p:p['id'])],
            retiredUids=sorted(uids-{p['uid'] for p in compiled}))
        audio_assets.copy_referenced(compiled,storage.DATA/'local-mod')
        _commit(changes)
        return copy.deepcopy(data)

def migrate_runtime_lines(file,value):
    """Update stable speech anchors and commit their manifest digest together."""
    marker=storage.RUNTIME/'pearl-project.json'
    if not marker.exists():atomic(file,value);return
    manifest=json.loads(marker.read_text('utf-8'))
    if manifest.get('schema')!='moreiterators.pearl-runtime.v1':raise ValueError('珍珠运行项目清单格式无效')
    records=manifest.get('files',[])
    record=next((item for item in records if item.get('name')==file.name and item.get('uid')==value['uid']),None)
    if record is None:raise ValueError('台词锚点不属于当前珍珠项目')
    for item in records:
        source=runtime()/item['name']
        if source.parent!=runtime() or not re.fullmatch(r'[A-Z]{1,4}[0-9]{2,4}\.json',item['name']):raise ValueError('珍珠运行项目文件名无效')
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        if item.get('sha256') and item['sha256']!=digest:raise ValueError('珍珠项目正在应用，请稍后再试')
        item['sha256']=digest
    record['sha256']=hashlib.sha256(json.dumps(value,ensure_ascii=False,indent=2).encode('utf-8')).hexdigest()
    manifest['generation']=uuid.uuid4().hex
    _commit({file:value,marker:manifest})
