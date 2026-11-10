
from pathlib import Path, PurePosixPath
import base64
import copy
import hashlib
import io
import json
import math
import re

from PIL import Image

SCHEMA='moreiterators.export-scenes.v1'
KINDS=('select_menu_scene','select_menu_scene_ascended','sleep_scene','death_scene','starve_scene')
SHADERS=('Basic','Normal','Lighten','LightEdges','Rain','Overlay','SoftLight','Multiply')
SCENE_KEYS={'kind','images','idle_depths','glow_pos','mark_pos','select_menu_pos','slugcat_depth','dream_override'}
IMAGE_KEYS={'name','png','pos','depth','shader','flatmode'}
MAX_IMAGE=12*1024*1024
MAX_PIXELS=64*1024*1024
MAX_BYTES=64*1024*1024


def _number(value,low,high):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError('场景数值超出范围')
    return value


def _point(value):
    if not isinstance(value,list) or len(value)!=2:raise ValueError('场景位置必须包含 X 和 Y')
    return [_number(n,-8192,8192) for n in value]


def _relative(value):
    if not isinstance(value,str) or not value or len(value)>200 or '\\' in value:
        raise ValueError('场景图片路径无效')
    path=PurePosixPath(value)
    if path.is_absolute() or str(path)!=value or any(p in ('','.','..') or p.endswith((' ','.')) or re.search(r'[<>:"|?*\x00-\x1f]',p) or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?',p) for p in value.split('/')):
        raise ValueError('场景图片路径无效')
    return value


def _png(value):
    if not isinstance(value,str) or not value.startswith('data:image/png;base64,') or len(value)>MAX_IMAGE*4//3+100:
        raise ValueError('场景图层需要 PNG 图片，最大 12 MB')
    try:
        raw=base64.b64decode(value.split(',',1)[1],validate=True)
        if len(raw)>MAX_IMAGE:raise ValueError()
        with Image.open(io.BytesIO(raw)) as image:
            if image.format!='PNG' or image.width<1 or image.height<1 or image.width>4096 or image.height>4096 or getattr(image,'n_frames',1)!=1:
                raise ValueError()
            size=image.size;image.verify()
        with Image.open(io.BytesIO(raw)) as image:image.load()
    except (ValueError,OSError,Image.DecompressionBombError) as error:
        raise ValueError('场景 PNG 无效或尺寸超过 4096') from error
    return raw,size


def validate(value):
    if value is None:return None
    if not isinstance(value,dict) or set(value)!={'schema','scenes'} or value.get('schema')!=SCHEMA or not isinstance(value.get('scenes'),list) or len(value['scenes'])>len(KINDS):
        raise ValueError('场景配置格式无效')
    result=[];kinds=set();total_pixels=total_bytes=0
    for scene in value['scenes']:
        if not isinstance(scene,dict) or set(scene)-SCENE_KEYS or scene.get('kind') not in KINDS or scene['kind'] in kinds:
            raise ValueError('场景用途无效或重复')
        kinds.add(scene['kind'])
        images=scene.get('images');focus=scene.get('idle_depths')
        if not isinstance(images,list) or not 1<=len(images)<=32:raise ValueError('每个场景需要 1 至 32 个图层')
        if not isinstance(focus,list) or not 1<=len(focus)<=16:raise ValueError('请设置场景聚焦深度')
        target={'kind':scene['kind'],'images':[],'idle_depths':[_number(n,.1,50) for n in focus]};names=set()
        for item in images:
            if not isinstance(item,dict) or set(item)-IMAGE_KEYS:raise ValueError('场景图层格式无效')
            name=_relative(item.get('name'))
            if name.lower().endswith('.png') or name.casefold() in names:raise ValueError('场景图层名称重复或包含扩展名')
            names.add(name.casefold());depth=item.get('depth',-1)
            if depth!=-1:_number(depth,.1,50)
            shader=item.get('shader','Normal')
            if shader not in SHADERS:raise ValueError('未知的原版场景着色器')
            flat=item.get('flatmode',False)
            if type(flat) is not bool:raise ValueError('场景平面模式值无效')
            raw,size=_png(item.get('png'))
            if depth!=-1 and shader not in ('Basic','Rain') and size[1]%2:raise ValueError('原版纵深图片高度必须为偶数')
            total_pixels+=size[0]*size[1];total_bytes+=len(raw)
            if total_pixels>MAX_PIXELS or total_bytes>MAX_BYTES:raise ValueError('场景图片总大小超过限制')
            target['images'].append(dict(name=name,png=item['png'],pos=_point(item.get('pos')),depth=depth,shader=shader,flatmode=flat))
        for key in ('glow_pos','mark_pos','select_menu_pos'):
            if key in scene:target[key]=_point(scene[key])
        if 'slugcat_depth' in scene:target['slugcat_depth']=_number(scene['slugcat_depth'],.1,50)
        if 'dream_override' in scene:
            if type(scene['dream_override']) is not bool:raise ValueError('场景梦境设置无效')
            target['dream_override']=scene['dream_override']
        result.append(target)
    return {'schema':SCHEMA,'scenes':result} if result else None


def _planned(mod_id,value):
    value=validate(value)
    if not isinstance(mod_id,str) or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,119}',mod_id):raise ValueError('模组 ID 无效')
    if value is None:return {},{}
    suffix=hashlib.sha256(mod_id.encode('utf-8')).hexdigest()[:16];files={};features={}
    for scene in value['scenes']:
        kind=scene['kind'];identifier='MI_'+suffix+'_'+kind;folder='scenes/mi_'+suffix+'/'+kind
        doc={key:copy.deepcopy(item) for key,item in scene.items() if key not in ('kind','images')}
        doc.update(id=identifier,scene_folder=folder,images=[])
        for image in scene['images']:
            doc['images'].append({key:copy.deepcopy(item) for key,item in image.items() if key!='png'})
            files[folder+'/'+image['name']+'.png']=_png(image['png'])[0]
        files['slugbase/scenes/'+identifier+'.json']=(json.dumps(doc,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        features[kind]=identifier
    return features,files


def write(stage,mod_id,value):
    features,files=_planned(mod_id,value);stage=Path(stage).resolve()
    for relative,raw in files.items():
        target=stage/relative
        if not target.resolve().is_relative_to(stage):raise ValueError('场景路径超出导出目录')
        if target.exists() and (not target.is_file() or target.read_bytes()!=raw):raise ValueError('场景文件与导出内容冲突：'+relative)
    for relative,raw in files.items():
        target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    return dict(features=features,files=sorted(files))


def audit(stage,mod_id,value):
    features,files=_planned(mod_id,value);stage=Path(stage).resolve()
    for relative,raw in files.items():
        target=stage/relative
        if not target.resolve().is_relative_to(stage) or not target.is_file() or target.read_bytes()!=raw:
            raise ValueError('场景文件校验失败：'+relative)
    return dict(features=features,files=sorted(files))


def audit_export(stage,mod_id,features,files):
    
    if not isinstance(features,dict) or set(features)-set(KINDS) or not isinstance(files,list) or any(not isinstance(path,str) for path in files) or len(set(files))!=len(files):
        raise ValueError('场景文件清单无效')
    stage=Path(stage).resolve();documents={};pngs={};total=0
    for relative in files:
        _relative(relative);path=stage/relative
        if not path.resolve().is_relative_to(stage) or not path.is_file():raise ValueError('场景文件路径无效')
        if relative.startswith('slugbase/scenes/') and relative.endswith('.json'):
            if path.stat().st_size>1024*1024:raise ValueError('场景配置格式无效')
            documents[relative]=json.loads(path.read_text('utf-8'))
        elif relative.startswith('scenes/') and relative.endswith('.png'):
            size=path.stat().st_size;total+=size
            if size>MAX_IMAGE or total>MAX_BYTES:raise ValueError('场景图片总大小超过限制')
            pngs[relative]=path.read_bytes()
        else:raise ValueError('场景文件清单无效')
    scenes=[]
    for kind,identifier in features.items():
        matches=[doc for doc in documents.values() if doc.get('id')==identifier]
        if len(matches)!=1:raise ValueError('场景绑定与文件不一致')
        scenes.append(import_scene(matches[0],pngs,kind))
    result=audit(stage,mod_id,{'schema':SCHEMA,'scenes':scenes})
    if result['features']!=features or set(result['files'])!=set(files):raise ValueError('场景绑定与文件清单不一致')
    return result


def import_scene(document,pngs,kind='select_menu_scene'):
    
    if not isinstance(document,dict) or set(document)-((SCENE_KEYS-{'kind'})|{'id','scene_folder'}):
        raise ValueError('不是支持的 SlugBase 2.x 场景')
    if not isinstance(pngs,dict):raise ValueError('请同时选择场景 JSON 和 PNG')
    assets={}
    for name,raw in pngs.items():
        name=_relative(name)
        if name.casefold() in assets:raise ValueError('场景 PNG 文件名重复')
        assets[name.casefold()]=raw
    result={key:copy.deepcopy(value) for key,value in document.items() if key not in ('id','scene_folder')}
    result['kind']=kind;result['images']=[]
    images=document.get('images')
    if not isinstance(images,list):raise ValueError('场景缺少图层列表')
    folder=document.get('scene_folder','')
    if folder:_relative(folder)
    for item in images:
        if not isinstance(item,dict) or set(item)-(IMAGE_KEYS-{'png'}):raise ValueError('不是支持的 SlugBase 2.x 图层')
        name=_relative(item.get('name'));expected=(folder+'/' if folder else '')+name+'.png'
        matches=[raw for path,raw in assets.items() if path==expected.casefold() or path.endswith('/'+expected.casefold())]
        if not matches:matches=[raw for path,raw in assets.items() if path==(name+'.png').casefold() or path.endswith('/'+(name+'.png').casefold())]
        if len(matches)!=1:raise ValueError('缺少图片或存在同名图片：'+name+'.png')
        raw=matches[0];image=copy.deepcopy(item)
        image['png']='data:image/png;base64,'+base64.b64encode(raw).decode() if isinstance(raw,bytes) else raw
        result['images'].append(image)
    return validate({'schema':SCHEMA,'scenes':[result]})['scenes'][0]
