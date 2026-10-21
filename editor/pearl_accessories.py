"""Connected decorative pearl groups, independent of event/readable pearls."""
import base64
import copy
import io
import math
import re
from PIL import Image
from necklaces import check_pearl, pearl

MAX_GROUPS=8
MAX_CHILDREN=8

def bead():
    return dict(color='#c5d6ce',highlight='#b7e5ef',dual=False,size=0,chain=-1,position=.5)

def child():
    return dict(name='',png='',color='#ffffff',enabled=True,bead=0,x=0,y=0,width=5,height=8,rotation=0)

def group(index=1):
    return dict(id='pearlAccessory:'+str(index),name='',anchor='head',stringColor='#737e78',enabled=True,
                pearls=5,hangingChains=1,horizontalChains=1,colorMode=0,u=.5,v=.5,x=0,y=0,rotation=0,
                width=14,length=18,sag=4,thickness=.4,size=2.2,softness=.7,gravity=1,
                primary=pearl(),alternate=pearl('#354d45','#d2ebe2',True),beads=[],children=[])

def _number(item,key,lo,hi,integer=False):
    value=item[key]
    if type(value) not in ((int,) if integer else (int,float)) or not math.isfinite(value) or not lo<=value<=hi:
        raise ValueError('珍珠组合 '+key+' 超出范围')

def _color(value):
    if not isinstance(value,str) or not re.fullmatch('#[a-fA-F0-9]{6}',value):raise ValueError('珍珠组合颜色格式错误')

def _png(value):
    if not isinstance(value,str):raise ValueError('子配件贴图格式错误')
    if not value:return ''
    if not value.startswith('data:image/png;base64,') or len(value)>6_000_000:raise ValueError('子配件只支持 PNG')
    try:
        raw=base64.b64decode(value.split(',',1)[1],validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            if image.format!='PNG' or not 1<=image.width<=1024 or not 1<=image.height<=1024:raise ValueError()
            image.load()
    except Exception as error:raise ValueError('子配件 PNG 损坏或超过 1024 × 1024') from error
    return value

def validate_pearl_accessories(design):
    import wardrobe
    items=design.setdefault('pearlAccessories',[])
    if not isinstance(items,list) or len(items)>MAX_GROUPS:raise ValueError('珍珠组合最多 8 组')
    allowed=set(['head','body','gown','shoulders','sleeveL','sleeveR','collar','handL','handR','legL','legR','neck']+wardrobe.HARDWARE_ANCHORS+[p['id'] for p in wardrobe.pieces(design)])
    ids=set()
    for index,item in enumerate(items):
        if not isinstance(item,dict):raise ValueError('珍珠组合格式错误')
        value=group(index+1)
        value.update({key:copy.deepcopy(v) for key,v in item.items() if key in value})
        if not isinstance(value['id'],str) or not re.fullmatch(r'pearlAccessory:[1-8]',value['id']) or value['id'] in ids:raise ValueError('珍珠组合编号无效或重复')
        ids.add(value['id'])
        if not isinstance(value['name'],str) or len(value['name'])>60:raise ValueError('珍珠组合名称过长')
        if not isinstance(value['anchor'],str) or value['anchor'] not in allowed:raise ValueError('珍珠组合绑定位置不存在')
        if type(value['enabled']) is not bool:raise ValueError('珍珠组合启用设置错误')
        for key,lo,hi in [('pearls',0,10),('horizontalChains',0,5),('hangingChains',0,5),('colorMode',0,2)]:_number(value,key,lo,hi,True)
        for key,lo,hi in [('u',0,1),('v',0,1),('x',-200,200),('y',-200,200),('rotation',-180,180),('width',.5,120),('length',.5,160),('sag',0,60),('thickness',.1,3),('size',.6,6),('softness',0,1),('gravity',0,3)]:_number(value,key,lo,hi)
        _color(value['stringColor'])
        for key in ('primary','alternate'):
            checked=check_pearl(value[key]);value[key]={k:checked[k] for k in pearl()}
        if not isinstance(value['beads'],list) or len(value['beads'])>10:raise ValueError('珍珠组合最多 10 颗珍珠')
        for i,item_bead in enumerate(value['beads']):
            if not isinstance(item_bead,dict):raise ValueError('装饰珍珠格式错误')
            b=bead();b.update({k:v for k,v in item_bead.items() if k in b});check_pearl(b);_number(b,'chain',-1,9,True);_number(b,'position',0,1);value['beads'][i]=b
        if not isinstance(value['children'],list) or len(value['children'])>MAX_CHILDREN:raise ValueError('珍珠组合最多 8 个子配件')
        for i,item_child in enumerate(value['children']):
            if not isinstance(item_child,dict):raise ValueError('子配件格式错误')
            c=child();c.update({k:v for k,v in item_child.items() if k in c})
            if type(c['enabled']) is not bool or not isinstance(c['name'],str) or len(c['name'])>60:raise ValueError('子配件名称或启用设置错误')
            for key,lo,hi in [('x',-80,80),('y',-80,80),('width',.1,120),('height',.1,120),('rotation',-180,180)]:_number(c,key,lo,hi)
            _number(c,'bead',0,9,True);_color(c['color']);c['png']=_png(c['png']);value['children'][i]=c
        items[index]=value
    return design
