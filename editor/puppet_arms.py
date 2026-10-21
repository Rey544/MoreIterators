"""Independent puppet limbs; mechanical arm settings are deliberately unrelated."""
import base64, copy, io, math, re
from PIL import Image

SIZES={**{'puppetHand'+str(i):(32,32) for i in range(4)},**{'puppetSleeve'+str(i):(32,64) for i in (2,3)}}
BOUNDS=dict(lengthScale=(.25,2.5),widthScale=(.25,3),handSize=(.25,3),shoulderX=(-40,40),shoulderY=(-40,40),sleeveRootX=(-40,40),sleeveRootY=(-40,40))
FLAGS=('enabled','sleeveEnabled','handOwnColor','handTextureEnabled','handTextureTint','sleeveTextureEnabled','sleeveOwnColor','sleeveOwnTexture')
SLEEVE_FIELDS=('widthScale','sleeveRootX','sleeveRootY','sleeveOwnColor','sleeveColor','sleeveTextureEnabled','sleeveOwnTexture','sleeveBasePng','sleevePng')
def arm(index):
    return dict(enabled=index<2,sleeveEnabled=True,handOwnColor=False,handColor='#a6aaa9',handTextureEnabled=False,handTextureTint=False,
        sleeveTextureEnabled=True,sleeveOwnColor=False,sleeveOwnTexture=False,sleeveColor='#b68b8e',lengthScale=1,widthScale=1,handSize=1,
        shoulderX=0,shoulderY=-8 if index>=2 else 0,sleeveRootX=0,sleeveRootY=0,handPng='',sleeveBasePng='',sleevePng='')
def defaults(d):
    d.setdefault('puppetArmSymmetry',True);d.setdefault('puppetExtraArmSymmetry',True)
    d.setdefault('puppetSleeveSyncSeparated',False);d.setdefault('puppetExtraSleeveSymmetry',d['puppetExtraArmSymmetry'])
    d.setdefault('puppetArms',[arm(i) for i in range(4)])
    return d
def validate(d):
    defaults(d)
    for key in ('puppetArmSymmetry','puppetExtraArmSymmetry','puppetSleeveSyncSeparated','puppetExtraSleeveSymmetry'):
        if type(d[key]) is not bool:raise ValueError('手臂同步设置必须是开关')
    if not isinstance(d['puppetArms'],list) or len(d['puppetArms'])!=4:raise ValueError('手臂配置需要两对、共四个位置')
    for i,item in enumerate(d['puppetArms']):
        if not isinstance(item,dict):raise ValueError('手臂配置必须是对象')
        value=arm(i);value.update(item)
        # Old versions multiplied imported art whenever a custom hand color was on.
        # Keep that appearance until the author explicitly disables texture tint.
        if 'handTextureTint' not in item:value['handTextureTint']=item.get('handOwnColor',False)
        for key in FLAGS:
            if type(value[key]) is not bool:raise ValueError('手臂开关无效：'+key)
        for key,(lo,hi) in BOUNDS.items():
            if type(value[key]) not in (int,float) or not math.isfinite(value[key]) or not lo<=value[key]<=hi:raise ValueError('手臂参数超出范围：'+key)
        for key in ('handColor','sleeveColor'):
            if not isinstance(value[key],str) or not re.fullmatch('#[a-fA-F0-9]{6}',value[key]):raise ValueError('手臂颜色无效：'+key)
        for key,size in [('handPng',(32,32)),('sleeveBasePng',(32,64)),('sleevePng',(32,64))]:
            png=value[key]
            if not isinstance(png,str):raise ValueError('手臂贴图格式无效')
            if png:
                if not png.startswith('data:image/png;base64,') or len(png)>1500000:raise ValueError('手臂贴图须为 PNG')
                image=Image.open(io.BytesIO(base64.b64decode(png.split(',',1)[1],validate=True)))
                if image.size!=size:raise ValueError('手臂贴图尺寸错误')
        d['puppetArms'][i]=value
    return d
def sleeve_mirrored(d,index):
    key=('puppetExtraSleeveSymmetry' if index>=2 else 'sleeveSymmetry') if d.get('puppetSleeveSyncSeparated',False) else ('puppetExtraArmSymmetry' if index>=2 else 'puppetArmSymmetry')
    return index%2==1 and d.get(key,True)

def resolved(d,index):
    mirror=index%2==1 and d.get('puppetExtraArmSymmetry' if index>=2 else 'puppetArmSymmetry',True)
    value=copy.deepcopy(d['puppetArms'][index-1 if mirror else index]);own=d['puppetArms'][index]
    sm=sleeve_mirrored(d,index);sleeve=d['puppetArms'][index-1 if sm else index]
    for key in SLEEVE_FIELDS:value[key]=sleeve[key]
    value['enabled']=own['enabled'];value['sleeveEnabled']=own['sleeveEnabled']
    if mirror:value['shoulderX']*=-1
    if sm:value['sleeveRootX']*=-1
    return value
def compile_textures(p,d,material,cloth_base,pattern_texture,composite,pngbytes):
    defaults(d);d['puppetArms']=copy.deepcopy(d['puppetArms'])
    def encoded(raw):return 'data:image/png;base64,'+base64.b64encode(raw).decode()
    for i,item in enumerate(d['puppetArms']):
        key='puppetHand'+str(i)
        if key in p.get('textures',{}):item['handPng']=encoded(material(p,key))
        key='puppetSleeve'+str(i)
        if i>=2 and key in p.get('textures',{}):
            item['sleeveBasePng']=encoded(pngbytes(cloth_base(p,key)))
            item['sleevePng']=encoded(composite(pattern_texture(p,key),SIZES[key]))
