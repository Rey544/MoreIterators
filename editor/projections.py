"""Project-owned projection groups, stable speech anchors and bounded PNG data."""
import base64,copy,datetime,io,json,math,re,uuid,warnings
from pathlib import Path
from PIL import Image,ImageEnhance,ImageChops
import storage,dialogue,pearls

SCHEMA='moreiterators.projection.v1'
MAX_IMAGE_BYTES=4*1024*1024
MAX_TOTAL_BYTES=8*1024*1024
MAX_TOTAL_PIXELS=8*1024*1024
CONTEXTS=('first','repeat','loop','pickup','leaving','returning',
          *('pearlReading.'+key for key in dialogue.PEARL_POOLS),
          *('observation.'+key for key in ('items','weapons','pearls','mixed','creatures','corpses','food',
                                         'repeatItems','repeatWeapons','repeatPearls','repeatMixed','repeatCreatures','repeatCorpses','repeatFood')),
          'affinity.refusal',
          *('affinity.'+weapon+'.'+tier for weapon in ('attackRock','attackSpear') for tier in dialogue.AFFINITY_TIERS))
PEARL_CONTEXTS=('pearl.read','pearl.repeat',*(f'pearl.affinity.{tier}.{kind}' for tier in dialogue.AFFINITY_TIERS for kind in ('read','repeat')))

def reader_bodies(reader):
    yield 'pearl',reader
    for tier,body in reader.get('affinity',{}).items():
        if tier in dialogue.AFFINITY_TIERS:yield 'pearl.affinity.'+tier,body

def root():return storage.DATA/'projections'
def path(uid):
    if not isinstance(uid,str) or not re.fullmatch('[a-f0-9]{32}',uid):raise ValueError('投影内部 ID 无效')
    return root()/uid/'projection.json'
def listing():
    return [json.loads(file.read_text('utf-8')) for file in sorted(root().glob('*/projection.json'))]
def applied_revisions(groups,roomnames):
    """Runtime publication status is separate from editable group documents."""
    result={}
    for group in groups:
        uid=group.get('uid');path(uid)
        file=storage.RUNTIME/'projections'/(uid+'.json')
        if not file.is_file():continue
        try:
            item=json.loads(file.read_text('utf-8'));project=storage.load_project(group['projectId'])
            owner=(storage.link(group['projectId']) or {}).get('id','moreiterators.local')
            if item.get('schema')==SCHEMA and item.get('uid')==uid and item.get('projectId')==group['projectId'] and item.get('oracleId')==roomnames(project)[2] and item.get('ownerMod')==owner and type(item.get('revision')) is int and item.get('projectMask',mask_default())==project_settings(group['projectId'])['mask']:
                result[uid]=item['revision']
        except (OSError,ValueError,KeyError,TypeError):continue
    return result

def default(pid):
    storage.load_project(storage.valid_id(pid))
    return dict(schema=SCHEMA,uid=uuid.uuid4().hex,name='新的投影动画',projectId=pid,revision=0,enabled=True,
        trigger=dict(kind='work',source='',pearlUid='',startLineId='',endLineId='',beforeSeconds=0,afterSeconds=0),loop=True,confineToRoom=True,images=[],tracks=[])

def mask_default():
    return dict(enabled=False,x=0,y=0,width=1,height=1)


def validate_mask(value):
    if not isinstance(value,dict) or type(value.get('enabled')) is not bool:
        raise ValueError('投影矩形蒙版格式无效')
    out={key:value.get(key) for key in ('enabled','x','y','width','height')}
    for key in ('x','y','width','height'):
        number(out[key],.001 if key in ('width','height') else 0,1,'蒙版 '+key)
    if out['x']+out['width']>1.000001 or out['y']+out['height']>1.000001:
        raise ValueError('投影矩形蒙版不能超出房间范围')
    return out


def settings_path(pid):
    return root()/'project-settings'/(storage.valid_id(pid)+'.json')


def project_settings(pid):
    storage.load_project(storage.valid_id(pid))
    file=settings_path(pid)
    if not file.exists():
        return dict(schema='moreiterators.projection-settings.v1',projectId=pid,revision=0,mask=mask_default())
    out=json.loads(file.read_text('utf-8'))
    if out.get('projectId')!=pid or out.get('schema')!='moreiterators.projection-settings.v1':
        raise ValueError('投影项目设置无效')
    if type(out.get('revision')) is not int or out['revision']<0:raise ValueError('投影项目设置版本无效')
    out['mask']=validate_mask(out.get('mask'))
    return out


def save_project_settings(value,apply=False):
    if type(apply) is not bool:raise ValueError('投影应用开关无效')
    if not isinstance(value,dict) or value.get('schema')!='moreiterators.projection-settings.v1':
        raise ValueError('投影项目设置无效')
    pid=storage.valid_id(value.get('projectId'));current=project_settings(pid)
    if type(value.get('revision')) is not int or value['revision']!=current['revision']:
        raise ValueError('投影项目设置已在另一页面修改；请重新打开')
    mask=validate_mask(value.get('mask'))
    out=dict(schema=current['schema'],projectId=pid,revision=current['revision']+1,mask=mask)
    pearls.atomic(settings_path(pid),out)
    if apply:
        # Update published runtime documents only; other saved drafts stay unpublished.
        for file in (storage.RUNTIME/'projections').glob('*.json'):
            item=json.loads(file.read_text('utf-8'))
            if item.get('projectId')==pid and item.get('schema')==SCHEMA:
                item['projectMask']=copy.deepcopy(mask);pearls.atomic(file,item)
    return out


def persist_pearl_lines(p,roomnames=None):
    """Migrate only speech IDs; do not rewrite legacy pearl behavior/settings."""
    out=copy.deepcopy(p);seen=set()
    for reader in out.get('readers',[]):
        arrays=[]
        for _,body in reader_bodies(reader):
            arrays.append(body.get('read',[]))
            for key in ('repeat','leaving','returning','many'):
                arrays.extend(group.get('lines',[]) for group in body.get(key,[]))
        for lines in arrays:
            for line in lines:dialogue.ensure_line_id(line,seen)
    if out!=p:
        out['revision']=out.get('revision',0)+1
        pearls.atomic(pearls.path(out['id'],out.get('collectionId','legacy')),out)
    runtime=pearls.runtime()/(out['id']+'.json')
    if runtime.is_file() and roomnames:
        # Only IDs change here; publishing unrelated draft edits requires Apply.
        compiled=json.loads(runtime.read_text('utf-8'));before=copy.deepcopy(compiled)
        if compiled.get('uid')!=out['uid']:return out
        for reader in compiled.get('readers',[]):
            authored=next((r for r in out.get('readers',[]) if r.get('projectId')==reader.get('projectId')),None)
            if not authored:continue
            def sync(old,new):
                if len(old)!=len(new):return
                if all(a.get('text')==b.get('text') for a,b in zip(old,new)):
                    for a,b in zip(old,new):
                        if not a.get('lineId'):a['lineId']=b['lineId']
            authored_bodies=dict(reader_bodies(authored))
            for context,body in reader_bodies(reader):
                draft=authored_bodies.get(context)
                if draft is None:continue
                sync(body.get('read',[]),draft.get('read',[]))
                for key in ('repeat','leaving','returning','many'):
                    for a,b in zip(body.get(key,[]),draft.get(key,[])):sync(a.get('lines',[]),b.get('lines',[]))
        if compiled!=before:pearls.migrate_runtime_lines(runtime,compiled)
    return out

def sources(pid,roomnames=None,collection_id=None):
    p=dialogue.persisted_profile(pid,roomnames)
    items=[persist_pearl_lines(item,roomnames) for item in pearls.listing(collection_id) if any(r.get('projectId')==pid for r in item.get('readers',[]))]
    return dict(projectId=pid,sources=source_entries(pid,p['dialogue'],items))

def spoken_line(line):
    return isinstance(line.get('text'),str) and bool(line['text'].strip())


def source_entries(pid,profile,items):
    result=[]
    labels={'first':'首次对话','repeat':'再次对话','loop':'后续循环对话','pickup':'拿起工作珍珠','leaving':'离开','returning':'返回',
        'pearlReading.greeting':'每循环初见','pearlReading.quickReturn':'快速返回','pearlReading.revisit':'重新拜访',
        'pearlReading.greetingItems':'携带物品','pearlReading.greetingWeapons':'携带武器','pearlReading.greetingPearls':'携带珍珠','pearlReading.greetingMixed':'携带珍珠与武器',
        'pearlReading.extractedPreRead':'取出胃中珍珠·前言','pearlReading.firstPreRead':'每循环首次读珍珠·前言',
        'pearlReading.greetingCreatures':'携带活体生物','pearlReading.greetingCorpses':'携带生物尸体','pearlReading.greetingFood':'携带食物',
        'pearlReading.repeat':'读珍珠·重复','pearlReading.many':'读珍珠·多颗','pearlReading.preRead':'读珍珠·前言','pearlReading.misc':'无色珍珠',
        'pearlReading.leaving':'读珍珠·离开','pearlReading.returning':'读珍珠·返回',
        'observation.items':'观察物品','observation.weapons':'观察武器','observation.pearls':'观察珍珠','observation.mixed':'观察珍珠与武器','affinity.refusal':'低好感拒绝读取'}
    for key,title in (('items','物品'),('weapons','武器'),('pearls','珍珠'),('mixed','珍珠与武器'),('creatures','活体生物'),('corpses','生物尸体'),('food','食物')):
        labels['observation.'+key]='观察'+title
        labels['observation.repeat'+key[0].upper()+key[1:]]='再次观察'+title
    for weapon,name in (('attackRock','石头攻击'),('attackSpear','矛攻击')):
        for tier,title in (('notSpeaking','拒绝交谈'),('dislikes','反感'),('neutral','中立'),('likes','好感')):
            labels['affinity.'+weapon+'.'+tier]=name+' · '+title
    def add(kind,source,name,lines,pearl_uid='',pool_name='',pearl_name=''):
        result.append(dict(id=source+':'+pearl_uid+':'+(lines[0]['lineId'] if lines else str(len(result))),
            kind=kind,source=source,name=name,label=name,pearlUid=pearl_uid,poolName=pool_name,pearlName=pearl_name,
            lines=[dict(line,id=line['lineId']) for line in lines if spoken_line(line)],
            unspokenLineIds=[line['lineId'] for line in lines if not spoken_line(line)]))
    for context in CONTEXTS:
        value=profile
        for key in context.split('.'):
            value=value.get(key,[]) if isinstance(value,dict) else []
        if context in ('first','repeat','loop'):add('dialogue',context,labels[context],value)
        else:
            for index,group in enumerate(value):add('dialogue',context,labels[context]+' · '+(group.get('name') or str(index+1)),group.get('lines',[]),pool_name=group.get('name',''))
    for index,chapter in enumerate(profile.get('meetings',[]),3):
        add('dialogue','meetings.'+chapter['id'],'第'+str(index)+'次见面 · '+(chapter.get('name') or str(index)),chapter.get('lines',[]))
        result[-1].update(meetingNumber=index,meetingName=chapter.get('name',''))
    for item in items:
        for reader in item.get('readers',[]):
            if reader.get('projectId')!=pid:continue
            titles={'notSpeaking':'拒绝交谈','dislikes':'反感','neutral':'中立','likes':'好感'}
            for context,body in reader_bodies(reader):
                title=item['name']+(' · '+titles[context.rsplit('.',1)[1]] if context!='pearl' else '')
                add('pearl',context+'.read',title+' · 首次读取',body.get('read',[]),item['uid'],pearl_name=item['name'])
                if body.get('repeatEnabled',False):
                    for index,group in enumerate(body.get('repeat',[])):add('pearl',context+'.repeat',title+' · 重复 · '+(group.get('name') or str(index+1)),group.get('lines',[]),item['uid'],group.get('name',''),item['name'])
    seen=set()
    for entry in result:
        for line_id in [line['lineId'] for line in entry['lines']]+entry['unspokenLineIds']:
            if line_id in seen:raise ValueError('当前迭代器的不同台词来源使用了重复 ID；请重新创建复制的台词')
            seen.add(line_id)
    return result

def image_bytes(item):
    value=item.get('png')
    if not isinstance(value,str) or not value.startswith('data:image/png;base64,') or len(value)>MAX_IMAGE_BYTES*4//3+64:
        raise ValueError('投影图片必须是 PNG，单张不超过 4 MiB')
    try:
        raw=base64.b64decode(value.split(',',1)[1],validate=True)
        if len(raw)>MAX_IMAGE_BYTES:raise ValueError('图片超过 4 MiB')
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as probe:
                if probe.format!='PNG' or not 1<=probe.width<=1024 or not 1<=probe.height<=1024:raise ValueError('PNG 宽高必须为 1—1024 像素')
                if getattr(probe,'n_frames',1)!=1:raise ValueError('请使用静态透明 PNG；动画请添加关键帧')
                probe.verify()
            with Image.open(io.BytesIO(raw)) as decoded:
                decoded.load();rgba=decoded.convert('RGBA');width,height=rgba.size
                if rgba.getchannel('A').getextrema()[0]==255:raise ValueError('PNG 需要透明区域，请先移除背景')
        if type(item.get('width')) is not int or type(item.get('height')) is not int or (item['width'],item['height'])!=(width,height):raise ValueError('PNG 标注尺寸与实际图片不一致')
        return raw,width*height
    except (OSError,SyntaxError,Image.DecompressionBombError,Image.DecompressionBombWarning) as error:raise ValueError('PNG 损坏或无法完整解码') from error
    except (TypeError,base64.binascii.Error) as error:raise ValueError('PNG 编码无效') from error

def number(value,lo,hi,label):
    if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError(label+' 超出范围（'+str(lo)+'—'+str(hi)+'）')

def identifier(value,label):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',value):raise ValueError(label+' ID 无效')

def validate(value,resolve_sources=True,roomnames=None):
    if not isinstance(value,dict) or value.get('schema')!=SCHEMA:raise ValueError('投影动画格式无效')
    p=copy.deepcopy(value);path(p.get('uid'));storage.valid_id(p.get('projectId'))
    if resolve_sources:storage.load_project(p['projectId'])
    if not isinstance(p.get('name'),str) or not 1<=len(p['name'].strip())<=100:raise ValueError('动画名称应为 1—100 字')
    if type(p.get('revision')) is not int or p['revision']<0:raise ValueError('投影版本无效')
    p.setdefault('confineToRoom',False)
    if 'projectMask' in p:p['projectMask']=validate_mask(p['projectMask'])
    if any(type(p.get(key)) is not bool for key in ('enabled','loop','confineToRoom')):raise ValueError('投影开关无效')
    trigger=p.get('trigger')
    if not isinstance(trigger,dict) or trigger.get('kind') not in ('dialogue','pearl','work','entity','item'):raise ValueError('投影触发类型无效')
    for key in ('source','pearlUid','startLineId','endLineId'):
        if not isinstance(trigger.get(key),str) or len(trigger[key])>100:raise ValueError('投影触发字段无效：'+key)
    for key in ('beforeSeconds','afterSeconds'):
        trigger.setdefault(key,0)
        number(trigger[key],0,120,'投影提前或延后时长')
    kind=trigger['kind']
    if kind in ('entity','item') and p['enabled']:raise ValueError('实体和物品绑定尚未实现；请保留为关闭状态')
    dialogue_source=trigger['source'] in CONTEXTS or bool(re.fullmatch(r'meetings\.[a-f0-9]{32}',trigger['source']))
    if kind=='dialogue' and (not dialogue_source or trigger['pearlUid']):raise ValueError('请选择当前迭代器的对话情境')
    if kind=='pearl' and (trigger['source'] not in PEARL_CONTEXTS or not re.fullmatch('[a-f0-9]{32}',trigger['pearlUid'])):raise ValueError('请选择当前迭代器读取的珍珠')
    if kind=='work' and any(trigger[key] for key in ('source','pearlUid','startLineId','endLineId')):raise ValueError('工作状态动画不使用台词或珍珠绑定')
    if kind in ('dialogue','pearl'):
        if not trigger['startLineId'] or not trigger['endLineId']:raise ValueError('请选择投影开始和结束的台词')
        if resolve_sources:resolve_lines(p,sources(p['projectId'],roomnames)['sources'])
    images=p.get('images');tracks=p.get('tracks')
    if not isinstance(images,list) or len(images)>16:raise ValueError('一个动画最多 16 张图片')
    if not isinstance(tracks,list) or len(tracks)>16:raise ValueError('一个动画最多 16 条轨道')
    byte_count=pixels=0;ids=set()
    for item in images:
        if not isinstance(item,dict):raise ValueError('投影图片格式无效')
        identifier(item.get('id'),'图片')
        if item['id'] in ids:raise ValueError('图片 ID 重复')
        ids.add(item['id'])
        if not isinstance(item.get('name'),str) or len(item['name'])>100:raise ValueError('图片名称无效')
        raw,count=image_bytes(item);byte_count+=len(raw);pixels+=count
        if byte_count>MAX_TOTAL_BYTES or pixels>MAX_TOTAL_PIXELS:raise ValueError('动画图片总量超过 8 MiB 或 800 万像素')
    track_ids=set();frame_count=0
    for track in tracks:
        if not isinstance(track,dict):raise ValueError('轨道格式无效')
        identifier(track.get('id'),'轨道')
        if track['id'] in track_ids:raise ValueError('轨道 ID 重复')
        track_ids.add(track['id'])
        if not isinstance(track.get('name'),str) or len(track['name'])>100:raise ValueError('轨道名称无效')
        if track.get('kind') not in ('image','circle','line','glyph','grid','cursor','scanline','matrix'):raise ValueError('未知投影元素')
        if track.get('kind')=='image' and track.get('imageId') not in ids:raise ValueError('图片轨道引用的 PNG 不存在')
        if track.get('kind')!='image' and track.get('imageId',''):raise ValueError('几何轨道不能引用 PNG')
        track.setdefault('imageId','');track.setdefault('style','native');track.setdefault('glyphIndex',0)
        track.setdefault('maskMode','inherit');track.setdefault('mask',mask_default())
        if track['maskMode'] not in ('inherit','none','custom'):raise ValueError('投影轨道蒙版模式无效')
        track['mask']=validate_mask(track['mask'])
        if type(track['glyphIndex']) is not int or not 0<=track['glyphIndex']<=49:raise ValueError('符文编号应为 0—49')
        if track['style'] not in ('native','plain'):raise ValueError('投影风格请选择 native 或 plain；Moon 效果仅供原版参考')
        if not isinstance(track.get('color'),str) or not re.fullmatch('#[0-9a-fA-F]{6}',track['color']):raise ValueError('投影颜色应为 RGB 十六进制')
        number(track.get('delay'),0,120,'轨道延迟')
        frames=track.get('frames')
        if not isinstance(frames,list) or not 1<=len(frames)<=120:raise ValueError('每条轨道需要 1—120 帧')
        frame_count+=len(frames)
        if frame_count>512:raise ValueError('动画最多 512 帧')
        total=track['delay']
        for frame in frames:
            if not isinstance(frame,dict):raise ValueError('关键帧格式无效')
            for key,lo,hi in [('duration',.02,120),('x',0,1),('y',0,1),('scale',.01,10),('rotation',-3600,3600),('opacity',0,1),('brightness',0,2),('flicker',0,1)]:number(frame.get(key),lo,hi,'关键帧 '+key)
            if frame.get('ease') not in ('linear','smooth','step'):raise ValueError('关键帧缓动无效')
            total+=frame['duration']
        if total>600:raise ValueError('单条轨道总时长不得超过 600 秒')
    return p

def resolve_lines(p,entries):
    trigger=p['trigger']
    if trigger['kind'] not in ('dialogue','pearl'):return []
    for source in entries:
        if source['kind']!=trigger['kind'] or source['source']!=trigger['source'] or source['pearlUid']!=trigger['pearlUid']:continue
        unspoken=set(source.get('unspokenLineIds',[]))
        unspoken.update(line['lineId'] for line in source['lines'] if not spoken_line(line))
        if trigger['startLineId'] in unspoken or trigger['endLineId'] in unspoken:
            raise ValueError('投影起始和结束台词不能留空；请填写台词或重新选择范围')
        ids=[line['lineId'] for line in source['lines'] if spoken_line(line)]
        if trigger['startLineId'] in ids and trigger['endLineId'] in ids:
            first,last=ids.index(trigger['startLineId']),ids.index(trigger['endLineId'])
            if first>last:raise ValueError('投影结束台词必须在开始台词之后；请重新选择范围')
            return ids[first:last+1]
    raise ValueError('绑定台词已被删除、移动到其他情境，或珍珠不再由此迭代器读取；请重新选择范围')

def save(value,roomnames=None):
    p=validate(value,roomnames=roomnames);file=path(p['uid'])
    if file.exists():
        old=json.loads(file.read_text('utf-8'))
        if p['revision']!=old.get('revision'):raise ValueError('投影已在另一页面修改；请重新打开')
        if p['projectId']!=old['projectId']:raise ValueError('已保存投影的所属迭代器不可更改；请另建动画')
    elif p['revision']!=0:raise ValueError('投影不存在或已移除；请重新打开')
    p['revision']+=1;p['updatedAt']=datetime.datetime.now().isoformat(timespec='seconds');pearls.atomic(file,p)
    return p

def compile_project(value,roomnames,owner_mod=None,entries=None):
    p=validate(value,resolve_sources=False);project=storage.load_project(p['projectId'])
    p['projectMask']=copy.deepcopy(project_settings(p['projectId'])['mask'])
    p['oracleId']=roomnames(project)[2];p['ownerMod']=owner_mod or (storage.link(p['projectId']) or {}).get('id','moreiterators.local')
    p['trigger']['lineIds']=resolve_lines(p,entries if entries is not None else sources(p['projectId'],roomnames)['sources'])
    p.pop('updatedAt',None)
    return p

def apply(value,roomnames):
    p=validate(value,roomnames=roomnames)
    compiled=compile_project(p,roomnames)
    p=save(p,roomnames);compiled['revision']=p['revision']
    pearls.atomic(storage.RUNTIME/'projections'/(p['uid']+'.json'),compiled)
    return p


def background(pid,server):
    project=storage.load_project(storage.valid_id(pid));name=server.roomnames(project)[0]
    source=server.standalone.room_source(project,name,'ai',server)
    rows=Path(str(source)+'.txt').read_text('utf-8-sig').splitlines()
    size=re.match(r'(\d+)\*(\d+)',rows[1]) if len(rows)>3 else None
    if not size:raise ValueError('演算室房间尺寸无效')
    width,height=int(size[1])*20,int(size[2])*20
    if not 20<=width<=8192 or not 20<=height<=8192 or width*height>32*1024*1024:raise ValueError('演算室过大，无法生成编辑预览')
    cameras=[tuple(float(v) for v in entry.split(',')) for entry in rows[3].split('|') if entry.strip()]
    palette=room_palette(project,source);canvas=Image.new('RGBA',(width,height),(15,19,23,255))
    depth=Image.new('RGBA',(width,height),(0,0,0,0))
    # Room.LoadFromDataString reads the light vector from the third row. Keep
    # the same game axes here; projection-depth.js converts texture Y itself.
    try:
        light=[float(value) for value in rows[2].split('|')[0].split('*')]
        if len(light)!=2 or not all(math.isfinite(value) for value in light):raise ValueError()
    except ValueError:light=[0,0]
    for index,(x,y) in enumerate(cameras,1):
        file=Path(str(source)+'_'+str(index)+'.png')
        if not file.is_file():raise ValueError('演算室相机图缺失：'+file.name)
        with Image.open(file) as image:
            image.load();art=decode_room_image(image,palette,project.get('design',{}))
            # Room files store camera offsets from the room's top-left.
            canvas.alpha_composite(art,(round(x),round(y)))
            depth.paste(projection_depth_map(image),(round(x),round(y)))
    data=io.BytesIO();canvas.save(data,'PNG')
    packed=io.BytesIO();depth.save(packed,'PNG')
    return dict(url='data:image/png;base64,'+base64.b64encode(data.getvalue()).decode(),width=width,height=height,room=name,clipAreas=chamber_mask(rows),
        depthUrl='data:image/png;base64,'+base64.b64encode(packed.getvalue()).decode(),lightAngle=light,
        mode='palette-depth-preview',note='房间深度预览；动态光照和生物遮挡以游戏为准')


def projection_depth_map(image):
    """Static branch of the installed Projection.shader: R=depth, G=visible.

    Native sprites/creatures use _GrabTexture and can change this mask at run
    time. They are intentionally absent from the authoring-room preview.
    """
    red,green,blue,alpha=image.convert('RGBA').split()
    depth=red.point([max(0,(value-1)%30) if value else 0 for value in range(256)])
    visible=red.point([255 if value>90 and (value-1)%30>=1 else 0 for value in range(256)])
    # White is the level's empty/sky sentinel, not depth 14 material.
    nonwhite=ImageChops.lighter(ImageChops.lighter(ImageChops.invert(red),ImageChops.invert(green)),ImageChops.invert(blue)).point(lambda value:255 if value else 0)
    visible=ImageChops.multiply(visible,nonwhite)
    return Image.merge('RGBA',(depth,visible,Image.new('L',image.size),alpha))


def chamber_mask(rows):
    """Disjoint rectangles of the main walkable chamber, in top-left pixels."""
    from collections import deque
    width,height=map(int,rows[1].split('|')[0].split('*'))
    if len(rows)<12:raise ValueError('演算室缺少地形数据，无法确定投影边界')
    cells=rows[11].split('|')
    if len(cells)<width*height:raise ValueError('演算室地形数据不完整')
    opened={(x,y) for x in range(width) for y in range(height) if cells[x*height+y].split(',')[0] not in ('1','2')}
    largest=set()
    while opened:
        start=min(opened);opened.remove(start);component={start};queue=deque([start])
        while queue:
            x,y=queue.popleft()
            for point in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if point in opened:opened.remove(point);component.add(point);queue.append(point)
        if len(component)>len(largest):largest=component
    result=[];previous={}
    for y in range(height):
        current={};x=0
        while x<width:
            if (x,y) not in largest:x+=1;continue
            start=x
            while x+1<width and (x+1,y) in largest:x+=1
            key=(start,x)
            if key in previous:index=previous[key];result[index][3]+=20
            else:index=len(result);result.append([start*20,y*20,(x-start+1)*20,20])
            current[key]=index;x+=1
        previous=current
    if len(result)>512:raise ValueError('演算室投影边界超过 512 个区域')
    return result


def room_palette(project,source):
    settings=Path(str(source)+'_settings.txt')
    text=settings.read_text('utf-8-sig') if settings.is_file() else ''
    match=re.search(r'(?m)^Palette:\s*(\d+)',text)
    index=int(match[1]) if match else int(project.get('design',{}).get('roomPalette',26))
    assets=storage.GAME/'RainWorld_Data/StreamingAssets'
    candidates=[storage.target_mod(project['projectId'])/'palettes'/('palette'+str(index)+'.png'),
        assets/'mods/moreslugcats/palettes'/('palette'+str(index)+'.png'),assets/'palettes'/('palette'+str(index)+'.png')]
    for file in candidates:
        if file.is_file():
            with Image.open(file) as image:
                image.load()
                if image.width<32 or image.height<8:raise ValueError('房间调色板尺寸无效')
                palette=image.convert('RGB').crop((0,0,32,8))
                # Mirror CreatorRuntime.Palette: keep sky/fog/effect columns,
                # tint the room material colors for this iterator's work theme.
                theme=project.get('design',{}).get('roomWorkColor','#476d67')
                tint=tuple(int(theme[i:i+2],16)/255 for i in (1,3,5))
                for y in range(2,8):
                    for x in range(30):
                        r,g,b=palette.getpixel((x,y));v=.299*r+.587*g+.114*b
                        palette.putpixel((x,y),tuple(round(min(255,max(0,v*(.45+.55*c*1.6)))) for c in tint))
                return palette
    raise ValueError('房间调色板不存在：palette'+str(index)+'.png')

def decode_room_image(image,palette,design):
    """Static LevelColor shader palette lookup; lighting/noise stays in-game."""
    image=image.convert('RGBA');colors=palette.load();cache={}
    fog_pixel=colors[9,0];fog_amount=1+fog_pixel[2]/255 if fog_pixel[0]==fog_pixel[1]==0 and fog_pixel[2]>0 else 1-fog_pixel[0]/255
    def mix(a,b,t):return tuple(a[i]+(b[i]-a[i])*t for i in range(3))
    def pixel(value):
        if value in cache:return cache[value]
        red,green,blue,alpha=value
        if (red,green,blue)==(255,255,255):out=colors[0,0]
        else:
            floor=green>=16
            if floor:green-=16
            prop=green>=8
            if prop:green-=8
            shadow=red<=90
            if red>90:red-=90
            band=max(0,min(2,(red-1)//30));depth=max(0,(red-1)%30) if red else 0
            out=colors[0 if floor else depth,(7 if shadow else 4)-band]
            if prop:
                decal=image.getpixel((max(0,min(image.width-1,255-blue)),0))[:3]
                if band==2:decal=mix(decal,(255,255,255),.1)
                decal=mix(decal,colors[1,0],depth/60)
                amount=.9+(.7-.9)*max(0,min(1,(depth-3.5)*.3))
                out=mix(mix(out,decal,.7),tuple(out[i]*decal[i]*1.5/255 for i in range(3)),amount)
            elif green in (1,2):
                y=2+(green-1)*2;column=31 if shadow else 30;effect=mix(colors[column,y],colors[column,y+1],depth/30)
                out=mix(out,effect,blue/255)
            fog=min(1,max(0,depth*(.5 if floor and depth<10 else 1)*fog_amount/30))
            out=mix(out,colors[1,0],fog)
        result=tuple(max(0,min(255,round(c))) for c in out)+(alpha,);cache[value]=result;return result
    decoded=Image.new('RGBA',image.size);decoded.putdata([pixel(value) for value in image.getdata()])
    for field,enhancer in [('roomSaturation',ImageEnhance.Color),('roomContrast',ImageEnhance.Contrast),('roomBrightness',ImageEnhance.Brightness)]:
        amount=design.get(field,1)
        if amount!=1:decoded=enhancer(decoded).enhance(amount)
    return decoded


REFERENCE_PATHS={'aiimg1': 'illustrations/aiimg1.png', 'aiimg2': 'illustrations/aiimg2.png', 'aiimg3': 'illustrations/aiimg3.png', 'aiimg3a': 'illustrations/aiimg3a.png', 'aiimg3b': 'illustrations/aiimg3b.png', 'aiimg1_dm': 'mods/moreslugcats/illustrations/aiimg1_dm.png', 'aiimg1_rivend': 'mods/moreslugcats/illustrations/aiimg1_rivend.png', 'aiimg1_rivend2': 'mods/moreslugcats/illustrations/aiimg1_rivend2.png', 'aiimg2_dm': 'mods/moreslugcats/illustrations/aiimg2_dm.png', 'aiimg2_rivend': 'mods/moreslugcats/illustrations/aiimg2_rivend.png', 'aiimg2_rivend2': 'mods/moreslugcats/illustrations/aiimg2_rivend2.png', 'aiimg3b_dm': 'mods/moreslugcats/illustrations/aiimg3b_dm.png', 'aiimg3c_dm': 'mods/moreslugcats/illustrations/aiimg3c_dm.png', 'aiimg4': 'mods/moreslugcats/illustrations/aiimg4.png', 'aiimg5a': 'mods/moreslugcats/illustrations/aiimg5a.png', 'aiimg5b': 'mods/moreslugcats/illustrations/aiimg5b.png', 'projection1': 'projections/projection1.png', 'rnd_proj': 'projections/rnd_proj.png', 'str_proj': 'projections/str_proj.png', 'ads_proj': 'mods/moreslugcats/projections/ads_proj.png', 'moonai_proj-saint': 'mods/moreslugcats/projections/moonai_proj-saint.png', 'moonai_proj': 'mods/moreslugcats/projections/moonai_proj.png', 'str_proj_remix': 'mods/rwremix/projections/str_proj.png'}

def reference():
    value=json.loads((Path(__file__).parent/'projection-reference.json').read_text('utf-8'))
    assets=storage.GAME/'RainWorld_Data/StreamingAssets'
    for item in value['assets']:item['available']=(assets/REFERENCE_PATHS[item['id']]).is_file()
    return value

def reference_image(key):
    if key not in REFERENCE_PATHS:raise ValueError('未知原版投影参考')
    file=storage.GAME/'RainWorld_Data/StreamingAssets'/REFERENCE_PATHS[key]
    if not file.is_file():raise ValueError('当前游戏未安装此原版投影素材')
    return file.read_bytes()
