"""Transaction plans for removing only a local project's published room outputs."""
import datetime
import json
import hashlib
import re
from pathlib import Path
import room_bindings
import room_cleanup
import storage
import project_packages

MANIFEST = '.mi-room-bindings.json'
WORLD_PATH = re.compile(r'(?:modify/)?world/[a-z0-9]+/(?:world_[a-z0-9]+|map_[a-z0-9]+|[a-z0-9]+_settingstemplate_[a-z0-9-]+|properties|displayname)\.txt|modify/world/regions\.txt')
ROOM_PATH = re.compile(r'world/[a-z0-9]+-rooms/([A-Z][A-Z0-9]{1,7}_[A-Z0-9_]{1,64})(?:\.txt|_settings\.txt|_[1-9][0-9]*\.png)')
ASSET_PATH = project_packages.OUTPUT_PATH

def safe(base, relative):
    base = Path(base).absolute()
    if base.resolve() != base or not isinstance(relative, str) or '\\' in relative or ':' in relative:
        raise ValueError('房间运行文件路径无效')
    path = base / relative
    if not path.resolve().is_relative_to(base) or any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(base)):
        raise ValueError('房间运行文件路径越界')
    return path

def require_closed():
    if room_cleanup._running_game() is not False:
        raise ValueError('请先退出雨世界，再删除或恢复已应用的迭代器房间。')

def roots(pid):
    result = [('local-room', storage.DATA/'local-mod')]
    installed = storage.installed_mod(pid, required=False)
    if installed is not None:result.append(('installed-room', installed))
    return result

def package_rooms(pid):
    rooms=set()
    for path in project_packages.deployed_paths(pid):
        match=ROOM_PATH.fullmatch(path)
        if match:rooms.add(match[1])
    return rooms

def package_references(pid):
    value=project_packages.archived_metadata(pid)
    result=set()
    for room in (value or {}).get('rooms',[]):
        name=room.get('name')
        if not isinstance(name,str) or not room_bindings.ROOM_RE.fullmatch(name):raise ValueError('项目房间编号无效')
        result.add(name)
        links=room.get('connections')
        if not isinstance(links,list):raise ValueError('项目房间连接无效')
        for link in links:
            if link=='DISCONNECTED':continue
            if not isinstance(link,str) or not room_bindings.ROOM_RE.fullmatch(link):raise ValueError('项目房间连接无效')
            result.add(link)
    return result

def owned_files(pid, project, owned, records, deleted_at=None):
    """Registry ownership plus active references prevents deleting shared/native rooms."""
    if storage.binding(pid):return []
    rooms = set()
    for record in owned:
        if record.get('ownerMod') != 'moreiterators.local':continue
        binding = record.get('roomBinding') or room_bindings.binding(project)
        rooms.add(record['ai'])
        if binding.get('entryMode') == 'copy':rooms.add(record['entry'])
    rooms.update(package_rooms(pid))
    referenced = set()
    for record in records:
        if record.get('projectId') != pid:referenced.update([record.get('ai'), record.get('entry')])
    for file in storage.project_files():
        if file.parent.name == pid:continue
        binding = room_bindings.binding(json.loads(file.read_text('utf-8')))
        referenced.update([binding['ai'], binding['entry']])
        plan = room_bindings._stored_plan(file.parent.name)
        if plan:
            for change in plan.get('connectionChanges', []):
                referenced.update([change.get('room'),change.get('to')])
        referenced.update(package_references(file.parent.name))
    shared = rooms & referenced
    if shared:raise ValueError('房间仍被其他项目连接，未删除：'+', '.join(sorted(shared)))
    cutoff = datetime.datetime.fromisoformat(deleted_at).timestamp() if deleted_at else None
    result = []
    locations = roots(pid)
    package_owned=project_packages.deployed_paths(pid)
    all_packages=[project_packages.output_manifest(base) for _,base in locations]
    for value in all_packages:package_owned.update(value['projects'].get(pid,[]))
    shared_assets={path for value in all_packages for owner,paths in value['projects'].items() if owner!=pid for path in paths}
    for kind, base in locations:
        for room in sorted(rooms):
            if not room_bindings.ROOM_RE.fullmatch(room):raise ValueError('已发布房间名称无效')
            folder = base/'world'/(room.split('_')[0].lower()+'-rooms')
            for file in sorted(folder.glob(room+'*')):
                if not file.is_file() or not re.fullmatch(re.escape(room)+r'(?:\.txt|_settings\.txt|_[1-9][0-9]*\.png)', file.name):continue
                relative = file.relative_to(base).as_posix();safe(base, relative)
                # Old deletion records have no output hashes. Never adopt files edited
                # after deletion as if they were part of the original snapshot.
                if cutoff is not None and file.stat().st_mtime > cutoff:
                    digest=hashlib.sha256(file.read_bytes()).hexdigest()
                    unchanged=False
                    for _,other in locations:
                        baseline=safe(other,relative)
                        if baseline.is_file() and baseline.stat().st_mtime<=cutoff and hashlib.sha256(baseline.read_bytes()).hexdigest()==digest:
                            unchanged=True;break
                    if not unchanged:raise ValueError('删除后房间文件已被修改，未自动清理：'+str(file))
                result.append((file, dict(kind=kind, path=relative)))
        existing={file for file,_ in result}
        for relative in sorted(package_owned-shared_assets):
            file=safe(base,relative)
            if file.is_file() and file not in existing:
                if cutoff is not None and file.stat().st_mtime>cutoff:raise ValueError('删除后项目素材已被修改，未自动清理：'+str(file))
                result.append((file,dict(kind=kind,path=relative)))
    return result

def plan(records, pid):
    """Rebuild shared indices from CURRENT records, never restore an old shared index."""
    result = {}
    compiled = None
    for _, base in roots(pid):
        manifest = safe(base, MANIFEST)
        if not manifest.is_file():continue
        previous = json.loads(manifest.read_text('utf-8'))
        if previous.get('schema') != 'moreiterators.room-bindings.v1' or not isinstance(previous.get('files'), list):
            raise ValueError('房间运行目录损坏，已停止操作')
        managed = set(previous['files'])
        if any(not isinstance(p,str) or not WORLD_PATH.fullmatch(p) for p in managed):raise ValueError('已管理的世界文件路径无效')
        if compiled is None:compiled = room_bindings.compile_worlds(records)
        for relative in managed | set(compiled):
            if not WORLD_PATH.fullmatch(relative):raise ValueError('已管理的世界文件路径无效')
            file = safe(base, relative)
            if file.exists() and relative not in managed:
                raise ValueError('本地模组已有未登记的同名文件，不能覆盖：'+relative)
            content = compiled[relative].encode('utf-8') if relative in compiled else None
            before = file.read_bytes() if file.exists() else None
            if before is not None and content is not None and b'\r\n' in before:
                content = content.replace(b'\n',b'\r\n')
            if before != content:result[file] = content
        value = dict(schema='moreiterators.room-bindings.v1', files=sorted(compiled))
        if previous != value:result[manifest] = json.dumps(value,ensure_ascii=False,indent=2).encode('utf-8')
    active={record['projectId'] for record in records if record.get('ownerMod')=='moreiterators.local'}
    for _,base in roots(pid):
        marker=safe(base,project_packages.OUTPUT_MANIFEST)
        previous=project_packages.output_manifest(base)
        projects={owner:list(paths) for owner,paths in previous['projects'].items() if owner in active}
        for owner in active:
            paths=project_packages.deployed_paths(owner)
            if paths:projects[owner]=sorted(paths)
        value=dict(schema=project_packages.OUTPUT_SCHEMA,projects=projects)
        if value!=previous:result[marker]=json.dumps(value,ensure_ascii=False,indent=2).encode('utf-8')
    return result

def apply(transaction, changes):
    if changes:require_closed()
    for file, content in changes.items():
        if content is None:transaction.remove(file)
        else:transaction.write(file, content)
