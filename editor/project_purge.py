"""Previewed permanent removal of one local iterator, without recovery content.

All mutations share a rollback transaction. A content-free ID tombstone prevents
old browser tabs from recreating a purged project. External Rained originals and
independent mods are never adopted by filename as project-owned files.
"""
import copy
import hashlib
import json
import re
import time
import uuid
import zipfile
from pathlib import Path

import storage
import project_lifecycle as life
import project_worlds
import project_associations as associations
import room_bindings
import room_cleanup
import room_migration
import pearl_suspension

_plans = {}
TTL = 900


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')


def _digest(content):
    return hashlib.sha256(content).hexdigest()


class Plan:
    def __init__(self):
        self.removes = set()
        self.writes = {}
        self.evidence = {}
        self.inventories = {}
        self.directories = set()
        self.conflicts = []
        self.counts = dict(projectFiles=0, historyFiles=0, projections=0,
                           pearlReaders=0, pearlSpawns=0, roomFiles=0, archives=0,
                           operations=0, exportCaches=0, recoveryCopies=0, audioFiles=0)
        self.game_files = False
        self._safe_paths = {}
        self._trees = {}
        self._checked_dirs = set()
        self._roots = tuple(Path(base).absolute() for base in
                            (storage.DATA, storage.PROJECTS, storage.RUNTIME, storage.EXPORTS,
                             storage.archive_root(), storage.installed_mod('purge-operation')))

    def safe(self, file, fresh=False):
        file = Path(file).absolute()
        if not fresh and file in self._safe_paths:
            return self._safe_paths[file]
        for base in self._roots:
            if file.is_relative_to(base):
                relative = file.relative_to(base).as_posix()
                if fresh:
                    return life._safe_path(base, '' if relative == '.' else relative)
                # A collection is read-only. Validate each ancestor once here;
                # apply recollects with a NEW Plan and checks every mutation
                # through the uncached lifecycle containment routine again.
                chain = []
                current = file
                while current != base.parent:
                    chain.append(current)
                    current = current.parent
                for current in reversed(chain):
                    if current not in self._checked_dirs:
                        life._safe_path(current)
                        self._checked_dirs.add(current)
                self._safe_paths[file] = file
                return file
        raise ValueError('永久删除路径不属于本地项目数据')

    def read(self, file):
        file = self.safe(file)
        content = file.read_bytes() if file.exists() else None
        self.evidence[str(file)] = _digest(content) if content is not None else None
        return content

    def json(self, file):
        return json.loads(self.read(file).decode('utf-8-sig'))

    def reference(self, file):
        """Fingerprint external references, without granting mutation ownership."""
        file = Path(file).absolute()
        content = file.read_bytes() if file.exists() else None
        self.evidence[str(file)] = _digest(content) if content is not None else None
        return content

    def tree(self, base):
        base = self.safe(base)
        if base in self._trees:
            return self._trees[base]
        files = []
        inventory = []
        if base.exists():
            for path in sorted(base.rglob('*')):
                self.safe(path)
                if path.is_file():
                    stat = path.stat()
                    files.append(path)
                    inventory.append((path.relative_to(base).as_posix(), stat.st_size, stat.st_mtime_ns))
                elif path.is_dir():
                    inventory.append((path.relative_to(base).as_posix()+'/', 0, 0))
        self.inventories[str(base)] = inventory
        self._trees[base] = files
        return files

    def remove(self, file):
        file = self.safe(file)
        if file.exists():
            self.read(file)
            self.removes.add(file)
            self.writes.pop(file, None)
            self.game_files |= file.is_relative_to(storage.RUNTIME) or file.is_relative_to(storage.DATA/'local-mod') or file.is_relative_to(storage.installed_mod('purge-operation'))

    def remove_tree(self, base):
        base = self.safe(base)
        files = self.tree(base)
        for file in files:
            self.remove(file)
        if base.exists():
            self.directories.add(base)
            self.directories.update(path for path in base.rglob('*') if path.is_dir())
        return len(files)

    def write(self, file, value):
        file = self.safe(file)
        before = self.read(file)
        content = value if isinstance(value, bytes) else _json_bytes(value)
        if before != content:
            self.writes[file] = content
            self.game_files |= file.is_relative_to(storage.RUNTIME) or file.is_relative_to(storage.DATA/'local-mod') or file.is_relative_to(storage.installed_mod('purge-operation'))

    def block(self, key, message):
        if not any(item['id'] == key for item in self.conflicts):
            self.conflicts.append(dict(id=key, message=message, canReplace=False))

    def signature(self):
        return _digest(json.dumps(dict(evidence=self.evidence, inventories=self.inventories),
                                  sort_keys=True, ensure_ascii=False).encode('utf-8'))


def _mentions(value, pid, rooms=()):
    if isinstance(value, dict):
        embedded = value.get('overseerJson')
        if isinstance(embedded, str):
            try:
                if _mentions(json.loads(embedded), pid, rooms):
                    return True
            except ValueError:
                pass
        return any((key in ('projectId', 'sourceProjectId', 'targetProjectId', 'ownerProjectId', 'project') and item == pid)
                   or (key in ('spawnProjects', 'projects', 'suspendedBy') and isinstance(item, list) and pid in item)
                   or _mentions(item, pid, rooms) for key, item in value.items())
    if isinstance(value, list):
        return any(_mentions(item, pid, rooms) for item in value)
    return isinstance(value, str) and value in rooms


def _source(data, plan):
    source = data.get('source')
    if not isinstance(source, dict) or bool(source.get('projectId')) == bool(source.get('token')):
        raise ValueError('请选择要永久删除的项目')
    archive = None
    if source.get('token'):
        token = life._token(source['token'])
        archive = life._read(token)
        plan.read(life._manifest(token))
        if archive['state'] not in life.ACTIVE_STATES:
            raise ValueError('此删除记录已恢复，请重新选择项目')
        pid = archive['projectId']
        if storage.project_file(pid).exists() and archive['state'] == 'deleted':
            raise ValueError('同名项目已重新存在，请从项目列表检查后删除')
        project = copy.deepcopy(archive['project'])
    else:
        pid = storage.valid_id(source['projectId'])
        life.assert_active(pid)
        file = storage.project_file(pid)
        if file.exists():
            project = plan.json(file)
        else:
            raise ValueError('项目不存在，请刷新项目列表')
    life._editable(pid, project)
    if project.get('projectId') != pid:
        raise ValueError('项目文件归属不符')
    return pid, project, archive


def _pearl_edit(value, pid, rooms, runtime=False):
    result = copy.deepcopy(value)
    readers = result.get('readers', [])
    if not isinstance(readers, list):
        raise ValueError('珍珠读取文本列表损坏')
    kept_readers = [item for item in readers if item.get('projectId') != pid]
    reader_count = len(readers)-len(kept_readers)
    if 'readers' in result:
        result['readers'] = kept_readers
    spawn_count = 0
    if runtime:
        for key in ('spawns', 'suspendedSpawns'):
            values = result.get(key, [])
            kept = [item for item in values if not (item.get('projectId') == pid or
                    not item.get('projectId') and item.get('entry') in rooms)]
            spawn_count += len(values)-len(kept)
            for item in kept:
                if pid in item.get('suspendedBy', []):
                    item['suspendedBy'] = [owner for owner in item['suspendedBy'] if owner != pid]
                    if not item['suspendedBy']:
                        raise ValueError('珍珠暂停归属与房间不一致，未自动恢复生成')
            if key in result:
                result[key] = kept
    else:
        for key, targets in (('spawnProjects', {pid}), ('spawnRooms', rooms)):
            values = result.get(key, [])
            kept = [item for item in values if item not in targets]
            spawn_count += len(values)-len(kept)
            if key in result:
                result[key] = kept
        for key, targets in (('spawnPositions', {pid}), ('spawnRoomPositions', rooms)):
            if key in result:
                result[key] = {name: value for name, value in result[key].items() if name not in targets}
        if result != value:
            result['revision'] = result.get('revision', 0)+1
    return result, reader_count, spawn_count


def _room_refs(plan, pid, rooms, records):
    referenced = set()
    for record in records:
        if record.get('projectId') != pid:
            referenced.update((record.get('ai'), record.get('entry')))
    for file in storage.project_files():
        if file.parent.name == pid:
            continue
        value = json.loads(plan.reference(file))
        binding = room_bindings.binding(value)
        referenced.update((binding['ai'], binding['entry']))
        saved_plan = file.parent/'room-binding-plan.json'
        if saved_plan.exists():
            for change in json.loads(plan.reference(saved_plan)).get('connectionChanges', []):
                referenced.update((change.get('room'), change.get('to')))
    shared = rooms & referenced
    if shared:
        plan.block('shared-rooms', '其他项目仍在使用这些房间，请先修改其房间连接：'+', '.join(sorted(shared)))


def _world_refs(plan, rooms):
    if not rooms:
        return
    pattern = re.compile(r'(?<![A-Z0-9_])(?:'+'|'.join(re.escape(room) for room in sorted(rooms))+r')(?![A-Z0-9_])', re.I)
    seen = set()
    for root in room_bindings._asset_roots():
        for folder in (root/'world', root/'modify/world'):
            files = sorted(folder.glob('*/world_*.txt'))
            plan.inventories['references:'+str(folder)] = [str(file.absolute()) for file in files]
            for file in files:
                file = file.absolute()
                if file in seen or file in plan.removes:
                    continue
                seen.add(file)
                original = plan.reference(file)
                content = plan.writes.get(file, original).decode('utf-8-sig')
                content = '\n'.join(line.split('//', 1)[0] for line in content.splitlines())
                if pattern.search(content):
                    plan.block('world-reference:'+str(file), '世界连接仍引用此房间：'+str(file))


def _detach_overseer(value, pid, rooms):
    if not isinstance(value, dict):
        return False
    changed = False
    for profile in [value, *value.get('guests', [])]:
        if profile.get('ownerProjectId') == pid:
            profile['ownerProjectId'] = ''
            changed = True
        if 'rooms' in profile:
            before = profile['rooms']
            profile['rooms'] = [room for room in before if room not in rooms]
            changed |= before != profile['rooms']
    return changed


def _dependent_references(plan, pid, rooms):
    for file in storage.project_files():
        if file.parent.name == pid:
            continue
        value = json.loads(plan.reference(file))
        if _detach_overseer(value.get('overseer'), pid, rooms):
            if storage.link(value['projectId']):
                plan.block('linked-owner:'+value['projectId'], '关联模组仍引用此项目，请先解除关联：'+value['projectId'])
            else:
                value['overseerRevision'] = value.get('overseerRevision', 0)+1
                plan.write(file, value)
    for file in plan.tree(storage.RUNTIME):
        if file.suffix != '.json' or file in plan.removes:
            continue
        try:
            value = plan.json(file)
        except (ValueError, UnicodeError):
            continue
        if not isinstance(value, dict):
            continue
        encoded = value.get('overseerJson')
        if isinstance(encoded, str):
            config = json.loads(encoded)
            if _detach_overseer(config, pid, rooms):
                value['overseerJson'] = json.dumps(config, ensure_ascii=False)
                plan.write(file, value)
                plan.game_files = True
        if file.name == 'room-catalog.json' and value.get('schema') == room_bindings.SCHEMA:
            before = copy.deepcopy(value)
            value['oracles'] = [entry for entry in value.get('oracles', []) if entry.get('projectId') != pid]
            for region in value.get('regions', []):
                region['rooms'] = [room for room in region.get('rooms', []) if room.get('name') not in rooms]
                for room in region['rooms']:
                    room['connections'] = ['DISCONNECTED' if name in rooms else name for name in room.get('connections', [])]
            if value != before:
                plan.write(file, value)
                plan.game_files = True
    for base in (storage.DATA/'broadcasts', storage.RUNTIME/'broadcasts'):
        for file in plan.tree(base):
            if file.suffix != '.json':
                continue
            value = plan.json(file)
            if isinstance(value, dict) and value.get('room') in rooms:
                value.update(room='', region='')
                if base == storage.DATA/'broadcasts':
                    value['revision'] = value.get('revision', 0)+1
                else:
                    plan.game_files = True
                plan.write(file, value)


def _collect(data):
    p = Plan()
    pid, project, selected_archive = _source(data, p)
    p.source = dict(projectId=pid, name=project.get('name', pid), archived=bool(selected_archive))
    if selected_archive:
        p.source['token'] = selected_archive['token']
    archived = []
    for file in p.tree(life.root()):
        if file.name != 'manifest.json':
            continue
        value = p.json(file)
        if value.get('schema') == life.SCHEMA and value.get('projectId') == pid:
            value = life._read(file.parent.name)
            archived.append(value)
    registry_file = storage.RUNTIME/'creator/registry.json'
    p.read(registry_file)
    records = life._registry()
    owned = [value for value in records if value.get('projectId') == pid]
    for archive in archived:
        for record in archive['registry']:
            if record not in owned:
                owned.append(record)
    remaining = [value for value in records if value.get('projectId') != pid]
    rooms = set(pearl_suspension.owned_rooms(project))
    oracles = {room_bindings.binding(project)['oracleId']}
    for archive in archived:
        rooms.update(pearl_suspension.owned_rooms(archive['project']))
        oracles.add(room_bindings.binding(archive['project'])['oracleId'])
    for record in owned:
        oracles.add(record.get('oracleId'))
        binding = record.get('roomBinding') or room_bindings.binding(project)
        rooms.add(record['ai'])
        if binding.get('entryMode') == 'copy':
            rooms.add(record['entry'])

    # Current and retired outputs need ownership proof; a matching external
    # Rained filename is deliberately not proof.
    ledger_file = storage.project_file(pid).parent/'room-ownership.json'
    ledgers = [p.json(ledger_file)] if ledger_file.exists() else []
    for archive in archived:
        for item in archive['files']:
            if item.get('kind') == 'project' and item.get('path') == 'room-ownership.json':
                blob, content = life._blob(archive, item)
                p.read(blob)
                ledgers.append(json.loads(content))
    ledger_files = {}
    for ledger in ledgers:
        if ledger.get('schema') != room_cleanup.SCHEMA or ledger.get('projectId') != pid:
            raise ValueError('房间归属记录无效')
        for room in ledger.get('rooms', []):
            if not room_bindings.ROOM_RE.fullmatch(room.get('name', '')):
                raise ValueError('房间归属记录无效')
            rooms.add(room['name'])
            for item in room.get('files', []):
                file = room_cleanup._resolve(pid, room['name'], item)
                if item.get('scope') == 'rendered' or not file.exists():
                    continue
                ledger_files.setdefault(file, dict(name=room['name'], hashes=set()))['hashes'].add(item.get('sha256'))
    for file, evidence in ledger_files.items():
        if _digest(p.read(file)) not in evidence['hashes']:
            p.block('changed-room:'+evidence['name'], '以前生成的房间文件已被修改，无法确认独占归属：'+evidence['name'])
        else:
            p.remove(file)
            p.counts['roomFiles'] += 1
            p.game_files = True
    _room_refs(p, pid, rooms, records)
    try:
        for file, item in project_worlds.owned_files(pid, project, owned, records,
                selected_archive.get('deletedAt') if selected_archive else None):
            p.remove(file)
            p.counts['roomFiles'] += 1
            p.game_files = True
    except ValueError as error:
        p.block('room-ownership', str(error))
    if owned:
        for file, content in project_worlds.plan(remaining, pid).items():
            if content is None:
                p.remove(file)
            else:
                p.write(file, content)
            p.game_files = True
    if records != remaining:
        p.write(registry_file, remaining)
        p.game_files = True
    _world_refs(p, rooms)

    p.counts['projectFiles'] = p.remove_tree(storage.PROJECTS/pid)
    p.counts['historyFiles'] = p.remove_tree(storage.history_directory(pid))
    for archive in archived:
        p.remove_tree(life.root()/archive['token'])
        p.counts['archives'] += 1
    for file in p.tree(storage.DATA/'projections'):
        if file.name == 'projection.json':
            value = p.json(file)
            if value.get('projectId') == pid:
                p.remove_tree(file.parent)
                p.counts['projections'] += 1
    p.remove(storage.DATA/'projections/project-settings'/(pid+'.json'))
    for file in p.tree(storage.RUNTIME):
        if file.suffix != '.json' or file == registry_file or 'pearls' in file.relative_to(storage.RUNTIME).parts:
            continue
        try:
            value = p.json(file)
        except (ValueError, UnicodeError):
            if file.parent == storage.RUNTIME and file.stem in oracles:
                p.remove(file)
                p.game_files = True
            continue
        if isinstance(value, dict) and value.get('projectId', value.get('project')) == pid:
            p.remove(file)
            if file.name == 'studio-frame.json':
                p.remove(file.with_suffix('.png'))
            p.game_files = True
        elif isinstance(value, dict) and file.name == 'studio-frame.json' and value.get('oracleId', value.get('oracle')) in oracles:
            p.remove(file)
            p.remove(file.with_suffix('.png'))
        elif isinstance(value, dict) and file.name in ('launch.json', 'heartbeat.json', 'status.json') and value.get('entry', value.get('room')) in rooms:
            p.remove(file)
    launch = storage.RUNTIME/'launch-room.txt'
    if launch.exists() and p.read(launch).decode('utf-8-sig').strip() in rooms:
        p.remove(launch)
    _dependent_references(p, pid, rooms)

    # Inspect migrated collections AND their legacy originals. Do not call a
    # catalog helper that initializes/migrates files during this read-only plan.
    for base in (storage.DATA/'pearls', storage.DATA/'pearl-projects'):
        for file in p.tree(base):
            if file.name != 'pearl.json':
                continue
            value = p.json(file)
            updated, readers, spawns = _pearl_edit(value, pid, rooms)
            if updated != value:
                p.write(file, updated)
                p.counts['pearlReaders'] += readers
                p.counts['pearlSpawns'] += spawns
    marker, manifest, published = pearl_suspension._published()
    p.read(marker)
    changed = False
    for file, value, entry in published:
        p.read(file)
        updated, readers, spawns = _pearl_edit(value, pid, rooms, runtime=True)
        if updated != value:
            p.write(file, updated)
            entry['sha256'] = _digest(_json_bytes(updated))
            changed = True
    if changed:
        manifest['generation'] = uuid.uuid4().hex
        p.write(marker, manifest)
        p.game_files = True
    published_files = {file for file, _, _ in published}
    for file in p.tree(storage.RUNTIME/'pearls'):
        if file.suffix != '.json' or file in published_files:
            continue
        value = p.json(file)
        if not isinstance(value, dict):
            continue
        uid = value.get('uid')
        if (value.get('schema') != pearl_suspension.PEARL_SCHEMA
                or value.get('ownerMod', '') not in ('', 'moreiterators.local')
                or not isinstance(uid, str) or not re.fullmatch('[a-f0-9]{32}', uid)
                or value.get('runtimeId') != 'MoreIterators_'+uid or value.get('id') != file.stem):
            continue
        updated, _, _ = _pearl_edit(value, pid, rooms, runtime=True)
        if updated != value:
            p.write(file, updated)
            p.game_files = True

    # Shared recovery documents may contain an old full pearl/registry snapshot,
    # even when this project was neither endpoint of the association operation.
    for file in p.tree(associations._operation_root()):
        if file.name != 'manifest.json':
            continue
        value = p.json(file)
        if value.get('schema') != associations.SCHEMA:
            continue
        matches = _mentions(value, pid, rooms)
        if not matches:
            for blob in p.tree(file.parent/'blobs'):
                content = p.read(blob)
                try:
                    matches = _mentions(json.loads(content), pid, rooms)
                except (ValueError, UnicodeError):
                    matches = False
                if matches:
                    break
        if matches:
            p.remove_tree(file.parent)
            p.counts['operations'] += 1

    for file in p.tree(storage.EXPORTS):
        if file.suffix.lower() != '.zip':
            continue
        try:
            with zipfile.ZipFile(file) as archive:
                for name in archive.namelist():
                    if Path(name).name not in ('manifest.json', 'content-manifest.json') or archive.getinfo(name).file_size > 1024*1024:
                        continue
                    value = json.loads(archive.read(name))
                    if value.get('schema') in ('moreiterators.export.v1', 'moreiterators.playback-export.v1') and _mentions(value, pid):
                        p.remove(file)
                        p.counts['exportCaches'] += 1
                        break
        except (zipfile.BadZipFile, ValueError, KeyError):
            continue
    backup_root = storage.archive_root()/'install-backups'
    for report in p.tree(backup_root):
        if report.name != 'install-result.json':
            continue
        result = p.json(report)
        pack = report.parent/'more_iterators_local'
        info = pack/'modinfo.json'
        if 'more_iterators_local' not in result.get('packages', []) or not info.exists() or p.json(info).get('id') != 'moreiterators.local':
            continue
        files = p.tree(pack)
        if any(file.suffix == '.txt' and file.stem in rooms for file in files):
            p.remove_tree(pack)
            p.counts['recoveryCopies'] += 1
    preferences = storage.DATA/'export-settings.json'
    if preferences.exists():
        value = p.json(preferences)
        if pid in value.get('projects', []):
            value['projects'] = [item for item in value['projects'] if item != pid]
            p.write(preferences, value)

    # Only reclaim hashes that occur in removed content, and have no reference in
    # any surviving local document/history/undo/export or shared installed pack.
    candidates = set()
    for file in p.removes | set(p.writes):
        if file.suffix.lower() not in ('.png', '.mp3', '.dll', '.zip'):
            content = p.read(file)
            if content is not None:
                candidates.update(match.decode() for match in re.findall(rb'(?<![a-f0-9])[a-f0-9]{64}(?![a-f0-9])', content))
    audio_roots = (storage.DATA/'audio', storage.DATA/'local-mod/mi_audio', storage.installed_mod(pid)/'mi_audio')
    candidates = {asset for asset in candidates if any((base/(asset+'.mp3')).is_file() for base in audio_roots)}
    if candidates:
        retained = set()
        # Most audio is shared by another active project. Its surviving document
        # is sufficient proof to keep the hash, so avoid scanning every old
        # archive when all candidates already have such a reference.
        for file in storage.project_files():
            if file in p.removes:
                continue
            content = p.writes.get(file)
            if content is None:
                content = p.reference(file)
            retained.update(asset for asset in candidates if asset.encode() in content)
            if retained >= candidates:
                break
        for link in storage.LINKS:
            if retained >= candidates:
                break
            workspace = Path(link['workspace'])
            for base in (workspace/'data/projects', workspace/'data/history'):
                for file in sorted(base.rglob('*.json')):
                    content = p.reference(file)
                    retained.update(asset for asset in candidates if asset.encode() in content)
        roots = (storage.DATA, storage.archive_root(), storage.installed_mod(pid))
        seen = set()
        for base in roots:
            if retained >= candidates:
                break
            for file in p.tree(base):
                if retained >= candidates:
                    break
                if file in seen or file in p.removes:
                    continue
                seen.add(file)
                if file.suffix.lower() == '.zip':
                    try:
                        with zipfile.ZipFile(file) as archive:
                            names = '\n'.join(archive.namelist())
                            retained.update(asset for asset in candidates if asset in names)
                            for name in archive.namelist():
                                if name.endswith('.json') and archive.getinfo(name).file_size <= 16*1024*1024:
                                    content = archive.read(name)
                                    retained.update(asset for asset in candidates if asset.encode() in content)
                    except zipfile.BadZipFile:
                        retained.update(candidates)
                elif file.suffix.lower() not in ('.png', '.mp3', '.dll', '.exe', '.woff2'):
                    content = p.writes.get(file)
                    if content is None:
                        content = p.read(file)
                    retained.update(asset for asset in candidates if asset.encode() in content)
        for asset in candidates-retained:
            for base in audio_roots:
                file = base/(asset+'.mp3')
                if file.exists() and _digest(p.read(file)) == asset:
                    p.remove(file)
                    p.counts['audioFiles'] += 1
                    if base != storage.DATA/'audio':
                        p.game_files = True
    p.write(storage.purge_marker(pid), dict(schema='moreiterators.purged-project.v1', projectId=pid))
    if p.game_files:
        try:
            project_worlds.require_closed()
        except ValueError as error:
            p.block('game-running', str(error))
    return p


def plan(data, server=None):
    p = _collect(data)
    token = uuid.uuid4().hex
    _plans[token] = dict(at=time.monotonic(), data=copy.deepcopy(data), plan=p, signature=p.signature())
    for key, saved in list(_plans.items()):
        if time.monotonic()-saved['at'] > TTL:
            _plans.pop(key, None)
    summary = ['永久删除项目本体、历史、最近删除与相关游戏内容；不能恢复。',
               '共享珍珠仅移除此项目的读取文本和生成位置，其他项目与独立广播保留。']
    if p.counts['exportCaches'] or p.counts['recoveryCopies']:
        summary.append('清理包含此项目的导出缓存和恢复副本；其他项目工程保留。')
    return dict(planToken=token, source=p.source, permanent=True, canApply=not p.conflicts,
                summary=summary, conflicts=p.conflicts, counts=p.counts)


def apply(data, server=None):
    saved = _plans.pop(life._token(data.get('planToken')), None)
    if not saved or time.monotonic()-saved['at'] > TTL:
        raise ValueError('删除确认已过期，请重新检查')
    p = saved['plan']
    if p.conflicts:
        raise ValueError(p.conflicts[0]['message'])
    current = _collect(saved['data'])
    if current.signature() != saved['signature']:
        raise ValueError('确认后项目或关联内容已改变，请重新检查')
    if current.conflicts:
        raise ValueError(current.conflicts[0]['message'])
    if p.game_files:
        project_worlds.require_closed()
    transaction = room_migration.Files()
    pid = p.source['projectId']
    marker = storage.purge_marker(pid)
    try:
        p.safe(marker, fresh=True)
        transaction.write(marker, p.writes[marker])
        for file in sorted(p.removes):
            p.safe(file, fresh=True)
            transaction.remove(file)
        for file, content in p.writes.items():
            if file != marker:
                p.safe(file, fresh=True)
                transaction.write(file, content)
    except Exception:
        transaction.rollback()
        raise
    # Only empty, verified owned directories are pruned after the transaction;
    # never recursively remove a directory that could have acquired new files.
    for directory in sorted(p.directories, key=lambda value: len(value.parts), reverse=True):
        p.safe(directory, fresh=True)
        if directory.exists() and not any(directory.iterdir()):
            try:
                directory.rmdir()
            except OSError:
                pass  # Content deletion committed; an empty directory is harmless.
    associations._plans.clear()
    room_bindings._offline_cache = None
    room_bindings._offline_at = 0
    room_migration.broadcasts._rooms = None
    room_migration.broadcasts._until = 0
    return dict(ok=True, permanent=True, deletedProject=True, projectId=pid,
                sourceProjectId=pid, name=p.source['name'])
