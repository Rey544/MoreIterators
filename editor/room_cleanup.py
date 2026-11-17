"""Preview and remove only unchanged, retired, transaction-recorded room outputs."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
import room_bindings
import storage

SCHEMA = 'moreiterators.room-ownership.v1'


def _file(pid):
    return storage.project_file(pid).parent / 'room-ownership.json'


def _root(pid, scope, required=True):
    if scope == 'installed':
        base = storage.installed_mod(pid, required=required)
        if base is None:return None
    elif scope == 'local':base = storage.DATA / 'local-mod'
    elif scope == 'rendered':base = storage.project_file(pid).parent / 'rooms/rendered'
    elif scope == 'source':base = storage.project_file(pid).parent / 'rooms'
    else:raise ValueError('旧房间记录的输出位置无效')
    absolute = base.absolute()
    resolved = absolute.resolve()
    if str(absolute).casefold() != str(resolved).casefold():
        raise ValueError('旧房间输出根目录存在链接或路径别名，已停止清理')
    return resolved


def _resolve(pid, name, item, required=True):
    root = _root(pid, item.get('scope'), required=required)
    relative = item.get('path')
    prefix = '' if item['scope'] in ('rendered','source') else 'world/' + name.split('_')[0].lower() + '-rooms/'
    suffix = r'(?:\.txt|\.png)' if item['scope']=='source' else r'(?:\.txt|_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|_mi_background\.json|_[1-9][0-9]*\.png|\.source\.json)'
    pattern = re.escape(prefix + name) + suffix
    if not isinstance(relative, str) or not re.fullmatch(pattern, relative):
        raise ValueError('旧房间记录包含不属于该房间的路径：' + str(relative))
    if root is None:return None
    file = (root / relative).resolve()
    if not file.is_relative_to(root) or file.relative_to(root).as_posix().casefold() != relative.casefold():
        raise ValueError('旧房间记录的路径越界或存在链接，已停止清理')
    return file


def _hash(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def _read(pid):
    file = _file(pid)
    if not file.exists():
        return dict(schema=SCHEMA, projectId=pid, generation='', rooms=[])
    value = json.loads(file.read_text('utf-8'))
    if not isinstance(value, dict) or value.get('schema') != SCHEMA or value.get('projectId') != pid or not isinstance(value.get('rooms'), list):
        raise ValueError('房间归属记录无效，无法安全清理')
    names = set()
    for room in value['rooms']:
        if not isinstance(room, dict) or not isinstance(room.get('name'), str) or not room_bindings.ROOM_RE.fullmatch(room['name']) or room['name'] in names or room.get('kind') not in ('ai', 'entry') or type(room.get('retired')) is not bool or not isinstance(room.get('files'), list):
            raise ValueError('房间归属记录包含无效房间')
        names.add(room['name'])
        paths = set()
        for item in room['files']:
            if not isinstance(item, dict) or not isinstance(item.get('sha256'), str) or not re.fullmatch('[a-f0-9]{64}', item['sha256']) or type(item.get('size')) is not int or item['size'] < 0:
                raise ValueError('房间归属记录缺少有效的文件校验')
            path = _resolve(pid, room['name'], item, required=False)
            if path is None:path = (item['scope'], item['path'])
            if path in paths:
                raise ValueError('房间归属记录包含重复文件')
            paths.add(path)
    return value


def record_migration(transaction, pid, old, new, written):
    """Called only after successful output writes, within the migration transaction."""
    if storage.binding(pid):
        raise ValueError('原版或关联模组的房间不能记为本项目所有')
    value = _read(pid)
    rooms = {item['name']: item for item in value['rooms']}
    old_owned = {'ai': old['ai']}
    new_owned = {'ai': new['ai']}
    if old['entryMode'] == 'copy': old_owned['entry'] = old['entry']
    if new['entryMode'] == 'copy': new_owned['entry'] = new['entry']
    for kind, name in old_owned.items():
        if name not in new_owned.values():
            room = rooms.setdefault(name, dict(name=name, kind=kind, files=[]))
            room['retired'] = True
    for kind, name in new_owned.items():
        files = []
        for scope, relative in written:
            if not re.fullmatch(re.escape(name) + r'(?:\.txt|_settings\.txt|_mi_background\.json|_[1-9][0-9]*\.png)', Path(relative).name):
                continue
            item = dict(scope=scope, path=relative)
            file = _resolve(pid, name, item)
            item.update(sha256=_hash(file), size=file.stat().st_size)
            files.append(item)
        if not files:
            raise ValueError('迁移没有生成可核验的房间文件：' + name)
        rooms[name] = dict(name=name, kind=kind, retired=False, files=files)
    value.update(generation=uuid.uuid4().hex, rooms=sorted(rooms.values(), key=lambda item: item['name']))
    transaction.json(_file(pid), value)


def prepare_migration(pid, old, new, records, managed):
    if storage.binding(pid):raise room_bindings.RoomBindingError('migrationForeignOwner',room=old['ai'])
    old_names={old['ai']}
    if old['entryMode']=='copy':old_names.add(old['entry'])
    current_names={new['ai'],new['entry']}
    retired=old_names-current_names
    if not retired:return dict(names=[],files=[],backup=None)
    for project in room_bindings._projects():
        if project['projectId']==pid:continue
        binding=room_bindings.binding(project)
        referenced=retired.intersection((binding['ai'],binding['entry']))
        if referenced:
            raise room_bindings.RoomBindingError('migrationProjectReference',room=sorted(referenced)[0],name=str(project.get('name',project['projectId'])))
    for record in records:
        referenced=retired.intersection((record.get('ai'),record.get('entry')))
        if record.get('projectId')!=pid and referenced:
            raise room_bindings.RoomBindingError('migrationRegistryReference',room=sorted(referenced)[0],project=str(record.get('projectId','')))
    ledger=_read(pid);known={item['name']:item for item in ledger['rooms']}
    registered=any(record.get('projectId')==pid and record.get('ownerMod')=='moreiterators.local' and record.get('ai')==old['ai'] and record.get('entry')==old['entry'] for record in records)
    root=storage.project_file(pid).parent
    files=[]
    for name in sorted(retired):
        rendered=_root(pid,'rendered')/(name+'.txt')
        source=_root(pid,'source')/(name+'.txt')
        project_evidence=rendered.is_file() or source.is_file()
        world_evidence=False
        for relative in managed:
            if not re.fullmatch(r'(?:modify/)?world/[a-z0-9]+/world_[a-z0-9]+\.txt',relative):continue
            world=_root(pid,'local')/relative
            if world.is_file() and any(row['name']==name for row in room_bindings.parse_world(world.read_text('utf-8-sig'),name.split('_')[0])):world_evidence=True
        shared_evidence=registered or bool(known.get(name,{}).get('files')) or project_evidence and world_evidence
        for scope in ('source','rendered','local','installed'):
            base=_root(pid,scope)
            directory=base if scope in ('source','rendered') else base/'world'/(name.split('_')[0].lower()+'-rooms')
            for file in sorted(directory.glob(name+'*')):
                suffix=r'(?:\.txt|\.png)' if scope=='source' else r'(?:\.txt|_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|_mi_background\.json|_[1-9][0-9]*\.png|\.source\.json)'
                if not re.fullmatch(re.escape(name)+suffix,file.name):continue
                relative=file.relative_to(base).as_posix()
                resolved=_resolve(pid,name,dict(scope=scope,path=relative))
                if not resolved.is_file():raise room_bindings.RoomBindingError('migrationPath',file=relative)
                if scope in ('local','installed') and not shared_evidence:
                    raise room_bindings.RoomBindingError('migrationOwnership',room=name)
                files.append(dict(room=name,scope=scope,path=relative,file=resolved,sha256=_hash(resolved),size=resolved.stat().st_size))
    import project_packages
    for scope in ('local','installed'):
        manifest=project_packages.output_manifest(_root(pid,scope))
        shared={name for owner,paths in manifest['projects'].items() if owner!=pid for name in paths}
        for item in files:
            if item['scope']==scope and item['path'] in shared:raise room_bindings.RoomBindingError('migrationSharedFile',file=item['path'])
    backup=root/'room-backups'/('rename-'+uuid.uuid4().hex)
    if not backup.resolve().is_relative_to(root.resolve()):raise room_bindings.RoomBindingError('migrationPath',file=str(backup))
    return dict(names=sorted(retired),files=files,backup=backup)


def backup_migration(transaction,pid,prepared,old,new):
    if not prepared['names']:return
    backup=prepared['backup'];entries=[]
    for item in prepared['files']:
        file=item['file']
        if not file.is_file() or _hash(file)!=item['sha256']:raise room_bindings.RoomBindingError('migrationFileChanged',room=item['room'],file=item['path'])
        relative=Path(item['scope'])/item['path']
        transaction.write(backup/relative,file.read_bytes())
        entries.append({key:item[key] for key in ('room','scope','path','sha256','size')})
    root=storage.project_file(pid).parent
    for name in ('project.json','room-binding-plan.json','room-package.json','room-ownership.json'):
        file=root/name
        if file.is_file():transaction.write(backup/'metadata'/name,file.read_bytes())
    transaction.json(backup/'manifest.json',dict(schema='moreiterators.room-rename-backup.v1',projectId=pid,oldBinding=old,newBinding=new,files=entries))


def retire_migration(transaction,pid,prepared):
    if not prepared['names']:return
    references=_references(prepared['names'],details=True)
    for name,reasons in references.items():
        if reasons:
            kind,source=reasons[0]
            key,parameter={'project':('migrationProjectReference','name'),'registry':('migrationRegistryReference','project'),'world':('migrationWorldReference','file')}[kind]
            raise room_bindings.RoomBindingError(key,room=name,**{parameter:source})
    for item in prepared['files']:
        file=item['file']
        if not file.is_file() or _hash(file)!=item['sha256']:raise room_bindings.RoomBindingError('migrationFileChanged',room=item['room'],file=item['path'])
        transaction.remove(file)
    ledger=_read(pid)
    ledger['rooms']=[room for room in ledger['rooms'] if room['name'] not in prepared['names']]
    ledger['generation']=uuid.uuid4().hex
    transaction.json(_file(pid),ledger)


def _running_game():
    if os.name != 'nt': return None
    try:
        result = subprocess.run([str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/tasklist.exe'),
                                 '/FI', 'IMAGENAME eq RainWorld.exe', '/FO', 'CSV', '/NH'], capture_output=True, timeout=5, check=True)
        return bool(re.search(rb'(?im)^"rainworld\.exe",', result.stdout))
    except (OSError, subprocess.SubprocessError):
        return None


def _game_blockers():
    reasons = []
    for file in (storage.RUNTIME / 'creator/heartbeat.json', storage.RUNTIME / 'creator/status.json'):
        try:
            if not file.exists() or time.time() - file.stat().st_mtime > 30: continue
            value = json.loads(file.read_text('utf-8'))
            room = value.get('room', value.get('currentRoom', ''))
            reasons.append('游戏仍有最近的运行状态' + ('（' + str(room) + '）' if room else '') + '，请退出游戏后刷新。')
        except (OSError, ValueError, AttributeError):
            reasons.append('无法确认最近游戏状态，请退出游戏后重新检查。')
    running = _running_game()
    if running is True: reasons.append('游戏仍在运行，请退出游戏后再清理旧房间。')
    elif running is None: reasons.append('无法确认游戏已退出，暂不允许清理旧房间。')
    return sorted(set(reasons))


def _references(names,details=False):
    result = {name: [] for name in names}
    if not result: return result
    for project in room_bindings._projects():
        binding = room_bindings.binding(project)
        for name in names:
            if name in (binding['ai'], binding['entry']):
                source=str(project.get('name',project['projectId']))
                result[name].append(('project',source) if details else '项目仍绑定此房间：'+source)
    registry = storage.RUNTIME / 'creator/registry.json'
    if registry.exists():
        records = json.loads(registry.read_text('utf-8'))
        if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
            raise ValueError('运行房间目录无法核验，暂不能清理')
        for item in records:
            for name in names:
                if name in (item.get('ai'), item.get('entry')):
                    source=str(item.get('projectId',''))
                    result[name].append(('registry',source) if details else '运行目录仍引用此房间：'+source)
    seen = set()
    pattern = re.compile(r'(?<![A-Z0-9_])(?:' + '|'.join(re.escape(n) for n in names) + r')(?![A-Z0-9_])', re.I)
    for root in room_bindings._asset_roots():
        for folder in (root / 'world', root / 'modify/world'):
            for file in folder.glob('*/world_*.txt'):
                file = file.resolve()
                if file in seen: continue
                seen.add(file)
                try: content = '\n'.join(line.split('//', 1)[0] for line in file.read_text('utf-8-sig').splitlines())
                except (OSError, UnicodeError):
                    if details:raise room_bindings.RoomBindingError('migrationPath',file=str(file))
                    raise ValueError('世界连接无法读取，暂不能清理：' + str(file))
                for match in pattern.finditer(content):
                    result[match.group().upper()].append(('world',str(file)) if details else '世界连接仍引用此房间：'+str(file))
    return {name: sorted(set(reasons)) for name, reasons in result.items()}


def _unverified_cache(pid, project, ledger):
    # A filename in this project's render cache is a discovery hint, never
    # ownership evidence. It must never acquire hashes or deletion permission.
    known = {room['name'] for room in ledger['rooms']}
    binding = room_bindings.binding(project)
    known.update((binding['ai'], binding['entry']))
    result = []
    folder = storage.project_file(pid).parent / 'rooms/rendered'
    for file in sorted(folder.glob('*.txt')):
        name = file.stem
        if name in known or not room_bindings.ROOM_RE.fullmatch(name): continue
        try: room_bindings.geometry(file)
        except ValueError: continue
        result.append(dict(name=name, kind='ai' if name.endswith('_AI') else 'unknown', retired=True, files=[]))
    return result


def preview(project_id):
    pid = storage.valid_id(project_id)
    project = storage.load_project(pid)
    if storage.binding(pid): raise ValueError('原版或关联模组的房间不能由此功能清理')
    ledger = _read(pid)
    retired = [room for room in ledger['rooms'] if room['retired']] + _unverified_cache(pid, project, ledger)
    retired.sort(key=lambda room: room['name'])
    game = _game_blockers()
    references = _references([room['name'] for room in retired])
    rooms = []
    for room in retired:
        reasons = list(game) + references[room['name']]
        files = []
        no_evidence = not room['files']
        if no_evidence: reasons.append('旧房间没有生成文件的归属校验记录，不能自动删除。')
        for item in room['files']:
            file = _resolve(pid, room['name'], item, required=False)
            if file is None:
                files.append(dict(item, exists=None, unavailable=True))
                reasons.append('Rain World was not found. Select RainWorld.exe in the editor settings.')
                continue
            current = dict(item, exists=file.exists())
            if current['exists']:
                if not file.is_file(): raise ValueError('房间文件位置已变成文件夹，已停止清理：' + str(file))
                current.update(actualSha256=_hash(file), actualSize=file.stat().st_size)
                if current['actualSha256'] != item['sha256'] or current['actualSize'] != item['size']:
                    reasons.append('文件在迁移后被修改，不能确认可删除：' + item['scope'] + '/' + item['path'])
            files.append(current)
        rooms.append(dict(name=room['name'], kind=room['kind'], noEvidence=no_evidence, files=files,
                          status='blocked' if reasons else ('ready' if any(item['exists'] for item in files) else 'missing'), reasons=sorted(set(reasons))))
    count = sum(room['status'] == 'ready' for room in rooms)
    result = dict(projectId=pid, name=project['name'], rooms=rooms, canApply=count > 0, readyCount=count, requiresRestart=True,
                  warnings=['只清理可确认归属且未被引用的旧运行房间；Rained 源工程始终保留。'])
    evidence = dict(preview=result, ledgerGeneration=ledger['generation'], binding=room_bindings.binding(project))
    result['token'] = hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
    return result


def apply(project_id, token):
    from room_migration import Files
    planned = preview(project_id)
    if not isinstance(token, str) or token != planned['token']:
        raise ValueError('旧房间、文件或运行状态已改变，请重新预览后再清理。')
    ready = [room for room in planned['rooms'] if room['status'] == 'ready']
    if not ready: raise ValueError('当前没有可安全清理的旧房间。')
    if _game_blockers():
        raise ValueError('游戏运行状态已改变，请退出游戏并重新预览后再清理。')
    transaction = Files()
    removed = []
    try:
        for room in ready:
            for item in room['files']:
                if not item['exists']: continue
                file = _resolve(project_id, room['name'], item)
                if not file.is_file() or _hash(file) != item['sha256']:
                    raise ValueError('旧房间文件在清理前改变，已取消并恢复，请重新预览。')
                transaction.remove(file)
                removed.append(dict(room=room['name'], scope=item['scope'], path=item['path']))
        ledger = _read(project_id)
        deleted = {room['name'] for room in ready}
        ledger['rooms'] = [room for room in ledger['rooms'] if room['name'] not in deleted]
        ledger['generation'] = uuid.uuid4().hex
        transaction.json(_file(project_id), ledger)
    except Exception:
        transaction.rollback()
        raise
    return dict(ok=True, projectId=project_id, deleted=sorted(deleted), removedFiles=removed,
                retained=[dict(name=room['name'], status=room['status'], reasons=room['reasons']) for room in planned['rooms'] if room['name'] not in deleted], requiresRestart=True)
