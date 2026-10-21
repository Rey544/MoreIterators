"""Broadcast authoring and active-world room placement; no campaign conditions."""
from pathlib import Path
import copy, json, math, os, re, time, uuid, xml.etree.ElementTree as ET
import storage
from pearls import atomic

SCHEMA='moreiterators.broadcast.v1'
_rooms=None
_until=0
def root():return storage.DATA/'broadcasts'
def listing():return [json.loads(f.read_text('utf-8')) for f in sorted(root().glob('*/broadcast.json'))]
def valid_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,31}',value):raise ValueError('广播 ID 使用大写字母、数字与下划线，长度 2—32')
    return value
def default():
    used={p['id'] for p in listing()};i=1
    while f'B{i:02}' in used:i+=1
    return dict(schema=SCHEMA,id=f'B{i:02}',uid=uuid.uuid4().hex,name=f'B{i:02}',revision=0,region='',room='',x=.5,y=.5,style=default_style(),useCharacterColors=False,speakers=[],pages=[dict(lines=[line()])])
def default_style():return dict(font='normal',size=1,speed=1,hold=2.5)

def line():return dict(text='',color='#ffffff',**default_style())

def validate_style(style):
    if not isinstance(style,dict) or style.get('font') not in ('normal','display'):raise ValueError('字体应为原版普通或标题字体')
    for key,lo,hi in [('size',.5,2),('speed',.25,4),('hold',.1,60)]:
        v=style.get(key)
        if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError(key+' 超出范围')

def speaker_key(value):
    return value.strip().strip('【】[]').strip().lower()

def speaker_prefix(text):
    match=re.match(r'^[ \t]*(?:【([^】\r\n]+)】|\[([^\]\r\n]+)\]|([^:：\r\n]+))[ \t]*[:：]',text)
    return speaker_key(next((v for v in match.groups() if v is not None),'')) if match else ''

def validate_speakers(speakers):
    if not isinstance(speakers,list) or len(speakers)>200:raise ValueError('角色绑定最多 200 个')
    used=set()
    for item in speakers:
        if not isinstance(item,dict) or not isinstance(item.get('name'),str) or not 1<=len(item['name'].strip())<=100:raise ValueError('角色名称需要 1—100 字')
        if not isinstance(item.get('color'),str) or not re.fullmatch('#[0-9a-fA-F]{6}',item['color']):raise ValueError('请输入 RGB 颜色')
        aliases=item.get('aliases',[])
        if not isinstance(aliases,list) or len(aliases)>30 or any(not isinstance(v,str) or not 1<=len(v.strip())<=100 for v in aliases):raise ValueError('角色别名无效')
        local=set()
        for name in [item['name'],*aliases]:
            key=speaker_key(name)
            if not key or ':' in key or '：' in key or '\n' in key or '\r' in key:raise ValueError('角色名称与别名不能包含冒号或换行')
            if key in used:raise ValueError('角色名称或别名重复，请合并绑定')
            local.add(key)
        used.update(local)

def line_color(project,text):
    if not project.get('useCharacterColors'):return '#ffffff'
    key=speaker_prefix(text)
    if key:
        for speaker in project.get('speakers',[]):
            if any(speaker_key(name)==key for name in [speaker['name'],*speaker.get('aliases',[])]):return speaker['color']
    return '#ffffff'

def compile_project(project):
    """Flatten broadcast controls for both current and legacy playback DLLs.

    Author files keep legacy fields so merely opening a document is lossless.
    Files with no unified style keep their original per-line playback unchanged.
    """
    out=copy.deepcopy(project)
    if 'style' in out:
        validate_style(out['style']);validate_speakers(out.get('speakers',[]))
        if type(out.get('useCharacterColors')) is not bool:raise ValueError('彩色广播开关无效')
        for page in out['pages']:
            for item in page['lines']:
                item.update(out['style']);item['color']=line_color(out,item['text'])
        for key in ('style','speakers','useCharacterColors'):out.pop(key,None)
    return out

def import_bundle(value):
    """Read a MI document or RainocTool 1.1.2 JSON without writing any files."""
    if isinstance(value,dict) and value.get('schema')==SCHEMA:return dict(projects=[validate(value)])
    if not isinstance(value,dict) or value.get('format')!='eoe-lore-project' or value.get('version')!=1:raise ValueError('请选择 MI 广播或 RainocTool 导出的 JSON')
    source=value.get('project')
    if not isinstance(source,dict) or not isinstance(source.get('documents'),list):raise ValueError('RainocTool 文档列表无效')
    documents=source['documents']
    if len(documents)>10000:raise ValueError('RainocTool 文档数量超出范围')
    def kind(item):return item.get('kind') or {'广播':'broadcast','角色':'character','蛞蝓猫':'slugcat'}.get(item.get('category'))
    speakers=[];used=set()
    for item in documents:
        if not isinstance(item,dict) or kind(item) not in ('character','slugcat'):continue
        details=item.get('details') or {}
        if not isinstance(details,dict):raise ValueError('RainocTool 角色格式无效')
        name=item.get('title','');aliases=details.get('aliases',[]);tags=details.get('characterTags',[])
        if not isinstance(aliases,list) or not isinstance(tags,list):raise ValueError('RainocTool 角色格式无效')
        aliases=aliases+tags
        if not isinstance(name,str) or not name.strip():continue
        # RainocTool resolves duplicate aliases by the first character. Keep that rule.
        candidates=[]
        for token in [name,*aliases]:
            if isinstance(token,str) and speaker_key(token) and speaker_key(token) not in used:
                candidates.append(token);used.add(speaker_key(token))
        if not candidates:continue
        color=details.get('characterColor') or '#ffffff'
        speakers.append(dict(name=candidates[0],aliases=candidates[1:],color=color))
    used_ids={p['id'] for p in listing()};projects=[]
    for item in documents:
        if not isinstance(item,dict) or kind(item)!='broadcast':continue
        details=item.get('details') or {}
        if not isinstance(details,dict):raise ValueError('RainocTool 广播格式无效')
        settings=details.get('broadcast') or {}
        if not isinstance(settings,dict):raise ValueError('RainocTool 广播格式无效')
        content=item.get('content','')
        if not isinstance(content,str):raise ValueError('RainocTool 广播正文无效')
        lines=[dict(line(),text=text) for text in content.replace('\r\n','\n').replace('\r','\n').split('\n')]
        if len(lines)>10000:raise ValueError('广播需要 1—100 页')
        number=1
        while f'B{number:02}' in used_ids:number+=1
        identifier=f'B{number:02}';used_ids.add(identifier)
        project=dict(schema=SCHEMA,id=identifier,uid=uuid.uuid4().hex,name=item.get('title') or identifier,revision=0,region='',room='',x=.5,y=.5,style=default_style(),useCharacterColors=settings.get('useCharacterColors',False),speakers=copy.deepcopy(speakers),pages=[dict(lines=lines[i:i+100]) for i in range(0,len(lines),100)])
        projects.append(validate(project))
    if not projects:raise ValueError('此 JSON 中没有广播')
    return dict(projects=projects)

def room_index(force=False):
    """Only enabled worlds; merged files take precedence exactly as the game does."""
    global _rooms,_until
    if _rooms is not None and time.monotonic()<_until and not force:return _rooms
    assets=storage.GAME/'RainWorld_Data/StreamingAssets'
    options=Path.home()/'AppData/LocalLow/Videocult/Rain World/options'
    enabled=set();order={}
    if options.exists():
        doc=ET.fromstring(options.read_bytes().rstrip(b'\0'));parts=list(doc)
        keys=next(x for x in parts if x.tag.rsplit('}',1)[-1]=='Keys')
        values=next(x for x in parts if x.tag.rsplit('}',1)[-1]=='Values')
        raw=dict(zip((x.text for x in keys),(x.text for x in values)))['options']
        opts=dict(x.split('<optB>',1) for x in raw.split('<optA>') if '<optB>' in x)
        enabled=set(opts.get('EnabledMods','').split('<optC>'))
        order={p.split('<optD>')[0]:int(p.split('<optD>')[1]) for p in opts.get('ModLoadOrder','').split('<optC>') if '<optD>' in p}
    bases=[assets]
    mods=list((assets/'mods').glob('*/modinfo.json'))
    workshop=storage.GAME.parents[1]/'workshop/content/312520'
    mods+=list(workshop.glob('*/modinfo.json'))
    active=[]
    for f in mods:
        try:
            mid=json.loads(f.read_text('utf-8-sig')).get('id')
            if mid in enabled:active.append((order.get(mid,0),f.parent))
        except (ValueError,OSError):pass
    bases.extend(p for _,p in sorted(active))
    bases.append(assets/'mergedmods')
    worlds={}
    for base in bases:
        for f in (base/'world').glob('*/world_*.txt'):worlds[f.parent.name.upper()]=f
    result={}
    for region,file in worlds.items():
        inside=False
        for raw in file.read_text('utf-8-sig',errors='replace').splitlines():
            s=raw.strip()
            if s=='ROOMS':inside=True;continue
            if s=='END ROOMS':break
            if not inside or not s or s.startswith('//') or ':' not in s:continue
            name=s.split(':',1)[0].strip()
            # Character filters belong to the world list, not to the room ID.
            name=re.sub(r'^\([^)]*\)','',name).strip()
            if not re.fullmatch(r'[A-Za-z0-9_]+',name):continue
            geometry=None
            for base in reversed(bases):
                candidate=base/'world'/(region.lower()+'-rooms')/(name+'.txt')
                if candidate.exists():geometry=candidate;break
            if geometry:result[name.upper()]=dict(region=region,room=name.upper(),path=str(geometry))
    _rooms=result;_until=time.monotonic()+15
    return result

def rooms():return [dict(region=v['region'],room=v['room']) for k,v in sorted(room_index().items())]
def geometry(name):
    item=room_index().get(name)
    if not item:raise ValueError('房间不在已启用地区中；新地区需要先应用并重启游戏')
    rows=Path(item['path']).read_text('utf-8-sig').splitlines();w,h=map(int,rows[1].split('|')[0].split('*'))
    cells=rows[11].split('|');solids=[];shortcuts=[]
    for i,cell in enumerate(cells[:w*h]):
        values=cell.split(',');x=i//h;y=h-1-i%h
        if values[0]=='1':solids.append([x,y])
        if values[0]=='4':shortcuts.append([x,y])
    cameras=[]
    for c in rows[3].split('|'):
        if c.strip():
            x,y=(float(v) for v in c.split(','));cameras.append([x,h*20-800-y])
    return dict(region=item['region'],room=name,width=w,height=h,solids=solids,shortcuts=shortcuts,cameras=cameras)

def validate(p,require_room=False):
    p=copy.deepcopy(p)
    if not isinstance(p,dict):raise ValueError('广播格式无效')
    if p.get('schema')!=SCHEMA:raise ValueError('广播格式无效')
    valid_id(p.get('id'))
    if not isinstance(p.get('uid'),str) or not re.fullmatch('[a-f0-9]{32}',p['uid']):raise ValueError('广播内部 ID 无效')
    if not isinstance(p.get('name'),str) or not 1<=len(p['name'].strip())<=100:raise ValueError('请输入 1—100 字的名称')
    for key,lo,hi in [('x',0,1),('y',0,1)]:
        v=p.get(key)
        if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('相对位置应为 0—1')
    if require_room or p.get('room'):
        r=room_index().get(p.get('room'))
        if not r or r['region']!=p.get('region'):raise ValueError('地区与房间不匹配，请从列表选择已启用房间')
    pages=p.get('pages')
    if not isinstance(pages,list) or not 1<=len(pages)<=100:raise ValueError('广播需要 1—100 页')
    nonempty=False
    for page in pages:
        if not isinstance(page,dict):raise ValueError('每页需要 1—100 句')
        lines=page.get('lines')
        if not isinstance(lines,list) or not 1<=len(lines)<=100:raise ValueError('每页需要 1—100 句')
        for l in lines:
            if not isinstance(l,dict):raise ValueError('广播格式无效')
            if not isinstance(l.get('text'),str) or len(l['text'])>4000:raise ValueError('单句最多 4000 字')
            nonempty |= bool(l['text'].strip())
            if not isinstance(l.get('color'),str) or not re.fullmatch('#[0-9a-fA-F]{6}',l['color']):raise ValueError('请输入 RGB 颜色')
            if l.get('font') not in ('normal','display'):raise ValueError('字体应为原版普通或标题字体')
            for key,lo,hi in [('size',.5,2),('speed',.25,4),('hold',.1,60)]:
                v=l.get(key)
                if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError(key+' 超出范围')
    if 'style' in p:
        validate_style(p['style'])
        if type(p.get('useCharacterColors')) is not bool:raise ValueError('彩色广播开关无效')
        validate_speakers(p.get('speakers'))
    if require_room and not nonempty:raise ValueError('应用前至少填写一句广播')
    return p
def save(p):
    p=validate(p);f=root()/p['id']/'broadcast.json'
    for other in listing():
        if other['uid']==p['uid'] and other['id']!=p['id']:raise ValueError('已保存广播的 ID 固定，名称可以修改')
    if f.exists():
        old=json.loads(f.read_text('utf-8'))
        if old['uid']!=p['uid']:raise ValueError('该广播 ID 已被占用')
        if old['revision']!=p.get('revision'):raise ValueError('广播已在其他页面修改，请重新打开')
    p['revision']=p.get('revision',0)+1;atomic(f,p);return p
def apply(p):
    p=validate(p,True);p=save(p);out=compile_project(p);out['runtimeId']='MoreIterators_Broadcast_'+p['uid']
    atomic(storage.RUNTIME/'broadcasts'/(p['id']+'.json'),out);return p
