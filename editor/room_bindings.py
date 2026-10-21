"""Owned chamber names and explicit, geometry-checked world connections.

The game snapshot is the authoritative enabled-mod catalog. Offline paths are
also reserved to avoid silently shadowing an installed but disabled content mod.
Only this module's manifest-owned world files may be replaced or removed.
"""
from pathlib import Path
import copy
import datetime
import hashlib
import json
import os
import re
import threading
import time
import uuid
import storage
import native_projects
import waiting_room

LOCK = threading.RLock()
SCHEMA = 'moreiterators.room-catalog.v1'
BINDING_KEYS = {'region', 'ai', 'entry', 'oracleId', 'entryMode', 'aiNode', 'entryNode'}
ROOM_RE = re.compile(r'[A-Z][A-Z0-9]{1,7}_[A-Z0-9_]{1,64}')
REGION_RE = re.compile(r'[A-Z][A-Z0-9]{1,7}')
_offline_cache = None
_offline_at = 0


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _fixed(pid):
    linked = storage.link(pid)
    return linked['projects'][pid] if linked else native_projects.binding(pid)


def binding(project):
    """Effective names; does not validate or write a loaded document."""
    pid = storage.valid_id(project['projectId'])
    fixed = _fixed(pid)
    if fixed:
        return dict(region=fixed['ai'].split('_')[0], ai=fixed['ai'], entry=fixed['entry'],
                    oracleId=fixed['oracleId'], entryMode='existing', aiNode=1, entryNode=1)
    if isinstance(project.get('roomBinding'), dict):
        return copy.deepcopy(project['roomBinding'])
    key = hashlib.sha256(pid.encode()).hexdigest()[:10].upper()
    return dict(region='TEST', ai='TEST_' + key + '_AI', entry='TEST_' + key + '_ENTRY',
                oracleId='test_' + key.lower(), entryMode='copy', aiNode=1,
                entryNode=waiting_room.default_node(project, 'TEST_' + key + '_ENTRY'))


def describe(project):
    fixed = bool(_fixed(project['projectId']))
    result = dict(binding=binding(project), editable=not fixed,
                  warnings=['此项目的房间由原版或关联内容模组提供，不能在此改写。请创建独立项目。'] if fixed else [])
    if not fixed:
        for kind, key in [('ai', 'aiExitCount'), ('entry', 'entryExitCount')]:
            try:
                result[key] = geometry(source_for(project, kind).with_suffix('.txt'))['exitCount']
            except ValueError as error:
                result['warnings'].append(str(error))
    return result


def parse_world(text, region):
    """Read all Warp-visible room alternatives; mark conditional records unsafe to edit."""
    result, conditional = [], set()
    section = ''
    for raw in text.splitlines():
        line = raw.strip()
        if line in ('ROOMS', 'CONDITIONAL LINKS'):
            section = line
            continue
        if line.startswith('END '):
            section = ''
            continue
        if not line or line.startswith('//'):
            continue
        if section == 'CONDITIONAL LINKS':
            conditional.update(re.findall(r'\b[A-Z0-9]+_[A-Z0-9_]+\b', line))
        elif section == 'ROOMS' and ':' in line:
            fields = [v.strip() for v in line.split(':')]
            name = re.split(r'[)}]', fields[0])[-1].strip()
            if not re.fullmatch(r'[A-Z0-9]+_[A-Z0-9_]+', name):
                continue
            result.append(dict(name=name, region=region, connections=[s.strip() for s in fields[1].split(',')],
                               exitCount=-1, verified=False, conditional=name != fields[0], loaded=False,
                               tags=' : '.join(fields[2:]), oracle=name.endswith('_AI')))
    for item in result:
        item['conditional'] |= item['name'] in conditional
    return result


def _asset_roots():
    assets = storage.GAME / 'RainWorld_Data/StreamingAssets'
    roots = [assets, storage.DATA / 'local-mod']
    mods = assets / 'mods'
    if mods.is_dir():
        roots.extend(p for p in mods.iterdir() if p.is_dir())
    workshop = storage.GAME.parent.parent / 'workshop/content/312520'
    if workshop.is_dir():
        for folder in workshop.iterdir():
            if not folder.is_dir():
                continue
            roots.extend([folder, folder / 'newest'])
    return roots


def offline_catalog(refresh=False):
    global _offline_cache, _offline_at
    if not refresh and _offline_cache is not None and time.monotonic() - _offline_at < 20:
        return copy.deepcopy(_offline_cache)
    regions, reserved = {}, set()
    for root in _asset_roots():
        for world_root in (root / 'world', root / 'modify/world'):
            if not world_root.is_dir():
                continue
            for folder in world_root.iterdir():
                if not folder.is_dir():
                    continue
                for file in folder.glob('world_*.txt'):
                    region = file.stem[6:].upper()
                    try:
                        rows = parse_world(file.read_text('utf-8-sig'), region)
                    except (OSError, UnicodeError):
                        continue
                    regions.setdefault(region, {})
                    for row in rows:
                        regions[region].setdefault(row['name'], row)
                        reserved.add(row['name'])
                if folder.name.lower().endswith('-rooms'):
                    for file in folder.glob('*.txt'):
                        name = file.stem.upper()
                        if not name.endswith('_SETTINGS') and re.fullmatch(r'[A-Z0-9]+_[A-Z0-9_]+', name):
                            reserved.add(name)
    _offline_cache = dict(source='offline', fresh=False, complete=False, capturedAt=None, generation=None,
                         regions=[dict(name=k, rooms=list(v.values())) for k, v in sorted(regions.items())],
                         reservedRooms=sorted(reserved), reservedRegions=sorted(regions),
                         warnings=['离线目录包含已安装内容；游戏中实际启用的房间和出口须进入游戏后核对。'])
    _offline_at = time.monotonic()
    return copy.deepcopy(_offline_cache)


def catalog():
    offline = offline_catalog()
    path = storage.RUNTIME / 'creator/room-catalog.json'
    try:
        value = json.loads(path.read_text('utf-8'))
        if value.get('schema') != SCHEMA or not isinstance(value.get('regions'), list):
            return offline
        stamp = datetime.datetime.fromisoformat(value['capturedAt'].replace('Z', '+00:00'))
        age = (datetime.datetime.now(datetime.timezone.utc) - stamp).total_seconds()
        fresh = 0 <= age <= 30
        value.update(source='live' if fresh else 'stale', fresh=fresh,
                     reservedRooms=offline['reservedRooms'], reservedRegions=offline['reservedRegions'],
                     warnings=[] if fresh else ['这是上一次游戏会话的目录；连接现有房间前请进入游戏并刷新。'])
        return value
    except (OSError, ValueError, KeyError, TypeError):
        return offline


def resolve_room_source(name):
    """Resolve only a captured, filename-matched native geometry under trusted roots.

    A stale snapshot is acceptable for reading a rendered background/export;
    connection mutation still separately requires a fresh live snapshot.
    """
    if not isinstance(name, str) or not re.fullmatch(r'[A-Z0-9]+_[A-Z0-9_]+', name):
        raise ValueError('房间编号无效')
    rows = [r for region in catalog().get('regions', []) for r in region.get('rooms', []) if r.get('name') == name]
    paths = {r.get('geometryPath') for r in rows if isinstance(r.get('geometryPath'), str)}
    if len(paths) != 1:
        raise ValueError('缺少此房间的游戏素材路径，请进入游戏后刷新房间目录。')
    path = Path(next(iter(paths))).resolve()
    roots = [storage.GAME.resolve(), (storage.GAME.parent.parent / 'workshop/content/312520').resolve()]
    if path.suffix.lower() != '.txt' or path.stem.upper() != name or not any(path.is_relative_to(root) for root in roots):
        raise ValueError('游戏目录中的房间素材路径无效或越界。')
    if not path.is_file():
        raise ValueError('此房间的实际素材已移动，请重新进入游戏并刷新目录。')
    return path.with_suffix('')


def _projects():
    result = []
    for file in storage.project_files():
        try:
            result.append(json.loads(file.read_text('utf-8')))
        except (OSError, ValueError):
            raise ValueError('有项目数据无法读取，无法可靠检查房间编号冲突：' + file.parent.name)
    return result


def geometry(path):
    """Native baked node map: line 10, generation|nodeCount|...; type 0 = Exit."""
    try:
        lines = Path(path).read_text('utf-8-sig').splitlines()
        parts = lines[9].split('|')
        count = int(parts[1])
        generation = int(parts[0])
        if generation < 0 or count < 1 or len(parts) < count + 3:
            raise ValueError()
        types = [int(part.split(',')[0]) for part in parts[3:3 + count]]
        exits = next((i for i, kind in enumerate(types) if kind != 0), count)
        if 0 in types[exits:]:
            raise ValueError()
        width = int(lines[1].split('*')[0])
        height = int(lines[1].split('*')[1].split('|')[0])
        if generation == 0:
            # Native PreprocessRoom writes generation 0 when setupValues.bake
            # is false. The connectivity map can still be complete. Validate
            # it and compare current tile endpoints instead of rejecting it.
            templates = int(parts[2])
            if templates < 1 or templates > 256 or width < 1 or height < 1:
                raise ValueError()
            for node in parts[3:3 + count]:
                fields = node.split(',')
                if len(fields) < 5 + count * templates:
                    raise ValueError()
                [int(value) for value in fields[:5]]
                for pair in fields[5:5 + count * templates]:
                    if len(pair.split()) != 2:
                        raise ValueError()
                    [int(value) for value in pair.split()]
            tiles = lines[11].split('|')
            if tiles[-1] == '':
                tiles.pop()
            if len(tiles) != width * height:
                raise ValueError()
            actual_exits = 0
            for tile in tiles:
                fields = tile.split(',')
                int(fields[0])
                shortcut = 0
                for feature in fields[1:]:
                    if feature == '3': shortcut = max(shortcut, 1)
                    elif feature in ('4', '5', '9', '12'): shortcut = {'4': 2, '5': 3, '9': 4, '12': 5}[feature]
                actual_exits += shortcut == 2
            if actual_exits != exits:
                raise ValueError()
        return dict(exitCount=exits, width=width, height=height)
    except (OSError, ValueError, IndexError, UnicodeError):
        raise ValueError('房间出口数据尚未烘焙或无法读取，请先在房间编辑器中保存并导入渲染结果。')


def source_for(project, kind):
    previous = binding(project)
    name = previous['ai' if kind == 'ai' else 'entry']
    if kind == 'entry' and project.get('roomBinding') and previous['entryMode'] == 'existing':
        return resolve_room_source(name)
    cache = storage.project_file(project['projectId']).parent / 'rooms/rendered' / name
    if cache.with_suffix('.txt').exists():
        return cache
    own = storage.target_mod(project['projectId']) / 'world' / (previous['region'].lower() + '-rooms') / name
    if own.with_suffix('.txt').exists():
        return own
    if project.get('roomBinding'):
        raise ValueError('当前绑定的房间素材缺失：' + name + '；请先同步此房间，不会回退到旧房间或默认模板。')
    assets = storage.GAME / 'RainWorld_Data/StreamingAssets'
    if kind == 'entry':
        configured = storage.settings.get('entryRoomTemplate')
        if configured:
            candidate = (storage.DATA / configured).resolve()
            if not candidate.is_relative_to(storage.DATA.resolve()):
                raise ValueError('入口模板路径越界')
            return candidate
        return waiting_room.rendered()
    return assets / 'world/ss-rooms/ss_ai'


def _room_map(cat):
    result = {}
    for region in cat.get('regions', []):
        for row in region.get('rooms', []):
            if row['name'] in result:
                result[row['name']]['conditional'] = True
            else:
                result[row['name']] = copy.deepcopy(row)
    return result


def normalize(raw):
    """Syntax-only validation for ordinary project deserialization."""
    if not isinstance(raw, dict) or set(raw) - BINDING_KEYS:
        raise ValueError('房间绑定字段无效；已占用出口暂不支持覆盖。')
    result = copy.deepcopy(raw)
    for key in ('region', 'ai', 'entry'):
        if not isinstance(result.get(key), str):
            raise ValueError('缺少房间或区域编号')
        result[key] = result[key].strip().upper()
    if not REGION_RE.fullmatch(result['region']):
        raise ValueError('区域编号须为 2–8 位大写英文字母或数字，并以字母开头。')
    for key in ('ai', 'entry'):
        if not ROOM_RE.fullmatch(result[key]) or not result[key].startswith(result['region'] + '_'):
            raise ValueError('房间编号须以区域编号加下划线开头，仅可使用大写字母、数字和下划线。')
    if result['ai'] == result['entry']:
        raise ValueError('演算室与入口不能使用相同房间编号。')
    if not isinstance(result.get('oracleId'), str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,47}', result['oracleId']):
        raise ValueError('迭代器内部编号须以英文字母开头，仅含字母、数字、下划线或短横线，最长 48 位。')
    if result.get('entryMode') not in ('copy', 'existing'):
        raise ValueError('入口模式无效')
    for key in ('aiNode', 'entryNode'):
        if type(result.get(key)) is not int or not 0 <= result[key] <= 63:
            raise ValueError('出口序号须为 0–63 的整数。')
    return result


def validate(project, raw, catalogue=None):
    if _fixed(project['projectId']):
        raise ValueError('此项目的固定房间属于原版或关联模组；请创建独立项目后修改。')
    result = normalize(raw)
    cat = catalogue if catalogue is not None else catalog()
    rooms = _room_map(cat)
    current = binding(project)
    reserved_ids = {value['oracleId'].lower() for value in native_projects.BINDINGS.values()}
    reserved_ids.add('default')
    for linked in storage.LINKS:
        reserved_ids.update(value['oracleId'].lower() for value in linked.get('projects', {}).values())
    for oracle in cat.get('oracles', []):
        if oracle.get('projectId') != project['projectId']:
            reserved_ids.add(oracle.get('oracleId', '').lower())
    if result['oracleId'].lower() in reserved_ids:
        raise ValueError('此迭代器内部编号已由原版、关联项目或已启用内容使用。')
    own = {current['ai']}
    if current.get('entryMode', 'copy') == 'copy':
        own.add(current['entry'])
    other_projects = [p for p in _projects() if p['projectId'] != project['projectId']]
    for other in other_projects:
        used = binding(other)
        if used['oracleId'].lower() == result['oracleId'].lower():
            raise ValueError('此迭代器内部编号已被另一项目使用。')
        if result['ai'] in (used['ai'], used['entry']) or result['entry'] in (used['ai'], used['entry']):
            raise ValueError('此房间编号已被另一项目使用。')
        if used['region'] == result['region'] and result['region'] != 'TEST':
            raise ValueError('目标区域已有另一个迭代器项目，请使用独立区域。')
    reserved = set(cat.get('reservedRooms', [])) | set(rooms)
    for key in ('ai', 'entry'):
        if key == 'entry' and result['entryMode'] == 'existing':
            continue
        if result[key] in reserved and result[key] not in own:
            raise ValueError('目标房间编号已存在于游戏或已安装模组中：' + result[key])
    if result['region'] != 'TEST':
        for room in rooms.values():
            if room.get('region') == result['region'] and room.get('oracle') and room['name'] not in own:
                raise ValueError('目标区域已有原版或其他模组的演算室。')
        for name in cat.get('reservedRooms', []):
            if name.startswith(result['region'] + '_') and name.endswith('_AI') and name not in own:
                raise ValueError('目标区域的已安装内容已有演算室。')
    known_regions = set(cat.get('reservedRegions', [])) | {v['name'] for v in cat.get('regions', [])}
    current_local_region = result['region'] == current['region'] and current.get('entryMode') == 'copy'
    if result['entryMode'] == 'copy' and result['region'] in known_regions and not current_local_region:
        raise ValueError('此区域已存在；请选择新区域，或明确选择该区域的现有房间作为入口。')
    ai_geometry = geometry(source_for(project, 'ai').with_suffix('.txt'))
    if result['aiNode'] >= ai_geometry['exitCount']:
        raise ValueError('所选演算室出口不在实际房间地形中。')
    if result['entryMode'] == 'copy':
        entry_geometry = geometry(source_for(project, 'entry').with_suffix('.txt'))
        if result['entryNode'] >= entry_geometry['exitCount']:
            raise ValueError('所选入口出口不在实际房间地形中。')
    else:
        if not cat.get('fresh') or not cat.get('complete') or cat.get('source') != 'live':
            raise ValueError('连接现有房间需要新鲜、完整的游戏目录；请进入游戏后刷新。')
        entry = rooms.get(result['entry'])
        if not entry or entry.get('region') != result['region']:
            raise ValueError('入口不在游戏当前加载的区域目录中。')
        if entry.get('oracle') or entry['name'] in own:
            raise ValueError('不能把已有演算室或本项目生成的房间作为外部入口。')
        if entry.get('conditional'):
            raise ValueError('该房间有角色或时间线条件连接，不能安全覆盖。')
        if not entry.get('verified') or len(entry.get('connections', [])) != entry.get('exitCount') or result['entryNode'] >= entry['exitCount']:
            raise ValueError('所选入口出口尚未通过实际地形验证。')
        target = entry['connections'][result['entryNode']]
        if target != 'DISCONNECTED' and not (current.get('entryMode') == 'existing' and target == current['ai'] and result['entry'] == current['entry'] and result['entryNode'] == current['entryNode']):
            raise ValueError('该出口已连接到 ' + target + '；请选择空闲出口，现有连接不会被自动拆除。')
    return result


def _room_line(name, connections, tags=''):
    return name + ' : ' + ', '.join(connections) + (' : ' + tags if tags else '')


def plan(project, raw, catalogue=None):
    cat = catalogue if catalogue is not None else catalog()
    normalized = validate(project, raw, cat)
    region = normalized['region']
    count = geometry(source_for(project, 'ai').with_suffix('.txt'))['exitCount']
    ai_links = ['DISCONNECTED'] * count
    ai_links[normalized['aiNode']] = normalized['entry']
    old = binding(project)
    previous_ai = old['entry'] if old['ai'] == normalized['ai'] and old['aiNode'] == normalized['aiNode'] else 'DISCONNECTED'
    changes = [dict(room=normalized['ai'], node=normalized['aiNode'], fromRoom=previous_ai, to=normalized['entry'])]
    if old['ai'] == normalized['ai'] and old['aiNode'] != normalized['aiNode']:
        changes.append(dict(room=normalized['ai'], node=old['aiNode'], fromRoom=old['entry'], to='DISCONNECTED'))
    if old['entryMode'] == 'existing' and old['entry'] != normalized['entry']:
        changes.append(dict(room=old['entry'], node=old['entryNode'], fromRoom=old['ai'], to='DISCONNECTED'))
    copies = [dict(kind='ai', name=normalized['ai'], source=str(source_for(project, 'ai')))]
    warnings = ['更改世界房间索引后需要重启游戏；已有存档中的旧房间位置不会自动迁移。']
    if normalized['oracleId'] != binding(project)['oracleId']:
        warnings.append('内部编号改变后，存档中以旧编号记录的好感度和阅读进度不会自动迁移。')
    lines = [_room_line(normalized['ai'], ai_links)]
    if normalized['entryMode'] == 'copy':
        entry_count = geometry(source_for(project, 'entry').with_suffix('.txt'))['exitCount']
        entry_links = ['DISCONNECTED'] * entry_count
        previous_entry = old['ai'] if old['entryMode'] == 'copy' and old['entry'] == normalized['entry'] and old['entryNode'] == normalized['entryNode'] else 'DISCONNECTED'
        if old['entryMode'] == 'copy' and old['entry'] == normalized['entry'] and old['entryNode'] != normalized['entryNode']:
            changes.append(dict(room=normalized['entry'], node=old['entryNode'], fromRoom=old['ai'], to='DISCONNECTED'))
        copies.append(dict(kind='entry', name=normalized['entry'], source=str(source_for(project, 'entry'))))
        path = 'world/' + region.lower() + '/world_' + region.lower() + '.txt'
    else:
        row = _room_map(cat)[normalized['entry']]
        entry_links = list(row['connections'])
        previous_entry = entry_links[normalized['entryNode']]
        if old.get('entryMode') == 'existing' and old['entry'] == normalized['entry']:
            old_node = old['entryNode']
            if old_node < len(entry_links) and entry_links[old_node] == old['ai']:
                entry_links[old_node] = 'DISCONNECTED'
                if old_node != normalized['entryNode']:
                    changes.append(dict(room=normalized['entry'], node=old_node, fromRoom=old['ai'], to='DISCONNECTED'))
        path = 'modify/world/' + region.lower() + '/world_' + region.lower() + '.txt'
        warnings.append('将通过本地模组的合并文件增加连接；启用模组顺序改变后需要重新核对出口。')
    previous = previous_entry
    entry_links[normalized['entryNode']] = normalized['ai']
    entry_line = _room_line(normalized['entry'], entry_links, row.get('tags', '') if normalized['entryMode'] == 'existing' else '')
    if normalized['entryMode'] == 'copy':
        lines.append(entry_line)
    changes.append(dict(room=normalized['entry'], node=normalized['entryNode'], fromRoom=previous, to=normalized['ai']))
    # Native MergeWorldFiles interleaves/deduplicates connection arrays. A fixed
    # geometry node must use its explicit line replacement, not a room merge.
    prefix = ('[FINDLINESTART]' + normalized['entry'] + ' :\n[REPLACE]' + entry_line + '\n[MERGE]\n') if normalized['entryMode'] == 'existing' else ''
    text = prefix + 'ROOMS\n' + '\n'.join(lines) + '\nEND ROOMS\n'
    if normalized['entryMode'] == 'copy':
        text += '\nCREATURES\nEND CREATURES\n'
    return dict(binding=normalized, warnings=warnings, requiresRestart=True, worldFiles={path: text},
                roomCopies=copies, connectionChanges=changes, catalogGeneration=cat.get('generation'))


def remember_plan(project_id, value):
    """Server calls only after plan() succeeds; never accepts a client supplied plan."""
    path = storage.project_file(storage.valid_id(project_id)).parent / 'room-binding-plan.json'
    with LOCK:
        _atomic(path, value)


def _stored_plan(pid):
    path = storage.project_file(pid).parent / 'room-binding-plan.json'
    if not path.exists():
        return None
    return json.loads(path.read_text('utf-8'))


def compile_worlds(records, plans=None):
    """Return reviewed local-mod relative text files without mutating storage."""
    plans = plans or {}
    files, groups, replacements, owned_regions = {}, {}, {}, set()
    for record in records:
        if record.get('ownerMod') != 'moreiterators.local' or _fixed(record['projectId']):
            continue
        pid = record['projectId']
        value = plans.get(pid) or _stored_plan(pid)
        if value:
            if any(value['binding'][key] != record[key] for key in ('ai', 'entry', 'oracleId')):
                raise ValueError('房间绑定计划与当前项目不同，请重新预览并保存房间设置。')
            current = storage.load_project(pid) if storage.project_file(pid).exists() else None
            current_matches = current is not None and binding(current) == value['binding']
            owned_links = {}
            for copied in value.get('roomCopies', []):
                kind = copied['kind']
                source = source_for(current, kind) if current_matches else Path(copied['source'])
                exits = geometry(source.with_suffix('.txt'))['exitCount']
                node = value['binding']['aiNode' if kind == 'ai' else 'entryNode']
                if node >= exits:
                    raise ValueError('房间地形的出口已改变，请重新预览并设置房间连接。')
                links = ['DISCONNECTED'] * exits
                links[node] = value['binding']['entry' if kind == 'ai' else 'ai']
                owned_links[copied['name']] = links
            for relative, text in value['worldFiles'].items():
                if not re.fullmatch(r'(?:modify/)?world/[a-z0-9]+/world_[a-z0-9]+\.txt', relative):
                    raise ValueError('房间计划输出路径无效')
                rows = parse_world(text, value['binding']['region'])
                for row in rows:
                    if row['name'] in owned_links:
                        row['connections'] = owned_links[row['name']]
                groups.setdefault(relative, []).extend(rows)
                if relative.startswith('modify/'):
                    directives = text.split('[MERGE]\n', 1)[0]
                    if not directives.startswith('[FINDLINESTART]') or '\n[REPLACE]' not in directives:
                        raise ValueError('现有房间缺少明确的原生连接替换指令，请重新预览。')
                    replacements.setdefault(relative, []).append(directives)
                if not relative.startswith('modify/'):
                    owned_regions.add(value['binding']['region'])
        else:
            region = record['ai'].split('_')[0]
            if region != 'TEST' or record.get('roomBinding'):
                raise ValueError('此自定义房间缺少已验证的连接计划，请重新保存房间设置。')
            relative = 'world/test/world_test.txt'
            owned_regions.add(region)
            groups.setdefault(relative, []).extend([
                dict(name=record['ai'], connections=['DISCONNECTED', record['entry']], tags=''),
                dict(name=record['entry'], connections=([record['ai']] if record.get('entryNode', 1) == 0 else ['DISCONNECTED', record['ai']]), tags='')])
    for relative, rows in groups.items():
        names = [row['name'] for row in rows]
        if len(names) != len(set(names)):
            raise ValueError('多个项目正在修改同一房间，请先解决房间冲突。')
        prefix = ''.join(replacements.get(relative, [])) + '[MERGE]\n' if relative.startswith('modify/') else ''
        files[relative] = prefix + 'ROOMS\n' + '\n'.join(_room_line(row['name'], row['connections'], row.get('tags', '')) for row in rows) + '\nEND ROOMS\n\nCREATURES\nEND CREATURES\n'
    for region in sorted(owned_regions):
        files['world/' + region.lower() + '/properties.txt'] = 'RoomSettingTemplates: SS\nPalette: 26\nGrime: 0\nClouds: 0\n'
        files['world/' + region.lower() + '/displayname.txt'] = region + '\n'
    files['modify/world/regions.txt'] = ''.join('[ADD]' + region + '\n' for region in sorted(owned_regions))
    return files


def write_worlds(records, plans=None):
    """Write only manifest-owned world files; geometry is the server's transaction.

    Linked/native records are ignored. Returns managed paths for installation
    cleanup. Original room geometry and foreign content are never touched.
    """
    files = compile_worlds(records, plans)
    root = storage.DATA / 'local-mod'
    manifest = root / '.mi-room-bindings.json'
    with LOCK:
        previous = json.loads(manifest.read_text('utf-8')) if manifest.exists() else {'files': []}
        managed = set(previous.get('files', []))
        # Adopt only the old creator's exact default TEST output paths during migration.
        legacy = {'world/test/world_test.txt', 'world/test/properties.txt', 'world/test/displayname.txt', 'modify/world/regions.txt'}
        for relative in files:
            path = root / relative
            if path.exists() and relative not in managed and relative not in legacy:
                raise ValueError('本地模组已有未登记的同名文件，不能覆盖：' + relative)
        snapshot = {}
        targets = managed | set(files)
        for relative in targets:
            path = (root / relative).resolve()
            if not path.is_relative_to(root.resolve()) or not (relative.startswith('world/') or relative.startswith('modify/world/')):
                raise ValueError('已管理的世界文件路径无效')
            snapshot[path] = path.read_bytes() if path.exists() else None
        snapshot[manifest] = manifest.read_bytes() if manifest.exists() else None
        try:
            for relative, text in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_name(path.name + '.tmp')
                temporary.write_text(text, 'utf-8')
                os.replace(temporary, path)
            for relative in managed - set(files):
                (root / relative).unlink(missing_ok=True)
            _atomic(manifest, dict(schema='moreiterators.room-bindings.v1', files=sorted(files)))
        except Exception:
            for path, content in snapshot.items():
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
            raise
    return dict(files=sorted(files), removed=sorted(managed - set(files)), requiresRestart=True)
