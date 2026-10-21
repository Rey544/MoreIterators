"""Build a read-only content mod from explicitly selected saved projects.

The creator and playback share rendering sources; playback-only menu/paths replace
the editor control surfaces. No game assemblies, local configuration or authoring
sources are shipped. Builds are made in temporary directories and audited first.
"""
from pathlib import Path
import base64,copy,datetime,hashlib,io,json,os,re,shutil,subprocess,tempfile,zipfile,math
from PIL import Image
import storage,dialogue,pearls,pearl_projects,broadcasts,native_projects,playback_adapters,room_editor,room_bindings,projections,overseers,audio_assets

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
    'readers':[{'projectId':str,'oracleId':str,'name':str,'requireMark':bool,'repeatEnabled':bool,
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
        if f.exists():return json.loads(f.read_text('utf-8'))
        p=storage.load_project(pid)
        return dict(id='author.'+pid.replace('oc-','iterator-'),name=p['name'],authors='',description='',version='0.1.0',cover='',projects=[pid],dialogue=False,pearls=False,broadcasts=False,workPearls=False)
    f=storage.DATA/'export-settings.json'
    value=json.loads(f.read_text('utf-8')) if f.exists() else dict(id='author.iterator',name='',authors='',description='',version='0.1.0',cover='',dialogue=False,pearls=False,broadcasts=False,workPearls=False)
    value['projects']=[pid] if pid else []
    return value

def compiler_sources(destination,meta,projects=()):
    src=storage.WORKSPACE/'src';templates=storage.WORKSPACE/'templates/standalone'
    suffix=hashlib.sha256(meta['id'].encode()).hexdigest()[:12]
    namespace='IteratorContent_'+suffix
    encounter=(src/'CreatorRuntime.cs').read_text('utf-8').split('public class CreatorEncounter:',1)[1]
    encounter='public class CreatorEncounter:'+encounter.rsplit('}',1)[0]
    sources=[]
    for file in sorted(src.glob('*.cs')):
        if file.name in ('StudioLauncher.cs','RoomCatalogSnapshot.cs'):continue
        replacement=templates/file.name
        text=(replacement if replacement.exists() else file).read_text('utf-8')
        text=text.replace('__ENCOUNTER__',encounter).replace('__MOD_ID__',meta['id'])
        text=text.replace('namespace MoreIterators','namespace '+namespace)
        # Atlas and extensible-enum identifiers must also be unique per content mod.
        text=text.replace('"MoreIterators_','"IC_'+suffix+'_').replace('"moreiterators_','"ic_'+suffix+'_')
        if file.name=='MoreIteratorsPlugin.cs':
            text,count=re.subn(r'\[BepInPlugin\("moreiterators\.core",\s*"[^"\\]*",\s*BuildVersion\.Plugin\)\]',lambda match:'[BepInPlugin('+json.dumps(meta['id'])+', '+json.dumps(meta['name'],ensure_ascii=False)+', '+json.dumps(meta['version'])+')]',text)
            if count!=1:raise ValueError('Playback plugin identity replacement failed')
            if any(p.get('legacyOracle') for p in projects):text=text.replace('Instance=this; RuntimePaths.Initialize();','Instance=this; RuntimePaths.Initialize(); IteratorIntegrations.Register(new PlaybackAppearanceIntegration());')
        if file.name=='MoreIteratorsPlugin.cs':
            text=text.replace('orig(cam,extension==null?pal:extension.BasePalette(cam,pal),ref texture);','orig(cam,extension==null?(target!=null&&IteratorCatalog.IsAI(target.abstractRoom.name)&&IteratorDesign.ForRoom(target).roomTemplate=="ir"?13:pal):extension.BasePalette(cam,pal),ref texture);')
        if file.name=='CreatorLaunch.cs':
            text=text.replace('请在编辑器重新应用项目。','请重新安装此内容模组。').replace('请重新应用项目后进入。','请重新安装此内容模组。').replace('请重新应用项目。','请重新安装此内容模组。').replace('请重新应用项目后重启游戏。','请重新安装此内容模组并重启游戏。')
        target=destination/file.name;target.write_text(text,'utf-8');sources.append(target)
    sources+=playback_adapters.export_sources(destination,projects,namespace)
    return sources,suffix

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
    resources=['/resource:'+str(path)+',mi.ui.'+path.stem+'.json' for path in sorted((storage.WORKSPACE/'localization/game').glob('*.json'))]
    if (storage.WORKSPACE/'src/UiText.cs').exists() and any(not (storage.WORKSPACE/'localization/game'/(language+'.json')).is_file() for language in ('en','zh-CN')):
        raise ValueError('Missing embedded game UI translations')
    result=subprocess.run([str(csc),'/nologo','/target:library','/optimize+','/define:PLAYBACK','/out:'+str(out),*['/r:'+str(r) for r in refs],*resources,*[str(s) for s in sources]],capture_output=True,timeout=120)
    if result.returncode:raise ValueError('独立运行版编译失败：'+result.stdout.decode('utf-8',errors='replace')[-6000:])
    return suffix

def room_source(p,name,kind,server):
    if kind not in ('ai','entry'):raise ValueError('房间类型无效')
    current=p.get('roomBinding')
    if current and name!=current[kind]:raise ValueError('只能导出此项目当前绑定的房间：'+current[kind])
    if kind=='entry' and p.get('roomBinding',{}).get('entryMode')=='existing':return room_bindings.resolve_room_source(name)
    if native_projects.binding(p['projectId']):return server.ASSETS/('mods/moreslugcats/world/'+name.split('_')[0].lower()+'-rooms')/name.lower()
    room_editor.ensure_synced(p['projectId'],name)
    cached=room_editor.cached_source(p['projectId'],name)
    if cached:return cached
    root=storage.target_mod(p['projectId'])/'world'
    source=root/(name.split('_')[0].lower()+'-rooms')/name
    if source.with_suffix('.txt').exists():return source
    if current or storage.binding(p['projectId']):raise ValueError(p['name']+' 当前绑定的房间素材缺失：'+name+'；请同步当前房间后重新导出，不会回退到旧房间或默认模板。')
    return server.ASSETS/'world/ss-rooms/ss_ai' if kind=='ai' else server.entry_room_template()

def room_connections(p,ai,entry,server):
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
    return {int(value) for value in re.findall(r'(?m)^(?:Palette|FadePalette):\s*(\d+)\b',text)}

def _palette_file(root,index):
    root=Path(root).resolve();candidate=root/'palettes'/('palette'+str(index)+'.png')
    resolved=candidate.resolve()
    if not resolved.is_relative_to(root):raise ValueError('调色板素材路径越界：palette'+str(index))
    return resolved if resolved.is_file() else None

def room_palette_source(project,source,index):
    """Resolve the selected room's owning asset root before base-game palettes.

    External geometry is already restricted to game/workshop roots by room_source.
    Authored renders/templates use this project's target mod. Never guess a
    palette from an unrelated installed mod or copy its directory wholesale.
    """
    source=Path(source).resolve()
    base=(storage.GAME/'RainWorld_Data/StreamingAssets').resolve()
    target=storage.target_mod(project['projectId']).resolve()
    roots={Path(root).resolve() for root in room_bindings._asset_roots()};roots.add(target)
    matches=[root for root in roots if source.is_relative_to(root)]
    owner=max(matches,key=lambda root:len(root.parts)) if matches else target
    asset=_palette_file(owner,index)
    if asset is None:asset=_palette_file(base,index)
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
        if source.is_relative_to(assets/'mods'/mod/'world'):return official_requirement(mod)[0]
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
        else:
            spawn.pop('projectId',None)
            requirement=pearl_room_requirement(room)
            if requirement:requirements[requirement[0]]=requirement[1]
        result.append(spawn)
    return result,requirements

def selected_pearl_content(request,selected_projects):
    if 'pearlCollectionIds' in request or isinstance(request.get('pearlCollectionId'),(list,dict)):
        raise ValueError('一次只能选择一套珍珠项目，或不导出珍珠。')
    if request.get('pearlCollectionId') is not None and not isinstance(request['pearlCollectionId'],str):raise ValueError('请选择有效的珍珠项目')
    if not request.get('pearls',False):return '',[]
    catalog=pearl_projects.catalog();collection=request.get('pearlCollectionId') or catalog['activeId']
    if not isinstance(collection,str):raise ValueError('请选择有效的珍珠项目')
    if collection not in {item['id'] for item in catalog['projects']}:raise ValueError('请选择有效的珍珠项目')
    selected=set(selected_projects)
    candidates=pearls.listing(collection);selected_rooms=set()
    if any(p.get('spawnRooms') for p in candidates):
        for pid in selected:
            binding=room_bindings.binding(storage.load_project(pid));selected_rooms.update((binding['ai'],binding['entry']))
    items=[p for p in candidates if any(r['projectId'] in selected for r in p['readers']) or selected.intersection(p['spawnProjects']) or selected_rooms.intersection(p.get('spawnRooms',[]))]
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

def build(request,server,save_preferences=True):
    meta=metadata(request);ids=request.get('projects',[])
    if not isinstance(ids,list) or not ids or len(ids)>100 or any(not isinstance(pid,str) for pid in ids) or len(set(ids))!=len(ids):raise ValueError('请选择 1–100 个不重复的迭代器项目。')
    ids=[storage.valid_id(pid) for pid in ids]
    components={k:request.get(k,False) for k in ('dialogue','pearls','broadcasts','workPearls')}
    components['projections']=request.get('projections',True)
    if any(type(v) is not bool for v in components.values()):raise ValueError('导出选项无效')
    pearl_collection,pearl_items=selected_pearl_content(request,ids)
    pearl_uids={p['uid'] for p in pearl_items}
    projection_items=[p for p in projections.listing() if p.get('projectId') in ids and components['projections']
        and (p.get('trigger',{}).get('kind') not in ('dialogue','pearl') or components['dialogue' if p['trigger']['kind']=='dialogue' else 'pearls'])
        and (p.get('trigger',{}).get('kind')!='pearl' or p['trigger'].get('pearlUid') in pearl_uids)]
    # Persist old anchors before capturing the selected runtime dialogue/pearl data.
    source_sets={pid:projections.sources(pid,server.roomnames,pearl_collection or None)['sources'] for pid in {p['projectId'] for p in projection_items}}
    projects=[server.validate(copy.deepcopy(storage.load_project(storage.valid_id(pid)))) for pid in ids]
    cover=cover_bytes(meta['cover'])
    room_names=export_room_names(projects,meta['id'])
    regions=sorted({names[0].split('_')[0] for names in room_names.values()})
    registry=[];mapping={};room_map={};connections={region:[] for region in regions};design_schema=runtime_design_schema()
    with tempfile.TemporaryDirectory(prefix='mi-content-') as temp:
        temporary=Path(temp);stage=temporary/meta['id'];stage.mkdir();sources=temporary/'source';sources.mkdir()
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
            record=dict(projectId=pid,name=p['name'],ai=new_ai,entry=new_entry,oracleId=oid,design='designs/'+oid+'.json',ownerMod=meta['id'],exitNode=exits[ai].index(entry),entryNode=exits[entry].index(ai))
            if native:record['timeline']=native.get('timeline','')
            registry.append(record);mapping[pid]=record;room_map.update({ai:new_ai,entry:new_entry})
            for old,new,other,new_other in [(ai,new_ai,entry,new_entry),(entry,new_entry,ai,new_ai)]:connections[region].append(new+' : '+', '.join(new_other if target==other else 'DISCONNECTED' for target in exits[old]))
            rooms=stage/('world/'+region.lower()+'-rooms')
            for old,new,kind in [(ai,new_ai,'ai'),(entry,new_entry,'entry')]:
                source=room_source(p,old,kind,server)
                server.copy_room(source,rooms,new)
                settings=rooms/(new+'_settings.txt')
                if kind=='entry':server.zero_gravity(settings)
                copy_room_palettes(p,source,settings,stage)
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
            world=stage/('world/'+region.lower());world.mkdir(parents=True)
            rows=['ROOMS']+connections[region]
            (world/('world_'+region.lower()+'.txt')).write_text('\n'.join(rows+['END ROOMS','','CREATURES','END CREATURES'])+'\n','utf-8')
            authored=next((p for p in projects if p.get('roomBinding',{}).get('region')==region and room_names[p['projectId']][0]==p['roomBinding']['ai']),None)
            defaults={'properties.txt':'Palette: 26\noverseersSpawnChance: 0\noverseersMin: 0\noverseersMax: 0\n','displayname.txt':(region if authored else meta['name'])+'\n'}
            for filename,text in defaults.items():
                if authored:
                    owner=storage.target_mod(authored['projectId']).resolve();source=owner/'world'/region.lower()/filename
                    if not source.resolve().is_relative_to(owner):raise ValueError('区域素材路径越界：'+region+'/'+filename)
                    if source.is_file():text=source.read_text('utf-8-sig')
                (world/filename).write_text(text,'utf-8')
            if authored:copy_room_palettes(authored,owner/'world'/region.lower(),world/'properties.txt',stage)
        registration=stage/'modify/world/regions.txt';registration.parent.mkdir(parents=True);registration.write_text(''.join('[ADD]'+region+'\n' for region in regions),'utf-8')
        pearl_requirements={}
        if components['pearls']:
            for p in pearl_items:
                readers=[r for r in p['readers'] if r['projectId'] in mapping];spawns=[pid for pid in p['spawnProjects'] if pid in mapping]
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
        dump(stage/'modinfo.json',info)
        if cover:(stage/'thumbnail.png').write_bytes(cover)
        manifest=dict(schema='moreiterators.playback-export.v1',independentMod=True,projects=[dict(projectId=p['projectId'],name=p['name']) for p in projects],components=components,region=regions[0],regions=regions,runtimeVersion=json.loads((storage.WORKSPACE/'version.json').read_text('utf-8'))['version'])
        if pearl_collection:manifest['pearlCollectionId']=pearl_collection
        dump(stage/'content-manifest.json',manifest)
        (stage/'README.txt').write_text('把这个文件夹放进 RainWorld_Data/StreamingAssets/mods，然后在拓展菜单里启用就行。\n\n这个包做了 MoreIterators 的适配（register），不过现在是被单独导出的模组，所以没有 MoreIterators 的时候它也能正常独立运行，不需要额外装工具包。\n\n进游戏后点主菜单右下角的按钮，可以选择预设。进入演算室之后按 F8 可以打开控制面板。\n\n关于迭代器的台词：默认是有交流印记的，能看到对方说话；如果没有印记，只有动画。\n','utf-8')
        audio_documents=[json.loads(file.read_text('utf-8')) for directory in (stage/'designs',stage/'moreiterators/pearls') for file in directory.glob('*.json')]
        audio_assets.copy_referenced(audio_documents,stage)
        audit(stage,ids)
        storage.EXPORTS.mkdir(parents=True,exist_ok=True)
        name=meta['id'].replace('.','-')+'-'+meta['version'].replace('.','-')+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S%f')+'.zip'
        with zipfile.ZipFile(storage.EXPORTS/name,'w',zipfile.ZIP_DEFLATED) as z:
            for f in sorted(stage.rglob('*')):
                if f.is_file():z.write(f,meta['id']+'/'+f.relative_to(stage).as_posix())
        if save_preferences:
            settings_pid=request.get('settingsProject','')
            target=storage.project_file(storage.valid_id(settings_pid)).parent/'export-settings.json' if settings_pid in ids else storage.DATA/'export-settings.json'
            dump(target,{**meta,**components,'projects':ids,'pearlCollectionId':pearl_collection})
        return dict(ok=True,url='/exports/'+name,manifest=manifest)

def audit(stage,ids):
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
    if {room.split('_')[0] for room in rooms}!=set(regions):reject('导出区域与实际房间不一致')
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
            for field,item in value.items():
                if field in ('runtimeDirectory','editorDirectory','previewToken','legacySource'):reject('独立包包含本地开发字段',file)
                if field=='projectId' and item not in selected:reject('独立包引用了未选择的项目',file)
                if field=='oracleId' and item not in oracles:reject('独立包引用了未选择的迭代器',file)
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

    allowed={'modinfo.json','content-manifest.json','README.txt','thumbnail.png','moreiterators/registry.json','modify/world/regions.txt'}|expected_designs
    for region in regions:allowed.update(('world/'+region.lower()+'/properties.txt','world/'+region.lower()+'/displayname.txt','world/'+region.lower()+'/world_'+region.lower()+'.txt'))
    suffix=hashlib.sha256(info['id'].encode()).hexdigest()[:12]
    allowed.add('plugins/IteratorContent_'+suffix+'.dll')
    required=allowed-{'thumbnail.png'}
    palettes=set();cameras=set()
    for room in rooms:
        prefix='world/'+room.split('_')[0].lower()+'-rooms/'+room
        allowed.update((prefix+'.txt',prefix+'_settings.txt'))
        required.update((prefix+'.txt',prefix+'_settings.txt'))
        terrain=stage/(prefix+'.txt');settings=stage/(prefix+'_settings.txt')
        if not terrain.is_file() or not settings.is_file():reject('缺少必需房间文件',room)
        rows=terrain.read_text('utf-8-sig').splitlines()
        if len(rows)<4 or rows[0]!=room:reject('房间地形名称或相机数据无效',room)
        positions=[x for x in rows[3].split('|') if x.strip()]
        if not positions or any(not re.fullmatch(r'-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?',x.strip()) for x in positions):reject('房间相机数据无效',room)
        for index in range(1,len(positions)+1):cameras.add(prefix+'_'+str(index)+'.png')
        for value in room_palette_ids(settings.read_text('utf-8-sig')):palettes.add('palettes/palette'+str(value)+'.png')
    for region in regions:
        properties=stage/('world/'+region.lower()+'/properties.txt')
        if properties.is_file():palettes.update('palettes/palette'+str(value)+'.png' for value in room_palette_ids(properties.read_text('utf-8-sig')))
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
    for region in regions:
        world=stage/('world/'+region.lower()+'/world_'+region.lower()+'.txt');region_rooms=set()
        for row in world.read_text('utf-8-sig').splitlines():
            parts=row.split(' : ')
            if len(parts)>1:
                if parts[0] in connections:reject('世界文件的房间编号重复',parts[0])
                region_rooms.add(parts[0]);connections[parts[0]]=[x.strip() for x in parts[1].split(',')]
        if region_rooms!={room for room in rooms if room.startswith(region+'_')}:reject('世界文件的区域房间集合不一致',region)
    if set(connections)!=rooms:reject('世界文件的房间集合不一致')
    for record in registry:
        ai,entry=record['ai'],record['entry'];exit_node=record.get('exitNode')
        if entry not in connections[ai] or ai not in connections[entry] or any(x not in (ai,entry,'DISCONNECTED') for room in (ai,entry) for x in connections[room]):reject('房间连接不属于选定房间对')
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
                    if not p or reader.get('oracleId')!=p['oracleId'] or reader.get('name')!=p['name']:reject('珍珠读取者不属于选定项目',rel)
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
                        if room in rooms:reject('项目内珍珠生成位置缺少项目编号',rel)
                        dependency=pearl_room_requirement(room)
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
    unreferenced_dependencies=set(requirements)-{'warp','moreslugcats','watcher'}-pearl_dependencies
    if unreferenced_dependencies:reject('导出包包含未被已选内容引用的地图依赖 '+', '.join(sorted(unreferenced_dependencies)))
    for f in stage.rglob('*'):
        if f.is_symlink():reject('独立包不能包含符号链接',f)
        if not f.is_file():continue
        rel=f.relative_to(stage).as_posix()
        if rel not in allowed and rel not in palettes:reject('独立包包含非运行文件',rel)
        if f.suffix=='.json':inspect(read(rel),rel)
        elif f.suffix=='.txt':inspect(f.read_text('utf-8'),rel)
