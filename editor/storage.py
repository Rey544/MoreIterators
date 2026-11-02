"""Local project storage and explicitly configured content-mod associations."""
from pathlib import Path
import os, json, re
import native_projects
import install_paths

WORKSPACE=Path(__file__).resolve().parent.parent
_developer=(WORKSPACE/'version.json').exists() and not (WORKSPACE/'release-layout.json').exists()
_user_data=(Path.home()/'AppData/LocalLow/Videocult/Rain World/MoreIterators/data' if os.name=='nt'
            else Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'MoreIterators/data')
DATA=Path(os.environ.get('MORE_ITERATORS_DATA',str(WORKSPACE/'data' if _developer else _user_data))).resolve()
CONFIG=DATA/'config.json'
settings=install_paths.read_settings(CONFIG)

def studio_port(value=18747):
    if isinstance(value,bool) or not isinstance(value,int) or not 1024<=value<=65535:
        raise ValueError('studioPort must be an integer between 1024 and 65535')
    return value

STUDIO_PORT=studio_port(settings.get('studioPort',18747))
def locate_game():
    result=install_paths.discover_game(settings,WORKSPACE)
    return Path(result['path']) if result['found'] else Path('.')
GAME=locate_game()
PROJECTS=DATA/'projects'
EXPORTS=DATA/'exports'
RUNTIME=DATA/'runtime'
LINKS=settings.get('linkedMods',[])

def installation_paths():
    """Refresh discovery, never move data or write a discovered path to config.

    Callers caching GAME/ASSETS must refresh those aliases from storage.GAME.
    """
    global GAME
    result=install_paths.discover(settings,WORKSPACE)
    GAME=Path(result['game']['path']) if result['game']['found'] else Path('.')
    return result

def locate_rained():
    game=install_paths.discover_game(settings,WORKSPACE)
    result=install_paths.discover_rained(settings,WORKSPACE,game)
    return Path(result['path']) if result['found'] else None

def configure_installation_paths(selections):
    value=install_paths.save_selection(CONFIG,selections)
    settings.clear();settings.update(value)
    # Existing modules access these shared objects; DATA and linked workspace
    # locations remain exactly as configured before this path-only change.
    LINKS[:]=value.get('linkedMods',[])
    return installation_paths()

def available_game_root():
    # The missing-game sentinel must never turn the working directory into a game.
    if not Path(GAME).is_absolute():return None
    return install_paths.game_root(GAME)


def require_game_root():
    root=available_game_root()
    if root is None:raise ValueError('Rain World was not found. Select RainWorld.exe in the editor settings.')
    return root

def archive_root():
    return Path(settings.get('archiveDirectory',str(DATA/'archive'))).resolve()

def history_directory(pid):
    valid_id(pid)
    return project_root(pid)/pid/'history' if link(pid) else archive_root()/'project-history'/pid

def valid_id(pid):
    if not isinstance(pid,str) or not re.fullmatch('[a-z][a-z0-9-]{0,47}',pid):raise ValueError('项目编号无效')
    return pid

def link(pid):
    valid_id(pid)
    return next((v for v in LINKS if pid in v.get('projects',{})),None)

def project_root(pid):
    v=link(pid)
    return Path(v['workspace'])/'data/projects' if v else PROJECTS

def project_file(pid):return project_root(pid)/valid_id(pid)/'project.json'

def project_files():
    result=list(PROJECTS.glob('*/project.json'))
    for v in LINKS:
        for pid in v.get('projects',{}):
            f=project_file(pid)
            if f.exists():result.append(f)
    return sorted(result,key=lambda f:f.parent.name)

def purge_marker(pid):return DATA/'project-tombstones'/(valid_id(pid)+'.json')

def assert_not_purged(pid):
    if purge_marker(pid).exists():raise ValueError('此项目已永久删除；旧页面不能恢复，请新建项目')

def load_project(pid):
    assert_not_purged(pid)
    return json.loads(project_file(pid).read_text('utf-8'))

def target_mod(pid):
    v=link(pid)
    return Path(v['workspace'])/'mod' if v else DATA/'local-mod'

def installed_mod(pid,required=True):
    v=link(pid)
    game=require_game_root() if required else available_game_root()
    if game is None:return None
    return game/'RainWorld_Data/StreamingAssets/mods'/(v['folder'] if v else 'more_iterators_local')

def binding(pid):
    v=link(pid)
    return v['projects'][pid] if v else native_projects.binding(pid)

def design_path(pid,oid):return target_mod(pid)/'designs'/(oid+'.json') if link(pid) else RUNTIME/(oid+'.json')

def legacy_asset(name):
    # Linked editor assets are not part of the distributable creator.
    if not re.fullmatch(r'[a-z0-9-]+\.(json|js)',name):raise ValueError('素材名称无效')
    for v in LINKS:
        f=Path(v['workspace'])/'editor'/name
        if f.exists():return f
    return None

def sync_design(pid,oid):
    import shutil
    v=link(pid)
    if not v:return
    source=design_path(pid,oid)
    installed=installed_mod(pid)
    if installed.exists():
        destination=installed/'designs'/source.name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)

def registry_record(p,ai,entry,oid):
    v=link(p['projectId'])
    r=dict(projectId=p['projectId'],name=p['name'],ai=ai,entry=entry,oracleId=oid,ownerMod=v['id'] if v else 'moreiterators.local')
    if v:r['design']='designs/'+oid+'.json'
    native=native_projects.binding(p['projectId'])
    if native:r.update(native)
    elif not v and p.get('roomBinding'):
        r['roomBinding']=p['roomBinding'];r['exitNode']=p['roomBinding']['aiNode'];r['entryNode']=p['roomBinding']['entryNode']
    elif not v and p.get('waitingRoomTemplate')=='mi-waiting':r.update(exitNode=1,entryNode=0)
    return r
