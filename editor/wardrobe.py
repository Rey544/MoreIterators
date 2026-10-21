"""Versioned garment configuration. New garments are opt-in; old projects remain intact."""
import copy, math, re

CORE_ORDER=['back','legs','body','neck','gown','sleeves','collar','shawl1','shawl2','shawl3','shawl4','shawl5','frontL','frontR','necklaces','head']
MAX_CUSTOM=12
HARDWARE_ANCHORS=['earL','earR','earDecorationL','earDecorationR','antennaL','antennaR','antennaUpperL','antennaUpperR','antennaLowerL','antennaLowerR']
def panel(key):
    side=-1 if key=='frontL' else 1
    return dict(id=key,enabled=False,type='cloth',width=10,length=27,topWidth=5,
        anchor='shoulders',anchor2='shoulders',u=0 if side<0 else 1,v=0,u2=0 if side<0 else 1,v2=0,
        x=0,y=0,x2=0,y2=0,midX=0,midY=0,sag=2,roundness=.65,elasticity=.65,gravity=1,
        fringe=False,fringeLength=5,fringeColor='#bbc4c7',topColor='#303a40',middleColor='#667079',bottomColor='#abb5bc',grain=.1,
        mirror=False,lockGown=False,rigidRotation=0,bindRow=0,canvasWidth=64,canvasHeight=96)
def shawl(i):
    d=panel('shawl'+str(i));d.update(anchor='sleeveL',anchor2='sleeveR',u=.5,u2=.5,width=23,length=8+i*2,topWidth=0,sag=3,midY=-1,roundness=.9)
    return d
def custom(i):
    d=panel('custom'+str(i));d.update(enabled=True,name='配件 '+str(i),type='rigid',anchor='head',anchor2='head',u=.3,u2=.7,width=12,length=14,topWidth=8,gravity=1)
    return d
def defaults(d):
    d.setdefault('sleeveSymmetry',True);d.setdefault('sleeveLeftEnabled',True);d.setdefault('sleeveRightEnabled',True)
    for k in ('TopColor','MiddleColor','BottomColor','Grain'):d.setdefault('sleeveRight'+k,d.get('sleeve'+k,.12 if k=='Grain' else '#b68b8e'))
    d.setdefault('frontSymmetry',True);d.setdefault('frontPanels',[panel('frontL'),panel('frontR')])
    d.setdefault('shawlCount',0);d.setdefault('shawls',[shawl(i) for i in range(1,6)])
    d.setdefault('accessories',[]);d.setdefault('renderOrder',list(CORE_ORDER))
    for k,v in dict(straightLegs=False,thighLength=10,shinLength=13,legWidth=2.5,kneeSize=3,legElasticity=.7,legSymmetry=True,legSpacing=6,legLeftOffset=0,legRightOffset=0).items():d.setdefault(k,v)
    for k in ('legLength','thighLength','shinLength','legWidth','kneeSize','legElasticity'):d.setdefault('right'+k[0].upper()+k[1:],d.get(k,1))
    return d
def pieces(d):
    return d.get('frontPanels',[])+d.get('shawls',[])+d.get('accessories',[])
def find(d,key):return next((x for x in pieces(d) if x['id']==key),None)
def sizes(d):
    return dict(sleeveR=(32,64),legThigh=(24,48),legKnee=(24,24),legShin=(24,48),legThighR=(24,48),legKneeR=(24,24),legShinR=(24,48),**{x['id']:(x['canvasWidth'],x['canvasHeight']) for x in pieces(d)})
def is_material(key):return key=='sleeveR' or key.startswith(('front','shawl','custom','leg'))
def validate(d):
    defaults(d)
    if type(d['shawlCount']) is not int or not 0<=d['shawlCount']<=5:raise ValueError('披肩层数为 0–5')
    if len(d['frontPanels'])!=2 or len(d['shawls'])!=5 or len(d['accessories'])>MAX_CUSTOM:raise ValueError('服装层数不正确')
    ids=[x.get('id') for x in pieces(d)]
    if ids[:7]!=['frontL','frontR']+['shawl'+str(i) for i in range(1,6)] or len(ids)!=len(set(ids)):raise ValueError('服装编号重复或次序错误')
    anchors=set(ids+['head','body','gown','shoulders','sleeveL','sleeveR','collar','handL','handR','legL','legR','neck']+HARDWARE_ANCHORS)
    bounds=dict(width=(.5,120),length=(1,120),topWidth=(0,80),u=(0,1),v=(0,1),u2=(0,1),v2=(0,1),x=(-80,80),y=(-80,80),x2=(-80,80),y2=(-80,80),midX=(-40,40),midY=(-40,40),sag=(-30,60),roundness=(0,1),elasticity=(0,1),gravity=(0,3),fringeLength=(0,30),grain=(0,.4),rigidRotation=(-180,180))
    for a in pieces(d):
        seed=panel(a['id']);seed.update(a);a.clear();a.update(seed)
        if a['type'] not in ('cloth','rigid'):raise ValueError('请选择布料或硬件')
        if not re.fullmatch(r'(front[LR]|shawl[1-5]|custom(?:[1-9]|1[0-2]))',a['id']):raise ValueError('配件编号无效')
        for k,(lo,hi) in bounds.items():
            if type(a[k]) not in (int,float) or not math.isfinite(a[k]) or not lo<=a[k]<=hi:raise ValueError(a['id']+' '+k+' 超出范围')
        if type(a['bindRow']) is not int or not 0<=a['bindRow']<=10:raise ValueError('绑定横排为 0–10')
        for k in ('canvasWidth','canvasHeight'):
            if type(a[k]) is not int or not 8<=a[k]<=256:raise ValueError('画布尺寸为 8–256 像素')
        for k in ('topColor','middleColor','bottomColor','fringeColor'):
            if not re.fullmatch('#[0-9a-fA-F]{6}',a[k]):raise ValueError('配件颜色无效')
        if a['anchor'] not in anchors or a['anchor2'] not in anchors:raise ValueError('绑定图层不存在')
    # Both anchors may reference other accessories, but never form a dependency cycle.
    graph={x['id']:[x['anchor'],x['anchor2']] for x in pieces(d)}
    def visit(node,chain):
        if node not in graph:return
        if node in chain:raise ValueError('配件绑定形成循环：'+' → '.join(chain+[node]))
        for target in graph[node]:visit(target,chain+[node])
    for key in graph:visit(key,[])
    order=d['renderOrder'];valid=set(CORE_ORDER+ids+[a.get('id') for a in d.get('pearlAccessories',[])])
    if not isinstance(order,list) or len(order)!=len(set(order)) or any(x not in valid for x in order):raise ValueError('图层顺序包含未知或重复项')
    order=order+[x for x in CORE_ORDER+ids if x not in order]
    order.remove('neck')
    covered=['gown','sleeves','collar','head','frontL','frontR']+['shawl'+str(i) for i in range(1,6)]
    order.insert(min(order.index(x) for x in covered),'neck')
    d['renderOrder']=order
    leg_bounds=[('legLength',.7,1.4),('thighLength',3,30),('shinLength',3,36),('legWidth',.5,10),('kneeSize',.5,12),('legElasticity',0,1)]
    bounds=leg_bounds+[('right'+k[0].upper()+k[1:],lo,hi) for k,lo,hi in leg_bounds]+[('legSpacing',0,30),('legLeftOffset',-15,15),('legRightOffset',-15,15)]
    for key,lo,hi in bounds:
        value=d.get(key,1)
        if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('腿部参数超出范围：'+key)
    for key in ['sleeveSymmetry','sleeveLeftEnabled','sleeveRightEnabled','frontSymmetry','straightLegs','legSymmetry']:
        if type(d[key]) is not bool:raise ValueError(key+' 必须是开关')
    return d

def material_config(p,key):
    d=p['design'];a=find(d,key)
    if a:return [a[k] for k in ('topColor','middleColor','bottomColor')],a['grain']
    if key.startswith('leg'):return [d['headColor']]*3,0
    if key=='sleeveR':return [d.get('sleeveRight'+k,d['sleeve'+k]) for k in ('TopColor','MiddleColor','BottomColor')],d.get('sleeveRightGrain',.12)
    return None
