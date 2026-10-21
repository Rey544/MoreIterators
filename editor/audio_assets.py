"""Content-addressed MP3 assets. Only explicitly referenced tracks enter a package."""
import base64
import hashlib
import math
from pathlib import Path
import re
import shutil
import tempfile
import storage

MAX_BYTES=10*1024*1024
MAX_SECONDS=600
HASH=re.compile(r'[0-9a-f]{64}')
DESIGN_FIELDS=('musicWork','musicReception','musicReading')

def default_track():return dict(mode='native',asset='',name='',volume=1,loop=True)

def validate_track(raw):
    if raw is None:raw={}
    if not isinstance(raw,dict):raise ValueError('音乐设置格式错误')
    value=default_track();value.update({k:v for k,v in raw.items() if k in value})
    if value['mode'] not in ('native','custom','silent'):raise ValueError('请选择原版、自定义或静音')
    if not isinstance(value['asset'],str) or value['asset'] and not HASH.fullmatch(value['asset']):raise ValueError('音乐资源编号无效')
    if value['mode']=='custom' and not value['asset']:raise ValueError('请先导入 MP3')
    if not isinstance(value['name'],str) or len(value['name'])>120 or any(ord(c)<32 for c in value['name']):raise ValueError('音乐名称格式错误')
    if type(value['volume']) not in (int,float) or not math.isfinite(value['volume']) or not 0<=value['volume']<=1:raise ValueError('音乐音量范围为 0–1')
    if type(value['loop']) is not bool:raise ValueError('音乐循环设置错误')
    return value

def runtime_track(raw):
    track=validate_track(raw)
    return dict(mode=track['mode'],asset=track['asset'] if track['mode']=='custom' else '',volume=track['volume'],loop=track['loop'])

def runtime_design(design):
    for key in DESIGN_FIELDS:design[key]=runtime_track(design.get(key))
    return design

def audit_referenced(documents,root):
    root=Path(root);expected=references(documents)
    actual={p.stem for p in (root/'mi_audio').glob('*.mp3')}
    if actual!=expected:raise ValueError('导出音乐与所选内容不一致')
    for asset in expected:
        data=(root/'mi_audio'/(asset+'.mp3')).read_bytes()
        if hashlib.sha256(data).hexdigest()!=asset or parse_mp3(data)[0]!=data:raise ValueError('音乐资源校验失败：'+asset[:12])
    return {'mi_audio/'+asset+'.mp3' for asset in expected}

def validate_design(design):
    for key in DESIGN_FIELDS:design[key]=validate_track(design.get(key))
    return design

def parse_mp3(data):
    if not isinstance(data,bytes) or not 12<=len(data)<=MAX_BYTES:raise ValueError('MP3 最大为 10 MB')
    offset=0
    while data[offset:offset+3]==b'ID3':
        if len(data)-offset<10 or data[offset+3] not in (2,3,4) or any(x&128 for x in data[offset+6:offset+10]):raise ValueError('MP3 标签损坏')
        size=0
        for n in data[offset+6:offset+10]:size=(size<<7)|n
        offset+=10+size+(10 if data[offset+5]&16 and data[offset+3]==4 else 0)
        if offset>=len(data):raise ValueError('MP3 没有音频帧')
    start=offset;frames=0;seconds=0;format_key=None
    while offset<len(data):
        remaining=len(data)-offset
        if remaining==128 and data[offset:offset+3]==b'TAG' or data[offset]==0 and not any(data[offset:]):break
        if remaining<4:raise ValueError('MP3 音频帧不完整')
        a,b,c,d=data[offset:offset+4]
        version=(b>>3)&3;layer=(b>>1)&3;bitrate_index=c>>4;sample_index=(c>>2)&3
        if a!=255 or b&224!=224 or version==1 or layer!=1 or bitrate_index in (0,15) or sample_index==3:raise ValueError('文件不是有效的 MP3')
        rate=(44100,48000,32000)[sample_index]//(1 if version==3 else 2 if version==2 else 4)
        bitrates=(0,32,40,48,56,64,80,96,112,128,160,192,224,256,320) if version==3 else (0,8,16,24,32,40,48,56,64,80,96,112,128,144,160)
        length=(144000 if version==3 else 72000)*bitrates[bitrate_index]//rate+((c>>1)&1)
        channels=1 if d>>6==3 else 2;current=(version,rate,channels)
        if format_key is not None and current!=format_key:raise ValueError('MP3 采样格式在文件中发生变化')
        if offset+length>len(data):raise ValueError('MP3 音频帧不完整')
        format_key=current;offset+=length;frames+=1;seconds+=(1152 if version==3 else 576)/rate
        if seconds>MAX_SECONDS:raise ValueError('音乐时长不能超过 10 分钟')
    if frames<3:raise ValueError('MP3 没有足够的音频帧')
    # ID3 artwork/comments and trailing tags are not part of the exported asset.
    return data[start:offset],dict(duration=round(seconds,3),sampleRate=format_key[1],channels=format_key[2])

def asset_path(asset):
    if not isinstance(asset,str) or not HASH.fullmatch(asset):raise ValueError('音乐资源编号无效')
    return storage.DATA/'audio'/(asset+'.mp3')

def import_audio(payload):
    if not isinstance(payload,dict):raise ValueError('音乐导入格式错误')
    text=payload.get('data','');name=payload.get('name','')
    if not isinstance(text,str) or len(text)>MAX_BYTES*4//3+100:raise ValueError('MP3 最大为 10 MB')
    if not text.startswith(('data:audio/mpeg;base64,','data:audio/mp3;base64,','data:application/octet-stream;base64,')):raise ValueError('仅支持 MP3')
    if not isinstance(name,str) or not name.lower().endswith('.mp3'):raise ValueError('仅支持 MP3')
    try:data=base64.b64decode(text.split(',',1)[1],validate=True)
    except Exception as error:raise ValueError('MP3 编码损坏') from error
    audio,info=parse_mp3(data);asset=hashlib.sha256(audio).hexdigest();dest=asset_path(asset)
    title=name.replace('\\','/').rsplit('/',1)[-1][:120]
    track=validate_track(dict(mode='custom',asset=asset,name=title,volume=1,loop=True))
    dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists() or hashlib.sha256(dest.read_bytes()).hexdigest()!=asset:
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(dir=dest.parent,suffix='.tmp',delete=False) as output:
                temporary=Path(output.name);output.write(audio)
            temporary.replace(dest)
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
    return dict(track=track,bytes=len(audio),**info)

def references(documents):
    found=set()
    def visit(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in DESIGN_FIELDS or key=='musicTrack':
                    track=validate_track(item)
                    if track['mode']=='custom':found.add(track['asset'])
                else:visit(item)
        elif isinstance(value,(list,tuple)):
            for item in value:visit(item)
    visit(documents);return found

def copy_referenced(documents,destination):
    destination=Path(destination);copied=[]
    for asset in sorted(references(documents)):
        source=asset_path(asset)
        if not source.is_file():raise ValueError('找不到已导入的音乐：'+asset[:12])
        data=source.read_bytes()
        if hashlib.sha256(data).hexdigest()!=asset:raise ValueError('音乐资源校验失败：'+asset[:12])
        target=destination/'mi_audio'/(asset+'.mp3');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);copied.append(target)
    return copied


def write_archive(archive,documents,prefix='assets/audio'):
    files=[]
    for asset in sorted(references(documents)):
        source=asset_path(asset)
        if not source.is_file():raise ValueError('找不到已导入的音乐：'+asset[:12])
        data=source.read_bytes()
        if hashlib.sha256(data).hexdigest()!=asset:raise ValueError('音乐资源校验失败：'+asset[:12])
        path=prefix+'/'+asset+'.mp3';archive.writestr(path,data);files.append(path)
    return files
