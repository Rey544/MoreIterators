
from pathlib import Path
import copy
import hashlib
import json
import re
import tempfile
import uuid
import zipfile

import project_packages
import region_packages
import room_bindings
import standalone
import storage
import playable_world
import scene_assets

SCHEMA='moreiterators.playable-export.v1'
SLUGBASE='slime-cubed.slugbase'
LOCAL_IDS={'moreiterators.local','moreiterators.core'}


def campaign_id(mod_id):
    return 'MIStory_'+hashlib.sha256(('story|'+mod_id).encode('utf-8')).hexdigest()[:24]


def _starting_room(value,rooms):
    if not isinstance(value,str) or not room_bindings.ROOM_RE.fullmatch(value) or value not in rooms:
        raise ValueError('请选择已导出的起始房间')
    if value.startswith('GATE_') or value.endswith('OFFSCREEN'):
        raise ValueError('起始房间不能是业力门或离屏房间')
    return value


def _rows(stage,regions):
    rows=[]
    for region in regions:
        text=(stage/('world/'+region.lower()+'/world_'+region.lower()+'.txt')).read_text('utf-8-sig')
        rows.extend(room_bindings.parse_world(text,region))
    names=[row['name'] for row in rows]
    if len(names)!=len(set(names)):raise ValueError('导出地区存在重复房间编号')
    if any(target!='DISCONNECTED' and target not in names for row in rows for target in row['connections']):
        raise ValueError('导出地区存在未包含的房间连接')
    return rows


def _check_entry(stage,rooms,start,required=(),room_files=None,regions=()):
    _starting_room(start,rooms)
    for room in rooms:
        files=(room_files or {}).get(room)
        geometry=stage/(files[0] if files else 'world/'+room.split('_')[0].lower()+'-rooms/'+room+'.txt')
        if not geometry.is_file():raise ValueError('缺少导出的房间：'+room)
        camera_count,_=project_packages._geometry(geometry.read_bytes(),room)
        for index in range(1,camera_count+1):
            if not geometry.with_name(geometry.stem+'_'+str(index)+'.png').is_file():raise ValueError('缺少房间相机：'+room)
    rows=playable_world.validate(stage,regions or sorted({room.split('_')[0] for room in rooms}),start,required)
    if any(row.get('replacement') for row in rows):raise ValueError('完整地图模组暂不支持替代房间素材')


def _story_files(stage,meta,start,regions,rooms,scope,room_files=None,required=(),scene=None):
    _check_entry(stage,rooms,start,required,room_files,regions)
    info=json.loads((stage/'modinfo.json').read_text('utf-8'))
    if info['id'] in info.get('requirements',[]):raise ValueError('导出模组不能依赖自身')
    if SLUGBASE not in info['requirements']:
        info['requirements'].append(SLUGBASE);info['requirements_names'].append('SlugBase')
    standalone.dump(stage/'modinfo.json',info)
    identifier=campaign_id(meta['id'])
    campaign=dict(id=identifier,name=meta['name'],description=meta['description'],
                  features=dict(start_room=start,world_state=['White'],story_regions=list(regions)))
    scene_result=scene_assets.write(stage,meta['id'],scene)
    scene_assets.audit(stage,meta['id'],scene)
    campaign['features'].update(scene_result['features'])
    relative='slugbase/'+identifier+'.json'
    standalone.dump(stage/relative,campaign)
    standalone.dump(stage/'rainmeadow.json',dict(sync_required_mods=[meta['id']]))
    manifest=dict(schema=SCHEMA,scope=scope,campaign=identifier,campaignFile=relative,startRoom=start,
                  regions=list(regions),rooms=sorted(rooms))
    if scene_result['files']:
        manifest.update(sceneFeatures=scene_result['features'],sceneFiles=scene_result['files'])
    standalone.dump(stage/'playable-manifest.json',manifest)
    (stage/'README.txt').unlink(missing_ok=True)
    audit_story(stage,manifest)
    return manifest


def audit_story(stage,manifest):
    stage=Path(stage)
    info=json.loads((stage/'modinfo.json').read_text('utf-8'))
    campaign=json.loads((stage/manifest['campaignFile']).read_text('utf-8'))
    standalone.metadata(info)
    expected=campaign_id(info['id'])
    if manifest.get('schema')!=SCHEMA or manifest['campaign']!=expected or manifest['campaignFile']!='slugbase/'+expected+'.json':
        raise ValueError('剧情注册编号与导出模组不一致')
    features=campaign.get('features',{})
    scene_features=manifest.get('sceneFeatures',{})
    if not isinstance(scene_features,dict) or set(scene_features)-set(scene_assets.KINDS):raise ValueError('场景注册与导出内容不一致')
    if campaign.get('id')!=expected or features!={'start_room':manifest['startRoom'],'world_state':['White'],'story_regions':manifest['regions'],**scene_features}:
        raise ValueError('剧情入口与已导出房间不一致')
    if scene_features:scene_assets.audit_export(stage,info['id'],scene_features,manifest.get('sceneFiles',[]))
    elif manifest.get('sceneFiles'):raise ValueError('场景注册与导出内容不一致')
    if SLUGBASE not in info.get('requirements',[]) or len(info['requirements'])!=len(info['requirements_names']):
        raise ValueError('完整地图模组缺少 SlugBase 依赖')
    if json.loads((stage/'rainmeadow.json').read_text('utf-8'))!=dict(sync_required_mods=[info['id']]):
        raise ValueError('雨甸模组同步声明不一致')
    declared={row['name'] for row in _rows(stage,manifest['regions'])}
    if declared!=set(manifest['rooms']):raise ValueError('剧情地区的房间清单不完整')
    _starting_room(manifest['startRoom'],declared)
    if (stage/'modify/world/regions.txt').read_text('utf-8-sig').splitlines()!=['[ADD]'+value for value in manifest['regions']]:
        raise ValueError('剧情地区注册与导出内容不一致')


def _files(stage):
    return {path.relative_to(stage).as_posix() for path in stage.rglob('*') if path.is_file()}


def _check_files(stage,expected):
    if _files(stage)!=expected:raise ValueError('完整地图模组包含未审核文件')


def verify_archive(stage,path):
    
    manifest=json.loads((stage/'playable-manifest.json').read_text('utf-8'))
    audit_story(stage,manifest)
    expected={stage.name+'/'+relative:stage/relative for relative in _files(stage)}
    with zipfile.ZipFile(path) as archive:
        if len(archive.namelist())!=len(expected) or set(archive.namelist())!=set(expected):
            raise ValueError('完整地图模组文件清单不一致')
        for name,source in expected.items():
            info=archive.getinfo(name)
            if info.file_size!=source.stat().st_size:raise ValueError('完整地图模组文件校验失败：'+name)
            digest=hashlib.sha256()
            with archive.open(name) as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
            if digest.hexdigest()!=region_packages._digest(source):raise ValueError('完整地图模组文件校验失败：'+name)


def _project_build(request,server):
    meta=standalone.metadata(request)
    start=request.get('startRoom')
    def finish(stage,manifest,mapping):
        expected=_files(stage)
        registry=json.loads((stage/'moreiterators/registry.json').read_text('utf-8'))
        if start is None:
            selected=request.get('settingsProject')
            record=next((row for row in registry if row['projectId']==selected),registry[0])
            final_start=record['entry']
        else:
            
            if start not in mapping:raise ValueError('请选择已导出的起始房间')
            final_start=mapping[start]
        rows=_rows(stage,manifest['regions']);rooms=[row['name'] for row in rows]
        story=_story_files(stage,meta,final_start,manifest['regions'],rooms,'project',required=[row['ai'] for row in registry],scene=request.get('scene'))
        manifest['story']=story
        standalone.dump(stage/'content-manifest.json',manifest)
        _check_files(stage,(expected-{'README.txt'})|{'playable-manifest.json','rainmeadow.json',story['campaignFile']}|set(story.get('sceneFiles',[])))
        return manifest
    return standalone.build(request,server,save_preferences=False,finalize=finish,verify=verify_archive)


def _region_projects(request,server,rooms):
    ids=request.get('projects',[])
    if not isinstance(ids,list) or len(ids)>100 or any(not isinstance(pid,str) for pid in ids) or len(set(ids))!=len(ids):
        raise ValueError('请选择有效项目')
    selected=[]
    for pid in ids:
        project=server.validate(copy.deepcopy(storage.load_project(storage.valid_id(pid))))
        import room_source_choices
        project=room_source_choices.export_project(project)
        pair=server.roomnames(project)[:2]
        present=[room in rooms for room in pair]
        if any(present) and not all(present):raise ValueError('整片区域没有包含此项目的两个房间：'+project['name'])
        if all(present):selected.append(project)
    names=standalone.export_room_names(selected,request['id'])
    for project in selected:
        if tuple(server.roomnames(project)[:2])!=tuple(names[project['projectId']]):
            raise ValueError('整片区域导出不能改写项目房间编号：'+project['name'])
    return selected


class CompleteRegion:
    
    def __init__(self,collector,region,rooms,room_files,dependencies,start):
        self.collector=collector;self.regions=[region];self.rooms=rooms;self.room_files=room_files
        self.dependencies=dependencies;self.start=start
        self.files=[dict(path=path,size=source.stat().st_size,sha256=region_packages._digest(source)) for path,source in sorted(collector.files.items())]
        self.files.extend(dict(path=path,size=len(data),sha256=hashlib.sha256(data).hexdigest()) for path,data in sorted(collector.generated.items()))
        self.file_names={record['path'] for record in self.files}
        self.templates=sorted(path for path in self.file_names if '_settingstemplate_' in Path(path).name.lower())

    def copy_to(self,stage):
        for relative,source in self.collector.files.items():
            target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
        for relative,data in self.collector.generated.items():
            target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        self.verify(stage)

    def verify(self,stage):
        for record in self.files:
            target=stage/record['path']
            if not target.is_file() or target.stat().st_size!=record['size'] or region_packages._digest(target)!=record['sha256']:
                raise ValueError('导出期间区域文件发生变化：'+record['path'])

    def validate_world(self,stage,required=()):
        rows=playable_world.validate(stage,self.regions,self.start,required)
        if any(row.get('replacement') for row in rows):raise ValueError('完整地图模组暂不支持替代房间素材')
        return rows


def _region_build(request,server):
    meta=standalone.metadata(request);region=region_packages._region(request.get('region'))
    collector,rooms,room_files=region_packages._collect(region,request.get('projects',[]))
    projects=_region_projects(request,server,set(rooms))
    if not projects and any(request.get(key,False) for key in ('pearls','broadcasts','workPearls','projections')):
        raise ValueError('此区域没有已选择的迭代器项目，不能导出关联内容')
    start=request.get('startRoom')
    if start is None:
        selected=next((project for project in projects if project['projectId']==request.get('settingsProject')),projects[0] if projects else None)
        if selected is None:raise ValueError('请选择已导出的起始房间')
        start=server.roomnames(selected)[1]
    _starting_room(start,rooms)
    dependencies={key:value for key,value in collector.dependencies.items()}
    if LOCAL_IDS.intersection(dependencies) and not projects:
        raise ValueError('完整区域缺少本地迭代器项目，请先选择其所属作品')
    if projects:
        for identifier in LOCAL_IDS:dependencies.pop(identifier,None)
    if any(identifier.startswith('moreiterators') for identifier in dependencies):
        raise ValueError('完整区域仍引用未打包的 MI 本地内容')
    if meta['id'] in dependencies:raise ValueError('请使用不同的模组 ID，不能覆盖当前区域来源模组')
    context=CompleteRegion(collector,region,rooms,room_files,dependencies,start)
    files=context.files
    def finish(stage,manifest=None,mapping=None):
        expected=_files(stage)|set(collector.files)|set(collector.generated)
        context.copy_to(stage)
        info=json.loads((stage/'modinfo.json').read_text('utf-8'))
        for dependency in sorted(dependencies.values(),key=lambda value:value['id']):
            if dependency['id'] not in info['requirements']:
                info['requirements'].append(dependency['id']);info['requirements_names'].append(dependency['name'])
        standalone.dump(stage/'modinfo.json',info)
        region_manifest=dict(schema=region_packages.SCHEMA,kind='region-files',region=region,rooms=rooms,roomFiles=room_files,
            dependencies=sorted(dependencies.values(),key=lambda value:value['id']),gameDependency=True,files=sorted(files,key=lambda value:value['path']))
        standalone.dump(stage/'region-manifest.json',region_manifest)
        if projects:
            registry=json.loads((stage/'moreiterators/registry.json').read_text('utf-8'))
            connections={row['name']:row['connections'] for row in context.validate_world(stage,[record['ai'] for record in registry])}
            for record in registry:
                for room,other,node in ((record['ai'],record['entry'],record['exitNode']),(record['entry'],record['ai'],record['entryNode'])):
                    if not 0<=node<len(connections[room]) or connections[room][node]!=other:
                        raise ValueError('区域实际连接与迭代器绑定不一致：'+room)
        story=_story_files(stage,meta,start,[region],rooms,'region',room_files,[server.roomnames(project)[0] for project in projects],scene=request.get('scene'))
        if manifest is not None:
            manifest['story']=story;manifest['completeRegion']=region
            standalone.dump(stage/'content-manifest.json',manifest)
        _check_files(stage,(expected-{'README.txt'})|{'region-manifest.json','playable-manifest.json','rainmeadow.json',story['campaignFile']}|set(story.get('sceneFiles',[])))
        return story
    if projects:
        content={**request,'projects':[project['projectId'] for project in projects],'extraRooms':[]}
        return standalone.build(content,server,save_preferences=False,finalize=finish,verify=verify_archive,region_context=context)
    with tempfile.TemporaryDirectory(prefix='mi-playable-') as temporary:
        stage=Path(temporary)/meta['id'];stage.mkdir()
        info={key:meta[key] for key in ('id','name','authors','description','version')}
        info.update(requirements=[],requirements_names=[],tags=['Regions'],target_game_version='v1.11.8')
        standalone.dump(stage/'modinfo.json',info)
        cover=standalone.cover_bytes(meta['cover'])
        if cover:(stage/'thumbnail.png').write_bytes(cover)
        manifest=finish(stage)
        expected=set(collector.files)|set(collector.generated)|{'modinfo.json','region-manifest.json','playable-manifest.json','rainmeadow.json',manifest['campaignFile']}|set(manifest.get('sceneFiles',[]))
        if cover:expected.add('thumbnail.png')
        if {path.relative_to(stage).as_posix() for path in stage.rglob('*') if path.is_file()}!=expected:
            raise ValueError('完整地图模组包含未审核文件')
        storage.EXPORTS.mkdir(parents=True,exist_ok=True)
        filename=meta['id'].replace('.','-')+'-playable-'+uuid.uuid4().hex[:12]+'.zip'
        with zipfile.ZipFile(storage.EXPORTS/filename,'w',zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file():archive.write(path,meta['id']+'/'+path.relative_to(stage).as_posix())
        try:verify_archive(stage,storage.EXPORTS/filename)
        except Exception:
            (storage.EXPORTS/filename).unlink(missing_ok=True)
            raise
        return dict(ok=True,url='/exports/'+filename,manifest=manifest)


def build(request,server):
    if not isinstance(request,dict):raise ValueError('导出选项无效')
    request={**request,'scene':scene_assets.validate(request.get('scene'))}
    scope=request.get('scope','project')
    if scope=='project':return _project_build(request,server)
    if scope=='region':return _region_build(request,server)
    raise ValueError('导出内容无效')


def save_preferences(request,server):
    
    if not isinstance(request,dict):raise ValueError('导出配置无效')
    pid=storage.valid_id(request.get('settingsProject'))
    project=storage.project_file(pid)
    if not project.is_file():raise ValueError('导出配置所属项目不存在')
    value={}
    for key,limit in (('id',64),('name',100),('authors',200),('description',4000),('version',32)):
        item=request.get(key,'')
        if not isinstance(item,str) or len(item)>limit or '\x00' in item:raise ValueError('导出配置无效：'+key)
        value[key]=item
    cover=request.get('cover','')
    if not isinstance(cover,str):raise ValueError('导出配置无效：cover')
    standalone.cover_bytes(cover);value['cover']=cover
    projects=request.get('projects',[])
    if not isinstance(projects,list) or len(projects)>100 or any(not isinstance(item,str) for item in projects) or len(set(projects))!=len(projects):raise ValueError('请选择有效项目')
    value['projects']=[storage.valid_id(item) for item in projects]
    import project_bundles
    external=request.get('externalMods',[])
    if not isinstance(external,list) or len(external)>20 or any(not isinstance(item,str) for item in external) or len(set(external))!=len(external):raise ValueError('请选择有效的地图模组')
    value['externalMods']=[project_bundles._mod_id(item) for item in external]
    if 'packageName' in request or 'packageVersion' in request:
        for key,limit in (('packageName',100),('packageVersion',32)):
            item=request.get(key,'')
            if not isinstance(item,str) or len(item)>limit or '\x00' in item:raise ValueError('导出配置无效：'+key)
            value[key]=item
    for key in ('dialogue','pearls','broadcasts','workPearls','projections'):
        item=request.get(key,False)
        if type(item) is not bool:raise ValueError('导出配置无效：'+key)
        value[key]=item
    value['extraRooms']=standalone._requested_extra_rooms(request)
    scope=request.get('scope','project')
    if scope not in ('project','region'):raise ValueError('导出内容无效')
    value['scope']=scope
    if 'parts' in request:
        parts=request['parts']
        if not isinstance(parts,list) or any(not isinstance(part,str) or part not in ('appearance','textures','room','dialogue') for part in parts) or len(parts)!=len(set(parts)):
            raise ValueError('导出内容无效')
        value['parts']=list(parts)
    if 'format' in request:
        if request['format'] not in ('project','json','mod','playable','assets','region'):raise ValueError('导出内容无效')
        value['format']=request['format']
    for key,pattern in (('startRoom',room_bindings.ROOM_RE),('region',room_bindings.REGION_RE)):
        item=request.get(key,'')
        if not isinstance(item,str) or item and not pattern.fullmatch(item):raise ValueError('导出配置无效：'+key)
        value[key]=item
    collection=request.get('pearlCollectionId','')
    if not isinstance(collection,str):raise ValueError('请选择有效的珍珠项目')
    if collection:
        import pearl_projects
        pearl_projects.valid_id(collection)
    value['pearlCollectionId']=collection
    value['scene']=scene_assets.validate(request.get('scene'))
    server.atomic(project.parent/'export-settings.json',value)
    return dict(ok=True)
