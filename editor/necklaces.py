import re

def pearl(color='#c5d6ce',highlight='#b7e5ef',dual=False):
    return dict(color=color,highlight=highlight,dual=dual,size=0)

def strand(i=0):
    return dict(pearls=9,size=2.2,thickness=.4,leftX=-5,leftY=0,rightX=5,rightY=0,
                symmetric=True,sag=8+i*4,softness=.7,stringColor='#737e78',colorMode=0,
                primary=pearl(),alternate=pearl('#354d45','#d2ebe2',True),beads=[])

def check_pearl(value):
    if not isinstance(value,dict):raise ValueError('珍珠配色格式错误')
    result=pearl();result.update(value)
    for key in ('color','highlight'):
        if not isinstance(result[key],str) or not re.fullmatch('#[a-fA-F0-9]{6}',result[key]):raise ValueError('项链珍珠颜色格式错误')
    if type(result['dual']) is not bool:raise ValueError('请选择珍珠单色或双色')
    if type(result['size']) not in (float,int) or not 0<=result['size']<=6:raise ValueError('单颗大小须为 0（跟随本层）到 6')
    return result

def validate_necklaces(design):
    count=design.setdefault('necklaceCount',0);items=design.setdefault('necklaces',[])
    if type(count) is not int or not 0<=count<=5:raise ValueError('项链数量须为 0—5')
    if not isinstance(items,list) or len(items)>5:raise ValueError('最多保存五条项链')
    for i in range(len(items),count):items.append(strand(i))
    limits=dict(pearls=(0,32),size=(.6,6),thickness=(.1,2),leftX=(-18,18),rightX=(-18,18),leftY=(-200,200),rightY=(-200,200),sag=(0,26),softness=(0,1),colorMode=(0,2))
    for i,item in enumerate(items):
        if not isinstance(item,dict):raise ValueError('项链设置格式错误')
        result=strand(i);result.update(item)
        for key,(lo,hi) in limits.items():
            v=result[key]
            if type(v) not in (int,float) or not lo<=v<=hi:raise ValueError('项链 '+key+' 超出范围')
            if key in ('pearls','colorMode') and type(v) is not int:raise ValueError('珍珠数量与配色方式须为整数')
        if type(result['symmetric']) is not bool:raise ValueError('项链对称设置错误')
        if not isinstance(result['stringColor'],str) or not re.fullmatch('#[a-fA-F0-9]{6}',result['stringColor']):raise ValueError('项链线颜色格式错误')
        result['primary']=check_pearl(result['primary']);result['alternate']=check_pearl(result['alternate'])
        if not isinstance(result['beads'],list) or len(result['beads'])>32:raise ValueError('逐颗配色最多 32 颗')
        result['beads']=[check_pearl(v) for v in result['beads']]
        items[i]=result
