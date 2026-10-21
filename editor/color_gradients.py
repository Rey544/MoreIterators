"""Optional colour ramps; the original solid appearance remains the default."""
import copy
import math
import re

KEYS=('armGradient','cableThinGradient','cableThickGradient','headCableAGradient','headCableBGradient')

def number(value,low,high,path):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError(path+' 超出范围')
    return value

def color(value,path):
    if not isinstance(value,str) or not re.fullmatch('#[0-9a-fA-F]{6}',value):raise ValueError(path+' 颜色格式无效')
    return value

def flag(value,path):
    if type(value) is not bool:raise ValueError(path+' 开关格式无效')
    return value

def ramp(raw,path):
    if not isinstance(raw,dict):raise ValueError(path+' 渐变格式无效')
    stops=raw.get('stops',[])
    if not isinstance(stops,list) or len(stops)>5:raise ValueError(path+' 最多五个色标')
    clean=[]
    for stop in stops:
        if not isinstance(stop,dict):raise ValueError(path+' 色标格式无效')
        clean.append(dict(position=number(stop.get('position'),0,1,path),color=color(stop.get('color'),path)))
    if len({x['position'] for x in clean})!=len(clean):raise ValueError(path+' 色标位置不能重复')
    return dict(enabled=flag(raw.get('enabled',False),path),stops=sorted(clean,key=lambda x:x['position']))

def validate(d):
    for key in KEYS:d[key]=ramp(d.get(key,{}),key)
    raw=d.get('roomGradient',{})
    if not isinstance(raw,dict):raise ValueError('房间渐变格式无效')
    direction=raw.get('direction','radial')
    if direction not in ('radial','horizontal','vertical'):raise ValueError('房间渐变方向无效')
    render_mode=raw.get('renderMode','lighting')
    if render_mode not in ('lighting','overlay'):raise ValueError('房间渐变混合模式无效')
    corners=raw.get('corners',[])
    if not isinstance(corners,list) or len(corners)>4:raise ValueError('房间角落光晕最多四个')
    clean=[]
    for item in corners:
        if not isinstance(item,dict):raise ValueError('角落光晕格式无效')
        clean.append(dict(enabled=flag(item.get('enabled',False),'角落光晕'),color=color(item.get('color','#ffffff'),'角落光晕'),
            opacity=number(item.get('opacity',.18),0,1,'角落光晕'),radius=number(item.get('radius',.5),.05,2,'角落光晕')))
    d['roomGradient']=dict(enabled=flag(raw.get('enabled',False),'房间渐变'),direction=direction,renderMode=render_mode,opacity=number(raw.get('opacity',.18),0,1,'房间渐变'),ramp=ramp(raw.get('ramp',{}),'房间渐变'),corners=clean)
    return d

