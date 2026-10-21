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


def _root(pid, scope):
    roots = dict(local=storage.DATA / 'local-mod', installed=storage.installed_mod(pid),
                 rendered=storage.project_file(pid).parent / 'rooms/rendered')
    if scope not in roots:
        raise ValueError('旧房间记录的输出位置无效')
    absolute = roots[scope].absolute()
    resolved = absolute.resolve()
    if str(absolute).casefold() != str(resolved).casefold():
        raise ValueError('旧房间输出根目录存在链接或路径别名，已停止清理')
    return resolved


def _resolve(pid, name, item):
    root = _root(pid, item.get('scope'))
    relative = item.get('path')
    prefix = '' if item['scope'] == 'rendered' else 'world/' + name.split('_')[0].lower() + '-rooms/'
    pattern = re.escape(prefix + name) + r'(?:\.txt|_settings\.txt|_[1-9][0-9]*\.png)'
    if not isinstance(relative, str) or not re.fullmatch(pattern, relative):
        raise ValueError('旧房间记录包含不属于该房间的路径：' + str(relative))
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
            path = _resolve(pid, room['name'], item)
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
            if not re.fullmatch(re.escape(name) + r'(?:\.txt|_settings\.txt|_[1-9][0-9]*\.png)', Path(relative).name):
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


def _references(names):
    result = {name: [] for name in names}
    if not result: return result
    for project in room_bindings._projects():
        binding = room_bindings.binding(project)
        for name in names:
            if name in (binding['ai'], binding['entry']):
                result[name].append('项目仍绑定此房间：' + str(project.get('name', project['projectId'])))
    registry = storage.RUNTIME / 'creator/registry.json'
    if registry.exists():
        records = json.loads(registry.read_text('utf-8'))
        if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
            raise ValueError('运行房间目录无法核验，暂不能清理')
        for item in records:
            for name in names:
                if name in (item.get('ai'), item.get('entry')):
                    result[name].append('运行目录仍引用此房间：' + str(item.get('projectId', '未知项目')))
    seen = set()
    pattern = re.compile(r'(?<![A-Z0-9_])(?:' + '|'.join(re.escape(n) for n in names) + r')(?![A-Z0-9_])', re.I)
    for root in room_bindings._asset_roots():
        for folder in (root / 'world', root / 'modify/world'):
            for file in folder.glob('*/world_*.txt'):
                file = file.resolve()
                if file in seen: continue
                seen.add(file)
                try: content = '\n'.join(line.split('//', 1)[0] for line in file.read_text('utf-8-sig').splitlines())
                except (OSError, UnicodeError): raise ValueError('世界连接无法读取，暂不能清理：' + str(file))
                for match in pattern.finditer(content):
                    result[match.group().upper()].append('世界连接仍引用此房间：' + str(file))
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
            file = _resolve(pid, room['name'], item)
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
