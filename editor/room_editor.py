"""Open per-project Rained sources and import their rendered game rooms."""
from pathlib import Path
import shutil, subprocess
import storage
import waiting_room

def rained_root():
    configured=storage.settings.get('rainedExecutable')
    exe=Path(configured) if configured else storage.WORKSPACE.parent/'工具/Rained_2.4.0/Rained.exe'
    if not exe.is_file():raise ValueError('未找到本地 Rained，请在 data/config.json 设置 rainedExecutable')
    return exe

def prepare(pid,kind,roomnames):
    if kind not in ('ai','entry'):raise ValueError('房间类型无效')
    p=storage.load_project(storage.valid_id(pid));ai,entry,_=roomnames(p)
    if kind=='entry' and p.get('roomBinding',{}).get('entryMode')=='existing':raise ValueError('此外部房间由原版或其他模组提供，不能覆盖其 Rained 工程。')
    name=ai if kind=='ai' else entry
    exe=rained_root();root=exe.parent/'Data/LevelEditorProjects'
    if kind=='entry':p=waiting_room.prepare(p)
    dest=storage.project_file(pid).parent/'rooms'/(name+'.txt')
    if dest.exists():return exe,dest
    candidates=[root/(name+'.txt')];bundled=None
    if not storage.binding(pid):
        candidates += [root/'EditorSamples/SS_AI.txt',root/'World/Other/SS_AI.txt'] if kind=='ai' else []
        if kind=='entry':
            bundled=waiting_room.editable_source(p,name)
            if bundled:candidates.insert(0,bundled.with_suffix('.txt'))
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
    subprocess.Popen([str(exe),str(file)],cwd=str(exe.parent))
    return dict(ok=True,room=file.stem,path=str(file))

def cache_base(pid,name):
    storage.valid_id(pid)
    return storage.project_file(pid).parent/'rooms/rendered'/name

def rendered_source(pid,kind,roomnames):
    """Return Rained's game-ready output, never its incompatible editor source."""
    if kind not in ('ai','entry'):raise ValueError('房间类型无效')
    p=storage.load_project(storage.valid_id(pid));ai,entry,_=roomnames(p)
    name=ai if kind=='ai' else entry
    source=rained_root().parent/'Data/Levels'/name
    if not Path(str(source)+'.txt').is_file():
        raise ValueError('Rained 尚未渲染 '+name+'；请在 Rained 保存后按 Ctrl+R，再回到这里同步。')
    text=Path(str(source)+'.txt').read_text('utf-8-sig').splitlines()
    if len(text)<4:raise ValueError('Rained 渲染结果不完整：'+name)
    cameras=[v.strip() for v in text[3].split('|') if v.strip()]
    if not cameras:raise ValueError('Rained 渲染结果没有相机：'+name)
    for i in range(1,len(cameras)+1):
        if not Path(str(source)+'_'+str(i)+'.png').is_file():raise ValueError('Rained 渲染结果缺少相机图片：'+name+'_'+str(i)+'.png')
    return source

def render(pid,kind,roomnames):
    """Render the saved project headlessly so sync never depends on a manual Ctrl+R."""
    exe,source=prepare(pid,kind,roomnames)
    app_data=storage.project_file(pid).parent/'rooms/.rained-renderer';app_data.mkdir(parents=True,exist_ok=True)
    try:
        result=subprocess.run([str(exe),'--no-splash-screen','--app-data',str(app_data),'--data',str(exe.parent/'Data'),'--render','--threads','1',str(source)],cwd=str(exe.parent),capture_output=True,timeout=180)
    except subprocess.TimeoutExpired:
        raise ValueError('Rained 渲染超过 180 秒，房间未同步；请确认房间能在 Rained 正常渲染后重试。') from None
    if result.returncode:
        message=(result.stdout+result.stderr).decode('utf-8',errors='replace')[-2000:]
        raise ValueError('Rained 渲染失败：'+message)
    return rendered_source(pid,kind,roomnames)

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
    source=render(pid,kind,roomnames)
    name=source.name;dest=cache_base(pid,name);dest.parent.mkdir(parents=True,exist_ok=True)
    lines=Path(str(source)+'.txt').read_text('utf-8-sig').splitlines()
    cameras=[v.strip() for v in lines[3].split('|') if v.strip()]
    shutil.copy2(Path(str(source)+'.txt'),Path(str(dest)+'.txt'))
    for old in dest.parent.glob(name+'_*.png'):old.unlink()
    for i in range(1,len(cameras)+1):shutil.copy2(Path(str(source)+'_'+str(i)+'.png'),Path(str(dest)+'_'+str(i)+'.png'))
    shutil.copy2(settings_source,Path(str(dest)+'_settings.txt'))
    return dict(ok=True,room=name,path=str(dest),cameras=len(cameras))
