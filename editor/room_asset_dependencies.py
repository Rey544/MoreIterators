
import io
from pathlib import Path
import re
from PIL import Image

PATH_PATTERN=r'(?:(?:decals|terrainpalettes)/[^/\\:*?"<>|\r\n\x00]+\.png|(?:soundeffects/(?:ambient/)?|loadedsoundeffects/ambient/)[^/\\:*?"<>|\r\n\x00]+\.(?:ogg|wav))'
PATH=re.compile(PATH_PATTERN)


def _name(value):
    return bool(value and len(value)<=180 and value not in ('.','..') and
                not any(c in value for c in '/\\:*?"<>|\r\n\x00') and not value.endswith((' ','.')))


def references(text,label='room'):
    result=[('terrainpalettes/'+name+'.png',) for name in terrain_palette_names(text,label)]
    for raw in re.findall(r'(?m)^PlacedObjects:\s*([^\r\n]*)',text):
        for item in re.split(r',\s*',raw):
            fields=item.split('><')
            if fields[0]!='CustomDecal':continue
            values=fields[3].split('~') if len(fields)>3 else []
            if len(values)<12:raise ValueError('自定义贴花数据无法解析：'+label)
            name=values[11]
            if not _name(name):raise ValueError('自定义贴花名称无效：'+label)
            result.append(('decals/'+name.lower()+'.png',))
    for raw in re.findall(r'(?m)^AmbientSounds:\s*([^\r\n]*)',text):
        for item in re.split(r',\s*',raw):
            if not item.strip():continue
            fields=item.split('><')
            if len(fields)<2:raise ValueError('环境音引用无法解析：'+label)
            name=fields[1]
            if not _name(name) or Path(name).suffix.lower() not in ('.ogg','.wav'):raise ValueError('环境音文件名称无效：'+label)
            
            name=name.lower()
            result.append(('soundeffects/ambient/'+name,'loadedsoundeffects/ambient/'+name,'soundeffects/'+name))
    return list(dict.fromkeys(result))


def terrain_palette_names(text,label='room'):
    result=[]
    values=dict(re.findall(r'(?m)^(TerrainPalette|TerrainFadePalette):[ \t]*([^\r\n]*)',text))
    if values.get('TerrainPalette','').strip()=='NO PALETTE':return []
    for field,raw in values.items():
        name=raw.split(',',1)[0].strip() if field=='TerrainFadePalette' else raw.strip()
        if name=='NO PALETTE':continue
        if not _name(name):raise ValueError('地形色板名称无效：'+label)
        result.append(name.lower())
    
    if result:result.append('rot')
    return list(dict.fromkeys(result))


def optional_references(text,label='room'):
    result=[]
    for name in terrain_palette_names(text,label):
        result.extend([('terrainpalettes/'+name+'_rain.png',),
                       ('terrainpalettes/'+name+'_echo.png','terrainpalettes/default_echo.png')])
    return list(dict.fromkeys(result))


def validate(relative,content):
    if not PATH.fullmatch(relative) or any(part.endswith((' ','.')) or part in ('.','..') for part in relative.split('/')):
        raise ValueError('房间附加素材路径无效：'+relative)
    if len(content)>64*1024*1024:raise ValueError('房间附加素材过大：'+relative)
    if relative.endswith('.png'):
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.format!='PNG' or image.width*image.height>64*1024*1024:raise ValueError('PNG')
                image.verify()
        except (OSError,ValueError) as error:raise ValueError('房间贴花图损坏：'+relative) from error
    elif relative.endswith('.wav'):
        if len(content)<44 or content[:4]!=b'RIFF' or content[8:12]!=b'WAVE':raise ValueError('房间环境音不是 WAV：'+relative)
    elif len(content)<27 or content[:4]!=b'OggS':raise ValueError('房间环境音不是 OGG：'+relative)


def native_ambient_reference(relative,source=None):
    





    if not PATH.fullmatch(relative) or not relative.startswith('loadedsoundeffects/ambient/'):return False
    import storage
    try:
        assets=storage.require_game_root()/'RainWorld_Data/StreamingAssets'
        placeholder=existing(assets,relative)
        if placeholder is None or placeholder.stat().st_size!=0:return False
        if source is not None and Path(source).resolve()!=placeholder.resolve():return False
        def child(root,name):
            matches=[path for path in root.iterdir() if path.name.casefold()==name.casefold()]
            if len(matches)!=1:return None
            path=matches[0]
            if path.is_symlink() or getattr(path,'is_junction',lambda:False)():return None
            return path
        folder=child(assets,'AssetBundles')
        if folder is None or not folder.is_dir():return False
        bundle=child(folder,'loadedsoundeffects_ambient')
        manifest=child(folder,'loadedsoundeffects_ambient.manifest')
        if bundle is None or not bundle.is_file() or bundle.stat().st_size<48:return False
        if manifest is None or not manifest.is_file() or not 0<manifest.stat().st_size<=2*1024*1024:return False
        with bundle.open('rb') as stream:
            if stream.read(8)!=b'UnityFS\0':return False
        text=manifest.read_text('utf-8-sig')
        if not text.startswith('ManifestFileVersion: 0\n') or not re.search(r'(?m)^- Class: 83\s*$',text):return False
        section=re.search(r'(?m)^Assets:\s*\n((?:- [^\r\n]+\r?\n?)*)',text)
        if section is None:return False
        names=[line[2:].strip().casefold() for line in section.group(1).splitlines()]
        return names.count(('assets/'+relative).casefold())==1
    except (OSError,ValueError):return False


def has_native_ambient_reference(candidates):
    return any(native_ambient_reference(relative) for relative in candidates)


def existing(root,relative):
    if not PATH.fullmatch(relative):raise ValueError('房间附加素材路径无效')
    root=Path(root).resolve();path=root
    for part in relative.split('/'):
        if not path.is_dir():return None
        matches=[entry for entry in path.iterdir() if entry.name.casefold()==part.casefold()]
        if len(matches)>1:raise ValueError('房间附加素材大小写冲突：'+relative)
        if not matches:return None
        path=matches[0]
        if path.is_symlink() or getattr(path,'is_junction',lambda:False)():raise ValueError('房间附加素材不能经过链接：'+relative)
    if not path.resolve().is_relative_to(root):raise ValueError('房间附加素材路径越界')
    return path if path.is_file() else None
