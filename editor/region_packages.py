
from pathlib import Path, PurePosixPath
import hashlib
import json
import re
import tempfile
import uuid
import zipfile

from PIL import Image
import project_packages
import room_bindings
import standalone
import storage
import room_asset_dependencies
import room_source_choices

SCHEMA='moreiterators.region-package.v1'
MAX_FILES=12000
MAX_BYTES=4*1024*1024*1024


def _region(value):
    if not isinstance(value,str) or not room_bindings.REGION_RE.fullmatch(value):raise ValueError('区域编号无效')
    if value=='TEST':raise ValueError('TEST 是共享测试区域，不能整片导出')
    return value


def _relative(value):
    if not isinstance(value,str) or '\\' in value or ':' in value or '\x00' in value or PurePosixPath(value).is_absolute():raise ValueError('区域文件路径无效')
    if any(part in ('','.','..') for part in value.split('/')):raise ValueError('区域文件路径越界')
    return value


def _asset_name(value):
    return bool(value and len(value)<=180 and value not in ('.','..') and
                not any(character in value for character in '/\\:*?"<>|\r\n\x00') and not value.endswith((' ','.')))


class Collector:
    def __init__(self):
        self.roots=[Path(root).resolve() for root in room_bindings.enabled_asset_roots()]
        self.assets=(storage.require_game_root()/'RainWorld_Data/StreamingAssets').resolve()
        self.files={};self.generated={};self.dependencies={};self.providers={};self.game_assets=set();self.directories={};self.lookups={};self.total=0
        self.project_ids=[]
        for root in self.roots:
            owner=root.parent if root.name=='newest' or re.fullmatch(r'v\d+(?:\.\d+)+',root.name) else root
            info=owner/'modinfo.json'
            if info.is_file():
                value=json.loads(info.read_text('utf-8-sig'));identifier=value.get('id');name=value.get('name')
                if not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',identifier) or not isinstance(name,str) or not name.strip():raise ValueError('已启用模组信息无效：'+owner.name)
                self.providers[root]=(identifier,value)

    def existing(self,root,relative):
        key=(root,relative.casefold())
        if key in self.lookups:return self.lookups[key]
        current=root
        for part in _relative(relative).split('/'):
            if current not in self.directories:
                entries={}
                if current.is_dir():
                    for path in current.iterdir():entries.setdefault(path.name.casefold(),[]).append(path)
                self.directories[current]=entries
            matches=self.directories[current].get(part.casefold(),[])
            if len(matches)>1:raise ValueError('文件大小写冲突：'+relative)
            if not matches:self.lookups[key]=None;return None
            current=matches[0]
            if current.is_symlink() or getattr(current,'is_junction',lambda:False)():raise ValueError('区域素材不能经过链接：'+relative)
        if not current.resolve().is_relative_to(root):raise ValueError('区域素材路径越界：'+relative)
        self.lookups[key]=current
        return current

    def dependency(self,identifier,seen=None):
        if identifier in self.dependencies:return
        provider=next((value for key,value in self.providers.values() if key==identifier),None)
        if provider is None:raise ValueError('区域依赖未启用或无法确认：'+identifier)
        self.dependencies[identifier]=dict(id=identifier,name=provider['name'].strip())
        dependencies=provider.get('requirements',[])
        if not isinstance(dependencies,list) or any(not isinstance(item,str) for item in dependencies):raise ValueError('区域所属模组的依赖声明无效：'+identifier)
        for item in dependencies:self.dependency(item)

    def provenance(self,relative):
        found=False;resolved=self.resolve(relative);merged=resolved.is_relative_to(self.assets/'mergedmods');base_found=False
        for root in self.roots:
            
            if root==self.assets/'mergedmods':continue
            direct=self.existing(root,relative);modify=self.existing(root,'modify/'+relative)
            uses_direct=bool(direct and direct.is_file() and (not base_found if merged else direct.resolve()==resolved.resolve()))
            uses_modify=bool(merged and modify and modify.is_file())
            if uses_direct:base_found=True
            if not (uses_direct or uses_modify):continue
            if root==self.assets:
                self.game_assets.add(relative);found=True
            elif root in self.providers:
                self.dependency(self.providers[root][0]);found=True
        if not found:raise ValueError('无法确认生效素材的所属模组：'+relative)

    def resolve(self,relative,required=True):
        for root in self.roots:
            candidate=self.existing(root,relative)
            if candidate is not None and candidate.is_file():return candidate
        if required:raise ValueError('缺少区域引用的素材：'+relative)
        return None

    def add(self,relative,source=None,choice=None):
        relative=_relative(relative)
        if relative in self.files:return self.files[relative]
        source=source or self.resolve(relative)
        if choice is None:
            if not room_bindings.is_enabled_asset(source,self.roots):raise ValueError('区域素材来自未启用模组：'+relative)
            self.provenance(relative)
        else:
            pid,name=choice
            if name is None:expected=room_source_choices.selected_asset(pid,relative)
            elif Path(relative).name in room_source_choices.selected_settings_files(pid,name):expected=room_source_choices.selected_settings_files(pid,name)[Path(relative).name]
            else:
                base=room_source_choices.selected_source(pid,name);version=room_source_choices.selected_version(pid,name)
                suffix=Path(relative).name[len(name):] if Path(relative).name.startswith(name) else ''
                camera=re.fullmatch(r'_([1-9][0-9]*)\.png',suffix)
                valid=suffix=='.txt' or camera and version and int(camera[1])<=version['cameraCount']
                expected=project_packages._sibling(base,suffix) if base is not None and valid else None
            if expected is None or Path(source).resolve()!=Path(expected).resolve():raise ValueError('所选区域素材版本无法确认：'+relative)
            owners=[root for root in self.roots if Path(source).resolve().is_relative_to(root)]
            if owners:
                owner=max(owners,key=lambda root:len(root.parts))
                if owner in self.providers:self.dependency(self.providers[owner][0])
                elif owner==self.assets:self.game_assets.add(relative)
        if source.suffix.lower()=='.png':
            try:
                with Image.open(source) as image:
                    if image.format!='PNG' or image.width*image.height>64*1024*1024:raise ValueError()
                    image.verify()
            except (OSError,ValueError) as error:raise ValueError('区域图片损坏：'+relative) from error
        self.files[relative]=source
        self.total+=source.stat().st_size
        if len(self.files)>MAX_FILES or self.total>MAX_BYTES:raise ValueError('区域文件超过导出限制')
        return source

    def selected_asset(self,relative):
        for pid in self.project_ids:
            source=room_source_choices.selected_asset(pid,relative)
            if source is not None:return source,pid
        return None,None

    def add_asset(self,relative):
        source,pid=self.selected_asset(relative)
        return self.add(relative,source,(pid,None)) if source is not None else self.add(relative)

    def asset_available(self,relative):
        source,_=self.selected_asset(relative)
        return source if source is not None else self.resolve(relative,False)

    def names(self,relative):
        result={}
        for root in self.roots:
            folder=self.existing(root,relative)
            if folder is None or not folder.is_dir():continue
            for path in folder.iterdir():
                if path.is_file():result.setdefault(path.name.casefold(),path.name)
        return sorted(result.values(),key=str.casefold)

    def relative_source(self,path):
        path=Path(path).resolve()
        for root in self.roots:
            if path.is_relative_to(root):
                relative=path.relative_to(root).as_posix()
                if root==self.assets and relative.split('/')[0] in ('mods','mergedmods'):continue
                return relative
        raise ValueError('房间素材来自未启用目录')

    def settings_dependencies(self,relative):
        text=self.files[relative].read_text('utf-8-sig')
        for value in sorted(standalone.room_palette_ids(text)):
            self.add_asset('palettes/palette'+str(value)+'.png')
        if standalone.uses_more_palettes(text):self.dependency('regionkit')
        for candidates in room_asset_dependencies.references(text,relative):
            selected=next((candidate for candidate in candidates if self.asset_available(candidate)),None)
            if not selected:raise ValueError('缺少区域房间素材：'+candidates[0])
            source=self.asset_available(selected)
            if room_asset_dependencies.native_ambient_reference(selected,source):
                self.game_assets.add(selected)
                continue
            room_asset_dependencies.validate(selected,source.read_bytes())
            self.add_asset(selected)
        for candidates in room_asset_dependencies.optional_references(text,relative):
            selected=next((candidate for candidate in candidates if self.asset_available(candidate)),None)
            if selected:self.add_asset(selected)


def _owned_rooms(project_ids):
    if not isinstance(project_ids,(list,tuple)) or any(not isinstance(pid,str) for pid in project_ids):raise ValueError('项目选择无效')
    selected=set(storage.valid_id(pid) for pid in project_ids);result={}
    for path in storage.project_files():
        try:project=json.loads(path.read_text('utf-8-sig'))
        except (OSError,ValueError) as error:raise ValueError('有项目无法读取，不能确认区域是否包含未选择作品') from error
        pid=project.get('projectId')
        if not isinstance(pid,str) or storage.binding(pid):continue
        binding=room_bindings.binding(project)
        for key in ('ai','entry'):
            if key=='entry' and binding['entryMode']!='copy':continue
            if binding[key] in result and result[binding[key]]!=pid:raise ValueError('本地项目的房间编号重复：'+binding[key])
            result[binding[key]]=pid
        metadata=project_packages.load_metadata(pid)
        for row in (metadata or {}).get('rooms',[]):
            if row.get('sourceOrigin','project')=='enabled':continue
            result.setdefault(row['name'],pid)
    return selected,result


def choices(project_ids=()):
    selected,owned=_owned_rooms(project_ids);items=[]
    for region in room_bindings.catalog().get('regions',[]):
        name=region.get('name');rows=region.get('rooms',[])
        if not isinstance(name,str) or not room_bindings.REGION_RE.fullmatch(name):continue
        private=sorted({owned[row['name']] for row in rows if row.get('name') in owned and owned[row['name']] not in selected})
        reason='TEST 是共享测试区域' if name=='TEST' else '区域包含未选择的本地作品' if private else ''
        items.append(dict(name=name,roomCount=len({row.get('name') for row in rows}),available=not reason,reason=reason,projectIds=private))
    return dict(regions=items)


def _collect(region,project_ids):
    region=_region(region);catalog=room_bindings.catalog()
    if not any(value.get('name')==region for value in catalog.get('regions',[])):raise ValueError('区域不在当前启用目录中：'+region)
    selected,owned=_owned_rooms(project_ids);collector=Collector();collector.project_ids=sorted(selected);folder='world/'+region.lower()
    world=collector.add(folder+'/world_'+region.lower()+'.txt');world_text=world.read_text('utf-8-sig');rows=room_bindings.parse_world(world_text,region)
    if not rows:raise ValueError('区域世界文件没有可识别的房间')
    in_rooms=False;raw_count=0
    for raw in world_text.splitlines():
        line=raw.strip()
        if line=='ROOMS':in_rooms=True;continue
        if line=='END ROOMS':in_rooms=False;continue
        if in_rooms and line and not line.startswith('//'):raw_count+=1
    if raw_count!=len(rows):raise ValueError('区域世界文件包含当前无法完整解析的房间定义，不会输出缺少房间的包')
    names=sorted({row['name'] for row in rows})
    private=sorted({owned[name] for name in names if name in owned and owned[name] not in selected})
    if private:raise ValueError('区域包含未选择的本地作品：'+', '.join(private))
    declared=set(names)
    for row in rows:
        for target in row['connections']:
            if target!='DISCONNECTED' and target not in declared:raise ValueError('区域世界文件引用了未定义房间：'+target)
    escaped=re.escape(region.lower())
    allowed=re.compile(r'(?:world_'+escaped+r'|properties(?:-[a-z0-9_-]+)?|displayname(?:-[a-z0-9_-]+)?|map_'+escaped+r'(?:-[a-z0-9_-]+)?|map_image_'+escaped+r'(?:-[a-z0-9_-]+)?|regioncolor|equivalences)\.txt|map_'+escaped+r'(?:-[a-z0-9_-]+)?\.png',re.I)
    for filename in collector.names(folder):
        if allowed.fullmatch(filename):collector.add(folder+'/'+filename.lower())
    if folder+'/properties.txt' not in collector.files:raise ValueError('区域缺少 properties.txt')
    template_names=set()
    for relative in list(collector.files):
        if Path(relative).name.startswith('properties'):
            template_names.update(standalone.region_template_names(collector.files[relative].read_text('utf-8-sig')))
    for name in template_names:collector.add(folder+'/'+region.lower()+'_settingstemplate_'+name+'.txt')
    settings=[];room_files={};paths={}
    for entry in catalog.get('regions',[]):
        for row in entry.get('rooms',[]):
            if isinstance(row.get('geometryPath'),str):paths.setdefault(row.get('name'),set()).add(row['geometryPath'])
    for name in names:
        pid=owned.get(name)
        chosen=room_source_choices.selected_source(pid,name) if pid in selected else None
        if chosen is not None:
            prefix='world/'+name.split('_')[0].lower()+'-rooms/'+name
            relative=prefix+'.txt'
            geometry=collector.add(relative,project_packages._sibling(chosen,'.txt'),(pid,name))
            count,exits=project_packages._geometry(geometry.read_bytes(),name)
            if any(len(row['connections'])!=exits for row in rows if row['name']==name):raise ValueError('所选房间版本的出口数量与区域连接不一致：'+name)
            room_files[name]=[relative]
            for index in range(1,count+1):
                relative=prefix+'_'+str(index)+'.png'
                collector.add(relative,project_packages._sibling(chosen,'_'+str(index)+'.png'),(pid,name));room_files[name].append(relative)
            relative=prefix+'_settings.txt'
            collector.add(relative,room_source_choices.selected_settings(pid,name),(pid,name));settings.append(relative);room_files[name].append(relative)
            for filename,path in room_source_choices.selected_settings_files(pid,name).items():
                if filename==name+'_settings.txt':continue
                relative=prefix.rsplit('/',1)[0]+'/'+filename
                collector.add(relative,path,(pid,name));settings.append(relative);room_files[name].append(relative)
            continue
        candidates=paths.get(name,set())
        if len(candidates)!=1:raise ValueError('缺少此房间的唯一生效素材路径：'+name)
        source=Path(next(iter(candidates))).resolve()
        if source.suffix.lower()!='.txt' or source.stem.upper()!=name or not room_bindings.is_enabled_asset(source,collector.roots):raise ValueError('房间素材路径不属于当前启用内容：'+name)
        source=source.with_suffix('')
        relative=collector.relative_source(source.with_suffix('.txt'));geometry=collector.add(relative)
        count,_=project_packages._geometry(geometry.read_bytes(),name)
        prefix=relative[:-4];room_files[name]=[relative]
        for index in range(1,count+1):
            relative=prefix+'_'+str(index)+'.png';collector.add(relative);room_files[name].append(relative)
        relative=prefix+'_settings.txt';collector.add(relative);settings.append(relative);room_files[name].append(relative)
        directory=prefix.rsplit('/',1)[0];base=prefix.rsplit('/',1)[1]
        for filename in collector.names(directory):
            if re.fullmatch(re.escape(base)+r'_(?:settings-[a-z0-9_-]+|properties)\.txt',filename,re.I):
                relative=directory+'/'+filename;collector.add(relative);settings.append(relative);room_files[name].append(relative)
    for relative in settings:
        text=collector.files[relative].read_text('utf-8-sig')
        template=re.search(r'(?m)^Template:\s*([^\r\n]+)',text)
        if template and template.group(1).strip().upper()!='NONE':
            parts=template.group(1).strip().lower().split('_')
            if len(parts)!=3 or parts[1]!='settingstemplate' or parts[2] not in template_names:raise ValueError('区域缺少房间引用的模板注册：'+template.group(1))
    for relative in list(collector.files):
        if relative.endswith('.txt'):collector.settings_dependencies(relative)
    gate_names={row['name'] for row in rows if 'GATE' in row.get('tags','').upper().split(' : ')}
    if gate_names:
        locks=collector.resolve('world/gates/locks.txt');collector.provenance('world/gates/locks.txt')
        lines=[line for line in locks.read_text('utf-8-sig').splitlines() if line.split(':',1)[0].strip() in gate_names]
        matched={line.split(':',1)[0].strip() for line in lines}
        if matched!=gate_names:raise ValueError('区域业力门缺少门槛设置：'+', '.join(sorted(gate_names-matched)))
        collector.generated['modify/world/gates/locks.txt']=''.join('[ADD]'+line+'\n' for line in lines).encode('utf-8')
    collector.generated['modify/world/regions.txt']=('[ADD]'+region+'\n').encode('utf-8')
    return collector,names,room_files


def _digest(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def inspect(region,project_ids=()):
    try:
        collector,rooms,room_files=_collect(region,project_ids)
        return dict(ok=True,region=region,kind='region-files',rooms=rooms,roomFiles=room_files,
                    fileCount=len(collector.files)+len(collector.generated),bytes=sum(file.stat().st_size for file in collector.files.values())+sum(map(len,collector.generated.values())),
                    dependencies=sorted(collector.dependencies.values(),key=lambda item:item['id']),gameDependency=True,blockers=[])
    except (OSError,ValueError,KeyError,TypeError) as error:
        return dict(ok=False,region=region,kind='region-files',rooms=[],roomFiles={},dependencies=[],gameDependency=True,blockers=[str(error)])


def build(region,metadata=None,project_ids=()):
    metadata={} if metadata is None else metadata
    if not isinstance(metadata,dict):raise ValueError('区域说明无效')
    meta={}
    for key,limit in (('name',100),('authors',200),('description',4000)):
        value=metadata.get(key,region if key=='name' else '')
        if not isinstance(value,str) or len(value)>limit:raise ValueError('区域说明无效：'+key)
        if value:meta[key]=value
    collector,rooms,room_files=_collect(region,project_ids)
    files=[dict(path=relative,size=path.stat().st_size,sha256=_digest(path)) for relative,path in sorted(collector.files.items())]
    files += [dict(path=relative,size=len(content),sha256=hashlib.sha256(content).hexdigest()) for relative,content in sorted(collector.generated.items())]
    manifest=dict(schema=SCHEMA,kind='region-files',region=region,metadata=meta,rooms=rooms,roomFiles=room_files,
                  dependencies=sorted(collector.dependencies.values(),key=lambda item:item['id']),gameDependency=True,
                  files=sorted(files,key=lambda item:item['path']))
    
    payload=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8')
    storage.EXPORTS.mkdir(parents=True,exist_ok=True);filename=region.lower()+'-region-'+uuid.uuid4().hex[:12]+'.zip'
    with tempfile.TemporaryDirectory(prefix='mi-region-') as temporary:
        output=Path(temporary)/filename
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
            for relative,path in sorted(collector.files.items()):archive.write(path,relative)
            for relative,content in sorted(collector.generated.items()):archive.writestr(relative,content)
            archive.writestr('region-manifest.json',payload)
        with zipfile.ZipFile(output) as archive:
            expected={item['path'] for item in files}|{'region-manifest.json'}
            if set(archive.namelist())!=expected:raise ValueError('区域文件集合与清单不一致')
            for item in files:
                info=archive.getinfo(item['path'])
                if info.file_size!=item['size']:raise ValueError('导出期间区域文件发生变化：'+item['path'])
                digest=hashlib.sha256()
                with archive.open(item['path']) as stream:
                    for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
                if digest.hexdigest()!=item['sha256']:raise ValueError('导出期间区域文件发生变化：'+item['path'])
        destination=storage.EXPORTS/filename;pending=destination.with_suffix('.zip.tmp')
        try:
            with output.open('rb') as source,pending.open('xb') as target:
                for chunk in iter(lambda:source.read(1024*1024),b''):target.write(chunk)
            pending.replace(destination)
        finally:pending.unlink(missing_ok=True)
    return dict(ok=True,url='/exports/'+filename,manifest=manifest)
