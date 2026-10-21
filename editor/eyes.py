"""Independent eye settings; native expression animation remains shared."""
import base64
import io
import math
import json
import re
from PIL import Image

MAX_EYES=16
FIELDS={'id','enabled','sourceSide','offsetX','offsetY','scale','color','textureEnabled','textureTint','texturePng','textureMirrorX','mirrorOf'}

def default(index):
    return dict(id='eye-'+str(index+1),enabled=True,sourceSide=index%2,
                offsetX=0,offsetY=0,scale=1,color='',textureEnabled=False,textureTint=False,texturePng='',textureMirrorX=False,mirrorOf='')

def validate(design):
    raw=design.setdefault('eyes',[])
    if not isinstance(raw,list) or len(raw)>MAX_EYES:raise ValueError('眼睛数量不能超过 16')
    result=[];ids=set()
    for index,item in enumerate(raw):
        if not isinstance(item,dict) or set(item)-FIELDS:raise ValueError('眼睛设置无效')
        eye={**default(index),**item}
        if not isinstance(eye['id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',eye['id']) or eye['id'] in ids:raise ValueError('眼睛编号无效或重复')
        ids.add(eye['id'])
        for key in ('enabled','textureEnabled','textureTint','textureMirrorX'):
            if type(eye[key]) is not bool:raise ValueError('眼睛开关无效')
        if type(eye['sourceSide']) is not int or eye['sourceSide'] not in (0,1):raise ValueError('眼睛参考侧无效')
        for key,low,high in [('offsetX',-40,40),('offsetY',-40,40),('scale',.1,8)]:
            value=eye[key]
            if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise ValueError('眼睛位置或大小超出范围')
        if not isinstance(eye['color'],str) or (eye['color'] and not re.fullmatch(r'#[0-9a-fA-F]{6}',eye['color'])):raise ValueError('眼睛颜色格式无效')
        if not isinstance(eye['mirrorOf'],str) or (eye['mirrorOf'] and not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',eye['mirrorOf'])):raise ValueError('眼睛镜像关联无效')
        png=eye['texturePng']
        if not isinstance(png,str):raise ValueError('眼睛贴图须为 PNG')
        if png:
            try:
                if not png.startswith('data:image/png;base64,') or len(png)>1500000:raise ValueError()
                image=Image.open(io.BytesIO(base64.b64decode(png.split(',',1)[1],validate=True)))
                if image.format!='PNG' or not 1<=image.width<=256 or not 1<=image.height<=256:raise ValueError()
                image.verify()
            except Exception as error:raise ValueError('眼睛贴图须为不超过 256 × 256 的 PNG') from error
        result.append(eye)
    by_id={eye['id']:eye for eye in result}
    for eye in result:
        if eye['mirrorOf']:
            source=by_id.get(eye['mirrorOf'])
            if source is None or source is eye or source['mirrorOf']:raise ValueError('眼睛镜像关联无效')
    design['eyes']=result


def resolved(eyes,index):
    eye=eyes[index]
    source=next((item for item in eyes if item['id']==eye.get('mirrorOf')),None)
    if source is None or source is eye or source.get('mirrorOf'):return dict(eye)
    return {**source,'id':eye['id'],'enabled':eye['enabled'],'sourceSide':1 if source['sourceSide']==0 else 0,
            'offsetX':-source['offsetX'],'textureMirrorX':not source.get('textureMirrorX',False),'mirrorOf':eye['mirrorOf']}


def export_textures(archive,design):
    # Eye images live with their eye rather than in the shared clothing canvases.
    # Include disabled artwork too, so authoring material exports are lossless.
    entries=[]
    for eye in design.get('eyes',[]):
        if eye.get('texturePng'):
            entries.append({key:eye[key] for key in ('id','textureEnabled','textureTint','texturePng')})
            archive.writestr('textures/eyes/'+eye['id']+'.png',base64.b64decode(eye['texturePng'].split(',',1)[1]))
    if entries:archive.writestr('editable-eyes.json',json.dumps(entries,ensure_ascii=False,indent=2))
