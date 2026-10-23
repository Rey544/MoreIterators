"""OC Creator: loopback-only project store, TEST room compiler, partial exports."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import json,os,re,datetime,threading,shutil,hashlib,base64,io,zipfile,urllib.parse
from PIL import Image,ImageColor
ROOT=Path(__file__).resolve().parent
import sys
sys.path.insert(0,str(ROOT))
from necklaces import validate_necklaces
from pearl_accessories import validate_pearl_accessories
import wardrobe
import puppet_arms
import head_segments
import eyes
import color_gradients
import project_templates
import audio_assets
import voice_settings
import paint_layers
import compatibility as legacy
import storage
import native_projects
import dialogue
import pearls
import pearl_projects
import projections
import broadcasts
import voice_samples
import room_editor
import room_bindings
import room_migration
import project_purge
import room_cleanup
import waiting_room
import overseers
import standalone
import diagnostics
import project_lifecycle
import project_associations
import local_content
import studio_drafts
import action_presets
PROJECTS=storage.PROJECTS; EXPORTS=storage.EXPORTS
GAME=storage.GAME
ASSETS=GAME/'RainWorld_Data/StreamingAssets'; MOD=storage.DATA/'local-mod'; DESIGNS=storage.RUNTIME
PORT=storage.STUDIO_PORT; LOCK=threading.RLock()
LIVE_CACHE={}

def live_snapshot(path):
    # The game replaces frame files and writes status during the web poll.
    # Keep the last complete status through that brief handoff.
    try:
        value=json.loads(path.read_text('utf-8'))
        if isinstance(value,dict):LIVE_CACHE[path]=value
    except (OSError,ValueError):pass
    return dict(LIVE_CACHE.get(path,{}))

def file_age(path):
    try:return datetime.datetime.now().timestamp()-path.stat().st_mtime
    except OSError:return float('inf')
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with LOCK:
        tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,path)

def atomic_text(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    with LOCK:
        tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(text,encoding='utf-8');os.replace(tmp,path)
def default():
    return dict(schema='moreiterators.project.v1',projectId='oc-'+datetime.datetime.now().strftime('%y%m%d%H%M%S'),name='新的迭代器',design=dict(
      headColor='#a6aaa9',eyeColor='#fbf5df',clothTopColor='#813c46',clothMiddleColor='#b68b8e',clothBottomColor='#e0dfd8',clothGrain=.12,
      antennaColor='#7fad99',metalColor='#323e3d',armColor='#7c8b85',armShadowStrength=.35,sleeveMapping='front',armJointColor='#414b48',collarColor='#98464b',
      antennaTint=True,antennaInnerColor='#9cafaa',antennaOuterColor='#323e3d',
      necklaceCount=0,necklaces=[],earTint=False,earCustom=False,earInnerColor='#9cafaa',earOuterColor='#323e3d',roomBrightness=1,roomContrast=1,roomSaturation=1,
      scarfPanels=0,scarfLength=36,scarfWidth=36,scarfGap=.18,scarfLightness=.7,scarfFringe=False,scarfFringeLength=5,
      scarfShape=0,scarfTopWidth=10,
      scarfTopColor='#384845',scarfMiddleColor='#688479',scarfBottomColor='#b5c7bd',scarfGrain=.12,
      cableColorA='#414b48',cableColorB='#aab3ab',headCableRed='#ff0000',headCableBlue='#0000ff',earWidth=3,earHeight=7,earOffsetX=0,earOffsetY=0,
      antennaHeight=13,antennaWidth=1.1,antennaSpread=8.2,antennaOffsetY=0,eyeSpacing=3.2,eyeSize=1.35,faceScale=1,faceOffsetX=0,faceOffsetY=0,cheekScale=1,cheekOffsetX=0,cheekOffsetY=0,
      puppetScale=1,torsoLength=1,armLength=1,legLength=1,robeLength=29,robeHemWidth=1,sleeveWidth=4,sleeveOwn=False,collarWidth=1,collarHeight=3,collarNotch=0,
      neckLength=1,collarOffsetY=0,collarTopNotch=0,collarRoundness=.5,collarTaper=1,sleeveTopColor='#813c46',sleeveMiddleColor='#b68b8e',sleeveBottomColor='#e0dfd8',sleeveGrain=.12,
      hemProfile='1,1,1,1,1,1,1,1,1,1,1',haloColor='#83b39e',haloPreset='original',haloScale=1,haloOpacity=.5,haloSpeed=1,roomPalette=26,rearGlowColor='#98b4a5',rearGlowOpacity=.12,rearGlowRadius=250,rearGlowEnabled=True,
      pearlCount=32,pearlColor1='#000000',pearlColor2='#658c7b',pearlColor3='#a2bfb1',pearlColor4='#e5dcca',pearlGlyphColor='#acbcb2',pearlGlyphOpacity=.65,
      pearlGlyph1=0,pearlGlyph2=3,pearlGlyph3=6,pearlGlyph4=9,pearlClusterX=.25,pearlClusterY=.18,pearlCluster2X=.75,pearlCluster2Y=.18,pearlScatter=1,pearlFixedCount=8,
      roomWorkColor='#476d67',roomReceptionColor='#bd8152',roomTransition=3,firstDialogue='……你好。',repeatDialogue='又见面了。',unmarkedDialogue='……',pearlDialogue='……让我看看。',
      layers={k:True for k in ['head','body','neck','eyes','face','antenna','ears','robe','sleeves','hands','feet','collar','mechanicalArm','cables','halo']}),textures={},editor={},overseer=overseers.defaults(),overseerRevision=0)
LIMITS={'puppetScale':(.65,1.6),'torsoLength':(.7,1.4),'armLength':(.7,1.4),'legLength':(.7,1.4),'earWidth':(1,12),'earHeight':(2,18),'earOffsetX':(-4,6),'earOffsetY':(-8,8),'antennaHeight':(3,32),'antennaWidth':(.3,5),'antennaSpread':(5,14),'antennaOffsetY':(-8,8),'robeLength':(18,45),'robeHemWidth':(.45,2.2),'sleeveWidth':(2,8),'collarWidth':(.5,1.8),'collarHeight':(0,8),'collarNotch':(-4,4),'pearlCount':(0,80),'pearlScatter':(0,3),'pearlFixedCount':(0,40),'roomTransition':(.2,15),'haloOpacity':(0,1),'haloScale':(.3,2),'haloSpeed':(0,3)}
TEXTURES={'earL':(24,32),'earR':(24,32),'forehead':(32,32),'face':(32,32),'antennaL':(24,48),'antennaR':(24,48),'gown':(64,96),'sleeve':(32,64),'collar':(32,16),'scarf':(64,96)}
LIMITS.update(rearGlowOpacity=(0,1),rearGlowRadius=(20,600))
LIMITS.update(armShadowStrength=(0,1))
LIMITS.update(roomBrightness=(.25,2),roomContrast=(.25,2),roomSaturation=(0,2))
LIMITS.update(neckLength=(0,8),collarOffsetY=(-8,8),collarTopNotch=(0,8),collarRoundness=(0,1),collarTaper=(.5,1.5),sleeveGrain=(0,.4))
LIMITS.update(scarfPanels=(0,2),scarfLength=(8,55),scarfWidth=(8,48),scarfGap=(0,.7),scarfLightness=(0,1),scarfFringeLength=(0,12),scarfGrain=(0,.4))
LIMITS.update(scarfShape=(0,1),scarfTopWidth=(2,32))
LIMITS.update(head_segments.LIMITS)
TEXTURES.update(head_segments.TEXTURES)
def texture_size(p,key):
    return puppet_arms.SIZES.get(key,wardrobe.sizes(p['design']).get(key,TEXTURES.get(key)))

def fabric(key):return key.startswith('puppetSleeve') or key in ('gown','sleeve','scarf','collar') or wardrobe.is_material(key)

def validate(p):
    if not isinstance(p,dict) or p.get('schema') not in ('eoe.creator.v2','moreiterators.project.v1'):raise ValueError('请选择项目文件（v2）')
    if not re.fullmatch('[a-z][a-z0-9-]{0,47}',p.get('projectId','')):raise ValueError('项目编号格式错误')
    project_lifecycle.assert_active(p['projectId'])
    if not isinstance(p.get('name'),str) or not 1<=len(p['name'].strip())<=60:raise ValueError('名称长度应为 1—60 字')
    if 'roomBinding' in p:p['roomBinding']=room_bindings.normalize(p['roomBinding'])
    if 'overseer' in p:p['overseer']=overseers.normalize(p['overseer'])
    original=p.get('design',{});base=default()['design'];base.update(original);p['design']=base
    base['sleeveMapping']=original.get('sleeveMapping','strip')
    if base['sleeveMapping'] not in ('front','strip'):raise ValueError('袖子贴图映射无效')
    wardrobe.defaults(base)
    for key in ('legLength','thighLength','shinLength','legWidth','kneeSize','legElasticity'):
        right='right'+key[0].upper()+key[1:]
        if right not in original:base[right]=base[key]
    base['layers']={'body':True,'neck':base.get('layers',{}).get('head',True),**base.get('layers',{})}
    audio_assets.validate_design(base)
    voice_settings.validate_design(base)
    head_segments.validate(base)
    eyes.validate(base)
    color_gradients.validate(base)
    validate_necklaces(base)
    validate_pearl_accessories(base)
    wardrobe.validate(base)
    puppet_arms.validate(base)
    if 'antennaTint' not in original:base['antennaTint']=False
    if legacy.oracle(p):
        base['capeLength']=base.get('capeLength',31)
        if type(base['capeLength']) not in (int,float) or not 20<=base['capeLength']<=55:raise ValueError('cloak 长度应为 20—55')
    if type(base['scarfPanels']) is not int or base['scarfPanels'] not in (0,1,2):raise ValueError('围巾请选择关闭、单片或双片')
    if type(base['scarfShape']) is not int or base['scarfShape'] not in (0,1):raise ValueError('请选择末端展开或等宽长片')
    for k,v in base.items():
        if 'Color' in k or k in ['headCableRed','headCableBlue']: 
            if not isinstance(v,str) or not re.fullmatch('#[a-fA-F0-9]{6}',v):raise ValueError(k+' 颜色格式无效')
        if k in LIMITS:
            lo,hi=LIMITS[k]
            if type(v) not in (int,float) or not lo<=v<=hi:raise ValueError(k+' 超出支持范围')
        if k.endswith('Dialogue') and (not isinstance(v,str) or len(v)>10000):raise ValueError('对话过长')
    if set(base['layers'])-set(default()['design']['layers']):raise ValueError('图层不存在')
    for key,texture in p.get('textures',{}).items():
        if key not in dict(TEXTURES,**wardrobe.sizes(base),**puppet_arms.SIZES):raise ValueError('未知纹理 '+key)
        if 'editableBase' in texture and type(texture['editableBase']) is not bool:raise ValueError('底图编辑模式无效')
        paint_layers.validate(texture,key)
        layers=texture['layers']
        for layer in layers:
            png=layer.get('png','')
            if png:
                if not png.startswith('data:image/png;base64,') or len(png)>1500000:raise ValueError('纹理须为 PNG')
                im=Image.open(io.BytesIO(base64.b64decode(png.split(',',1)[1],validate=True)))
                if im.size!=texture_size(p,key):raise ValueError(key+' 纹理尺寸错误')
            if not 0<=float(layer.get('opacity',1))<=1:raise ValueError('透明度超出范围')
    if 'dialogue' in p:p['dialogue']=dialogue.validate(p['dialogue'])
    p['updatedAt']=datetime.datetime.now().isoformat(timespec='seconds');return p
def save(p,dialogue_edit=False):
    with LOCK:return _save(p,dialogue_edit)

def _save(p,dialogue_edit=False):
    p=validate(p);folder=storage.project_root(p['projectId'])/p['projectId'];old=folder/'project.json'
    if old.exists():
        previous=json.loads(old.read_text('utf-8'))
        # Room identity changes only through the previewed migration endpoint.
        if 'roomBinding' in previous:p['roomBinding']=previous['roomBinding']
        else:p.pop('roomBinding',None)
        if waiting_room.FIELD in previous:p[waiting_room.FIELD]=previous[waiting_room.FIELD]
        else:p.pop(waiting_room.FIELD,None)
        p['overseer']=overseers.normalize(previous.get('overseer'));p['overseerRevision']=previous.get('overseerRevision',0)
        if not dialogue_edit and 'dialogue' in previous:p['dialogue']=dialogue.validate(previous['dialogue']);p['dialogueRevision']=previous.get('dialogueRevision',0)+(p['dialogue']!=previous['dialogue'])
        stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');atomic(storage.history_directory(p['projectId'])/(stamp+'.json'),json.loads(old.read_text('utf-8')))
    elif p.get('roomBinding'):
        raise ValueError('新项目包含房间绑定，请使用导入项目来校验区域和房间；不会静默改回 TEST。')
    else:p.pop(waiting_room.FIELD,None)
    if 'dialogue' not in p:p['dialogue']=dialogue.profile(p)
    atomic(old,p);sync_project_name(p);return p

def import_project(raw):
    """Import room identity through the same checked transaction as the room studio.

    Project JSON contains appearance/settings, not Rained geometry. A new import
    uses its existing local rendered cache or the normal new-project template.
    Foreign entry connections still require an explicit room-studio preview.
    """
    with LOCK:
        project=validate(raw);pid=project['projectId'];file=storage.project_file(pid)
        if file.exists() or not project.get('roomBinding'):return _save(project)
        requested=project.pop('roomBinding')
        if storage.binding(pid) or requested['entryMode']!='copy':
            raise ValueError('导入不能自动改写原版、关联模组或现有房间连接；请在区域连接预览并应用。')
        # Check identifiers, collisions and every source before creating a project.
        room_bindings.plan(project,requested)
        if 'dialogue' not in project:project['dialogue']=dialogue.profile(project)
        transaction=room_migration.Files()
        try:
            transaction.json(file,project)
            planned=room_migration.preview(pid,requested)
            result=room_migration.apply(pid,requested,planned['token'],sys.modules[__name__])
            return result['project']
        except Exception:
            transaction.rollback();raise

def project_association(pid):
    pid=storage.valid_id(pid);owner=storage.link(pid);fixed=storage.binding(pid)
    project=storage.load_project(pid) if storage.project_file(pid).exists() else dict(projectId=pid)
    current=room_bindings.binding(project)
    return dict(linked=bool(fixed),owner=Path(owner['workspace']).name if owner else '原版 · 矛大师时间线' if fixed else '',
                region=current['region'],ai=current['ai'],entry=current['entry'])

def sync_project_name(p):
    """Renaming a saved project must not require reapplying its appearance/rooms."""
    with LOCK:
        registry=DESIGNS/'creator/registry.json'
        if not registry.exists():return
        items=json.loads(registry.read_text('utf-8'))
        changed=False
        for item in items:
            if item.get('projectId')==p['projectId'] and item.get('name')!=p['name']:
                item['name']=p['name'];changed=True
        if changed:atomic(registry,items)

def sync_saved_project_names():
    for file in storage.project_files():
        try:sync_project_name(json.loads(file.read_text('utf-8')))
        except (OSError,ValueError,KeyError):continue
def composite(texture,size):
    result=Image.new('RGBA',size)
    for layer in texture.get('layers',[]):
        if not layer.get('visible',True) or not layer.get('png'):continue
        im=Image.open(io.BytesIO(base64.b64decode(layer['png'].split(',',1)[1]))).convert('RGBA');alpha=im.getchannel('A').point(lambda x:round(x*layer.get('opacity',1)));im.putalpha(alpha);result=Image.alpha_composite(result,im)
    b=io.BytesIO();result.save(b,format='PNG');return b.getvalue()

def pngbytes(im):
    b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()

def antenna_layer(p,key,index):
    selected=paint_layers.select_surface(p.get('textures',{}).get(key,{}),index==1)
    im=Image.open(io.BytesIO(composite({'layers':selected},texture_size(p,key)))).convert('RGBA')
    return head_segments.recolor_layer(p['design'],key,index,im)

def procedural_cloth(p,key):
    """Opaque material under the editable layers. Erasing a pattern exposes this."""
    d=p['design'];w,h=texture_size(p,key);own=key=='sleeve' and d.get('sleeveOwn',False)
    prefix='scarf' if key=='scarf' else 'sleeve' if own else 'cloth'
    colors=[ImageColor.getrgb(d.get(prefix+k,d['cloth'+k])) for k in ('TopColor','MiddleColor','BottomColor')]
    config=wardrobe.material_config(p,key)
    if config:colors=[ImageColor.getrgb(c) for c in config[0]]
    grain=config[1] if config else d.get(prefix+'Grain',d['clothGrain']);im=Image.new('RGBA',(w,h));pixels=[]
    for y in range(h):
        t=y/(h-1);a,b,f=(colors[0],colors[1],t/.58) if t<.58 else (colors[1],colors[2],(t-.58)/.42)
        for x in range(w):
            noise=(((y*w+x)*4*16807%127)/127-.5)*grain*130
            if legacy.oracle(p) and not wardrobe.is_material(key):
                tt=t
                if key=='sleeve':tt*=.65
                if legacy.oracle(p)=='cf':a,b,f=colors[0],colors[2],tt*tt
                else:
                    aa=colors[0] if tt<.68 else colors[1];bb=colors[1] if tt<.68 else colors[2]
                    f=max(0,min(1,(tt-.42)/.26 if tt<.68 else (tt-.68)/.32));f=f*f*(3-2*f);a,b=aa,bb
            pixels.append(tuple(max(0,min(255,int(a[i]+(b[i]-a[i])*f+noise+.5))) for i in range(3))+(255,))
    im.putdata(pixels)
    return im

def cloth_base(p,key):
    tex=p.get('textures',{}).get(key,{})
    if tex.get('layers') and tex['layers'][0].get('visible',True) is False:return Image.new('RGBA',texture_size(p,key))
    painted=Image.open(io.BytesIO(composite({'layers':tex.get('layers',[])[:1]},texture_size(p,key)))).convert('RGBA')
    accessory=wardrobe.find(p['design'],key)
    if tex.get('editableBase',False) or accessory and accessory.get('type')=='rigid':return painted
    base_layers=[dict(layer,opacity=1) for layer in tex.get('layers',[])[:1]]
    painted=Image.open(io.BytesIO(composite({'layers':base_layers},texture_size(p,key)))).convert('RGBA')
    base=Image.new('RGBA',texture_size(p,key),p['design']['collarColor']) if key=='collar' else procedural_cloth(p,key)
    result=Image.alpha_composite(base,painted)
    opacity=tex['layers'][0].get('opacity',1) if tex.get('layers') else 1
    if opacity<1:result.putalpha(result.getchannel('A').point(lambda value:round(value*opacity)))
    return result

def pattern_texture(p,key):
    tex=p.get('textures',{}).get(key,{})
    return {'layers':tex.get('layers',[])[1:]} if fabric(key) else tex

def material(p,key):
    if key.startswith(('antenna','ear')):return pngbytes(Image.alpha_composite(antenna_layer(p,key,0),antenna_layer(p,key,1)))
    size=texture_size(p,key);overlay=Image.open(io.BytesIO(composite(pattern_texture(p,key),size))).convert('RGBA')
    base=cloth_base(p,key) if fabric(key) else Image.new('RGBA',size)
    return pngbytes(Image.alpha_composite(base,overlay))
def roomnames(p):
    binding=room_bindings.binding(p)
    return binding['ai'],binding['entry'],binding['oracleId']

def zero_gravity(file):
    text=file.read_text('utf-8-sig')
    effects=re.search(r'(?m)^Effects:(.*)$',text)
    entries=[] if not effects else [x.strip() for x in re.split(r',\s*(?=[A-Za-z][\w. ]*-)',effects[1].strip().rstrip(',')) if x.strip() and not x.strip().startswith(('ZeroG-','BrokenZeroG-'))]
    line='Effects: '+', '.join(entries+['ZeroG-1-0-0'])+', '
    text=re.sub(r'(?m)^Effects:.*$',line,text) if effects else text.rstrip()+'\n'+line+'\n'
    atomic_text(file,text)

def room_camera_count(text):
    lines=text.splitlines()
    if len(lines)<4:raise ValueError('房间文件缺少相机位置')
    cameras=[x.strip() for x in lines[3].split('|') if x.strip()]
    if not cameras:raise ValueError('房间没有相机画面')
    for camera in cameras:
        if not re.fullmatch(r'-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?',camera):raise ValueError('房间相机位置格式错误：'+camera)
    return len(cameras)

def copy_room(source,directory,name,palette=None,replace=False):
    """Copy a room's own geometry, camera art and settings; never share its exits."""
    text=Path(str(source)+'.txt').read_text('utf-8-sig')
    suffixes=['.txt','_settings.txt']+['_'+str(i)+'.png' for i in range(1,room_camera_count(text)+1)]
    # Validate the complete source before writing anything. Every camera needs its own image.
    for suffix in suffixes:
        if not Path(str(source)+suffix).is_file():raise ValueError('房间模板素材缺失：'+source.name+suffix)
    directory.mkdir(parents=True,exist_ok=True)
    for suffix in suffixes:
        dest=directory/(name+suffix)
        if dest.exists() and not replace:continue
        src=Path(str(source)+suffix)
        if suffix=='.txt':
            lines=src.read_text('utf-8-sig').splitlines();lines[0]=name;dest.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        elif suffix=='_settings.txt':
            text=src.read_text('utf-8-sig');text=re.sub(r'(?m)^Template:.*','Template: NONE',text)
            if palette is not None:text=re.sub(r'(?m)^Palette:.*','Palette: '+str(palette),text)
            dest.write_text(text,encoding='utf-8')
        else:shutil.copy2(src,dest)
def compile_design(p):
    wardrobe.defaults(p['design'])
    ai,entry,oid=roomnames(p);d=dict(p['design'],schema='moreiterators.oracle.v1',projectId=p['projectId'],name=p['name'],oracleId=oid,roomTemplate=p.get('roomTemplate','fp'),previewToken=datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'))
    fields={'forehead':'facePng','face':'cheekPng','gown':'gownPng','sleeve':'sleevePng','collar':'collarPng','scarf':'scarfPng'}
    for key,field in fields.items():
        d[field]=''
        if key in p.get('textures',{}):
            png=composite(pattern_texture(p,key),texture_size(p,key))
            if Image.open(io.BytesIO(png)).getchannel('A').getbbox():d[field]='data:image/png;base64,'+base64.b64encode(png).decode()
    for key,side in [('antennaL','Left'),('antennaR','Right'),('earL','Left'),('earR','Right')]:
        prefix=head_segments.prefix(key)
        for index,suffix in [(0,'InnerPng'),(1,'Png')]:
            im=antenna_layer(p,key,index);d[prefix+side+suffix]='data:image/png;base64,'+base64.b64encode(pngbytes(im)).decode() if im.getchannel('A').getbbox() else ''
    for key in ('gown','sleeve','scarf','collar'):
        d[key+'BasePng']='data:image/png;base64,'+base64.b64encode(pngbytes(cloth_base(p,key))).decode()
    for key in ('sleeveR','legThigh','legKnee','legShin','legThighR','legKneeR','legShinR'):
        d[key+'BasePng']='data:image/png;base64,'+base64.b64encode(pngbytes(cloth_base(p,key))).decode()
        d[key+'Png']='data:image/png;base64,'+base64.b64encode(composite(pattern_texture(p,key),texture_size(p,key))).decode()
    # Compile a copy: embedded runtime textures must never pollute editable source data.
    import copy
    for group in ('frontPanels','shawls','accessories'):
        d[group]=copy.deepcopy(d[group])
        for item in d[group]:
            key=item['id'];item['basePng']='data:image/png;base64,'+base64.b64encode(pngbytes(cloth_base(p,key))).decode()
            item['patternPng']='data:image/png;base64,'+base64.b64encode(composite(pattern_texture(p,key),texture_size(p,key))).decode()
    if d['frontSymmetry']:
        left=d['frontPanels'][0];right=d['frontPanels'][1]
        for k in ('width','length','topWidth','sag','roundness','elasticity','gravity','fringe','fringeLength','fringeColor','topColor','middleColor','bottomColor','grain','lockGown'):right[k]=left[k]
        for k in ('basePng','patternPng'):
            im=Image.open(io.BytesIO(base64.b64decode(left[k].split(',',1)[1]))).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            right[k]='data:image/png;base64,'+base64.b64encode(pngbytes(im)).decode()
    d['earCustom']=bool(p['design'].get('earCustom',False))
    d['dialogueJson']=json.dumps(dialogue.profile(p),ensure_ascii=False)
    d[overseers.RUNTIME_FIELD]=json.dumps(overseers.normalize(p.get('overseer')),ensure_ascii=False)
    head_segments.compile_textures(p,d,antenna_layer,pngbytes)
    puppet_arms.compile_textures(p,d,material,cloth_base,pattern_texture,composite,pngbytes)
    legacy.compile_flags(p,d)
    for key in audio_assets.DESIGN_FIELDS:d[key]=audio_assets.runtime_track(d.get(key))
    d['voice']=voice_settings.runtime(d.get('voice'))
    return d
def update_version():
    # Room changes use the game's normal content checksum; saves do not change versions.
    return

def write_project_worlds(items):
    members=[x for x in items if x.get('ownerMod')=='moreiterators.local']
    if not members:return
    result=room_bindings.write_worlds(items)
    installed=ASSETS/'mods/more_iterators_local'
    for relative in result['removed']:
        target=(installed/relative).resolve()
        if not target.is_relative_to(installed.resolve()):raise ValueError('已管理房间输出路径越界')
        target.unlink(missing_ok=True)
    info=MOD/'modinfo.json'
    if not info.exists():atomic(info,dict(id='moreiterators.local',name='更多迭代器 · 本地作品',version='0.1.0',authors='Local',description='本机作品。不要上传。',requirements=['moreiterators.core'],requirements_names=['更多迭代器'],tags=['Regions'],target_game_version='v1.11.8',checksum_override_version=False))

def sync_local_world():
    destination=ASSETS/'mods/more_iterators_local'
    shutil.copytree(MOD,destination,dirs_exist_ok=True)

def entry_room_template():
    relative=storage.settings.get('entryRoomTemplate')
    if not relative:return waiting_room.rendered()
    source=(storage.DATA/relative).resolve()
    if not source.is_relative_to(storage.DATA.resolve()):raise ValueError('等待房间模板必须位于 data 内')
    if not Path(str(source)+'.txt').is_file():raise ValueError('本地等待房间模板缺失：'+str(relative))
    return source

def default_room_source(p,name,kind):
    room_editor.ensure_synced(p['projectId'],name)
    cached=room_editor.cached_source(p['projectId'],name)
    if cached:return cached
    if storage.binding(p['projectId']) or p.get('roomBinding'):
        root=storage.target_mod(p['projectId'])/'world'/(name.split('_')[0].lower()+'-rooms')/name
        if Path(str(root)+'.txt').is_file():return root
    if kind=='entry' and p.get('roomBinding',{}).get('entryMode')=='existing':return room_bindings.resolve_room_source(name)
    return ASSETS/'world/ss-rooms/ss_ai' if kind=='ai' else entry_room_template()

def rained_settings_source(p,name,kind):
    installed=storage.installed_mod(p['projectId'])/'world'/(name.split('_')[0].lower()+'-rooms')/(name+'_settings.txt')
    authored=storage.target_mod(p['projectId'])/'world'/(name.split('_')[0].lower()+'-rooms')/(name+'_settings.txt')
    for value in (installed,authored):
        if value.is_file():return value
    source=ASSETS/'world/ss-rooms/ss_ai' if kind=='ai' else entry_room_template()
    return Path(str(source)+'_settings.txt')

def sync_rained(pid,kind):
    if native_projects.binding(pid):
        raise ValueError('原版固定房间暂不支持地形同步，不能覆盖游戏原始房间；请使用自建项目编辑房间。')
    p=storage.load_project(storage.valid_id(pid));ai,entry,_=roomnames(p);name=ai if kind=='ai' else entry
    if kind=='entry' and p.get('roomBinding',{}).get('entryMode')=='existing':raise ValueError('所选外部房间属于原版或其他模组，不能在此覆盖地形。')
    result=room_editor.import_render(pid,kind,roomnames,rained_settings_source(p,name,kind))
    deploy(p)
    return result

def sync_linked_rooms(p,ai,entry):
    """Apply only explicitly rendered rooms owned by this linked project."""
    pid=p['projectId']
    if not storage.link(pid):return
    target=storage.target_mod(pid);installed=storage.installed_mod(pid)
    for name in (ai,entry):room_editor.ensure_synced(pid,name)
    for name,kind in ((ai,'ai'),(entry,'entry')):
        source=room_editor.cached_source(pid,name)
        if source is None:continue
        relative=Path('world')/(name.split('_')[0].lower()+'-rooms')
        rooms=target/relative
        copy_room(source,rooms,name,replace=True)
        if kind=='entry':zero_gravity(rooms/(name+'_settings.txt'))
        if installed.is_dir():copy_room(rooms/name,installed/relative,name,replace=True)

def deploy(p):
    with LOCK:return _deploy(p)

def _deploy(p):
    p=save(p);d=compile_design(p);p=waiting_room.prepare(p);ai,entry,oid=roomnames(p)
    audio_assets.copy_referenced([d],storage.target_mod(p['projectId']))
    audio_assets.copy_referenced([d],storage.installed_mod(p['projectId']))
    path=storage.design_path(p['projectId'],oid);atomic(path,d)
    if storage.link(p['projectId']):
        storage.sync_design(p['projectId'],oid)
        sync_linked_rooms(p,ai,entry)
    elif not native_projects.binding(p['projectId']):
        rooms=MOD/'world'/(ai.split('_')[0].lower()+'-rooms');rooms.mkdir(parents=True,exist_ok=True)
        # Local map templates stay in data, outside the distributable creator.
        ai_source=default_room_source(p,ai,'ai')
        copy_room(ai_source,rooms,ai,palette=26,replace=room_editor.cached_source(p['projectId'],ai) is not None)
        if p.get('roomBinding',{}).get('entryMode')!='existing':
            entry_source=default_room_source(p,entry,'entry')
            copy_room(entry_source,rooms,entry,replace=room_editor.cached_source(p['projectId'],entry) is not None)
            zero_gravity(rooms/(entry+'_settings.txt'))
    with LOCK:
        registry=DESIGNS/'creator/registry.json';items=json.loads(registry.read_text('utf-8')) if registry.exists() else []
        items=[x for x in items if x['projectId']!=p['projectId']]+[storage.registry_record(p,ai,entry,oid)]
        items.sort(key=lambda x:x['projectId']);atomic(registry,items)
        if not storage.binding(p['projectId']):write_project_worlds(items);sync_local_world()
    return dict(ok=True,ai=ai,entry=entry,oracleId=oid,project=p,activation=local_content.status(p))

def ensure_native_projects():
    # A distributed tool starts with the user's own empty library. The native
    # reference remains available, but opening the editor must not deploy it.
    if (ROOT.parent/'release-layout.json').exists():return
    # Seed once; never replace the user's subsequent edits or native room files.
    if not (ASSETS/'mods/moreslugcats/world/dm-rooms/dm_ai.txt').exists():return
    for pid in native_projects.BINDINGS:
        file=storage.project_file(pid)
        if not file.exists():deploy(native_projects.moon_project(default))
        elif not storage.design_path(pid,storage.binding(pid)['oracleId']).exists():deploy(storage.load_project(pid))

def appearance_without_textures(value):
    if isinstance(value,dict):return {k:appearance_without_textures(v) for k,v in value.items() if not k.endswith('Png')}
    if isinstance(value,list):return [appearance_without_textures(v) for v in value]
    return value

def room_reference_files(project_id):
    # Room identity is controlled by the saved migration, not an older browser draft.
    project=storage.load_project(storage.valid_id(project_id))
    ai,entry,_=roomnames(project)
    result=[]
    with room_migration.staging_directory() as staged:
        for name,kind in ((ai,'ai'),(entry,'entry')):
            source=standalone.room_source(project,name,kind,sys.modules[__name__])
            copy_room(source,staged,name)
        for file in sorted(staged.iterdir()):
            result.append((file.name,file.read_bytes()))
    return result

def export(p,parts):
    validate(p);allowed={'appearance','textures','room','dialogue'}
    if not parts or set(parts)-allowed:raise ValueError('请选择导出的部分')
    room_files=room_reference_files(p['projectId']) if 'room' in parts else []
    EXPORTS.mkdir(parents=True,exist_ok=True);name=p['projectId']+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.zip';d=compile_design(p)
    with zipfile.ZipFile(EXPORTS/name,'w',zipfile.ZIP_DEFLATED) as z:
        audio_files=audio_assets.write_archive(z,[d] if 'appearance' in parts else [])
        z.writestr('manifest.json',json.dumps(dict(schema='moreiterators.export.v1',projectId=p['projectId'],name=p['name'],components=parts,runtime='MoreIterators >= 0.1.0',independentMod=False,audioAssets=audio_files),ensure_ascii=False,indent=2))
        if 'appearance' in parts:z.writestr('appearance.json',json.dumps(appearance_without_textures({k:v for k,v in d.items() if not k.endswith('Dialogue') and k!='dialogueJson' and not k.startswith(('room','pearl'))}),ensure_ascii=False,indent=2))
        if 'textures' in parts:
            eyes.export_textures(z,p['design'])
            z.writestr('editable-textures.json',json.dumps(p.get('textures',{}),ensure_ascii=False))
            for key,tex in p.get('textures',{}).items():
                z.writestr('textures/'+key+'.png',material(p,key))
                if key.startswith(('antenna','ear')):
                    for i,label in enumerate(('inner','outer')):z.writestr('textures/'+key+'-'+label+'.png',pngbytes(antenna_layer(p,key,i)))
                if fabric(key):z.writestr('overlays/'+key+'.png',composite(pattern_texture(p,key),texture_size(p,key)))
        if 'dialogue' in parts:z.writestr('dialogue.json',json.dumps(dialogue.profile(p),ensure_ascii=False,indent=2))
        if 'room' in parts:
            z.writestr('room-settings.json',json.dumps({k:v for k,v in d.items() if k.startswith(('room','pearl'))},ensure_ascii=False,indent=2))
            for room_file,content in room_files:z.writestr('room-reference/'+room_file,content)
        z.writestr('README.txt','供内容模组选择性集成的素材包；不是独立模组。\nmanifest 列出本次选择的组件。房间名称与入口需在正式地区中重新分配，不能直接连接 TEST。\n两层面部纹案独立；gown 使用 11×11 网格 UV，PNG 顶部为肩部。\n')
    return '/exports/'+name
def legacy_control(control):
    # All project types use the same live pose control.
    f=DESIGNS/'studio-control.json';pose=json.loads(f.read_text('utf-8')) if f.exists() else {}
    paused=control.get('paused',False);story=control.get('mode','silent')=='story'
    pose.update(animate=True,playMode=True,recording=False,pose='idle',bpPearl='none',hasMark=control.get('hasMark',True),manualLeft=False,manualRight=False,bodyAngle=0,testGravity=-1)
    atomic(f,pose)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,status,data,ctype='application/json; charset=utf-8'):
        b=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
    def do_GET(self):
        if self.headers.get('Host') not in (f'127.0.0.1:{PORT}',f'localhost:{PORT}'):return self.reply(403,{'error':'仅限本机'})
        path=urllib.parse.urlparse(self.path).path
        try:
            if path=='/api/health':return self.reply(200,dict(service='more-iterators-studio',protocol=1,pid=os.getpid(),dataDirectory=str(storage.DATA.resolve()),editorDirectory=str(ROOT)))
            if path.startswith('/api/audio/') and path.endswith('.mp3'):
                return self.reply(200,audio_assets.asset_path(path[len('/api/audio/'):-4]).read_bytes(),'audio/mpeg')
            if path=='/api/export-settings':
                pid=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('id',[''])[0]
                return self.reply(200,standalone.preferences(pid))
            if path=='/api/dialogue':
                pid=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('id',[''])[0]
                with LOCK:
                    deleted=bool(project_lifecycle.archived(pid))
                    if deleted:
                        p=project_lifecycle.reference_project(pid);p['dialogue']=dialogue.profile(p)
                    else:p=dialogue.persisted_profile(pid,roomnames)
                return self.reply(200,dict(projectId=pid,name=p['name'],deleted=deleted,legacy=bool(legacy.oracle(p)),dialogue=p['dialogue'],revision=p.get('dialogueRevision',0)))
            if path=='/api/projection-settings':
                pid=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('projectId',[''])[0]
                with LOCK:value=projections.project_settings(pid)
                return self.reply(200,value)
            if path=='/api/projections':
                groups=projections.listing()
                return self.reply(200,dict(projections=groups,applied=projections.applied_revisions(groups,roomnames),projects=[dict(projectId=p['projectId'],name=p['name']) for p in (json.loads(f.read_text('utf-8')) for f in storage.project_files())]))
            if path in ('/api/projection-default','/api/projection-sources','/api/projection-background'):
                pid=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('projectId',[''])[0]
                with LOCK:
                    value=projections.default(pid) if path.endswith('default') else projections.sources(pid,roomnames) if path.endswith('sources') else projections.background(pid,sys.modules[__name__])
                return self.reply(200,value)
            if path=='/api/projection-reference':return self.reply(200,projections.reference())
            if path=='/api/projection-reference-image':
                key=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('id',[''])[0]
                return self.reply(200,projections.reference_image(key),'image/png')
            if path=='/api/voice-sample':
                query=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                return self.reply(200,voice_samples.sample(storage.GAME,query.get('bank',[''])[0],int(query.get('index',['-1'])[0])),'audio/wav')
            if path=='/api/broadcasts':return self.reply(200,broadcasts.listing())
            if path=='/api/rooms':return self.reply(200,room_bindings.catalog())
            if path=='/api/overseer':
                pid=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('projectId',[''])[0]
                with LOCK:value=overseers.read(pid)
                return self.reply(200,value)
            if path=='/api/room-cleanup':
                pid=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('projectId',[''])[0]
                with LOCK:result=room_cleanup.preview(pid)
                return self.reply(200,result)
            if path=='/api/room-draft':
                pid=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('projectId',[''])[0]
                with LOCK:result=studio_drafts.load(pid)
                return self.reply(200,result)
            if path=='/api/room-binding':
                pid=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('projectId',[''])[0]
                p=storage.load_project(storage.valid_id(pid))
                return self.reply(200,dict(room_bindings.describe(p),projectId=pid,name=p['name']))
            if path=='/api/broadcast-default':return self.reply(200,broadcasts.default())
            if path=='/api/broadcast-rooms':
                if 'refresh=1' in self.path:broadcasts.room_index(True)
                return self.reply(200,broadcasts.rooms())
            if path=='/api/broadcast-room':
                name=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('room',[''])[0]
                return self.reply(200,broadcasts.geometry(name))
            if path=='/api/pearl-projects':
                with LOCK:value=pearl_projects.catalog()
                return self.reply(200,value)
            if path=='/api/pearls':
                collection=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('collectionId',[None])[0]
                with LOCK:value=pearls.listing(collection)
                return self.reply(200,value)
            if path=='/api/pearl-room':
                query=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                pid=query.get('projectId',[''])[0];room=query.get('room',[''])[0]
                with LOCK:value=pearls.room_geometry(room) if room else pearls.spawn_geometry(pid)
                return self.reply(200,value)
            if path=='/api/pearl-destinations':
                return self.reply(200,pearls.destinations(roomnames))
            if path=='/api/pearl-default':
                collection=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('collectionId',[None])[0]
                with LOCK:value=pearls.default(collection)
                return self.reply(200,value)
            if path=='/api/pearl-reader':
                pid=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('id',[''])[0];storage.load_project(pid);return self.reply(200,pearls.reader(pid))
            if path=='/api/default':return self.reply(200,project_templates.create(default()))
            if path=='/api/association':
                pid=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('id',[''])[0]
                return self.reply(200,project_association(pid))
            if path=='/api/projects':return self.reply(200,[dict(json.loads(f.read_text('utf-8')),fixedProject=bool(storage.binding(f.parent.name))) for f in storage.project_files() if not project_lifecycle.archived(f.parent.name)])
            if path=='/api/status':
                f=DESIGNS/'creator/status.json';d=live_snapshot(f);h=DESIGNS/'creator/heartbeat.json';beat=live_snapshot(h)
                if beat:d.update(beat)
                else:h=f
                d['online']=file_age(h)<8;frame=DESIGNS/'studio-frame.png';d['frameOnline']=d['online'] and file_age(frame)<5;return self.reply(200,d)
            if path=='/api/control':
                f=DESIGNS/'creator/control.json';return self.reply(200,json.loads(f.read_text('utf-8')) if f.exists() else {'mode':'silent','behavior':'work','paused':False,'hasMark':True,'rearGlow':True,'lightning':True,'pearls':True,'glyphs':True,'palettePreview':-1})
            if path=='/api/history':
                pid=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('id',[''])[0]
                if not re.fullmatch('[a-z][a-z0-9-]{0,47}',pid):raise ValueError('项目无效')
                with LOCK:
                    project_lifecycle.assert_active(pid)
                    current=storage.project_file(pid)
                    entries=[{'file':'project.json','current':True,'project':json.loads(current.read_text('utf-8'))}] if current.exists() else []
                    entries.extend({'file':f.name,'current':False,'project':json.loads(f.read_text('utf-8'))} for f in sorted(storage.history_directory(pid).glob('*.json'),reverse=True)[:30])
                return self.reply(200,entries)
            if path=='/api/version':return self.reply(200,dict(version=json.loads((ROOT.parent/'version.json').read_text('utf-8-sig')),changelog=json.loads((ROOT/'changelog.json').read_text('utf-8')),community=json.loads((ROOT/'community.json').read_text('utf-8')) if (ROOT/'community.json').exists() else {}))
            if path=='/api/action-presets':
                kind=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('kind',['action'])[0]
                return self.reply(200,action_presets.listing(kind))
            if path=='/api/project-trash':return self.reply(200,project_lifecycle.listing())
            if path=='/api/project-association-operations':
                with LOCK:result=project_associations.operations()
                return self.reply(200,result)
            if path=='/api/diagnostics':return self.reply(200,diagnostics.snapshot())
            if path=='/api/frame.png':
                f=DESIGNS/'studio-frame.png';return self.reply(200,f.read_bytes(),'image/png') if f.exists() else self.reply(404,{'error':'尚无实机画面'})
            if path=='/api/preset.json':return self.reply(200,(storage.WORKSPACE/'templates/native-preset.json').read_bytes())
            if path in ('/api/legacy-cf.json','/api/legacy-ir.json'):
                oid=path.split('-')[1].split('.')[0];f=storage.legacy_asset('legacy-'+oid+'.json');return self.reply(200,json.loads(f.read_text('utf-8')) if f and f.exists() else None)
            if path.startswith('/exports/'):
                name=path.split('/')[-1]
                if not re.fullmatch(r'[a-z0-9-]+\.zip',name):raise ValueError('文件名无效')
                return self.reply(200,(EXPORTS/name).read_bytes(),'application/zip')
            file={'/studio-status.css':'studio-status.css','/studio-status.js':'studio-status.js','/standalone.js':'standalone.js','/broadcasts':'broadcasts.html','/broadcasts.html':'broadcasts.html','/broadcasts.js':'broadcasts.js','/broadcasts.css':'broadcasts.css','/':'index.html','/index.html':'index.html','/app.js':'app.js','/preview-background.js':'preview-background.js','/sleeve-mapping.js':'sleeve-mapping.js','/pearl-accessories.js':'pearl-accessories.js','/head-segments.js':'head-segments.js','/color-gradients.js':'color-gradients.js','/puppet-arms.js':'puppet-arms.js','/wardrobe.js':'wardrobe.js','/necklaces.js':'necklaces.js','/legacy-preview.js':'legacy-preview.js','/style.css':'style.css','/dialogue':'dialogue.html','/dialogue.html':'dialogue.html','/dialogue.js':'dialogue.js','/line-actions.js':'line-actions.js','/dialogue.css':'dialogue.css','/pearls':'pearls.html','/pearls.html':'pearls.html','/pearls.js':'pearls.js','/pearl-icons.js':'pearl-icons.js','/pearls.css':'pearls.css'}.get(path)
            if path in ('/projections','/projections.html','/projections.js','/projections.css','/projection-depth.js'):file='projections.html' if path in ('/projections','/projections.html') else path.lstrip('/')
            if path in ('/rooms','/rooms.html','/rooms.js','/rooms.css','/overseer-preview.js'):file='rooms.html' if path in ('/rooms','/rooms.html') else path.lstrip('/')
            if path in ('/studio-theme.css','/paint-layers.js','/project-actions.js','/studio-chrome.js'):file=path.lstrip('/')
            if path.startswith('/fonts/'):
                name=path.removeprefix('/fonts/')
                allowed={'fusion-pixel.woff2','fusion-pixel-ja.woff2','fusion-pixel-zh_hant.woff2','fusion-pixel-zh_hk.woff2','fusion-pixel-zh_tw.woff2','Fusion-Pixel-OFL.txt'}
                if name not in allowed:return self.reply(404,{'error':'未找到'})
                return self.reply(200,(ROOT/'fonts'/name).read_bytes(),'font/woff2' if name.endswith('.woff2') else 'text/plain; charset=utf-8')
            if path=='/hand-texture-base.js':file='hand-texture-base.js'
            if path=='/eyes.js':file='eyes.js'
            if path=='/workspace.js':file='workspace.js'
            if path=='/audio-settings.js':file='audio-settings.js'
            if path=='/voice-settings.js':file='voice-settings.js'
            if path=='/i18n.js':file='i18n.js'
            if path in ('/locales/zh-CN.json','/locales/en.json'):return self.reply(200,(ROOT/path.lstrip('/')).read_bytes())
            if not file and re.fullmatch(r'/[a-z][a-z0-9-]*\.(?:js|css)',path) and (ROOT/path[1:]).is_file():file=path[1:]
            if file:
                linked=storage.legacy_asset(file) if file=='legacy-preview.js' else None
                return self.reply(200,(linked or ROOT/file).read_bytes(), 'text/html; charset=utf-8' if file.endswith('html') else 'text/css; charset=utf-8' if file.endswith('css') else 'application/javascript; charset=utf-8')
            self.reply(404,{'error':'未找到'})
        except (OSError,ValueError,KeyError,TypeError) as e:self.reply(400,diagnostics.error_payload(e,urllib.parse.urlparse(self.path).path))
        except Exception as e:self.reply(500,diagnostics.error_payload(e,urllib.parse.urlparse(self.path).path))
    def do_POST(self):
        if self.headers.get('Origin') not in (f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'):return self.reply(403,{'error':'拒绝外部来源'})
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<16000000:raise ValueError('项目体积超限')
            data=json.loads(self.rfile.read(n));path=self.path
            if path in ('/api/project-purge-plan','/api/project-purge'):
                action=project_purge.plan if path.endswith('-plan') else project_purge.apply
                with LOCK:result=action(data,sys.modules[__name__])
                return self.reply(200,result)
            if path=='/api/project-associations-restore':
                with LOCK:result=project_associations.restore(data,sys.modules[__name__])
                return self.reply(200,result)
            if path in ('/api/project-associations','/api/project-associations-plan','/api/project-associations-apply'):
                action={'/api/project-associations':project_associations.inspect,'/api/project-associations-plan':project_associations.plan,'/api/project-associations-apply':project_associations.apply}[path]
                with LOCK:result=action(data,sys.modules[__name__])
                return self.reply(200,result)
            if path=='/api/action-presets':
                with LOCK:result=action_presets.save(data,sys.modules[__name__])
                return self.reply(200,result)
            if path=='/api/project-delete':
                with LOCK:result=project_lifecycle.delete(data,sys.modules[__name__])
                return self.reply(200,result)
            if path=='/api/project-restore':
                with LOCK:result=project_lifecycle.restore(data['token'],sys.modules[__name__])
                return self.reply(200,result)
            if path=='/api/audio/import':
                with LOCK:result=audio_assets.import_audio(data)
                return self.reply(200,result)
            if path=='/api/projection-settings':
                with LOCK:result=projections.save_project_settings(data['settings'],apply=data.get('apply',False))
                return self.reply(200,result)
            if path in ('/api/overseer/save','/api/overseer/apply'):
                with LOCK:result=overseers.save(data['projectId'],data['config'],data.get('revision'),apply=path.endswith('/apply'))
                return self.reply(200,result)
            if path=='/api/room-cleanup/apply':
                with LOCK:result=room_cleanup.apply(data['projectId'],data.get('token'))
                return self.reply(200,result)
            if path=='/api/room-draft':
                with LOCK:result=studio_drafts.save(data,atomic)
                return self.reply(200,result)
            if path=='/api/room-binding/preview':
                with LOCK:result=room_migration.preview(data['projectId'],data['binding'])
                return self.reply(200,result)
            if path=='/api/room-binding/apply':
                with LOCK:result=room_migration.apply(data['projectId'],data['binding'],data.get('token'),sys.modules[__name__])
                return self.reply(200,result)
            if path=='/api/export-standalone':
                with LOCK:result=standalone.build(data,sys.modules[__name__])
                return self.reply(200,result)
            if path=='/api/pearl-projects':
                with LOCK:value=pearl_projects.save(data)
                return self.reply(200,value)
            if path=='/api/pearl-projects/activate':
                with LOCK:value=pearl_projects.activate(data.get('id'),roomnames)
                return self.reply(200,value)
            if path in ('/api/projection-save','/api/projection-apply'):
                with LOCK:p=projections.apply(data,roomnames) if path.endswith('apply') else projections.save(data,roomnames)
                return self.reply(200,dict(ok=True,projection=p))
            if path=='/api/open-room':
                with LOCK:
                    project_lifecycle.assert_active(data['projectId'])
                    result=room_editor.open_room(data['projectId'],data['kind'],roomnames)
                return self.reply(200,result)
            if path=='/api/sync-room':
                with LOCK:
                    project_lifecycle.assert_active(data['projectId'])
                    result=sync_rained(data['projectId'],data['kind'])
                return self.reply(200,result)
            if path=='/api/dialogue':
                with LOCK:
                    project_lifecycle.assert_active(data['projectId'])
                    p=storage.load_project(data['projectId'])
                    if data.get('revision',0)!=p.get('dialogueRevision',0):raise ValueError('对话已在另一页面保存，请重新打开此项目后再修改。')
                    p['dialogue']=dialogue.validate(data['dialogue']);p['dialogueRevision']=p.get('dialogueRevision',0)+1;p=save(p,dialogue_edit=True)
                    if data.get('apply',False):
                        oid=roomnames(p)[2];f=storage.design_path(p['projectId'],oid)
                        if not f.exists():raise ValueError('对话已保存；请先在外观调整应用该项目。')
                        design=json.loads(f.read_text('utf-8'));design['dialogueJson']=json.dumps(p['dialogue'],ensure_ascii=False);atomic(f,design);storage.sync_design(p['projectId'],oid)
                return self.reply(200,dict(ok=True,revision=p['dialogueRevision'],dialogue=p['dialogue']))
            if path=='/api/broadcast-import':return self.reply(200,broadcasts.import_bundle(data))
            if path=='/api/broadcast-validate':return self.reply(200,broadcasts.validate(data))
            if path in ('/api/broadcast-save','/api/broadcast-apply'):
                with LOCK:p=broadcasts.apply(data) if path.endswith('apply') else broadcasts.save(data)
                return self.reply(200,dict(ok=True,project=p))
            if path in ('/api/pearl-save','/api/pearl-apply'):
                with LOCK:p=pearls.apply(data,roomnames) if path.endswith('apply') else pearls.save(data)
                return self.reply(200,dict(ok=True,project=p))
            if path=='/api/save':return self.reply(200,{'ok':True,'project':save(data)})
            if path=='/api/import-project':return self.reply(200,{'ok':True,'project':import_project(data)})
            if path=='/api/deploy':return self.reply(200,deploy(data))
            if path=='/api/control':
                if data.get('mode','silent') not in ('silent','story','read') or data.get('behavior','work') not in ('work','reception'):raise ValueError('状态无效')
                with LOCK:
                    if data.get('projectId'):project_lifecycle.assert_active(data['projectId'])
                    atomic(DESIGNS/'creator/control.json',data);legacy_control(data)
                return self.reply(200,{'ok':True})
            if path=='/api/launch':
                with LOCK:
                    p=validate(data['project']);r=deploy(p);control=dict(data.get('control',{}),projectId=p['projectId']);atomic(DESIGNS/'creator/control.json',control);atomic(DESIGNS/'creator/launch.json',dict(projectId=p['projectId'],entry=r['entry'],mode=control.get('mode','silent'),hasMark=control.get('hasMark',True),reset=data.get('reset',True)))
                    legacy_control(control)
                    atomic_text(DESIGNS/'launch-room.txt',r['entry'])
                return self.reply(200,r)
            if path=='/api/export':
                with LOCK:result=export(data['project'],data['parts'])
                return self.reply(200,{'ok':True,'url':result})
            self.reply(404,{'error':'未知操作'})
        except (ValueError,KeyError,TypeError,OSError) as e:self.reply(400,diagnostics.error_payload(e,self.path))
        except Exception as e:self.reply(500,diagnostics.error_payload(e,self.path))
if __name__=='__main__':
    PROJECTS.mkdir(parents=True,exist_ok=True);(DESIGNS/'creator').mkdir(parents=True,exist_ok=True);ensure_native_projects();sync_saved_project_names();ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
