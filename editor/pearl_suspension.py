"""Pause published local pearl spawns while their iterator project is deleted.

Authoring pearl files and already-realized game objects are never touched. All
runtime files are preflighted before a change plan is returned to the caller's
existing Files transaction; the manifest must be written last.
"""
from pathlib import Path
import copy
import hashlib
import json
import re
import uuid

import storage

PEARL_SCHEMA = 'moreiterators.pearl.v1'
MANIFEST_SCHEMA = 'moreiterators.pearl-runtime.v1'
_ROOM = re.compile(r'[A-Z0-9]+_[A-Z0-9_]+')
_UID = re.compile(r'[a-f0-9]{32}')
_FILE = re.compile(r'[A-Z]{1,4}[0-9]{2,4}\.json')
_SHA = re.compile(r'[a-f0-9]{64}')


def _archive_state():
    # Lazy import avoids the pearls -> lifecycle -> room_migration cycle.
    import project_lifecycle
    result = {}
    for record in project_lifecycle._records():
        pid = storage.valid_id(record['projectId'])
        if pid in result:
            raise ValueError('同一项目存在多份删除记录，已停止更新珍珠生成。')
        result[pid] = record['project']
    return result


def _owned_rooms(project):
    import room_bindings
    binding = room_bindings.binding(project)
    rooms = [binding.get('ai')]
    if binding.get('entryMode') == 'copy':
        rooms.append(binding.get('entry'))
    elif binding.get('entryMode') != 'existing':
        raise ValueError('项目房间归属无效，已停止更新珍珠生成。')
    if any(not isinstance(room, str) or not _ROOM.fullmatch(room) for room in rooms):
        raise ValueError('项目房间编号无效，已停止更新珍珠生成。')
    return set(rooms)


def _owners(ids, records):
    return {pid: _owned_rooms(records[pid] if pid in records else storage.load_project(pid))
            for pid in ids}


def owned_rooms(project):
    """The same local-only room ownership set used by archive UI filtering."""
    return _owned_rooms(project)


def _spawn_list(project, key):
    values = project.get(key, [])
    if not isinstance(values, list):
        raise ValueError('珍珠生成列表损坏，已停止更新。')
    for value in values:
        if not isinstance(value, dict):
            raise ValueError('珍珠生成位置损坏，已停止更新。')
        pid = value.get('projectId', '')
        if pid != '':
            storage.valid_id(pid)
        if not isinstance(value.get('entry'), str) or not _ROOM.fullmatch(value['entry']):
            raise ValueError('珍珠生成房间编号损坏，已停止更新。')
        if 'suspendedBy' in value:
            blocked = value['suspendedBy']
            if not isinstance(blocked, list) or not blocked:
                raise ValueError('珍珠暂停来源损坏，已停止更新。')
            for owner in blocked:
                storage.valid_id(owner)
            if len(set(blocked)) != len(blocked) or key != 'suspendedSpawns' or pid and set(blocked) != {pid}:
                raise ValueError('珍珠暂停来源与生成位置不符，已停止更新。')
        elif key == 'suspendedSpawns':
            raise ValueError('珍珠暂停位置缺少来源，已停止更新以免恢复错误房间。')
    return values


def _partition(project, owners):
    if not isinstance(project, dict):
        raise ValueError('珍珠运行内容无效。')
    active, suspended = [], []
    for value in _spawn_list(project, 'spawns') + _spawn_list(project, 'suspendedSpawns'):
        spawn = copy.deepcopy(value)
        pid = spawn.get('projectId', '')
        blocked = ({pid} if pid in owners else set()) if pid else {
            owner for owner, rooms in owners.items() if spawn['entry'] in rooms}
        spawn.pop('suspendedBy', None)
        if blocked:
            spawn['suspendedBy'] = sorted(blocked)
            suspended.append(spawn)
        else:
            active.append(spawn)
    result = copy.deepcopy(project)
    if 'spawns' in result or active or suspended:
        result['spawns'] = active
    if suspended:
        result['suspendedSpawns'] = suspended
    else:
        result.pop('suspendedSpawns', None)
    return result


def partition(project, archived_ids=None):
    """Return a compiled local-publish copy with deleted-project spawns paused.

    Call only after compile_project, when publishing locally. Standalone exports
    keep their original compiled spawns. Explicit IDs also support a delete
    preflight before its recoverable archive record has been created.
    """
    records = _archive_state()
    if archived_ids is None:
        ids = set(records)
    else:
        if isinstance(archived_ids, (str, bytes)):
            raise ValueError('已删除项目列表无效。')
        ids = {storage.valid_id(pid) for pid in archived_ids}
    return _partition(project, _owners(ids, records))


def _safe(relative):
    base = Path(storage.RUNTIME).absolute()
    if base.resolve() != base:
        raise ValueError('珍珠运行目录存在链接，已停止更新。')
    target = base / relative
    if not target.resolve().is_relative_to(base):
        raise ValueError('珍珠运行文件路径越界。')
    for path in [target, *target.parents]:
        if path == base.parent:
            break
        if path.is_symlink() or path.exists() and path.resolve() != path.absolute():
            raise ValueError('珍珠运行文件存在链接，已停止更新。')
    return target


def _read(file):
    try:
        content = file.read_bytes()
        value = json.loads(content.decode('utf-8'))
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError('无法校验已发布的珍珠文件：' + file.name) from error
    if not isinstance(value, dict):
        raise ValueError('已发布的珍珠文件格式无效：' + file.name)
    return content, value


def _local_owner(value):
    return value.get('ownerMod', '') in ('', 'moreiterators.local')


def _published():
    marker = _safe('pearl-project.json')
    if not marker.exists():
        # Unlisted legacy or external files must never be adopted implicitly.
        return marker, None, []
    _, manifest = _read(marker)
    cid = manifest.get('collectionId')
    generation = manifest.get('generation')
    if (manifest.get('schema') != MANIFEST_SCHEMA or not _local_owner(manifest)
            or not isinstance(cid, str) or not (cid == 'legacy' or _UID.fullmatch(cid))
            or not isinstance(generation, str) or not _UID.fullmatch(generation)
            or not isinstance(manifest.get('files'), list)):
        raise ValueError('珍珠运行清单无效，已停止更新。')
    names, uids, published = set(), set(), []
    for entry in manifest['files']:
        if not isinstance(entry, dict):
            raise ValueError('珍珠运行清单条目无效。')
        name, uid, digest = (entry.get(key) for key in ('name', 'uid', 'sha256'))
        if (not isinstance(name, str) or not _FILE.fullmatch(name) or name in names
                or not isinstance(uid, str) or not _UID.fullmatch(uid) or uid in uids
                or not isinstance(digest, str) or not _SHA.fullmatch(digest)):
            raise ValueError('珍珠运行清单条目无效或重复。')
        names.add(name);uids.add(uid)
        file = _safe('pearls/' + name)
        content, value = _read(file)
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError('已发布珍珠校验失败，可能正在被其他操作修改：' + name)
        if (value.get('schema') != PEARL_SCHEMA or value.get('id') != name[:-5]
                or value.get('uid') != uid or value.get('runtimeId') != 'MoreIterators_' + uid
                or value.get('collectionId', 'legacy') != cid or not _local_owner(value)):
            raise ValueError('珍珠运行文件身份或本地归属不符：' + name)
        _spawn_list(value, 'spawns');_spawn_list(value, 'suspendedSpawns')
        published.append((file, value, entry))
    return marker, manifest, published


def verify_runtime():
    """Read-only preflight, usable before saving the draft during deletion."""
    _published()


def runtime_changes(project_id, restoring=False):
    """Preflight and return Path -> JSON changes; no filesystem writes occur.

    Apply each returned item with the lifecycle's room_migration.Files.json.
    The last item is the new SHA manifest/generation, so rollback can include
    these files together with the iterator's archive/registry changes.
    """
    pid = storage.valid_id(project_id)
    if type(restoring) is not bool:
        raise ValueError('珍珠恢复操作无效。')
    marker, manifest, published = _published()
    if manifest is None:
        return {}
    records = _archive_state()
    ids = set(records)
    if restoring:
        ids.discard(pid)
    else:
        ids.add(pid)
    owners = _owners(ids, records)
    # A missing unrelated archive record is not permission to release its
    # paused spawns. Keep that prior blocker until its own restore is requested.
    for _, value, _ in published:
        for spawn in _spawn_list(value, 'suspendedSpawns'):
            for owner in spawn['suspendedBy']:
                if restoring and owner == pid:
                    continue
                rooms = owners.setdefault(owner, set())
                if not spawn.get('projectId', ''):
                    rooms.add(spawn['entry'])
    changes = {}
    for file, value, entry in published:
        updated = _partition(value, owners)
        if updated != value:
            changes[file] = updated
            entry['sha256'] = hashlib.sha256(json.dumps(updated, ensure_ascii=False, indent=2).encode('utf-8')).hexdigest()
    if changes:
        manifest['generation'] = uuid.uuid4().hex
        changes[marker] = manifest
    return changes
