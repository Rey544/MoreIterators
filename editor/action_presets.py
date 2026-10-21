"""Shared, local author presets. Applying a preset copies it into the project."""
import copy, json, re, uuid
import dialogue, storage

SCHEMA='moreiterators.action-presets.v1'
BUILTINS=[
    dict(id='builtin-lift-spin-mark',name='举起玩家旋转并开智',kind='action',builtin=True,value=dict(type='sequence',actions=[dict(type='liftSpinPlayer',delay=0,duration=3,offsetX=0,offsetY=70,radius=14,endAngle=360),dict(type='giveMark',delay=0)])),
    dict(id='builtin-still-closed',name='闭眼静止',kind='presentation',builtin=True,value=dict(movement='still',eyes='closed')),
]

def path():return storage.DATA/'action-presets.json'
def _kind(kind):
    if kind not in ('action','presentation'):raise ValueError('预设类型无效')
    return kind
def _name(value):
    if not isinstance(value,str) or not 1<=len(value.strip())<=80 or any(ord(c)<32 for c in value):raise ValueError('预设名称应为 1—80 个字符')
    return value.strip()
def _value(kind,value):
    value=copy.deepcopy(value)
    if kind=='action':
        dialogue.validate_action(value)
        if value['type']=='none':raise ValueError('请先设置动作再保存预设')
    else:
        value=dialogue.validate_presentation(value)
        if all(v=='inherit' for v in value.values()):raise ValueError('请先设置表现再保存预设')
    return value
def _custom():
    if not path().exists():return []
    document=json.loads(path().read_text('utf-8'))
    if not isinstance(document,dict) or document.get('schema')!=SCHEMA or not isinstance(document.get('presets'),list):raise ValueError('预设库损坏，已停止保存')
    result=[];identities=set();names=set()
    for item in document['presets']:
        if not isinstance(item,dict) or not re.fullmatch('[a-f0-9]{32}',str(item.get('id',''))) or item['id'] in identities:raise ValueError('预设库损坏，已停止保存')
        kind=_kind(item.get('kind'));name=_name(item.get('name'));key=(kind,name.casefold())
        if key in names or any(v['kind']==kind and v['name'].casefold()==name.casefold() for v in BUILTINS):raise ValueError('预设库损坏，已停止保存')
        result.append(dict(id=item['id'],name=name,kind=kind,builtin=False,value=_value(kind,item.get('value'))));identities.add(item['id']);names.add(key)
    return result
def listing(kind='action'):
    kind=_kind(kind)
    return copy.deepcopy([v for v in BUILTINS+_custom() if v['kind']==kind])
def save(data,server):
    """Call under the editor server lock to serialize duplicate-name checks."""
    kind=_kind(data.get('kind','action'));name=_name(data.get('name'));value=_value(kind,data.get('value'));custom=_custom();overwrite=data.get('overwriteId')
    if any(v['kind']==kind and v['name'].casefold()==name.casefold() for v in BUILTINS) or isinstance(overwrite,str) and overwrite.startswith('builtin-'):raise ValueError('内置预设不能覆盖，请换一个名称')
    existing=next((v for v in custom if v['kind']==kind and v['name'].casefold()==name.casefold()),None)
    if existing and overwrite!=existing['id']:raise ValueError('已有同名预设，请确认覆盖')
    if overwrite is not None and (not existing or overwrite!=existing['id']):raise ValueError('要覆盖的预设已变化，请重新选择')
    if not existing and len(custom)>=200:raise ValueError('自定义预设已达到 200 个')
    item=dict(id=existing['id'] if existing else uuid.uuid4().hex,name=name,kind=kind,builtin=False,value=value)
    if existing:custom[custom.index(existing)]=item
    else:custom.append(item)
    server.atomic(path(),dict(schema=SCHEMA,presets=custom))
    return dict(ok=True,preset=copy.deepcopy(item),presets=listing(kind))
