"""Build a read-only content mod from explicitly selected saved projects.

The creator and playback share rendering sources; playback-only menu/paths replace
the editor control surfaces. No game assemblies, local configuration or authoring
sources are shipped. Builds are made in temporary directories and audited first.
"""
from pathlib import Path
import base64,copy,datetime,hashlib,io,json,os,re,shutil,subprocess,tempfile,zipfile,math
from PIL import Image
import storage,dialogue,pearls,pearl_projects,broadcasts,native_projects,playback_adapters,room_editor,room_bindings,projections,overseers,audio_assets
import palette_export_sources

ATOMIC_ACTION={'type':str,'delay':float,'duration':float,'exitNode':int,**dict.fromkeys(('offsetX','offsetY','radius','endAngle'),float)}
ACTION={**ATOMIC_ACTION,'actions':[ATOMIC_ACTION]}
PRESENTATION={'movement':str,'eyes':str}
LINE={'lineId':str,'kind':str,'text':str,'hold':float,'gap':float,'beforeAction':ACTION,'action':ACTION,'presentation':PRESENTATION}
POOL={'name':str,'lines':[LINE],'action':ACTION}
AFFINITY={'enabled':bool,'initial':float,'attackMode':str,'rockPenalty':float,'spearPenalty':float,'refuseBelow':float,'pearlGiftEnabled':bool,'pearlGiftAmount':float,
    'refusal':[POOL],**{key:{tier:[POOL] for tier in dialogue.AFFINITY_TIERS} for key in ('attackRock','attackSpear')}}
OBSERVATION={'enabled':bool,'cooldown':float,**{key:[POOL] for key in dialogue.OBSERVATION_POOLS}}
PEARL_RULES={**dict.fromkeys(('greetingEnabled','preventSameCycleRepeat','manyEnabled','extractStomachPearl'),bool),
    'greetingDelay':float,'manyThreshold':int,'leavePolicy':str,'quickReturnWindow':float,'returnCooldown':float,'presentation':PRESENTATION,
    **{k:[POOL] for k in dialogue.PEARL_POOLS}}
MEETING_CONDITION={'minEntries':int,'minCycle':int,'held':str}
DIALOGUE={'schema':str,'enabled':bool,'requireMark':bool,'first':[LINE],'repeat':[LINE],
    'storyMode':str,'firstCondition':MEETING_CONDITION,'repeatCondition':MEETING_CONDITION,'meetings':[{'id':str,'condition':MEETING_CONDITION,**POOL}],'loop':[LINE],'loopAction':ACTION,
    'pickupEnabled':bool,'leaveEnabled':bool,'cooldown':float,'pearlReading':PEARL_RULES,
    'affinity':AFFINITY,'observation':OBSERVATION,'firstAction':ACTION,'repeatAction':ACTION,
    **{k:[POOL] for k in ('pickup','leaving','returning')}}
PEARL_BODY={'read':[LINE],'readAction':ACTION,'repeatEnabled':bool,'repeatPrependCommon':bool,'repeat':[POOL],'presentation':PRESENTATION}
AUDIO_TRACK={'mode':str,'asset':str,'volume':float,'loop':bool}
PEARL={'schema':str,'id':str,'uid':str,'name':str,'collectionId':str,'revision':int,'runtimeId':str,'ownerMod':str,
    'appearance':{'musicTrack':AUDIO_TRACK,**dict.fromkeys(('baseColor','highlightColor','secondaryColor','effectColor','effect'),str),
        **dict.fromkeys(('twoTone','music'),bool),**dict.fromkeys(('size','effectOpacity','effectSize','pulseSpeed','musicVolume'),float)},
    'readers':[{'projectId':str,'nativeOracleId':str,'oracleId':str,'name':str,'requireMark':bool,'repeatEnabled':bool,
        'leavePolicy':str,**PEARL_BODY,'affinity':{tier:PEARL_BODY for tier in dialogue.AFFINITY_TIERS},**{k:[POOL] for k in ('leaving','returning')}}],
    'spawns':[{'projectId':str,'entry':str,'position':{'x':float,'y':float}}]}
BROADCAST={'schema':str,'id':str,'uid':str,'name':str,'revision':int,'runtimeId':str,
    'region':str,'room':str,'x':float,'y':float,
    'pages':[{'lines':[{'text':str,'color':str,'font':str,'size':float,'speed':float,'hold':float}]}]}

OVERSEER_PROFILE={'enabled':bool,'ownerAbbreviation':str,'ownerProjectId':str,'rooms':[str],
    'bodyColors':[str],'tipColors':[str],'eyeWhite':str,'eyePupil':str,
    'probabilities':dict.fromkeys(('lens','GateScene','Angry'),float)}
OVERSEER={**OVERSEER_PROFILE,'guests':[{**OVERSEER_PROFILE,'id':str,'name':str}]}

PROJECTION_MASK={'enabled':bool,**dict.fromkeys(('x','y','width','height'),float)}
PROJECTION={'projectMask':PROJECTION_MASK,'schema':str,'uid':str,'name':str,'projectId':str,'revision':int,'enabled':bool,'loop':bool,'confineToRoom':bool,'oracleId':str,'ownerMod':str,
    'trigger':{'kind':str,'source':str,'pearlUid':str,'startLineId':str,'endLineId':str,'lineIds':[str],'beforeSeconds':float,'afterSeconds':float},
    'images':[{'id':str,'name':str,'png':str,'width':int,'height':int}],
    'tracks':[{'maskMode':str,'mask':PROJECTION_MASK,'id':str,'name':str,'kind':str,'imageId':str,'color':str,'style':str,'glyphIndex':int,'delay':float,
        'frames':[{**dict.fromkeys(('duration','x','y','scale','rotation','opacity','brightness','flicker'),float),'ease':str}]}]}

def runtime_design_schema():
    """Mirror public serialized C# fields, including nested runtime structures.

    Read from the same source tree used for compilation so adding a runtime field
    cannot require a second, easily stale list of appearance field names.
    """
    types={'string':str,'int':int,'float':float,'bool':bool}
    files={'PuppetArmDesign':'PuppetArmDesign.cs','IteratorDesign':'IteratorDesign.cs','IteratorLayers':'IteratorDesign.cs','EyeDesign':'EyeDesign.cs',
           'GarmentDesign':'GarmentPhysics.cs','NecklaceDesign':'NecklaceDesign.cs','NecklacePearl':'NecklaceDesign.cs','AudioTrackDesign':'AudioTrackDesign.cs','CreatorVoiceDesign':'CreatorVoice.cs',
           **dict.fromkeys(('ColorGradient','GradientStop','RoomGradient','CornerGlow'),'CreatorColorGradient.cs'),
           **dict.fromkeys(('PearlAccessoryDesign','PearlAccessoryBead','PearlAccessoryChild'),'PearlAccessoryDesign.cs')}
    result={name:{} for name in files}
    for name,filename in files.items():
        source=(storage.WORKSPACE/'src'/filename).read_text('utf-8-sig')
        source=re.sub(r'@"(?:[^"]|"")*"|"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/','""',source)
        match=re.search(r'\bclass\s+'+name+r'\s*\{',source)
        if not match:raise ValueError('Runtime schema class missing: '+name)
        start=match.end();depth=1;end=start
        while depth and end<len(source):
            depth+=(source[end]=='{')-(source[end]=='}');end+=1
        body=source[start:end-1]
        for declaration in re.finditer(r'\bpublic\s+(\w+(?:\[\])?)\s+([^;]+);',body):
            kind,fields=declaration.groups()
            if kind not in types and kind.removesuffix('[]') not in result and kind!='string[]':continue
            # A public method is not serialized; constructors/initializers after
            # '=' can contain parentheses, braces, and comma-separated values.
            if '(' in fields.split('=',1)[0]:continue
            chunks=[];offset=0;nest=0
            for index,char in enumerate(fields):
                if char in '({[':nest+=1
                elif char in ')}]':nest-=1
                elif char==',' and nest==0:chunks.append(fields[offset:index]);offset=index+1
            chunks.append(fields[offset:])
            for field in chunks:
                key=field.split('=',1)[0].strip()
                if not re.fullmatch(r'\w+',key):raise ValueError('Unsupported runtime field declaration: '+name)
                element=kind.removesuffix('[]');shape=types.get(element,result.get(element))
                result[name][key]=[shape] if kind.endswith('[]') else shape
    for key in ('previewToken','firstDialogue','repeatDialogue','unmarkedDialogue','pearlDialogue'):
        result['IteratorDesign'].pop(key,None)
    return result['IteratorDesign']

def runtime_fields(value,shape,path,strict=False):
    """Project only known runtime fields; independent audits reject extras."""
    if isinstance(shape,dict):
        if not isinstance(value,dict):raise ValueError('运行字段必须是对象：'+path)
        extra=set(value)-set(shape)
        if strict and extra:raise ValueError('未知运行字段：'+path+'.'+sorted(extra)[0])
        return {key:runtime_fields(item,shape[key],path+'.'+key,strict) for key,item in value.items() if key in shape}
    if isinstance(shape,list):
        if not isinstance(value,list):raise ValueError('运行字段必须是列表：'+path)
        return [runtime_fields(item,shape[0],path+'[]',strict) for item in value]
    valid=type(value) in (int,float) and math.isfinite(value) if shape is float else type(value) is shape
    if not valid:raise ValueError('运行字段类型无效：'+path)
    return copy.deepcopy(value)

def metadata(value):
    value=copy.deepcopy(value)
    for key,limit in [('id',64),('name',100),('authors',200),('description',4000),('version',32)]:
        if not isinstance(value.get(key),str) or len(value[key])>limit:raise ValueError('导出信息无效：'+key)
        value[key]=value[key].strip()
    if not re.fullmatch(r'[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+',value['id']):raise ValueError('模组 ID 使用小写字母、数字和点，例如 author.myiterator')
    if value['id'].startswith(('moreiterators','eoe.')):raise ValueError('独立作品需要自己的模组 ID')
    if not value['name'] or not value['authors']:raise ValueError('请填写模组名称和作者')
    if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)',value['version']):raise ValueError('版本格式为 0.1.0')
    return {k:value[k] for k in ('id','name','authors','description','version')} | {'cover':value.get('cover','')}

def cover_bytes(value):
    if not value:return None
    try:
        if not value.startswith(('data:image/png;base64,','data:image/jpeg;base64,')):raise ValueError()
        raw=base64.b64decode(value.split(',',1)[1],validate=True)
        if len(raw)>8_000_000:raise ValueError()
        im=Image.open(io.BytesIO(raw));im.load()
        if im.width>4096 or im.height>4096:raise ValueError()
        im=im.convert('RGB');im.thumbnail((1024,1024));out=io.BytesIO();im.save(out,'PNG');return out.getvalue()
    except Exception as e:raise ValueError('封面需要 PNG / JPEG，最大 4096 像素和 8 MB') from e

def preferences(pid=''):
    if pid:
        pid=storage.valid_id(pid);f=storage.project_file(pid).parent/'export-settings.json'
        if f.exists():
            value=json.loads(f.read_text('utf-8'));value.setdefault('externalMods',[])
            value.setdefault('packageName',storage.load_project(pid)['name']);value.setdefault('packageVersion','0.1.0')
            return value
        p=storage.load_project(pid)
        return dict(id='author.'+pid.replace('oc-','iterator-'),name=p['name'],authors='',description='',version='0.1.0',packageName=p['name'],packageVersion='0.1.0',cover='',projects=[pid],externalMods=[],dialogue=False,pearls=False,broadcasts=False,workPearls=False)
    f=storage.DATA/'export-settings.json'
    value=json.loads(f.read_text('utf-8')) if f.exists() else dict(id='author.iterator',name='',authors='',description='',version='0.1.0',cover='',dialogue=False,pearls=False,broadcasts=False,workPearls=False)
    value['projects']=[pid] if pid else []
    value.setdefault('externalMods',[])
    return value

SOURCE_MANIFEST='templates/standalone/sources.json'

def _runtime_source_plan(workspace=None):
    root=Path(workspace if workspace is not None else storage.WORKSPACE).resolve()
    manifest_path=root/SOURCE_MANIFEST
    if not manifest_path.is_file():raise ValueError('Missing standalone source manifest: '+SOURCE_MANIFEST)
    manifest=json.loads(manifest_path.read_text('utf-8-sig'))
    if manifest.get('schema')!='moreiterators.standalone-sources.v1':raise ValueError('Unsupported standalone source manifest')
    sources=manifest.get('sources');fragments=manifest.get('fragments');excluded=manifest.get('excluded')
    if not isinstance(sources,list) or not sources or not isinstance(fragments,dict) or set(fragments)!={'encounter'} or not isinstance(excluded,dict):
        raise ValueError('Invalid standalone source manifest')
    def checked(relative):
        if not isinstance(relative,str) or not re.fullmatch(r'(?:src|templates/standalone)/[A-Za-z][A-Za-z0-9_]*\.cs',relative):
            raise ValueError('Invalid standalone source path: '+str(relative))
        path=root/relative
        if not path.resolve().is_relative_to(root):raise ValueError('Standalone source path escapes workspace: '+relative)
        return path
    names=[checked(relative).name.casefold() for relative in sources]
    if len(set(names))!=len(names):raise ValueError('Duplicate standalone compiler source name')
    inputs={SOURCE_MANIFEST:manifest_path}
    for relative in [*sources,*fragments.values()]:
        path=checked(relative)
        if not path.is_file():raise ValueError('Missing standalone export source: '+relative)
        inputs[relative]=path
    for relative,reason in excluded.items():
        checked(relative)
        if relative in inputs or not relative.startswith('src/') or not isinstance(reason,str) or not reason.strip():
            raise ValueError('Invalid standalone source exclusion: '+relative)
    classified=set(inputs)|set(excluded)
    for directory in ('src','templates/standalone'):
        for path in (root/directory).glob('*.cs'):
            relative=path.relative_to(root).as_posix()
            if relative not in classified:raise ValueError('Unclassified standalone source: '+relative)
    return manifest,inputs

def runtime_source_inputs(workspace=None):
    """Files required by export; shared by the Workshop packager and compiler."""
    return _runtime_source_plan(workspace)[1]

def compiler_sources(destination,meta,projects=()):
    manifest,inputs=_runtime_source_plan()
    suffix=hashlib.sha256(meta['id'].encode()).hexdigest()[:12]
    namespace='IteratorContent_'+suffix
    encounter=inputs[manifest['fragments']['encounter']].read_text('utf-8').split('public class CreatorEncounter:',1)[1]
    encounter='public class CreatorEncounter:'+encounter.rsplit('}',1)[0]
    sources=[]
    for relative in manifest['sources']:
        file=inputs[relative]
        text=file.read_text('utf-8')
        text=text.replace('__ENCOUNTER__',encounter).replace('__MOD_ID__',meta['id'])
        text=text.replace('namespace MoreIterators','namespace '+namespace)
        # Atlas and extensible-enum identifiers must also be unique per content mod.
        text=text.replace('"MoreIterators_','"IC_'+suffix+'_').replace('"moreiterators_','"ic_'+suffix+'_')
        if file.name=='MoreIteratorsPlugin.cs':
            text,count=re.subn(r'\[BepInPlugin\("moreiterators\.core",\s*"[^"\\]*",\s*BuildVersion\.Plugin\)\]',lambda match:'[BepInPlugin('+json.dumps(meta['id'])+', '+json.dumps(meta['name'],ensure_ascii=False)+', '+json.dumps(meta['version'])+')]',text)
            if count!=1:raise ValueError('Playback plugin identity replacement failed')
            if any(p.get('legacyOracle') for p in projects):text=text.replace('Instance=this; RuntimePaths.Initialize();','Instance=this; RuntimePaths.Initialize(); IteratorIntegrations.Register(new PlaybackAppearanceIntegration());')
        if file.name=='MoreIteratorsPlugin.cs':
            text=text.replace('orig(cam,extension==null?pal:extension.BasePalette(cam,pal),ref texture);','orig(cam,extension==null?(target!=null&&IteratorCatalog.IsAI(target.abstractRoom.name)&&!CreatorRoomSettings.RoomPalette(IteratorDesign.ForRoom(target))&&IteratorDesign.ForRoom(target).roomTemplate=="ir"?13:pal):extension.BasePalette(cam,pal),ref texture);')
        if file.name=='CreatorLaunch.cs':
            text=text.replace('请在编辑器重新应用项目。','请重新安装此内容模组。').replace('请重新应用项目后进入。','请重新安装此内容模组。').replace('请重新应用项目。','请重新安装此内容模组。').replace('请重新应用项目后重启游戏。','请重新安装此内容模组并重启游戏。')
        target=destination/file.name;target.write_text(text,'utf-8');sources.append(target)
    sources+=playback_adapters.export_sources(destination,projects,namespace)
    return sources,suffix

GAME_UI_FILES=tuple('text/text_'+language+'/strings.txt' for language in ('eng','chi','tra'))

def game_ui_sources():
    root=storage.WORKSPACE/'mod' if (storage.WORKSPACE/'mod/text').is_dir() else storage.WORKSPACE
    files={relative:root/relative for relative in GAME_UI_FILES}
    for relative,path in files.items():
        if not path.is_file():raise ValueError('Missing native game UI translations: '+relative)
    return files

def copy_game_ui(stage):
    for relative,path in game_ui_sources().items():
        target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)

def compile_runtime(stage,source_dir,meta,projects=()):
    sources,suffix=compiler_sources(source_dir,meta,projects)
    managed=storage.GAME/'RainWorld_Data/Managed'
    refs=[managed/name for name in ('Assembly-CSharp.dll','Assembly-CSharp-firstpass.dll','UnityEngine.dll','Unity.Mathematics.dll','UnityEngine.CoreModule.dll','UnityEngine.InputLegacyModule.dll','UnityEngine.JSONSerializeModule.dll','UnityEngine.ImageConversionModule.dll','UnityEngine.AudioModule.dll','UnityEngine.UnityWebRequestModule.dll','UnityEngine.UnityWebRequestAudioModule.dll','UnityEngine.IMGUIModule.dll','UnityEngine.TextRenderingModule.dll')]
    refs += [storage.GAME/name for name in ('BepInEx/core/BepInEx.dll','BepInEx/plugins/HOOKS-Assembly-CSharp.dll','BepInEx/core/MonoMod.Utils.dll','BepInEx/core/MonoMod.RuntimeDetour.dll','BepInEx/core/Mono.Cecil.dll')]
    for ref in refs:
        if not ref.exists():raise ValueError('缺少编译依赖：'+ref.name)
    csc=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    out=stage/'plugins'/('IteratorContent_'+suffix+'.dll');out.parent.mkdir(parents=True,exist_ok=True)
    if not csc.is_file():raise ValueError('独立 DLL 导出需要 Windows .NET Framework 编译器；当前平台可以编辑项目和导出素材。')
    result=subprocess.run([str(csc),'/nologo','/target:library','/optimize+','/define:PLAYBACK','/out:'+str(out),*['/r:'+str(r) for r in refs],*[str(s) for s in sources]],capture_output=True,timeout=120)
    if result.returncode:raise ValueError('独立运行版编译失败：'+result.stdout.decode('utf-8',errors='replace')[-6000:])
    return suffix

def room_source(p,name,kind,server):
    if kind not in ('ai','entry'):raise ValueError('房间类型无效')
    current=p.get('roomBinding')
    if current and name!=current[kind]:raise ValueError('只能导出此项目当前绑定的房间：'+current[kind])
    if kind=='entry' and p.get('roomBinding',{}).get('entryMode')=='existing':
        import room_source_choices
        return room_source_choices.selected_source(p['projectId'],name) or room_bindings.resolve_room_source(name)
    if native_projects.binding(p['projectId']):return server.ASSETS/('mods/moreslugcats/world/'+name.split('_')[0].lower()+'-rooms')/name.lower()
    import room_source_choices
    selected=room_source_choices.selected_source(p['projectId'],name)
    if selected is not None:return selected
    room_editor.ensure_synced(p['projectId'],name)
    cached=room_editor.cached_source(p['projectId'],name)
    root=storage.target_mod(p['projectId'])/'world'
    source=root/(name.split('_')[0].lower()+'-rooms')/name
    installed=storage.installed_mod(p['projectId'],required=False)
    installed_source=installed/'world'/(name.split('_')[0].lower()+'-rooms')/name if installed else None
    if cached or source.with_suffix('.txt').is_file() or installed_source and installed_source.with_suffix('.txt').is_file():
        import project_packages
        return project_packages.selected_room_source(p,name,rows={})
    if current or storage.binding(p['projectId']):raise ValueError(p['name']+' 当前绑定的房间素材缺失：'+name+'；请同步当前房间后重新导出，不会回退到旧房间或默认模板。')
    return server.ASSETS/'world/ss-rooms/ss_ai' if kind=='ai' else server.entry_room_template()

def room_connections(p,ai,entry,server):
    if not storage.binding(p['projectId']):
        import project_packages
        import room_connection_checks
        result={}
        for name,kind in ((ai,'ai'),(entry,'entry')):
            source=room_source(p,name,kind,server)
            check=project_packages.connection_snapshot(p,name,rows={},source=source)
            room_connection_checks.require(check)
            result[name]=check['connections']
        return result
    if p.get('roomConnections'):
        import project_packages
        rows=project_packages.saved_connection_rows(p);result={}
        for name,kind in ((ai,'ai'),(entry,'entry')):
            if name not in rows:raise room_bindings.RoomBindingError('workflowMissingConnections',room=name)
            links=list(rows[name]['connections'])
            if len(links)!=room_bindings.geometry(room_source(p,name,kind,server).with_suffix('.txt'))['exitCount']:
                raise room_bindings.RoomBindingError('workflowGeometry',room=name)
            result[name]=links
        return result
    if p.get('roomBinding'):
        binding=p['roomBinding'];ai_links=['DISCONNECTED']*room_bindings.geometry(room_source(p,ai,'ai',server).with_suffix('.txt'))['exitCount']
        entry_links=['DISCONNECTED']*room_bindings.geometry(room_source(p,entry,'entry',server).with_suffix('.txt'))['exitCount']
        if binding['aiNode']>=len(ai_links) or binding['entryNode']>=len(entry_links):raise ValueError('绑定出口与最新地形不一致，请重新设置房间连接。')
        ai_links[binding['aiNode']]=entry;entry_links[binding['entryNode']]=ai
        return {ai:ai_links,entry:entry_links}
    region=ai.split('_')[0].lower()
    world=storage.target_mod(p['projectId'])/('world/'+region+'/world_'+region+'.txt')
    if native_projects.binding(p['projectId']):world=server.ASSETS/('mods/moreslugcats/world/'+region+'/world_'+region+'.txt')
    result={}
    if world.exists():
        for raw in world.read_text('utf-8-sig').splitlines():
            fields=raw.split(' : ')
            if len(fields)>1 and fields[0] in (ai,entry):result[fields[0]]=[x.strip() for x in fields[1].split(',')]
    if not result and not storage.binding(p['projectId']):
        node=room_bindings.binding(p)['entryNode']
        return {ai:['DISCONNECTED',entry],entry:([ai] if node==0 else ['DISCONNECTED',ai])}
    if entry not in result.get(ai,[]) or ai not in result.get(entry,[]):raise ValueError(p['name']+' 的演算室和等待房间未直接相连')
    return result

def room_palette_ids(text):
    """Only explicit room palette dependencies; never enumerate a mod's assets."""
    return {int(value) for value in re.findall(r'(?m)^(?:Palette|FadePalette|MorePalette[0-9]+):[ \t]*(\d+)\b',text)}

def uses_more_palettes(text):
    return bool(re.search(r'(?m)^MorePalette[0-9]+:',text))

def room_palette_requirements(stage,rooms,templates=(),room_files=None):
    files=[stage/relative for room in rooms for relative in (room_files[room] if room_files else _room_files(stage,room))
           if re.fullmatch(re.escape(room)+r'(?:_settings(?:-[A-Za-z0-9_-]+)?|_properties)\.txt',Path(relative).name)]
    files.extend(stage/relative for relative in templates)
    return {'regionkit':'RegionKit'} if any(uses_more_palettes(file.read_text('utf-8-sig')) for file in files) else {}

def _palette_file(root,index):
    root=Path(root).resolve();candidate=root/'palettes'/('palette'+str(index)+'.png')
    resolved=candidate.resolve()
    if not resolved.is_relative_to(root):raise ValueError('调色板素材路径越界：palette'+str(index))
    return resolved if resolved.is_file() else None

def _owner_asset_roots(root):
    
    root=Path(root).resolve()
    assets=(storage.GAME/'RainWorld_Data/StreamingAssets').resolve()
    if root==assets:return [root]
    try:version=(assets/'GameVersion.txt').read_text('utf-8-sig').strip()
    except OSError:version=''
    candidates=([root/version] if re.fullmatch(r'v\d+(?:\.\d+)+',version) else [])+[root/'newest',root]
    return [candidate.resolve() for candidate in candidates if candidate.is_dir() and candidate.resolve().is_relative_to(root)]

def room_palette_source(project,source,index,include_saved=True):
    """Resolve the selected room's owning asset root before base-game palettes.

    External geometry is already restricted to game/workshop roots by room_source.
    Authored renders/templates use this project's target mod. Never guess a
    palette from an unrelated installed mod or copy its directory wholesale.
    """
    import room_source_choices
    selected=room_source_choices.selected_asset(project['projectId'],'palettes/palette'+str(index)+'.png')
    if selected is not None:return selected
    source=Path(source).resolve()
    project_root=storage.project_file(project['projectId']).parent.resolve()
    bundled=None
    if source.is_relative_to(project_root/'rooms'):
        import project_packages
        bundled=project_packages.palette_source(project['projectId'],index)
    base=(storage.GAME/'RainWorld_Data/StreamingAssets').resolve()
    target=storage.target_mod(project['projectId']).resolve()
    roots={Path(root).resolve() for root in room_bindings._asset_roots()};roots.add(target)
    matches=[root for root in roots if source.is_relative_to(root)]
    owner=max(matches,key=lambda root:len(root.parts)) if matches else target
    if (owner.name=='newest' or re.fullmatch(r'v\d+(?:\.\d+)+',owner.name)) and owner.parent in roots:
        owner=owner.parent
    asset=bundled or next((value for root in _owner_asset_roots(owner) if (value:=_palette_file(root,index)) is not None),None)
    if asset is None:asset=_palette_file(base,index)
    if include_saved:asset=palette_export_sources.choose(index,room_bindings.enabled_asset_roots(),asset)
    if asset is None:
        raise ValueError('所选房间引用的调色板来源无法确定：palette'+str(index)+'；请把依赖放在该房间所属模组的 palettes 目录后再导出。')
    return asset

def copy_room_palettes(project,source,settings,stage):
    for index in sorted(room_palette_ids(settings.read_text('utf-8-sig'))):
        asset=room_palette_source(project,source,index);content=asset.read_bytes()
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.format!='PNG':raise ValueError('not PNG')
                image.verify()
        except (OSError,ValueError) as error:raise ValueError('房间调色板不是有效 PNG：palette'+str(index)) from error
        destination=stage/'palettes'/('palette'+str(index)+'.png')
        if destination.exists() and destination.read_bytes()!=content:
            raise ValueError('所选房间使用同号但内容不同的调色板：palette'+str(index)+'；请先为它们分配不同编号。')
        destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(content)
    for relative,asset in room_settings_assets(project,source,settings.read_text('utf-8-sig')).items():
        content=asset.read_bytes();destination=stage/relative
        if destination.exists() and destination.read_bytes()!=content:raise ValueError('所选房间使用同名但内容不同的素材：'+relative)
        destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(content)


def room_settings_assets(project,source,text):
    
    import project_packages,room_asset_dependencies
    source=Path(source).resolve();pid=project['projectId'];project_root=storage.project_file(pid).parent.resolve()
    target=storage.target_mod(pid).resolve();roots=[Path(root).resolve() for root in room_bindings.enabled_asset_roots()]
    installed=storage.installed_mod(pid,required=False)
    own=[target]+([installed.resolve()] if installed is not None else [])
    owners=[root for root in [*own,*roots] if source.is_relative_to(root)]
    owner=max(owners,key=lambda root:len(root.parts)) if owners else target
    selected_roots=_owner_asset_roots(owner)+[root for root in roots if root!=owner]
    result={}
    groups=[(item,True) for item in room_asset_dependencies.references(text,str(source))]
    groups.extend((item,False) for item in room_asset_dependencies.optional_references(text,str(source)))
    for candidates,required in groups:
        selected=None
        import room_source_choices
        for relative in candidates:
            chosen=room_source_choices.selected_asset(pid,relative)
            if chosen is not None:selected=(relative,chosen);break
        authored=source.is_relative_to(project_root/'rooms') or any(source.is_relative_to(root) for root in own)
        def authored_copy(relative):
            copies=[file for root in own if (file:=room_asset_dependencies.existing(root,relative)) is not None]
            bundled=project_packages.asset_source(pid,relative)
            if bundled is not None:copies.append(bundled)
            return (relative,max(copies,key=lambda path:path.stat().st_mtime_ns)) if copies else None
        
        if selected is None and authored and not candidates[0].startswith('terrainpalettes/'):
            for relative in candidates:
                selected=authored_copy(relative)
                if selected is not None:break
        if selected is None and candidates[0].startswith('terrainpalettes/'):
            
            
            for relative in candidates:
                if authored:selected=authored_copy(relative)
                if selected is not None:break
                for root in roots:
                    file=room_asset_dependencies.existing(root,relative)
                    if file is not None:selected=(relative,file);break
                if selected is not None:break
        elif selected is None:
            for root in selected_roots:
                for relative in candidates:
                    file=room_asset_dependencies.existing(root,relative)
                    if file is not None:selected=(relative,file);break
                if selected is not None:break
        if selected is None:
            if required:raise ValueError('所选房间引用的素材缺失：'+candidates[0])
            continue
        relative,file=selected
        if room_asset_dependencies.native_ambient_reference(relative,file):continue
        room_asset_dependencies.validate(relative,file.read_bytes());result[relative]=file
    return result

def dump(file,value):
    file.parent.mkdir(parents=True,exist_ok=True);file.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf-8')

def without_dialogue(profile):
    """An appearance-only export carries no authored responses or actions."""
    profile=copy.deepcopy(profile)
    profile.update(enabled=False,first=[],repeat=[],meetings=[],loop=[],loopAction=dict(type='none',delay=0),pickup=[],leaving=[],returning=[],pickupEnabled=False,leaveEnabled=False,
        firstAction=dict(type='none',delay=0),repeatAction=dict(type='none',delay=0),
        affinity={**dialogue.affinity_defaults(),'enabled':False},observation={**dialogue.observation_defaults(),'enabled':False})
    profile['pearlReading'].update(greetingEnabled=False,manyEnabled=False,**{key:[] for key in dialogue.PEARL_POOLS})
    return profile

def unselected_owned_rooms(selected):
    """Read only room identities; unrelated project content never enters the package."""
    result=set()
    for file in storage.project_files():
        try:
            project=json.loads(file.read_text('utf-8'));pid=project['projectId']
            if pid in selected or native_projects.binding(pid):continue
            binding=room_bindings.binding(project);result.add(binding['ai'])
            if storage.link(pid) or binding.get('entryMode')!='existing':result.add(binding['entry'])
        except (OSError,ValueError,KeyError,TypeError):continue
    return result

def official_requirement(mod):
    if mod not in ('moreslugcats','watcher'):raise ValueError('官方扩展依赖无效：'+mod)
    assets=(storage.GAME/'RainWorld_Data/StreamingAssets').resolve();root=assets/'mods'/mod
    info=(root/'modinfo.json').resolve()
    try:
        if not info.is_relative_to(root):raise ValueError()
        value=json.loads(info.read_text('utf-8-sig'))
        if value.get('id')!=mod or not isinstance(value.get('name'),str) or not value['name'].strip():raise ValueError()
    except (OSError,ValueError,TypeError,AttributeError) as error:
        raise ValueError('无法确认官方扩展信息：'+mod) from error
    return value['id'],value['name']

def official_room_requirement(room):
    """Trust the captured resolved source, never a room-name prefix."""
    source=room_bindings.resolve_room_source(room).with_suffix('.txt').resolve()
    assets=(storage.GAME/'RainWorld_Data/StreamingAssets').resolve()
    if source.is_relative_to(assets/'world'):return None
    for mod in ('moreslugcats','watcher'):
        if any(source.is_relative_to(root/'world') for root in _owner_asset_roots(assets/'mods'/mod)):
            return official_requirement(mod)[0]
    provider=source.parent.name
    roots=sorted((root.resolve() for root in room_bindings._asset_roots()),key=lambda root:len(root.parts),reverse=True)
    for root in roots:
        if not source.is_relative_to(root):continue
        info=root/'modinfo.json'
        if info.is_file():
            try:
                metadata=json.loads(info.read_text('utf-8-sig'));provider=str(metadata.get('id') or root.name)
            except (OSError,ValueError,TypeError):provider=root.name
        else:provider=root.name
        break
    raise ValueError('监视器房间 '+room+' 来自第三方内容 '+provider+'；请移除此地点后导出，当前不能自动声明该模组依赖。')

def export_overseers(raw,room_map,selected,excluded):
    config=runtime_fields(overseers.decode(raw),OVERSEER,'overseer',strict=True)
    requirements=set()
    for profile in [config,*config['guests']]:
        owner=profile.get('ownerProjectId')
        if owner and owner not in selected:profile['ownerProjectId']=''
        if 'rooms' not in profile:continue
        locations=[]
        for room in profile['rooms']:
            if room in room_map:target=room_map[room]
            elif room in excluded:continue
            else:
                requirement=official_room_requirement(room)
                if requirement:requirements.add(requirement)
                target=room
            if target not in locations:locations.append(target)
        profile['rooms']=locations
    return config,requirements

def pearl_room_requirement(room):
    """Resolve an explicit spawn room through the captured game's actual asset path."""
    try:
        source=room_bindings.resolve_room_source(room).with_suffix('.txt').resolve()
        assets=(storage.GAME/'RainWorld_Data/StreamingAssets').resolve()
        if source.is_relative_to(assets/'world'):return None
        active=set(room_bindings.catalog().get('activeMods',[]))
        roots=sorted((root.resolve() for root in room_bindings._asset_roots()),key=lambda root:len(root.parts),reverse=True)
        for root in roots:
            if not source.is_relative_to(root/'world'):continue
            info=root/'modinfo.json'
            if not info.is_file():continue
            value=json.loads(info.read_text('utf-8-sig'));mod=value.get('id');name=value.get('name')
            if not isinstance(mod,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',mod) or not isinstance(name,str) or not name.strip():raise ValueError('所属模组的 modinfo 信息无效')
            if mod not in active:raise ValueError('所属模组 '+mod+' 未在游戏房间目录中启用')
            if mod.startswith('moreiterators'):raise ValueError('此地点属于 MI 本地测试数据；请选择一并导出该迭代器，或移除此生成点')
            return mod,name.strip()
        raise ValueError('无法确认房间所属模组')
    except (OSError,ValueError,TypeError,KeyError) as error:
        raise ValueError('珍珠生成房间 '+str(room)+' 的导出依赖无法确认：'+str(error)+'。请刷新游戏房间目录，或从珍珠中移除此生成点后再导出。') from error

def export_pearl_spawns(spawns,room_map,mapping):
    owners={record[key]:record['projectId'] for record in mapping.values() for key in ('ai','entry')}
    result=[];requirements={};seen=set()
    for original in spawns:
        spawn=copy.deepcopy(original);room=spawn['entry'];target=room_map.get(room,room)
        if target in seen:continue
        seen.add(target);spawn['entry']=target
        if target in owners:spawn['projectId']=owners[target]
        elif target in room_map.values():spawn.pop('projectId',None)
        else:
            spawn.pop('projectId',None)
            requirement=pearl_room_requirement(room)
            if requirement:requirements[requirement[0]]=requirement[1]
        result.append(spawn)
    return result,requirements

def selected_pearl_content(request,selected_projects,included_rooms=()):
    if 'pearlCollectionIds' in request or isinstance(request.get('pearlCollectionId'),(list,dict)):
        raise ValueError('一次只能选择一套珍珠项目，或不导出珍珠。')
    if request.get('pearlCollectionId') is not None and not isinstance(request['pearlCollectionId'],str):raise ValueError('请选择有效的珍珠项目')
    if not request.get('pearls',False):return '',[]
    catalog=pearl_projects.catalog();collection=request.get('pearlCollectionId') or catalog['activeId']
    if not isinstance(collection,str):raise ValueError('请选择有效的珍珠项目')
    if collection not in {item['id'] for item in catalog['projects']}:raise ValueError('请选择有效的珍珠项目')
    selected=set(selected_projects)
    candidates=pearls.listing(collection);selected_rooms=set(request.get('extraRooms',[]))|set(included_rooms)
    if any(p.get('spawnRooms') for p in candidates):
        for pid in selected:
            binding=room_bindings.binding(storage.load_project(pid));selected_rooms.update((binding['ai'],binding['entry']))
    items=[p for p in candidates if any(pearls.native_reader(r) or r['projectId'] in selected for r in p['readers']) or selected.intersection(p['spawnProjects']) or selected_rooms.intersection(p.get('spawnRooms',[]))]
    return collection,items

def export_room_names(projects,mod_id):
    """Keep authored region/room identifiers; isolate only shared source worlds."""
    digest=hashlib.sha256(mod_id.encode()).hexdigest()
    isolated='M'+''.join(chr(65+int(c,16)) for c in digest[:5])
    owned={}
    for project in projects:
        current=project.get('roomBinding')
        if current and not storage.binding(project['projectId']):
            current=room_bindings.normalize(current)
            if current['entryMode']=='copy' and current['region']!='TEST':owned[project['projectId']]=current
    # Never silently rename an author's rooms to make two selected projects fit.
    reserved={value['region'] for value in owned.values()}
    attempt=0
    while isolated in reserved:
        attempt+=1;digest=hashlib.sha256((mod_id+'|'+str(attempt)).encode()).hexdigest()
        isolated='M'+''.join(chr(65+int(c,16)) for c in digest[:5])
    result={};used={}
    for index,project in enumerate(projects,1):
        pid=project['projectId'];current=owned.get(pid)
        names=(current['ai'],current['entry']) if current else (isolated+'_'+str(index).zfill(3)+'_AI',isolated+'_'+str(index).zfill(3)+'_ENTRY')
        for name in names:
            if name in used:raise ValueError('所选项目的房间编号重复：'+name+'（'+used[name]+' / '+project['name']+'）；请先修改房间设置，不会覆盖或自动改名。')
            used[name]=project['name']
        result[pid]=names
    return result

def _extra_room_row(row,name):
    if not isinstance(row,dict) or row.get('name')!=name or row.get('conditional'):
        raise ValueError('额外房间包含未支持的条件连接：'+name)
    links=row.get('connections',[]);tags=row.get('tags','')
    if not isinstance(links,list) or any(not isinstance(x,str) or x!='DISCONNECTED' and not room_bindings.ROOM_RE.fullmatch(x) for x in links):
        raise ValueError('额外房间连接无效：'+name)
    if not isinstance(tags,str) or '\n' in tags or '\r' in tags or any(x in tags for x in ('[',']','//')):
        raise ValueError('额外房间标签无效：'+name)
    if 'GATE' in tags.upper().split(' : '):raise ValueError('额外房间包含尚未支持的跨区域业力门：'+name)
    return dict(name=name,connections=list(links),tags=tags)

def _extra_room_owner(source):
    
    source=Path(source).resolve();assets=(storage.GAME/'RainWorld_Data/StreamingAssets').resolve()
    if not room_bindings.is_enabled_asset(source.with_suffix('.txt')):
        raise ValueError('额外房间不属于当前启用的内容')
    if source.is_relative_to(assets/'world'):return None
    for root in sorted(room_bindings.enabled_asset_roots(),key=lambda p:len(p.parts),reverse=True):
        root=root.resolve()
        if not source.is_relative_to(root/'world'):continue
        owner=root.parent if root.name=='newest' or re.fullmatch(r'v\d+(?:\.\d+)+',root.name) else root
        info=owner/'modinfo.json'
        if not info.is_file():continue
        value=json.loads(info.read_text('utf-8-sig'));identifier=value.get('id');name=value.get('name')
        if not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',identifier) or not isinstance(name,str) or not name.strip():
            raise ValueError('额外房间所属模组的信息无效')
        if identifier.startswith('moreiterators'):
            raise ValueError('此房间属于 MI 本地内容，请从所属项目导出')
        if identifier in ('moreslugcats','watcher'):name=official_requirement(identifier)[1]
        return dict(id=identifier,name=name.strip())
    raise ValueError('无法确认额外房间所属模组')

def _requested_extra_rooms(request):
    requested=request.get('extraRooms',[])
    if not isinstance(requested,list) or len(requested)>500 or any(not isinstance(x,str) or not room_bindings.ROOM_RE.fullmatch(x) for x in requested) or len(set(requested))!=len(requested):
        raise ValueError('请选择不重复的额外房间')
    return requested

def extra_room_plan(request,projects,room_names,server):
    requested=_requested_extra_rooms(request)
    if not requested:return []
    import project_packages
    core_sources={name for p in projects for name in server.roomnames(p)[:2]}
    if core_sources.intersection(requested):raise ValueError('当前两房间会自动导出，无需重复选择：'+sorted(core_sources.intersection(requested))[0])
    exported={name for pair in room_names.values() for name in pair};owned_regions={name.split('_')[0] for name in exported}
    default_region=room_names[projects[0]['projectId']][0].split('_')[0]
    archived={};catalog=None;result=[]
    for project in projects:
        meta=project_packages.load_metadata(project['projectId'])
        for row in (meta or {}).get('rooms',[]):
            if row.get('name') in requested:archived.setdefault(row['name'],[]).append((project,row))
    for name in requested:
        matches=archived.get(name,[])
        if len(matches)>1:raise ValueError('所选项目的额外房间编号重复：'+name+'；不会覆盖或自动改名。')
        if matches:
            project,row=matches[0];source=project_packages.selected_room_source(project,name,rows={})
            origin='project';dependency=None
            target=name if name.split('_')[0] in owned_regions else default_region+'_'+name
        else:
            if catalog is None:catalog=room_bindings.catalog()
            rows=[r for region in catalog.get('regions',[]) for r in region.get('rooms',[]) if r.get('name')==name]
            if len(rows)!=1:raise ValueError('额外房间不在当前启用目录中，或编号重复：'+name)
            row=rows[0];project=projects[0]
            import room_source_choices
            source=room_source_choices.selected_source(project['projectId'],name) or room_bindings.resolve_room_source(name)
            origin='enabled';dependency=_extra_room_owner(source);target=default_region+'_'+name
        row=_extra_room_row(row,name)
        if origin=='project':
            links,tags=project_packages.selected_room_connections(project,name,source,rows={})
            row=_extra_room_row(dict(name=name,connections=links,tags=tags),name)
        if not room_bindings.ROOM_RE.fullmatch(target):raise ValueError('额外房间导出编号过长：'+target)
        if target in exported:raise ValueError('导出房间编号重复：'+target+'；不会覆盖或自动改名。')
        import room_source_choices
        geometry_file=room_source_choices.selected_render_files(name,source).get(name+'.txt',source.with_suffix('.txt'))
        if len(row['connections'])!=room_bindings.geometry(geometry_file)['exitCount']:
            raise ValueError('额外房间连接数量与地形出口不一致：'+name)
        exported.add(target)
        result.append(dict(sourceRoom=name,name=target,source=origin,project=project,sourcePath=source,
                           connections=row['connections'],tags=row['tags'],dependency=dependency))
    return result

def _selected_room_links(project,name,fallback):
    
    import project_packages
    source=project_packages.selected_room_source(project,name,rows={})
    links,tags=project_packages.selected_room_connections(project,name,source,rows={})
    row=_extra_room_row(dict(name=name,connections=links,tags=tags),name);links=row['connections']
    if len(links)!=len(fallback):raise ValueError('房间连接数量与当前地形不一致：'+name)
    for index,target in enumerate(fallback):
        if target!='DISCONNECTED':links[index]=target
    return links,row['tags']

def _world_row(name,links,tags,room_map):
    row=name+' : '+', '.join(room_map.get(target,'DISCONNECTED') for target in links)
    return row+(' : '+tags if tags else '')

def _route_exit(start,end,rows,selected):
    queue=[(start,None)];seen={start}
    for room,first in queue:
        for node,target in enumerate(rows.get(room,[])):
            if target not in selected or target in seen:continue
            step=node if first is None else first
            if target==end:return step
            seen.add(target);queue.append((target,step))
    missing=sorted({target for room in seen for target in rows.get(room,[])
                    if target!='DISCONNECTED' and target not in selected})
    if missing:raise room_bindings.RoomBindingError('workflowMissingExportRooms',rooms=', '.join(missing))
    raise room_bindings.RoomBindingError('workflowExportDisconnected')

def _room_files(stage,name):
    prefix='world/'+name.split('_')[0].lower()+'-rooms/'+name
    rows=(stage/(prefix+'.txt')).read_text('utf-8-sig').splitlines()
    cameras=[x for x in rows[3].split('|') if x.strip()] if len(rows)>3 else []
    variants=sorted(path.relative_to(stage).as_posix() for path in (stage/prefix).parent.iterdir()
                    if re.fullmatch(re.escape(name)+r'(?:_settings-[A-Za-z0-9_-]+|_properties)\.txt',path.name) and path.is_file())
    background=[prefix+'_mi_background.json'] if (stage/(prefix+'_mi_background.json')).is_file() else []
    return [prefix+'.txt',prefix+'_settings.txt']+[prefix+'_'+str(i)+'.png' for i in range(1,len(cameras)+1)]+variants+background

def _room_region_file(project,source,name,filename):
    import project_packages
    source=Path(source).resolve();region=name.split('_')[0]
    if source.parent.parent.name.lower()=='world':
        owner=source.parent.parent.parent
        if owner.name=='newest' or re.fullmatch(r'v\d+(?:\.\d+)+',owner.name):owner=owner.parent
        roots=_owner_asset_roots(owner)
    else:
        installed=storage.installed_mod(project['projectId'],required=False)
        roots=([installed] if installed is not None else [])+[storage.target_mod(project['projectId'])]
    for root in roots:
        candidate=Path(root)/'world'/region.lower()/filename
        if candidate.is_file():return candidate
    return project_packages.region_file(project['projectId'],region,filename)

def _remap_room_template(text,old_region,new_region):
    return re.sub(r'(?mi)^(Template:[ \t]*)'+re.escape(old_region)+r'(_settingstemplate_[A-Za-z0-9-]+)[ \t]*$',
                  lambda match:match[1]+new_region+match[2],text)

def _copy_room_region_assets(project,files,paths,old,new,directory,core):
    old_region=old.split('_')[0];new_region=new.split('_')[0];stage=directory.parent.parent
    world=stage/'world'/new_region.lower();world.mkdir(parents=True,exist_ok=True)
    original=files.get('properties.txt',b'').decode('utf-8-sig')
    properties=world/'properties.txt';existing=properties.read_bytes().decode('utf-8-sig') if properties.is_file() else None
    names=region_template_names(original);current=region_template_names(existing or '')
    if core and 'properties.txt' in files:
        if existing is not None and existing!=original:raise ValueError('房间引用的区域设置不一致：'+new_region+'/properties.txt')
        properties.write_bytes(original.encode('utf-8'))
        copy_room_palettes(project,paths['properties.txt'],properties,stage)
    elif names:
        combined=current+[name for name in names if name not in current]
        text=existing if existing is not None else 'Palette: 26\noverseersSpawnChance: 0\noverseersMin: 0\noverseersMax: 0\n'
        text=re.sub(r'(?m)^Room Setting Templates:[^\r\n]*(?:\r?\n|$)','',text)
        properties.write_bytes((text.rstrip('\r\n')+'\nRoom Setting Templates: '+', '.join(combined)+'\n').encode('utf-8'))
    for filename,content in files.items():
        if '_settingstemplate_' not in filename:continue
        renamed=new_region.lower()+filename[len(old_region):]
        destination=world/renamed;text=_remap_room_template(content.decode('utf-8-sig').replace('\r\n','\n'),old_region,new_region)
        if destination.is_file() and destination.read_bytes().decode('utf-8-sig')!=text:raise ValueError('房间模板名称冲突：'+renamed)
        destination.write_bytes(text.encode('utf-8'));copy_room_palettes(project,paths[filename],destination,stage)
    map_name='map_'+old_region.lower()+'.txt'
    if map_name in files:
        destination=world/('map_'+new_region.lower()+'.txt')
        lines=destination.read_text('utf-8-sig').splitlines() if destination.is_file() else []
        entries={line.split(':',1)[0].strip():line for line in lines}
        for line in files[map_name].decode('utf-8-sig').splitlines():
            name,separator,value=line.partition(':')
            if name.strip().upper()!=old:continue
            value=new+separator+value
            if new in entries and entries[new]!=value:raise ValueError('房间地图坐标冲突：'+new)
            entries[new]=value
        destination.write_text('\n'.join(entries[name] for name in sorted(entries))+'\n','utf-8')

def copy_selected_room(project,source,old,new,directory,server,core=True):
    import project_packages
    import room_package_dependencies
    settings=project_packages.selected_room_settings(project,old,source)
    setting_files=project_packages.room_settings_files(project,old,settings)
    rendered=project_packages._collect_render(source,settings,old,setting_files)
    files,paths=project_packages._collect_region(project,old.split('_')[0],source,{old})
    region_texts={filename:content.decode('utf-8-sig') for filename,content in files.items()}
    sky=room_package_dependencies.validate_room(old.split('_')[0],old,
        {filename:rendered[filename].decode('utf-8-sig') for filename in setting_files},region_texts,
        lambda filename:project_packages._dependency_origin(project,setting_files[filename]))
    if sky:
        if old.startswith('OE_') and not new.startswith('OE_'):raise ValueError('房间 '+old+' 的 OE 天空远景暂不支持跨区域导出')
        context=project_packages._background_context(project,old,source,rendered[old+'.txt'],project_packages._catalog_rows())
        context=copy.deepcopy(context);context['room']=new
        rendered[old+'_mi_background.json']=project_packages._json(context)
    text=settings.read_text('utf-8-sig')
    if old.split('_')[0]!=new.split('_')[0] and not re.search(r'(?m)^Palette:',text):
        properties=_room_region_file(project,source,old,'properties.txt')
        inherited=re.search(r'(?m)^Palette:[ \t]*(\d+)\b',properties.read_text('utf-8-sig')) if properties else None
        if inherited:text=text.rstrip('\r\n')+'\nPalette: '+inherited.group(1)+'\n'
    rendered[old+'_settings.txt']=text.encode('utf-8')
    directory.mkdir(parents=True,exist_ok=True)
    for filename,content in rendered.items():
        suffix=filename[len(old):]
        if suffix=='.txt':
            rows=content.decode('utf-8-sig').splitlines();rows[0]=new;content=('\n'.join(rows)+'\n').encode('utf-8')
        elif '_settings' in suffix:
            text=content.decode('utf-8-sig')
            if old.split('_')[0]!=new.split('_')[0]:
                parent=room_package_dependencies.parent_template(old.split('_')[0],text,region_texts.get('properties.txt',''))
                actual=new.split('_')[0]+parent[len(old.split('_')[0]):-4] if parent else 'NONE'
                if re.search(r'(?m)^Template:',text):text=re.sub(r'(?m)^Template:[^\r\n]*','Template: '+actual,text)
                else:text=text.rstrip('\r\n')+'\nTemplate: '+actual+'\n'
            content=_remap_room_template(text,old.split('_')[0],new.split('_')[0]).encode('utf-8')
        (directory/(new+suffix)).write_bytes(content)
    _copy_room_region_assets(project,files,paths,old,new,directory,core)
    return settings


def copy_selected_room_palettes(project,settings,old,new,directory,stage):
    import project_packages
    for filename,source in project_packages.room_settings_files(project,old,settings).items():
        copy_room_palettes(project,source,directory/(new+filename[len(old):]),stage)

def region_template_names(text):
    values=re.findall(r'(?m)^Room Setting Templates:[ \t]*([^\r\n]*)',text)
    if len(values)>1:raise ValueError('区域房间模板注册重复')
    names=[name.strip().lower() for name in values[0].split(',') if name.strip()] if values else []
    if len(set(names))!=len(names) or any(not re.fullmatch(r'[a-z0-9-]+',name) for name in names):
        raise ValueError('区域房间模板名称无效')
    return names

def copy_region_templates(project,source,region,stage):
    properties=stage/'world'/region.lower()/'properties.txt';result=[]
    for name in region_template_names(properties.read_text('utf-8-sig')):
        filename=region.lower()+'_settingstemplate_'+name+'.txt'
        candidate=source.parent/filename if source is not None else None
        if candidate is None or not candidate.is_file() or candidate.is_symlink() or not candidate.resolve().is_relative_to(source.parent.resolve()):
            raise ValueError('缺少区域注册的房间模板：'+filename)
        relative='world/'+region.lower()+'/'+filename;destination=stage/relative
        destination.write_bytes(candidate.read_bytes());copy_room_palettes(project,candidate,destination,stage)
        result.append(relative)
    return result

def build(request,server,save_preferences=True,finalize=None,verify=None,region_context=None):
    meta=metadata(request);ids=request.get('projects',[])
    _requested_extra_rooms(request)
    if not isinstance(ids,list) or not ids or len(ids)>100 or any(not isinstance(pid,str) for pid in ids) or len(set(ids))!=len(ids):raise ValueError('请选择 1–100 个不重复的迭代器项目。')
    ids=[storage.valid_id(pid) for pid in ids]
    components={k:request.get(k,False) for k in ('dialogue','pearls','broadcasts','workPearls')}
    components['projections']=request.get('projections',True)
    if any(type(v) is not bool for v in components.values()):raise ValueError('导出选项无效')
    pearl_collection,pearl_items=selected_pearl_content(request,ids,region_context.rooms if region_context else ())
    pearl_uids={p['uid'] for p in pearl_items}
    projection_items=[p for p in projections.listing() if p.get('projectId') in ids and components['projections']
        and (p.get('trigger',{}).get('kind') not in ('dialogue','pearl') or components['dialogue' if p['trigger']['kind']=='dialogue' else 'pearls'])
        and (p.get('trigger',{}).get('kind')!='pearl' or p['trigger'].get('pearlUid') in pearl_uids)]
    # Persist old anchors before capturing the selected runtime dialogue/pearl data.
    source_sets={pid:projections.sources(pid,server.roomnames,pearl_collection or None)['sources'] for pid in {p['projectId'] for p in projection_items}}
    projects=[server.validate(copy.deepcopy(storage.load_project(storage.valid_id(pid)))) for pid in ids]
    import room_source_choices
    projects=[room_source_choices.export_project(project) for project in projects]
    cover=cover_bytes(meta['cover'])
    room_names=export_room_names(projects,meta['id'])
    extra_plan=extra_room_plan(request,projects,room_names,server)
    if region_context and extra_plan:raise ValueError('完整区域不能同时使用局部房间编号映射')
    regions=sorted({names[0].split('_')[0] for names in room_names.values()})
    registry=[];mapping={};room_map={name:name for name in region_context.rooms} if region_context else {};connections={region:[] for region in regions};design_schema=runtime_design_schema()
    for project in projects:
        for old,new in zip(server.roomnames(project)[:2],room_names[project['projectId']]):
            if old in room_map and room_map[old]!=new:raise ValueError('额外房间无法确认重复来源房间的连接：'+old)
            room_map[old]=new
    if extra_plan:
        room_map.update({item['sourceRoom']:item['name'] for item in extra_plan})
    extra_manifest=[];room_templates=list(region_context.templates) if region_context else []
    with tempfile.TemporaryDirectory(prefix='mi-content-') as temp:
        temporary=Path(temp);stage=temporary/meta['id'];stage.mkdir();sources=temporary/'source';sources.mkdir()
        if region_context:region_context.copy_to(stage)
        copy_game_ui(stage)
        suffix=compile_runtime(stage,sources,meta,projects)
        for i,p in enumerate(projects,1):
            ai,entry,old_oid=server.roomnames(p);pid=p['projectId'];new_ai,new_entry=room_names[pid];region=new_ai.split('_')[0];oid='pack_'+suffix+'_'+str(i)
            d=runtime_fields(audio_assets.runtime_design(server.compile_design(p)),design_schema,'design');d.update(oracleId=oid,appearanceAdapter=p.get('legacyOracle',''))
            # Playback always carries a validated dialogue profile. Editor frame
            # tokens and obsolete text fallbacks do not belong in a content mod.
            for key in ('previewToken','firstDialogue','repeatDialogue','unmarkedDialogue','pearlDialogue'):d.pop(key,None)
            if not d.get('appearanceAdapter'):d.pop('appearanceAdapter',None)
            native=native_projects.binding(pid)
            if native:d['nativeOracle']=native.get('nativeOracle','')
            profile=runtime_fields(dialogue.profile(p),DIALOGUE,'dialogue')
            if not components['dialogue']:
                profile=without_dialogue(profile)
            d['dialogueJson']=json.dumps(profile,ensure_ascii=False)
            if not components['workPearls']:d['pearlCount']=d['pearlFixedCount']=0
            dump(stage/'designs'/(oid+'.json'),d)
            exits=room_connections(p,ai,entry,server)
            if p.get('roomConnections'):
                import project_packages
                graph={name:list(row['connections']) for name,row in project_packages.saved_connection_rows(p).items()}
                graph.update({item['sourceRoom']:item['connections'] for item in extra_plan})
                selected=set(room_map)|{ai,entry}
                ai_node=_route_exit(ai,entry,graph,selected);entry_node=_route_exit(entry,ai,graph,selected)
            else:ai_node=exits[ai].index(entry);entry_node=exits[entry].index(ai)
            record=dict(projectId=pid,name=p['name'],ai=new_ai,entry=new_entry,oracleId=oid,design='designs/'+oid+'.json',ownerMod=meta['id'],exitNode=ai_node,entryNode=entry_node)
            if p.get('roomConnections'):record['connectionVersion']=2
            if native:record['timeline']=native.get('timeline','')
            registry.append(record);mapping[pid]=record;room_map.update({ai:new_ai,entry:new_entry})
            for old,new,other,new_other in [(ai,new_ai,entry,new_entry),(entry,new_entry,ai,new_ai)]:
                if extra_plan or p.get('roomConnections') or region_context:
                    links,tags=_selected_room_links(p,old,exits[old]);connections[region].append(_world_row(new,links,tags,room_map))
                else:connections[region].append(new+' : '+', '.join(new_other if target==other else 'DISCONNECTED' for target in exits[old]))
            rooms=stage/('world/'+region.lower()+'-rooms')
            for old,new,kind in [(ai,new_ai,'ai'),(entry,new_entry,'entry')]:
                if region_context:
                    if old!=new or new not in region_context.rooms:raise ValueError('完整区域的迭代器房间编号不一致')
                    continue
                source=room_source(p,old,kind,server)
                settings_source=copy_selected_room(p,source,old,new,rooms,server)
                settings=rooms/(new+'_settings.txt')
                copy_selected_room_palettes(p,settings_source,old,new,rooms,stage)
        for item in extra_plan:
            name=item['name'];region=name.split('_')[0];directory=stage/('world/'+region.lower()+'-rooms')
            settings_source=copy_selected_room(item['project'],item['sourcePath'],item['sourceRoom'],name,directory,server,core=False)
            copy_selected_room_palettes(item['project'],settings_source,item['sourceRoom'],name,directory,stage)
            links=[room_map.get(target,'DISCONNECTED') for target in item['connections']]
            connections[region].append(_world_row(name,item['connections'],item['tags'],room_map))
            record=dict(sourceRoom=item['sourceRoom'],name=name,region=region,source=item['source'],connections=links,tags=item['tags'],files=_room_files(stage,name))
            if item['source']=='project':record['projectId']=item['project']['projectId']
            if item['dependency']:
                if item['dependency']['id']==meta['id']:raise ValueError('额外房间不能依赖当前导出模组自身')
                record['dependency']=item['dependency']
            extra_manifest.append(record)
        overseer_requirements=set();excluded=None
        for project,record in zip(projects,registry):
            design_file=stage/record['design'];design=json.loads(design_file.read_text('utf-8'))
            if overseers.RUNTIME_FIELD not in design:continue
            raw=design[overseers.RUNTIME_FIELD];config=overseers.decode(raw)
            if excluded is None and any(room not in room_map for profile in [config,*config['guests']] for room in profile.get('rooms',[])):
                excluded=unselected_owned_rooms(set(ids))
            # An external entrance can be shared by selected projects. Its host
            # copy takes priority for this host's configuration.
            old_ai,old_entry,_=server.roomnames(project)
            own_map={**room_map,old_ai:record['ai'],old_entry:record['entry']}
            config,requirements=export_overseers(raw,own_map,set(ids),excluded or set())
            overseer_requirements.update(requirements)
            design[overseers.RUNTIME_FIELD]=json.dumps(config,ensure_ascii=False)
            dump(design_file,design)
        dump(stage/'moreiterators/registry.json',registry)
        for region in regions:
            if region_context:continue
            world=stage/('world/'+region.lower());world.mkdir(parents=True,exist_ok=True)
            rows=['ROOMS']+connections[region]
            (world/('world_'+region.lower()+'.txt')).write_text('\n'.join(rows+['END ROOMS','','CREATURES','END CREATURES'])+'\n','utf-8')
            authored=next((p for p in projects if p.get('roomBinding',{}).get('region')==region and room_names[p['projectId']][0]==p['roomBinding']['ai']),None)
            defaults={'properties.txt':'Palette: 26\noverseersSpawnChance: 0\noverseersMin: 0\noverseersMax: 0\n','displayname.txt':(region if authored else meta['name'])+'\n'}
            for filename,text in defaults.items():
                if (world/filename).is_file():continue
                if authored:
                    old_ai=server.roomnames(authored)[0]
                    source=_room_region_file(authored,room_source(authored,old_ai,'ai',server),old_ai,filename)
                    if source is not None:text=source.read_text('utf-8-sig')
                    if filename=='properties.txt':properties_source=source
                (world/filename).write_text(text,'utf-8')
            room_templates.extend('world/'+region.lower()+'/'+region.lower()+'_settingstemplate_'+name+'.txt'
                                  for name in region_template_names((world/'properties.txt').read_text('utf-8-sig')))
        if not region_context:
            registration=stage/'modify/world/regions.txt';registration.parent.mkdir(parents=True,exist_ok=True);registration.write_text(''.join('[ADD]'+region+'\n' for region in regions),'utf-8')
        pearl_requirements={}
        if components['pearls']:
            for p in pearl_items:
                readers=[r for r in p['readers'] if pearls.native_reader(r) or r['projectId'] in mapping];spawns=[pid for pid in p['spawnProjects'] if pid in mapping]
                if not readers and not spawns and not set(p.get('spawnRooms',[])).intersection(room_map):continue
                p=copy.deepcopy(p);p['readers']=readers;p['spawnProjects']=spawns
                item=pearls.compile_project(p,lambda q:(mapping[q['projectId']]['ai'],mapping[q['projectId']]['entry'],mapping[q['projectId']]['oracleId']))
                item['spawns'],dependencies=export_pearl_spawns(item['spawns'],room_map,mapping)
                pearl_requirements.update(dependencies)
                item['runtimeId']='IC_'+suffix+'_'+item['uid'];item['ownerMod']=meta['id'];item.pop('updatedAt',None);item.pop('spawnProjects',None)
                dump(stage/'moreiterators/pearls'/(item['id']+'.json'),runtime_fields(item,PEARL,'pearl'))
        for p in projection_items:
            record=mapping[p['projectId']]
            compiled=projections.compile_project(p,lambda q:(mapping[q['projectId']]['ai'],mapping[q['projectId']]['entry'],mapping[q['projectId']]['oracleId']),meta['id'],source_sets[p['projectId']])
            dump(stage/'moreiterators/projections'/(p['uid']+'.json'),runtime_fields(compiled,PROJECTION,'projection'))
        if components['broadcasts']:
            for p in broadcasts.listing():
                if p.get('room') not in room_map:continue
                p=broadcasts.compile_project(p);p['room']=room_map[p['room']];p['region']=p['room'].split('_')[0];p['runtimeId']='IC_'+suffix+'_Broadcast_'+p['uid'];p.pop('notes',None)
                dump(stage/'moreiterators/broadcasts'/(p['id']+'.json'),runtime_fields(p,BROADCAST,'broadcast'))
        info={k:meta[k] for k in ('id','name','authors','description','version')}
        info.update(requirements=['warp'],requirements_names=['Warp Menu'],tags=['Regions','Creatures'],target_game_version='v1.11.8',checksum_override_version=False)
        selected_rooms=[name for pair in room_names.values() for name in pair]+[item['name'] for item in extra_plan]
        palette_requirements=room_palette_requirements(stage,selected_rooms,room_templates)
        if palette_requirements:
            import region_packages
            dependencies=region_packages.Collector()
            for dependency_id in palette_requirements:dependencies.dependency(dependency_id)
            for dependency_id,dependency in sorted(dependencies.dependencies.items()):
                if dependency_id not in info['requirements']:
                    info['requirements'].append(dependency_id);info['requirements_names'].append(dependency['name'])
        # Broadcasts and Halcyon assets use the official expansion, never MI.
        if components['broadcasts'] or any(native_projects.binding(p['projectId']) for p in projects) or any(p.get('appearance',{}).get('music') and p.get('appearance',{}).get('effect')=='halcyon' and p.get('appearance',{}).get('musicTrack',{}).get('mode','native')=='native' for p in pearl_items):
            info['requirements'].append('moreslugcats');info['requirements_names'].append('More Slugcats Expansion')
        for requirement in sorted(overseer_requirements):
            if requirement not in info['requirements']:
                dependency_id,dependency_name=official_requirement(requirement)
                info['requirements'].append(dependency_id);info['requirements_names'].append(dependency_name)
        for dependency_id,dependency_name in sorted(pearl_requirements.items()):
            if dependency_id==meta['id']:raise ValueError('珍珠生成房间依赖当前导出模组自身，请同时选择其所属迭代器导出。')
            if dependency_id not in info['requirements']:
                info['requirements'].append(dependency_id);info['requirements_names'].append(dependency_name)
        for item in extra_manifest:
            dependency=item.get('dependency')
            if dependency and dependency['id'] not in info['requirements']:
                info['requirements'].append(dependency['id']);info['requirements_names'].append(dependency['name'])
        if region_context:
            for dependency in sorted(region_context.dependencies.values(),key=lambda item:item['id']):
                if dependency['id'] not in info['requirements']:
                    info['requirements'].append(dependency['id']);info['requirements_names'].append(dependency['name'])
        dump(stage/'modinfo.json',info)
        if cover:(stage/'thumbnail.png').write_bytes(cover)
        manifest=dict(schema='moreiterators.playback-export.v1',independentMod=True,projects=[dict(projectId=p['projectId'],name=p['name']) for p in projects],components=components,region=regions[0],regions=regions,runtimeVersion=json.loads((storage.WORKSPACE/'version.json').read_text('utf-8'))['version'])
        if pearl_collection:manifest['pearlCollectionId']=pearl_collection
        if extra_manifest:
            manifest['selectedExtraRooms']=list(request['extraRooms']);manifest['extraRooms']=extra_manifest
        if room_templates:manifest['roomTemplates']=sorted(room_templates)
        dump(stage/'content-manifest.json',manifest)
        (stage/'README.txt').write_text('把这个文件夹放进 RainWorld_Data/StreamingAssets/mods，然后在拓展菜单里启用就行。\n\n这个包做了 MoreIterators 的适配（register），不过现在是被单独导出的模组，所以没有 MoreIterators 的时候它也能正常独立运行，不需要额外装工具包。\n\n进游戏后点主菜单右下角的按钮，可以选择预设。进入演算室之后按 F8 可以打开控制面板。\n\n关于迭代器的台词：默认是有交流印记的，能看到对方说话；如果没有印记，只有动画。\n','utf-8')
        audio_documents=[json.loads(file.read_text('utf-8')) for directory in (stage/'designs',stage/'moreiterators/pearls') for file in directory.glob('*.json')]
        audio_assets.copy_referenced(audio_documents,stage)
        audit(stage,ids,request.get('extraRooms',[]),region_context=region_context)
        if finalize is not None:
            manifest=finalize(stage,manifest,room_map)
        storage.EXPORTS.mkdir(parents=True,exist_ok=True)
        name=meta['id'].replace('.','-')+'-'+meta['version'].replace('.','-')+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S%f')+'.zip'
        with zipfile.ZipFile(storage.EXPORTS/name,'w',zipfile.ZIP_DEFLATED) as z:
            for f in sorted(stage.rglob('*')):
                if f.is_file():z.write(f,meta['id']+'/'+f.relative_to(stage).as_posix())
        if verify is not None:
            try:verify(stage,storage.EXPORTS/name)
            except Exception:
                (storage.EXPORTS/name).unlink(missing_ok=True)
                raise
        if save_preferences:
            settings_pid=request.get('settingsProject','')
            target=storage.project_file(storage.valid_id(settings_pid)).parent/'export-settings.json' if settings_pid in ids else storage.DATA/'export-settings.json'
            previous=json.loads(target.read_text('utf-8')) if target.is_file() else {}
            dump(target,{**previous,**meta,**components,'projects':ids,'pearlCollectionId':pearl_collection,'extraRooms':list(request.get('extraRooms',[]))})
        return dict(ok=True,url='/exports/'+name,manifest=manifest)

def audit(stage,ids,extra_rooms=None,region_context=None):
    stage=Path(stage);selected=set(ids);design_schema=runtime_design_schema()
    def reject(message,file=''):
        raise ValueError(message+('：'+str(file) if file else ''))
    def read(file):
        try:return json.loads((stage/file).read_text('utf-8'))
        except (OSError,ValueError) as error:raise ValueError('独立包数据无法读取：'+str(file)) from error
    info=read('modinfo.json');registry=read('moreiterators/registry.json');manifest=read('content-manifest.json')
    metadata(info)
    requirements=info.get('requirements',[]);names=info.get('requirements_names',[])
    if 'warp' not in requirements or len(requirements)!=len(names) or names[requirements.index('warp')]!='Warp Menu':reject('独立包必须声明 Warp Menu 依赖')
    if any(x.startswith('moreiterators') for x in requirements):reject('独立包不能依赖 MI 工具包')
    pearl_dependencies=set()
    if not isinstance(registry,list) or sorted(p.get('projectId','') for p in registry)!=sorted(ids):reject('导出项目与选择不一致')
    records={p['projectId']:p for p in registry}
    expected_projects=[dict(projectId=p['projectId'],name=p['name']) for p in registry]
    if manifest.get('schema')!='moreiterators.playback-export.v1' or not isinstance(manifest.get('runtimeVersion'),str):reject('导出清单版本无效')
    if manifest.get('projects')!=expected_projects or manifest.get('independentMod') is not True:reject('导出清单与实际项目不一致')
    region=manifest.get('region','');regions=manifest.get('regions',[region]);components=manifest.get('components',{})
    if not isinstance(regions,list) or not regions or any(not isinstance(value,str) or not room_bindings.REGION_RE.fullmatch(value) for value in regions) or len(set(regions))!=len(regions) or region not in regions or any(type(components.get(k)) is not bool for k in ('dialogue','pearls','broadcasts','workPearls')):reject('导出清单格式无效')
    oracles={p['oracleId'] for p in registry};rooms={p[k] for p in registry for k in ('ai','entry')}
    if len(oracles)!=len(registry) or len(rooms)!=len(registry)*2:reject('导出项目的迭代器或房间编号重复')
    core_rooms=set(rooms);extra_manifest=manifest.get('extraRooms',[]);extra_dependencies=set()
    if region_context:
        region_context.verify(stage)
        if not rooms.issubset(set(region_context.rooms)):reject('完整区域缺少所选迭代器房间')
        rooms=set(region_context.rooms)
    if not isinstance(extra_manifest,list):reject('额外房间清单无效')
    requested=_requested_extra_rooms({'extraRooms':manifest.get('selectedExtraRooms',[])})
    if extra_rooms is not None and requested!=extra_rooms:reject('额外房间清单与选择不一致')
    if [row.get('sourceRoom') for row in extra_manifest if isinstance(row,dict)]!=requested:reject('额外房间清单与选择不一致')
    for row in extra_manifest:
        if not isinstance(row,dict) or set(row)-{'sourceRoom','name','region','source','projectId','connections','tags','files','dependency'}:reject('额外房间清单字段无效')
        name=row.get('name');origin=row.get('source');dependency=row.get('dependency')
        if not isinstance(name,str) or not room_bindings.ROOM_RE.fullmatch(name) or name in rooms:reject('额外房间编号重复或无效')
        if row.get('region')!=name.split('_')[0] or row['region'] not in regions:reject('额外房间区域无效',name)
        if origin=='project':
            if row.get('projectId') not in selected or dependency is not None:reject('额外房间所属项目无效',name)
        elif origin=='enabled':
            if 'projectId' in row:reject('外部房间不能冒充项目房间',name)
            verified=_extra_room_owner(room_bindings.resolve_room_source(row['sourceRoom']))
            if verified!=dependency:reject('额外房间依赖与实际来源不符',name)
        else:reject('额外房间来源无效',name)
        if dependency is not None:
            if not isinstance(dependency,dict) or set(dependency)!={'id','name'}:reject('额外房间依赖无效',name)
            dependency_id=dependency['id']
            if dependency_id not in requirements or names[requirements.index(dependency_id)]!=dependency['name']:reject('额外房间缺少所属模组依赖',name)
            extra_dependencies.add(dependency_id)
        _extra_room_row(row,name);rooms.add(name)
    if region_context:
        if regions!=region_context.regions:reject('导出区域与完整区域清单不一致')
    elif {room.split('_')[0] for room in rooms}!=set(regions):reject('导出区域与实际房间不一致')
    expected_designs=set()
    for p in registry:
        design=p.get('design','')
        if design!='designs/'+p['oracleId']+'.json' or not re.fullmatch(r'designs/[A-Za-z0-9_]+\.json',design):reject('设计文件路径无效',design)
        if p.get('ownerMod')!=info['id'] or any(not room_bindings.ROOM_RE.fullmatch(p[k]) or p[k].split('_')[0] not in regions for k in ('ai','entry')) or p['ai'].split('_')[0]!=p['entry'].split('_')[0]:reject('项目包含包外的模组或房间绑定',p['projectId'])
        expected_designs.add(design);d=read(design)
        if d.get('schema')!='moreiterators.oracle.v1':reject('设计格式版本无效',design)
        if any(d.get(k)!=p[k] for k in ('projectId','oracleId','name')):reject('设计文件与项目绑定不一致',design)
        if any(k in d for k in ('legacySource','previewToken','firstDialogue','repeatDialogue','unmarkedDialogue','pearlDialogue')):reject('设计文件包含编辑器或旧台词字段',design)
        if 'appearanceAdapter' in d and not d['appearanceAdapter']:reject('设计文件包含空的旧外观绑定',design)
        runtime_fields(d,design_schema,design,strict=True)
        if overseers.RUNTIME_FIELD in d:
            try:config=runtime_fields(overseers.decode(d[overseers.RUNTIME_FIELD]),OVERSEER,'overseer',strict=True)
            except (ValueError,TypeError):reject('设计中的监视器配置无效',design)
            for overseer in [config,*config['guests']]:
                if overseer.get('ownerProjectId') and overseer['ownerProjectId'] not in selected:reject('监视器引用了未选择的所属迭代器',design)
                for room in overseer.get('rooms',[]):
                    if room in rooms:continue
                    requirement=official_room_requirement(room)
                    if requirement and requirement not in requirements:reject('监视器地点缺少官方扩展依赖：'+requirement,design)
                    if requirement and names[requirements.index(requirement)]!=official_requirement(requirement)[1]:reject('监视器地点的官方扩展名称与来源不符：'+requirement,design)
        try:profile=json.loads(d['dialogueJson'])
        except (KeyError,ValueError,TypeError):reject('设计缺少有效对话配置',design)
        runtime_fields(profile,DIALOGUE,design+'.dialogueJson',strict=True)
        dialogue.validate(profile)
        if not components['dialogue']:
            if any(profile.get(k) for k in ('enabled','pickupEnabled','leaveEnabled','first','repeat','meetings','loop','pickup','leaving','returning')):reject('未启用的对话仍有正文或开关',design)
            rules=profile.get('pearlReading',{})
            if any(rules.get(k) for k in ('greetingEnabled','manyEnabled',*dialogue.PEARL_POOLS)):reject('未启用的对话仍有珍珠台词',design)
            for section in ('affinity','observation'):
                for key,value in profile.get(section,{}).items():
                    if key=='enabled' and value or isinstance(value,list) and value or isinstance(value,dict) and any(value.values()):
                        reject('未启用的对话仍有好感或观察规则',design)
            if any(profile.get(k,{}).get('type','none')!='none' for k in ('firstAction','repeatAction','loopAction')):reject('未启用的对话仍有执行动作',design)
        if not components['workPearls'] and any(d.get(k)!=0 for k in ('pearlCount','pearlFixedCount')):reject('未启用的工作珍珠数量必须为零',design)
    actual_designs={f.relative_to(stage).as_posix() for f in (stage/'designs').rglob('*') if f.is_file()}
    if actual_designs!=expected_designs:reject('设计文件集合与选定项目不一致')

    # JSON escaping and JSON stored inside a string must not hide local paths or
    # references to unselected projects. Texture bytes are runtime artwork.
    local_path=re.compile(r'(?:[A-Za-z]:[\\/]|\\\\[^\\\s]+[\\/]|file://|/(?:Users|home|mnt|tmp)/|(?:https?://)?(?:127\.0\.0\.1|localhost)(?::\d+)?(?:/|\b))',re.I)
    def inspect(value,file,key=''):
        if isinstance(value,dict):
            native=pearls.native_reader(value) and value.get('projectId')=='' and value.get('oracleId')==value.get('nativeOracleId')
            for field,item in value.items():
                if field in ('runtimeDirectory','editorDirectory','previewToken','legacySource'):reject('独立包包含本地开发字段',file)
                if field=='projectId' and item not in selected and not native:reject('独立包引用了未选择的项目',file)
                if field=='oracleId' and item not in oracles and not native:reject('独立包引用了未选择的迭代器',file)
                inspect(item,file,field)
        elif isinstance(value,list):
            for item in value:inspect(item,file,key)
        elif isinstance(value,str):
            if value.startswith('data:image/'):return
            if local_path.search(value) or any(x in value.lower() for x in ('studio-control.json','studio-frame.json','launch-room.txt')):reject('独立包包含本地开发信息',file)
            if key.endswith('Json'):
                try:nested=json.loads(value)
                except ValueError:reject('独立包内嵌数据格式无效',file)
                inspect(nested,file)

    allowed={'modinfo.json','content-manifest.json','README.txt','thumbnail.png','moreiterators/registry.json','modify/world/regions.txt'}|expected_designs|set(GAME_UI_FILES)
    if region_context:allowed.update(region_context.file_names)
    else:
        for region in regions:allowed.update(('world/'+region.lower()+'/properties.txt','world/'+region.lower()+'/displayname.txt','world/'+region.lower()+'/world_'+region.lower()+'.txt'))
        for region in regions:
            relative='world/'+region.lower()+'/map_'+region.lower()+'.txt'
            if not (stage/relative).is_file():continue
            import room_package_dependencies
            text=(stage/relative).read_text('utf-8-sig')
            names={line.split(':',1)[0].strip().upper() for line in text.splitlines() if line.strip()}
            if names-set(rooms):reject('房间地图包含未选择的房间',relative)
            room_package_dependencies.map_positions(text,names);allowed.add(relative)
    suffix=hashlib.sha256(info['id'].encode()).hexdigest()[:12]
    allowed.add('plugins/IteratorContent_'+suffix+'.dll')
    required=allowed-{'thumbnail.png'}
    palettes=set();cameras=set();room_asset_refs=[];room_optional_refs=[]
    import room_asset_dependencies
    templates=[]
    for region in regions:
        properties=stage/('world/'+region.lower()+'/properties.txt')
        if not properties.is_file():continue
        for name in region_template_names(properties.read_text('utf-8-sig')):
            relative='world/'+region.lower()+'/'+region.lower()+'_settingstemplate_'+name+'.txt'
            file=stage/relative
            if not file.is_file():reject('缺少区域注册的房间模板',relative)
            templates.append(relative);allowed.add(relative)
            palettes.update('palettes/palette'+str(value)+'.png' for value in room_palette_ids(file.read_text('utf-8-sig')))
            room_asset_refs.extend(room_asset_dependencies.references(file.read_text('utf-8-sig'),relative))
            room_optional_refs.extend(room_asset_dependencies.optional_references(file.read_text('utf-8-sig'),relative))
    if manifest.get('roomTemplates',[])!=sorted(region_context.templates if region_context else templates):reject('区域房间模板清单不一致')
    for room in rooms:
        prefix=region_context.room_files[room][0][:-4] if region_context else 'world/'+room.split('_')[0].lower()+'-rooms/'+room
        allowed.update((prefix+'.txt',prefix+'_settings.txt'))
        required.update((prefix+'.txt',prefix+'_settings.txt'))
        terrain=stage/(prefix+'.txt');settings=stage/(prefix+'_settings.txt')
        if not terrain.is_file() or not settings.is_file():reject('缺少必需房间文件',room)
        rows=terrain.read_text('utf-8-sig').splitlines()
        if len(rows)<4 or rows[0]!=room:reject('房间地形名称或相机数据无效',room)
        background=stage/(prefix+'_mi_background.json')
        if background.is_file():
            import room_package_dependencies
            room_package_dependencies.background(json.loads(background.read_text('utf-8-sig')),room,
                                                  tuple(map(int,rows[1].split('|')[0].split('*'))))
            allowed.add(prefix+'_mi_background.json');required.add(prefix+'_mi_background.json')
        positions=[x for x in rows[3].split('|') if x.strip()]
        if not positions or any(not re.fullmatch(r'-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?',x.strip()) for x in positions):reject('房间相机数据无效',room)
        for index in range(1,len(positions)+1):cameras.add(prefix+'_'+str(index)+'.png')
        setting_files=[relative for relative in (region_context.room_files[room] if region_context else _room_files(stage,room))
                       if re.fullmatch(re.escape(room)+r'(?:_settings(?:-[A-Za-z0-9_-]+)?|_properties)\.txt',Path(relative).name)]
        dependency_settings={}
        for relative in setting_files:
            allowed.add(relative);required.add(relative);text=(stage/relative).read_text('utf-8-sig')
            dependency_settings[Path(relative).name]=text
            for value in room_palette_ids(text):palettes.add('palettes/palette'+str(value)+'.png')
            room_asset_refs.extend(room_asset_dependencies.references(text,relative))
            room_optional_refs.extend(room_asset_dependencies.optional_references(text,relative))
        if room.startswith('OE_'):
            import room_package_dependencies
            folder=stage/'world/oe'
            regional={file.name:file.read_text('utf-8-sig') for file in folder.glob('*.txt')
                      if file.name in ('properties.txt','map_oe.txt') or file.name.startswith('oe_settingstemplate_')}
            if room_package_dependencies.validate_room('OE',room,dependency_settings,regional,lambda name:name):
                world=folder/'world_oe.txt'
                available={row['name'] for row in room_bindings.parse_world(world.read_text('utf-8-sig'),'OE')} if world.is_file() else set()
                room_package_dependencies.require_sky_rooms('OE',room,available,prefix+'_settings.txt')
    for row in extra_manifest:
        expected=_room_files(stage,row['name'])
        if row.get('files')!=expected:reject('额外房间文件白名单不一致',row['name'])
    palette_dependencies=set()
    palette_requirements=room_palette_requirements(stage,rooms,templates,region_context.room_files if region_context else None)
    if palette_requirements:
        import region_packages
        dependencies=region_packages.Collector()
        for dependency_id in palette_requirements:dependencies.dependency(dependency_id)
        for dependency_id,dependency in dependencies.dependencies.items():
            if dependency_id not in requirements or names[requirements.index(dependency_id)]!=dependency['name']:
                reject('额外色板缺少 RegionKit 依赖 '+dependency_id,'modinfo.json')
            palette_dependencies.add(dependency_id)
    for region in regions:
        properties=stage/('world/'+region.lower()+'/properties.txt')
        if properties.is_file():
            palettes.update('palettes/palette'+str(value)+'.png' for value in room_palette_ids(properties.read_text('utf-8-sig')))
            room_asset_refs.extend(room_asset_dependencies.references(properties.read_text('utf-8-sig'),str(properties)))
            room_optional_refs.extend(room_asset_dependencies.optional_references(properties.read_text('utf-8-sig'),str(properties)))
    for candidates in room_asset_refs:
        present=[relative for relative in candidates if (stage/relative).is_file()]
        if not present and room_asset_dependencies.has_native_ambient_reference(candidates):continue
        if len(present)!=1:reject('房间附加素材缺失或来源不明确',candidates[0])
        relative=present[0];room_asset_dependencies.validate(relative,(stage/relative).read_bytes())
        allowed.add(relative);required.add(relative)
    for candidates in room_optional_refs:
        for relative in candidates:
            if not (stage/relative).is_file():continue
            room_asset_dependencies.validate(relative,(stage/relative).read_bytes());allowed.add(relative)
    for relative in palettes:
        file=stage/relative
        if not file.is_file():
            # Original numbered palettes may be supplied by the base game. A
            # custom dependency must be present; another mod is not a fallback.
            index=int(Path(relative).stem[7:])
            if _palette_file(storage.GAME/'RainWorld_Data/StreamingAssets',index) is None:reject('缺少房间引用的自定义调色板',relative)
            continue
        try:
            with Image.open(file) as palette:
                if palette.format!='PNG':reject('房间调色板必须为 PNG',relative)
                palette.verify()
        except (OSError,ValueError) as error:raise ValueError('房间调色板图损坏：'+relative) from error
    required.update(cameras);allowed.update(cameras)
    for relative in sorted(required):
        file=stage/relative
        if not file.is_file() or file.stat().st_size==0:reject('缺少必需运行文件',relative)
    for relative in cameras:
        try:
            with Image.open(stage/relative) as camera:
                if camera.format!='PNG':reject('房间相机必须为 PNG',relative)
                camera.verify()
        except (OSError,ValueError) as error:raise ValueError('房间相机图损坏：'+relative) from error
    dll=stage/('plugins/IteratorContent_'+suffix+'.dll')
    if not dll.read_bytes().startswith(b'MZ'):reject('运行 DLL 格式无效')
    connections={}
    if region_context:
        rows=region_context.validate_world(stage,[record['ai'] for record in registry])
        connections={row['name']:row['connections'] for row in rows}
    for region in ([] if region_context else regions):
        world=stage/('world/'+region.lower()+'/world_'+region.lower()+'.txt');region_rooms=set()
        for row in world.read_text('utf-8-sig').splitlines():
            parts=row.split(' : ')
            if len(parts)>1:
                if parts[0] in connections:reject('世界文件的房间编号重复',parts[0])
                region_rooms.add(parts[0]);connections[parts[0]]=[x.strip() for x in parts[1].split(',')]
        if region_rooms!={room for room in rooms if room.startswith(region+'_')}:reject('世界文件的区域房间集合不一致',region)
    if region_context:
        if not set(connections).issubset(rooms) or not core_rooms.issubset(connections):reject('世界文件的生效房间集合不一致')
    elif set(connections)!=rooms:reject('世界文件的房间集合不一致')
    for room,links in connections.items():
        if any(target not in rooms and target!='DISCONNECTED' for target in links):reject('房间连接引用未选择的房间',room)
    for row in extra_manifest:
        if connections[row['name']]!=row['connections']:reject('额外房间连接与清单不一致',row['name'])
    for record in registry:
        ai,entry=record['ai'],record['entry'];exit_node=record.get('exitNode')
        if record.get('connectionVersion')==2:
            if type(exit_node) is not int or exit_node!=_route_exit(ai,entry,connections,rooms):reject('房间出口编号无效')
            if type(record.get('entryNode')) is not int or record['entryNode']!=_route_exit(entry,ai,connections,rooms):reject('等待房间出口编号无效')
            continue
        if entry not in connections[ai] or ai not in connections[entry] or not region_context and not extra_manifest and any(x not in (ai,entry,'DISCONNECTED') for room in (ai,entry) for x in connections[room]):reject('房间连接不属于选定房间对')
        if type(exit_node) is not int or not 0<=exit_node<len(connections[ai]) or connections[ai][exit_node]!=entry:reject('房间出口编号无效')
        entry_node=record.get('entryNode',connections[entry].index(ai))
        if type(entry_node) is not int or not 0<=entry_node<len(connections[entry]) or connections[entry][entry_node]!=ai:reject('等待房间出口编号无效')
    if (stage/'modify/world/regions.txt').read_text('utf-8-sig').splitlines()!=['[ADD]'+region for region in regions]:reject('区域注册与清单不一致')
    for kind in ('pearls','broadcasts'):
        files=[f for f in (stage/'moreiterators'/kind).rglob('*') if f.is_file()]
        if files and not components[kind]:reject('未启用的导出内容仍有文件',kind)
        for f in files:
            rel=f.relative_to(stage).as_posix();item=read(rel)
            if not re.fullmatch(r'[A-Z][A-Z0-9_]{1,31}',item.get('id','')) or rel!='moreiterators/'+kind+'/'+item['id']+'.json':reject('内容文件编号与路径不一致',rel)
            uid=item.get('uid','')
            expected_runtime='IC_'+suffix+('_Broadcast_' if kind=='broadcasts' else '_')+uid
            if not re.fullmatch('[a-f0-9]{32}',uid) or item.get('runtimeId')!=expected_runtime:reject('内容运行编号无效',rel)
            if 'notes' in item or kind=='pearls' and any(k in item for k in ('updatedAt','spawnProjects','spawnPositions','spawnRooms','spawnRoomPositions')):reject('内容包含制作室记录',rel)
            runtime_fields(item,PEARL if kind=='pearls' else BROADCAST,rel,strict=True)
            expected_schema='moreiterators.pearl.v1' if kind=='pearls' else 'moreiterators.broadcast.v1'
            required_fields=('name','appearance','readers','spawns') if kind=='pearls' else ('name','x','y','pages')
            if item.get('schema')!=expected_schema or any(key not in item for key in required_fields):reject('内容缺少必需运行字段',rel)
            if kind=='pearls':
                collection=manifest.get('pearlCollectionId')
                if collection and item.get('collectionId')!=collection:reject('珍珠不属于本次选择的珍珠项目',rel)
                if item.get('ownerMod')!=info['id']:reject('珍珠绑定了包外模组',rel)
                if not item.get('readers') and not item.get('spawns'):reject('珍珠没有选定项目的绑定',rel)
                for reader in item.get('readers',[]):
                    p=records.get(reader.get('projectId'))
                    if pearls.native_reader(reader):
                        if reader.get('projectId')!='' or reader.get('oracleId')!=reader['nativeOracleId'] or reader.get('name')!=reader['nativeOracleId']:reject('原版珍珠读取者无效',rel)
                        pearls.validate_native_features(reader)
                    elif not p or reader.get('oracleId')!=p['oracleId'] or reader.get('name')!=p['name']:reject('珍珠读取者不属于选定项目',rel)
                    def check_actions(body):
                        if 'readAction' in body:dialogue.validate_action(body['readAction'])
                        for line in body.get('read',[]):
                            if 'action' in line:dialogue.validate_action(line['action'])
                        for group in [group for key in ('repeat','leaving','returning') for group in body.get(key,[])]:
                            if 'action' in group:dialogue.validate_action(group['action'])
                            for line in group.get('lines',[]):
                                if 'action' in line:dialogue.validate_action(line['action'])
                    check_actions(reader)
                    for branch in reader.get('affinity',{}).values():check_actions(branch)
                for spawn in item.get('spawns',[]):
                    p=records.get(spawn.get('projectId'));room=spawn.get('entry')
                    if spawn.get('projectId'):
                        if not p or room not in (p['ai'],p['entry']):reject('珍珠生成位置不属于选定项目',rel)
                    else:
                        if room in core_rooms:reject('项目内珍珠生成位置缺少项目编号',rel)
                        dependency=None if room in rooms else pearl_room_requirement(room)
                        if dependency:
                            dependency_id,dependency_name=dependency
                            if dependency_id not in requirements or names[requirements.index(dependency_id)]!=dependency_name:reject('珍珠生成房间缺少已确认的地图依赖 '+dependency_id,rel)
                            pearl_dependencies.add(dependency_id)
                    if 'position' in spawn and (set(spawn['position'])!={'x','y'} or any(not 0<=spawn['position'][key]<=1 for key in ('x','y'))):reject('珍珠生成坐标无效',rel)
            elif item.get('room') not in rooms or item.get('region')!=item['room'].split('_')[0]:reject('广播位置不属于选定项目',rel)
            allowed.add(rel)
    projection_files=[f for f in (stage/'moreiterators/projections').rglob('*') if f.is_file()]
    if projection_files and not components.get('projections',False):reject('未启用的投影仍有文件')
    exported_pearls=[read(f.relative_to(stage).as_posix()) for f in (stage/'moreiterators/pearls').glob('*.json')]
    for file in projection_files:
        rel=file.relative_to(stage).as_posix();item=read(rel)
        runtime_fields(item,PROJECTION,rel,strict=True)
        projections.validate(item,resolve_sources=False)
        record=records.get(item['projectId'])
        if not record or item.get('oracleId')!=record['oracleId'] or item.get('ownerMod')!=info['id']:reject('投影不属于选定项目或模组',rel)
        if rel!='moreiterators/projections/'+item['uid']+'.json':reject('投影文件编号与路径不一致',rel)
        kind=item['trigger']['kind']
        if kind=='dialogue' and not components['dialogue'] or kind=='pearl' and not components['pearls']:reject('投影依赖未导出的台词内容',rel)
        profile=json.loads(read(record['design'])['dialogueJson'])
        entries=projections.source_entries(item['projectId'],profile,exported_pearls)
        if item['trigger'].get('lineIds')!=projections.resolve_lines(item,entries):reject('投影台词范围与导出的台词不一致',rel)
        allowed.add(rel)
    audio_documents=[read(p['design']) for p in registry]+exported_pearls
    allowed.update(audio_assets.audit_referenced(audio_documents,stage))
    unreferenced_dependencies=set(requirements)-{'warp','moreslugcats','watcher'}-pearl_dependencies-extra_dependencies-palette_dependencies
    if region_context:unreferenced_dependencies-=set(region_context.dependencies)
    if unreferenced_dependencies:reject('导出包包含未被已选内容引用的地图依赖 '+', '.join(sorted(unreferenced_dependencies)))
    for f in stage.rglob('*'):
        if f.is_symlink():reject('独立包不能包含符号链接',f)
        if not f.is_file():continue
        rel=f.relative_to(stage).as_posix()
        if rel not in allowed and rel not in palettes:reject('独立包包含非运行文件',rel)
        if f.suffix=='.json':inspect(read(rel),rel)
        elif f.suffix=='.txt':inspect(f.read_text('utf-8'),rel)
