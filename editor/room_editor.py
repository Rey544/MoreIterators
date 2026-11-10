"""Open per-project Rained sources and import their rendered game rooms."""
from pathlib import Path
import json, os, shutil, subprocess, hashlib
import storage
import waiting_room
import desktop_launch

def rained_root():
    exe=storage.locate_rained()
    if exe is None:raise ValueError('Rained was not found. Select Rained.exe in the editor settings.')
    return exe

def rained_data_root(exe=None):
    
    exe=exe or rained_root()
    preferences=[(exe.parent/'config/preferences.json',exe.parent/'Data')]
    if os.name=='nt':
        profile=Path(os.environ.get('APPDATA',str(Path.home()/'AppData/Roaming')))/'rained'
        preferences.append((profile/'config/preferences.json',profile/'Data'))
    else:
        preferences.append((Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'rained/preferences.json',
                            Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'rained/Data'))
    for file,default in preferences:
        if not file.is_file():continue
        try:
            settings=json.loads(file.read_text('utf-8-sig'))
            value=settings.get('dataPath',settings.get('DataPath',str(default)))
            if not isinstance(value,str) or not value.strip():raise ValueError()
            root=Path(value)
            if not root.is_absolute():root=exe.parent/root
            if not root.is_dir():raise ValueError()
            return root.resolve()
        except (OSError,ValueError,AttributeError):
            raise ValueError('Rained 素材目录无效，请先在 Rained 完成初始配置。') from None
    root=exe.parent/'Data'
    if not root.is_dir():raise ValueError('Rained 素材目录无效，请先在 Rained 完成初始配置。')
    return root.resolve()

def prepare(pid,kind,roomnames):
    if kind not in ('ai','entry'):raise ValueError('房间类型无效')
    p=storage.load_project(storage.valid_id(pid));ai,entry,_=roomnames(p)
    if kind=='entry' and p.get('roomBinding',{}).get('entryMode')=='existing':raise ValueError('此外部房间由原版或其他模组提供，不能覆盖其 Rained 工程。')
    name=ai if kind=='ai' else entry
    exe=rained_root()
    if kind=='entry':p=waiting_room.prepare(p)
    dest=storage.project_file(pid).parent/'rooms'/(name+'.txt')
    if dest.exists():return exe,dest
    bundled=waiting_room.editable_source(p,name) if kind=='entry' and not storage.binding(pid) else None
    if bundled:candidates=[bundled.with_suffix('.txt')]
    else:
        root=rained_data_root(exe)/'LevelEditorProjects'
        candidates=[root/(name+'.txt')]
        if kind=='ai' and not storage.binding(pid):candidates += [root/'EditorSamples/SS_AI.txt',root/'World/Other/SS_AI.txt']
    source=next((f for f in candidates if f.is_file()),None)
    if source is None:raise ValueError('未找到 '+name+' 的 Rained 源工程；不会把游戏导出文件冒充可编辑工程')
    # Rained's source starts with a nested geometry array, unlike a rendered room.
    if not source.read_text('utf-8-sig').lstrip().startswith('[[['):raise ValueError('房间源工程格式不正确')
    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    light=source.with_suffix('.png')
    if light.exists():shutil.copy2(light,dest.with_suffix('.png'))
    if bundled and source==bundled.with_suffix('.txt'):
        cached=cached_source(pid,name)
        if cached:cached.with_suffix('.txt').touch()
    return exe,dest

def open_room(pid,kind,roomnames):
    exe,file=prepare(pid,kind,roomnames)
    desktop_launch.open_rained(exe,file)
    return dict(ok=True,room=file.stem,path=str(file))

def cache_base(pid,name):
    storage.valid_id(pid)
    return storage.project_file(pid).parent/'rooms/rendered'/name

def rendered_source(pid,kind,roomnames,data_root=None):
    """Return Rained's game-ready output, never its incompatible editor source."""
    if kind not in ('ai','entry'):raise ValueError('房间类型无效')
    p=storage.load_project(storage.valid_id(pid));ai,entry,_=roomnames(p)
    name=ai if kind=='ai' else entry
    source=(data_root if data_root is not None else rained_data_root())/'Levels'/name
    if not Path(str(source)+'.txt').is_file():
        raise ValueError('Rained 尚未渲染 '+name+'；请在 Rained 保存后按 Ctrl+R，再回到这里同步。')
    text=Path(str(source)+'.txt').read_text('utf-8-sig').splitlines()
    if len(text)<4:raise ValueError('Rained 渲染结果不完整：'+name)
    cameras=[v.strip() for v in text[3].split('|') if v.strip()]
    if not cameras:raise ValueError('Rained 渲染结果没有相机：'+name)
    for i in range(1,len(cameras)+1):
        if not Path(str(source)+'_'+str(i)+'.png').is_file():raise ValueError('Rained 渲染结果缺少相机图片：'+name+'_'+str(i)+'.png')
    return source

def render(pid,kind,roomnames,source_hashes=None):
    """Render the saved project headlessly so sync never depends on a manual Ctrl+R."""
    exe,source=prepare(pid,kind,roomnames)
    if source_hashes is not None:
        source_hashes.update({file.name:hashlib.sha256(file.read_bytes()).hexdigest() for file in (source,source.with_suffix('.png')) if file.is_file()})
    data=rained_data_root(exe)
    app_data=storage.project_file(pid).parent/'rooms/.rained-renderer';app_data.mkdir(parents=True,exist_ok=True)
    try:
        result=subprocess.run([str(exe),'--no-splash-screen','--app-data',str(app_data),'--data',str(data),'--render','--threads','1',str(source)],cwd=str(exe.parent),capture_output=True,timeout=180)
    except subprocess.TimeoutExpired:
        raise ValueError('Rained 渲染超过 180 秒，房间未同步；请确认房间能在 Rained 正常渲染后重试。') from None
    if result.returncode:
        message=(result.stdout+result.stderr).decode('utf-8',errors='replace')[-2000:]
        raise ValueError('Rained 渲染失败：'+message)
    return rendered_source(pid,kind,roomnames,data_root=data)

def cached_source(pid,name):
    source=cache_base(pid,name)
    return source if Path(str(source)+'.txt').is_file() and Path(str(source)+'_settings.txt').is_file() else None

def ensure_synced(pid,name):
    """Do not silently deploy an older render after a saved Rained edit."""
    source=storage.project_file(pid).parent/'rooms'/(name+'.txt')
    if not source.is_file():return
    cached=cached_source(pid,name)
    if cached is None or source.stat().st_mtime_ns>Path(str(cached)+'.txt').stat().st_mtime_ns:
        raise ValueError(name+' 有尚未同步的 Rained 修改；请先在 Rained 保存，再点击对应的“同步等待房间”或“同步演算室”，然后重新应用或导出。')

def import_render(pid,kind,roomnames,settings_source):
    """Snapshot a Rained render into this project so deploy and export use it."""
    settings_source=Path(settings_source)
    if not settings_source.is_file():raise ValueError('缺少房间设置模板：'+str(settings_source))
    source_hashes={}
    source=render(pid,kind,roomnames,source_hashes)
    name=source.name;dest=cache_base(pid,name);dest.parent.mkdir(parents=True,exist_ok=True)
    lines=Path(str(source)+'.txt').read_text('utf-8-sig').splitlines()
    cameras=[v.strip() for v in lines[3].split('|') if v.strip()]
    
    writes={Path(str(dest)+'.txt'):Path(str(source)+'.txt').read_bytes(),
            Path(str(dest)+'_settings.txt'):settings_source.read_bytes()}
    for i in range(1,len(cameras)+1):writes[Path(str(dest)+'_'+str(i)+'.png')]=Path(str(source)+'_'+str(i)+'.png').read_bytes()
    import room_migration
    transaction=room_migration.Files()
    try:
        for file,content in writes.items():transaction.write(file,content)
        for old in dest.parent.glob(name+'_*.png'):
            if old not in writes:transaction.remove(old)
        import room_source_choices
        if source_hashes:
            record=room_source_choices.pairing_record(pid,name)
            if record['sourceHashes']!=source_hashes:raise room_source_choices.RoomChoiceError('room_choices_stale')
            transaction.json(dest.with_name(name+'.source.json'),record)
    except Exception:
        transaction.rollback()
        raise
    return dict(ok=True,room=name,path=str(dest),cameras=len(cameras))
