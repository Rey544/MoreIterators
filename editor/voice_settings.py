"""Opt-in native iterator syllables; no audio files are added to a package."""
import math,re

def defaults():
    return dict(enabled=False,bank='pebbles',unmarkedOnly=False,speed=1,pitch=1,volume=.35,
                shortWeight=50,mediumWeight=35,longWeight=15,echo=0,muffle=0,electric=0,chaos=0,
                repeat=True,reverse=True,split=True,templateId='pebbles',templates=[])

def runtime(raw):
    value=validate(raw)
    return {key:item for key,item in value.items() if key not in ('templateId','templates')}

def validate(raw):
    if raw is None:raw={}
    if not isinstance(raw,dict):raise ValueError('语音设置格式错误')
    value=defaults();value.update({key:item for key,item in raw.items() if key in value})
    for key in ('enabled','unmarkedOnly','repeat','reverse','split'):
        if type(value[key]) is not bool:raise ValueError('语音开关必须为开启或关闭')
    if value['bank'] not in ('pebbles','moon'):raise ValueError('请选择原版迭代器声音库')
    for key,low,high in (('speed',.25,3),('pitch',.2,3),('volume',0,1),('echo',0,1),('muffle',0,1),('electric',0,1),('chaos',0,1)):
        item=value[key]
        if type(item) not in (int,float) or not math.isfinite(item) or not low<=item<=high:raise ValueError('语音参数超出范围：'+key)
    for key in ('shortWeight','mediumWeight','longWeight'):
        if type(value[key]) is not int or not 0<=value[key]<=100:raise ValueError('音节权重范围为 0–100 的整数')
    if sum(value[key] for key in ('shortWeight','mediumWeight','longWeight'))==0:raise ValueError('至少保留一种音节')
    if not isinstance(value['templates'],list) or len(value['templates'])>32:raise ValueError('最多保存 32 个声音模板')
    templates=[];ids={'pebbles','moon'}
    for item in value['templates']:
        if not isinstance(item,dict):raise ValueError('声音模板格式错误')
        tid=item.get('id');name=item.get('name');settings=item.get('settings')
        if not isinstance(tid,str) or not re.fullmatch(r'voice-[a-zA-Z0-9_-]{1,64}',tid) or tid in ids:raise ValueError('声音模板编号无效或重复')
        if not isinstance(name,str) or not name.strip() or len(name)>60 or any(ord(c)<32 for c in name):raise ValueError('声音模板名称需要 1–60 个字符')
        if not isinstance(settings,dict):raise ValueError('声音模板格式错误')
        # Presets contain timbre, never recursive libraries or playback switches.
        clean=validate({key:item for key,item in settings.items() if key not in ('templates','templateId')})
        clean={key:item for key,item in clean.items() if key not in ('enabled','unmarkedOnly','templates','templateId')}
        templates.append(dict(id=tid,name=name.strip(),settings=clean));ids.add(tid)
    value['templates']=templates
    if not isinstance(value['templateId'],str) or value['templateId'] not in ids:raise ValueError('选择的声音模板不存在')
    return value

def validate_design(design):
    design['voice']=validate(design.get('voice'))
    return design
