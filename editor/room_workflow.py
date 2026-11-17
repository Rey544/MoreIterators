import copy
import hashlib
import json
import re
import uuid
from pathlib import Path
import room_bindings
import room_migration
import storage
import room_connection_checks

SCHEMA='moreiterators.room-workflow.v1'
SUFFIX=r'(?:\.txt|\.png|_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|_mi_background\.json|_[1-9][0-9]*\.png|\.source\.json)'


def _error(code,**params):raise room_bindings.RoomBindingError('workflow'+code,**params)
def _root(pid):return storage.project_file(storage.valid_id(pid)).parent
def _path(pid):return _root(pid)/'editor-drafts/room-workflow.json'
def _hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def _document(pid):
    file=_path(pid)
    if not file.is_file():return dict(schema=SCHEMA,revision=0,pending=None)
    value=json.loads(file.read_text('utf-8'))
    if not isinstance(value,dict) or value.get('schema')!=SCHEMA or type(value.get('revision')) is not int:_error('State')
    return value


def _revision(doc,revision):
    if type(revision) is not int or revision!=doc['revision']:_error('Changed')


def _owned(binding):
    result={'ai':binding['ai']}
    if binding.get('entryMode')=='copy':result['entry']=binding['entry']
    return result


def require_sources(project):
    sources={}
    for kind,name in _owned(room_bindings.binding(project)).items():
        try:source=room_bindings.source_for(project,kind)
        except FileNotFoundError:_error('SourceMissing',room=name)
        if not source.with_suffix('.txt').is_file():_error('SourceMissing',room=name)
        sources[kind]=source
    return sources


def normalize_connections(project,value):
    if not isinstance(project.get('roomBinding'),dict) or set(project['roomBinding'])!=room_bindings.BINDING_KEYS:_error('State')
    try:room_bindings.normalize(project['roomBinding'])
    except ValueError:_error('State')
    if not isinstance(value,dict) or set(value)-{'version','rows','ownedRegions'} or value.get('version')!=2:_error('State')
    rows=value.get('rows');regions=value.get('ownedRegions')
    if not isinstance(rows,list) or len(rows)>512 or not isinstance(regions,list) or len(regions)>32:_error('State')
    binding=room_bindings.binding(project)
    if not room_bindings.REGION_RE.fullmatch(str(binding.get('region',''))) or any(not isinstance(binding.get(kind),str) or not room_bindings.ROOM_RE.fullmatch(binding[kind]) for kind in ('ai','entry')):_error('State')
    if binding.get('entryMode') not in ('copy','existing') or any(type(binding.get(key)) is not int or binding[key]<0 for key in ('aiNode','entryNode')):_error('State')
    owned=_owned(binding);found=set();result=[]
    for raw in rows:
        if not isinstance(raw,dict) or set(raw)-{'name','region','connections','tags','owned','kind'}:_error('State')
        name=raw.get('name');links=raw.get('connections');region=raw.get('region')
        if not isinstance(name,str) or not room_bindings.ROOM_RE.fullmatch(name) or name in found or region!=name.split('_')[0]:_error('State')
        if type(raw.get('owned')) is not bool or not isinstance(links,list) or len(links)>64:_error('State')
        if any(not isinstance(v,str) or v!='DISCONNECTED' and not room_bindings.ROOM_RE.fullmatch(v) for v in links):_error('State')
        if any(v!='DISCONNECTED' and not v.startswith(region+'_') for v in links):_error('CrossRegion')
        tags=raw.get('tags','')
        if not isinstance(tags,str) or len(tags)>4096 or '\n' in tags or '\r' in tags:_error('State')
        if raw['owned']:
            if raw.get('kind') not in owned or owned[raw['kind']]!=name:_error('State')
        elif name in owned.values():_error('State')
        found.add(name);result.append(dict(name=name,region=region,connections=list(links),tags=tags,owned=raw['owned'],**({'kind':raw['kind']} if raw['owned'] else {})))
    if {r['name'] for r in result if r['owned']}!=set(owned.values()):_error('State')
    if any(not isinstance(v,str) or not room_bindings.REGION_RE.fullmatch(v) for v in regions):_error('State')
    if any(v!=binding['region'] for v in regions):_error('State')
    return dict(version=2,rows=result,ownedRegions=sorted(set(regions)))


def _catalog():return room_bindings.catalog()


def _base_rows(project,cat):
    binding=room_bindings.binding(project);owned=_owned(binding);all_rows=room_bindings._room_map(cat)
    value=project.get('roomConnections')
    if value is not None:return normalize_connections(project,value)['rows']
    saved=room_bindings._stored_plan(project['projectId'])
    if saved and saved.get('connectionVersion')==2:
        return normalize_connections(project,dict(version=2,rows=saved['connectionRows'],ownedRegions=saved.get('ownedRegions',[])))['rows']
    local=storage.target_mod(project['projectId'])
    for folder in (local/'world',local/'modify/world'):
        for path in folder.glob('*/world_*.txt'):
            for row in room_bindings.parse_world(path.read_text('utf-8-sig'),path.parent.name.upper()):all_rows[row['name']]=row
    result=[]
    for kind,name in owned.items():
        import project_packages
        try:
            source=room_bindings.source_for(project,kind)
            links,tags=project_packages.selected_room_connections(project,name,source,all_rows)
        except (ValueError,OSError):
            links=list(all_rows.get(name,{}).get('connections',[]));tags=all_rows.get(name,{}).get('tags','')
        result.append(dict(name=name,region=name.split('_')[0],connections=list(links),tags=tags,owned=True,kind=kind))
    targets={link for row in result for link in row['connections'] if link!='DISCONNECTED' and link not in owned.values()}
    for name in targets:
        row=all_rows.get(name)
        if row:result.append(dict(name=name,region=name.split('_')[0],connections=list(row['connections']),tags=row.get('tags',''),owned=False))
    return result


def _edges(rows):
    by_name={row['name']:row for row in rows};seen=set();result=[]
    for row in rows:
        if not row['owned']:continue
        for node,target in enumerate(row['connections']):
            if target=='DISCONNECTED':continue
            opposite=by_name.get(target)
            reverse=[] if opposite is None else [i for i,v in enumerate(opposite['connections']) if v==row['name']]
            other=reverse[0] if len(reverse)==1 else None
            key=tuple(sorted(((row['name'],node),(target,-1 if other is None else other))))
            if key in seen:continue
            seen.add(key);result.append(dict(id=_digest(key)[:24],room=row['name'],node=node,toRoom=target,toNode=other))
    return result


def _pending_files(pid,pending):
    root=_root(pid).resolve()
    for row in pending.get('files',[]):
        path=(root/row['path']).resolve()
        if not path.is_relative_to(root/'editor-drafts/room-workflow'):_error('State')
        yield path,row


def _public(project,doc,cat):
    binding=room_bindings.binding(project);owned=_owned(binding);rows=_base_rows(project,cat);pending=doc.get('pending');names=pending['names'] if pending else {}
    mapping={original:names[kind] for kind,original in owned.items()} if pending else {}
    available=room_bindings._room_map(cat);own_rows={row['name']:row for row in rows if row['owned']}
    result=[];issues=[]
    for kind,name in owned.items():
        row=own_rows[name];display=mapping.get(name,name);links=[mapping.get(v,v) for v in row['connections']]
        import project_packages
        source=None
        try:
            source=room_bindings.source_for(project,kind)
            check=project_packages.connection_snapshot(project,name,room_bindings._room_map(cat),source=source,connections=row['connections'])
        except (ValueError,OSError):
            geometry_source=project_packages._source_label(project,source.with_suffix('.txt')) if source is not None else name+'.txt'
            connection_source='project.json' if project.get('roomConnections') is not None else 'room-binding-plan.json' if room_bindings._stored_plan(project['projectId']) else 'world_'+binding['region'].lower()+'.txt'
            check=dict(actualExitCount=None,connectionSlotCount=len(links),verified=False,canReconcile=False,issues=[dict(code='geometryUnavailable',room=display,actualExitCount=None,connectionSlotCount=len(links),geometrySource=geometry_source,connectionSource=connection_source,canReconcile=False)])
        if pending:
            check['canReconcile']=False
            for issue in check['issues']:issue.update(room=display,canReconcile=False)
        issues.extend(check['issues'])
        if pending:
            for required in pending['required']:
                for room,node in ((required.get('room'),required.get('node')),(required.get('toRoom'),required.get('toNode'))):
                    if room!=display or type(node) is not int or not 0<=node<len(links):continue
                    links[node]='DISCONNECTED'
        result.append(dict(name=display,sourceName=name,sourceRoom=name,original=name,kind=kind,owned=True,renameable=True,region=display.split('_')[0],exitCount=check['actualExitCount'],connections=links,pending=bool(pending),**{key:check[key] for key in ('actualExitCount','connectionSlotCount','verified','canReconcile','issues')}))
    for row in available.values():
        if row['name'] in owned.values():continue
        result.append(dict(row,kind='external',owned=False,renameable=False,sourceName=row['name'],sourceRoom=row['name'],original=row['name']))
    public_pending=None if not pending else {key:copy.deepcopy(pending[key]) for key in ('id','names','rooms','required')}
    return dict(projectId=project['projectId'],revision=doc['revision'],binding=binding,pending=public_pending,rooms=result,issues=issues,connections=[dict(from_={'room':edge['room'],'node':edge['node']},to={'room':edge['toRoom'],'node':edge['toNode']}) for edge in _edges(rows)],editable=not bool(room_bindings._fixed(project['projectId'])),catalogLive=bool(cat.get('fresh') and cat.get('complete') and cat.get('source')=='live'))


def load(pid):
    pid=storage.valid_id(pid);project=storage.load_project(pid)
    value=_public(project,_document(pid),_catalog())
    for edge in value['connections']:edge['from']=edge.pop('from_')
    return value


def _validate_names(project,names,cat):
    if room_bindings._fixed(project['projectId']):_error('ReadOnly')
    if not isinstance(names,dict) or set(names)-{'region','ai','entry'}:_error('State')
    old=room_bindings.binding(project);new=room_bindings.normalize(dict(old,**names));owned=_owned(old)
    if old['entryMode']=='existing' and new['entry']!=old['entry']:_error('ForeignRename',room=old['entry'])
    for other in room_bindings._projects():
        if other['projectId']==project['projectId']:continue
        b=room_bindings.binding(other)
        if new['region']!='TEST' and b['region']==new['region']:raise room_bindings.RoomBindingError('regionProject',region=new['region'],name=other.get('name') or other['projectId'])
        for name in (new['ai'],new['entry']):
            if name in (b['ai'],b['entry']):raise room_bindings.RoomBindingError('roomTaken',room=name)
    if new['region']!='TEST' and (new['region']!=old['region'] or old['entryMode']=='copy') and room_bindings._foreign_region_source(project,new['region']):raise room_bindings.RoomBindingError('regionTaken',region=new['region'])
    reserved=set(cat.get('reservedRooms',[]))|set(room_bindings._room_map(cat))
    for kind,previous in owned.items():
        name=new[kind]
        if name!=previous and (name in reserved or name in owned.values()):raise room_bindings.RoomBindingError('roomTaken',room=name)
        if name==previous:continue
        for folder in (_root(project['projectId'])/'rooms',_root(project['projectId'])/'rooms/rendered'):
            for path in folder.glob(name+'*'):
                if re.fullmatch(re.escape(name)+SUFFIX,path.name):raise room_bindings.RoomBindingError('migrationTargetExists',file=str(path))
    return new


def names(data,server):
    pid=storage.valid_id(data['projectId']);project=storage.load_project(pid);doc=_document(pid);_revision(doc,data.get('revision'));cat=_catalog()
    old=room_bindings.binding(project);new=_validate_names(project,data.get('names'),cat)
    if all(old[key]==new[key] for key in ('region','ai','entry')):_error('NoNameChanges')
    owned=_owned(old);mapping={name:new[kind] for kind,name in owned.items()};rows=_base_rows(project,cat);required=[]
    for edge in _edges(rows):
        if mapping.get(edge['room'],edge['room'])==edge['room'] and mapping.get(edge['toRoom'],edge['toRoom'])==edge['toRoom']:continue
        if edge['toNode'] is None:_error('UnknownConnection',room=edge['room'])
        required.append(dict(edge,room=mapping.get(edge['room'],edge['room']),toRoom=mapping.get(edge['toRoom'],edge['toRoom'])))
    transaction=room_migration.Files();identifier=uuid.uuid4().hex;folder=_root(pid)/'editor-drafts/room-workflow'/identifier
    pending=dict(id=identifier,names={key:new[key] for key in ('region','ai','entry')},binding=new,previousBinding=old,graphDigest=_digest(rows),required=required,rooms=[],files=[],originalFiles=[])
    try:
        for kind,name in owned.items():
            source=require_sources(project)[kind];count=room_bindings.geometry(source.with_suffix('.txt'))['exitCount']
            pending['rooms'].append(dict(kind=kind,original=name,sourceName=name,sourceRoom=name,name=new[kind],exitCount=count))
            for path in source.parent.glob(source.name+'*'):
                if not path.is_file() or not re.fullmatch(re.escape(source.name)+SUFFIX,path.name):continue
                target=folder/'rendered'/(new[kind]+path.name[len(source.name):]);transaction.write(target,path.read_bytes())
                pending['files'].append(dict(path=target.relative_to(_root(pid)).as_posix(),sha256=_hash(target)))
                pending['originalFiles'].append(dict(path=str(path.resolve()),sha256=_hash(path)))
            for suffix in ('.txt','.png'):
                original=_root(pid)/'rooms'/(name+suffix)
                if original.is_file():pending['originalFiles'].append(dict(path=str(original.resolve()),sha256=_hash(original)))
        if doc.get('pending'):
            for path,_ in _pending_files(pid,doc['pending']):transaction.remove(path)
        transaction.json(_path(pid),dict(schema=SCHEMA,revision=doc['revision']+1,pending=pending))
    except Exception:transaction.rollback();raise
    return load(pid)


def cancel(data):
    pid=storage.valid_id(data['projectId']);doc=_document(pid);_revision(doc,data.get('revision'));transaction=room_migration.Files()
    try:
        if doc.get('pending'):
            for path,_ in _pending_files(pid,doc['pending']):transaction.remove(path)
        transaction.json(_path(pid),dict(schema=SCHEMA,revision=doc['revision']+1,pending=None))
    except Exception:transaction.rollback();raise
    return load(pid)


def _endpoint(raw,rows):
    if not isinstance(raw,dict) or set(raw)-{'room','node'}:_error('Selection')
    name=raw.get('room');node=raw.get('node');row=rows.get(name)
    if row is None or type(node) is not int or not 0<=node<len(row['connections']):_error('Selection')
    return name,node


def _disconnect(rows,name,node):
    target=rows[name]['connections'][node]
    if target=='DISCONNECTED':return
    other=rows.get(target)
    opposite=[] if other is None else [i for i,v in enumerate(other['connections']) if v==name]
    if len(opposite)!=1:_error('UnknownConnection',room=name)
    other['connections'][opposite[0]]='DISCONNECTED';rows[name]['connections'][node]='DISCONNECTED'


def _plan(project,binding,rows,owned_regions,source_names=None):
    value=normalize_connections(dict(project,roomBinding=binding),dict(version=2,rows=rows,ownedRegions=owned_regions))
    copies=[]
    for kind,name in _owned(binding).items():
        source=Path(source_names[kind]) if source_names else require_sources(project)[kind]
        if not source.with_suffix('.txt').is_file():_error('SourceMissing',room=name)
        links=next(row['connections'] for row in value['rows'] if row['name']==name)
        import project_packages
        check=room_connection_checks.inspect(name,links,source.with_suffix('.txt').read_bytes(),project_packages._source_label(project,source.with_suffix('.txt')),'project.json')
        room_connection_checks.require(check)
        copies.append(dict(kind=kind,name=name,source=str(source)))
    result=dict(binding=binding,connectionVersion=2,connectionRows=value['rows'],ownedRegions=value['ownedRegions'],roomCopies=copies,warnings=[],requiresRestart=True,connectionChanges=[])
    result['worldFiles']=room_bindings.connection_world_files(result)
    return result


def import_plan(project):
    value=normalize_connections(project,project.get('roomConnections'));binding=room_bindings.binding(project)
    room_bindings.validate_connection_ownership(project,value)
    sources=require_sources(project)
    for row in value['rows']:
        if row['owned']:
            import project_packages
            check=project_packages.connection_snapshot(project,row['name'],source=sources[row['kind']],connections=row['connections'])
            room_connection_checks.require(check)
    if not room_connection_checks.connected(value['rows'],binding['ai'],binding['entry']) or not room_connection_checks.connected(value['rows'],binding['entry'],binding['ai']):_error('MissingConnections',room=binding['ai'])
    return _plan(project,binding,value['rows'],value['ownedRegions'])


def apply(data,server):
    pid=storage.valid_id(data['projectId']);project=storage.load_project(pid);doc=_document(pid);_revision(doc,data.get('revision'))
    if room_bindings._fixed(pid):_error('ReadOnly')
    require_sources(project)
    cat=_catalog();old=room_bindings.binding(project);base=_base_rows(project,cat);pending=doc.get('pending');binding=copy.deepcopy(old)
    source_names=None;mapping={}
    if pending:
        if old!=pending['previousBinding'] or _digest(base)!=pending['graphDigest']:_error('Changed')
        for item in pending['originalFiles']:
            path=Path(item['path'])
            if not path.is_file() or _hash(path)!=item['sha256']:_error('SourceChanged',file=path.name)
        for path,item in _pending_files(pid,pending):
            if not path.is_file() or _hash(path)!=item['sha256']:_error('SourceChanged',file=path.name)
        binding=_validate_names(project,pending['names'],cat);mapping={name:binding[kind] for kind,name in _owned(old).items()}
        source_names={kind:str(_root(pid)/'editor-drafts/room-workflow'/pending['id']/'rendered'/binding[kind]) for kind in _owned(old)}
    rows={mapping.get(row['name'],row['name']):dict(row,name=mapping.get(row['name'],row['name']),region=mapping.get(row['name'],row['name']).split('_')[0],connections=[mapping.get(v,v) for v in row['connections']]) for row in base}
    reconcile=data.get('reconcileRooms',[])
    if not isinstance(reconcile,list) or any(not isinstance(name,str) or name not in _owned(binding).values() for name in reconcile) or len(set(reconcile))!=len(reconcile):_error('Selection')
    if pending and reconcile:_error('Required')
    for kind,name in _owned(binding).items():
        if name not in reconcile:continue
        source=Path(source_names[kind]) if source_names else require_sources(project)[kind]
        count=room_bindings.geometry(source.with_suffix('.txt'))['exitCount'];links=rows[name]['connections']
        if any(link!='DISCONNECTED' for link in links[count:]):_error('ConnectedExitMissing',room=name)
        rows[name]['connections']=links[:count]+['DISCONNECTED']*max(0,count-len(links))
    raw=data.get('connections')
    if raw is None:raw=[{'from':{'room':data.get('ownedRoom'),'node':data.get('ownedNode')},'to':{'room':data.get('targetRoom'),'node':data.get('targetNode')}}]
    if not isinstance(raw,list) or not (0 if reconcile else 1)<=len(raw)<=64:_error('Selection')
    selected=[];seen=set();catalog=room_bindings._room_map(cat);foreign_selected=set()
    for edge in raw:
        if not isinstance(edge,dict) or set(edge)-{'from','to','replaces'}:_error('Selection')
        for endpoint in (edge.get('from'),edge.get('to')):
            name=endpoint.get('room') if isinstance(endpoint,dict) else None
            if name not in rows:
                found=catalog.get(name)
                if not found:_error('Selection')
                rows[name]=dict(name=name,region=found['region'],connections=list(found['connections']),tags=found.get('tags',''),owned=False)
        first=_endpoint(edge.get('from'),rows);second=_endpoint(edge.get('to'),rows)
        if first[0]==second[0] or not rows[first[0]]['owned']:_error('Selection')
        if rows[first[0]]['region']!=rows[second[0]]['region']:_error('CrossRegion')
        for endpoint in (first,second):
            if endpoint in seen:_error('PortRepeated',room=endpoint[0])
            seen.add(endpoint)
            if not rows[endpoint[0]]['owned']:foreign_selected.add(endpoint[0])
        selected.append(dict(first=first,second=second,replaces=edge.get('replaces')))
    foreign_selected.update(name for name,row in rows.items() if not row['owned'])
    if foreign_selected:
        if not cat.get('fresh') or not cat.get('complete') or cat.get('source')!='live':_error('LiveCatalog')
        other_owned={name for p in room_bindings._projects() if p['projectId']!=pid for name in _owned(room_bindings.binding(p)).values()}
        for name in foreign_selected:
            row=catalog.get(name)
            if name in other_owned:_error('OtherProject',room=name)
            if not row or not row.get('verified') or row.get('conditional') or row.get('exitCount')!=len(row.get('connections',[])):_error('Geometry',room=name)
            previous=rows[name]['connections'];live=list(row['connections'])
            if len(previous)!=len(live):_error('Geometry',room=name)
            own_names=set(_owned(old).values())|set(_owned(binding).values())
            for node,target in enumerate(previous):
                if target not in own_names:continue
                aliases={target,next((a for a,b in mapping.items() if b==target),target),'DISCONNECTED'}
                if live[node] not in aliases:_error('Changed')
                live[node]=target
            rows[name]['connections']=live;rows[name]['tags']=row.get('tags','')
            for item in selected:
                if item['second'][0]!=name:continue
                node=item['second'][1];target=row['connections'][node]
                allowed={item['first'][0],next((a for a,b in mapping.items() if b==item['first'][0]),item['first'][0]),'DISCONNECTED'}
                if target not in allowed:_error('Occupied',room=name,node=node+1)
                if rows[name]['connections'][node]!=target and rows[name]['connections'][node] not in allowed:_error('Changed')
    required={} if not pending else {row['id']:row for row in pending['required']}
    covered=set()
    for item in selected:
        key=item['replaces']
        if key is None and len(required)==1:key=next(iter(required))
        if key is None:continue
        if key not in required or key in covered:_error('Required')
        required_edge=required[key];needed={name for name in (required_edge['room'],required_edge['toRoom']) if rows.get(name,{}).get('owned')}
        if not needed.issubset({item['first'][0],item['second'][0]}):_error('Required')
        covered.add(key)
    if set(required)!=covered:_error('Required')
    for required_edge in required.values():_disconnect(rows,required_edge['room'],required_edge['node'])
    for item in selected:
        first,second=item['first'],item['second']
        target=rows[second[0]]['connections'][second[1]]
        if target not in ('DISCONNECTED',first[0]):_error('Occupied',room=second[0],node=second[1]+1)
        _disconnect(rows,*first)
        if rows[second[0]]['connections'][second[1]]!='DISCONNECTED':_disconnect(rows,*second)
        rows[first[0]]['connections'][first[1]]=second[0];rows[second[0]]['connections'][second[1]]=first[0]
    for kind,name in _owned(binding).items():
        field='aiNode' if kind=='ai' else 'entryNode';links=rows[name]['connections']
        if binding[field]>=len(links) or links[binding[field]]=='DISCONNECTED':
            connected=[index for index,target in enumerate(links) if target!='DISCONNECTED']
            if connected:binding[field]=connected[0]
    if binding['entryMode']=='existing':
        links=rows[binding['ai']]['connections'];binding['entry']=links[binding['aiNode']]
        if binding['entry']=='DISCONNECTED':_error('Required')
        reverse=[node for node,target in enumerate(rows[binding['entry']]['connections']) if target==binding['ai']]
        if len(reverse)!=1:_error('UnknownConnection',room=binding['entry'])
        binding['entryNode']=reverse[0]
    owned_regions=project.get('roomConnections',{}).get('ownedRegions')
    if owned_regions is None:owned_regions=[old['region']] if old['entryMode']=='copy' and not room_bindings._foreign_region_source(project,old['region']) else []
    owned_regions=[binding['region'] if r==old['region'] else r for r in owned_regions]
    plan=_plan(project,binding,list(rows.values()),owned_regions,source_names)
    def finish(transaction):
        if pending:
            for path,_ in _pending_files(pid,pending):transaction.remove(path)
        transaction.json(_path(pid),dict(schema=SCHEMA,revision=doc['revision']+1,pending=None))
    outcome=room_migration.apply(pid,binding,None,server,draft_revision=data.get('draftRevision'),_plan=plan,_finalize=finish)
    value=load(pid);value.update(ok=True,requiresRestart=True)
    for key in ('draftRevision','draftPreserved'):
        if key in outcome:value[key]=outcome[key]
    return value
