from pathlib import Path
import copy
import hashlib
import io
import json
import re
import time
import uuid
import zipfile

import project_packages as packages
import room_bindings
import room_migration
import storage

SCHEMA = 'moreiterators.project-bundle.v1'
MOD_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}')
UID = re.compile(r'[a-f0-9]{32}')
SEMVER = re.compile(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)')
EXCLUDED_DIRS = {'.git', '.svn', '.vs', '.idea', '__pycache__', 'node_modules', 'obj', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
EXCLUDED_SUFFIXES = {'.log', '.pdb', '.pyc', '.tmp', '.bak', '.user', '.suo'}


def _safe(root, relative=''):
    root = Path(root).absolute()
    if relative and any(any(ord(char)<32 or char in '<>"|?*' for char in part) or re.fullmatch(r'(?i)(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',part)
                        for part in packages._relative(relative).split('/')):raise ValueError('项目包文件名无效')
    target = root / packages._relative(relative) if relative else root
    current = target
    while True:
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            raise ValueError('项目包不能读取或写入链接目录')
        if current == current.parent:break
        current = current.parent
    if not target.resolve().is_relative_to(root.resolve()):raise ValueError('项目包路径越界')
    return target


def _mod_id(value):
    if not isinstance(value, str) or not MOD_ID.fullmatch(value) or value in ('.', '..'):raise ValueError('请选择有效的地图模组')
    return value


def _mod_roots():
    found = {}
    for value in room_bindings.enabled_asset_roots():
        root = Path(value);asset_root = root
        root = root.parent if root.name == 'newest' or re.fullmatch(r'v\d+(?:\.\d+)+', root.name) else root
        info = root / 'modinfo.json'
        if not info.is_file() or not ((root / 'world').is_dir() or (asset_root / 'world').is_dir()):continue
        _safe(root, 'modinfo.json')
        meta = packages._read_json(info.read_bytes(), 'modinfo.json')
        identifier = _mod_id(meta.get('id'))
        if identifier.lower().startswith(('moreiterators', 'more_iterators')):continue
        found.setdefault(identifier, {})[str(root.resolve())] = (root, meta)
    return found


def mod_choices():
    result = []
    for identifier, roots in _mod_roots().items():
        meta = next(iter(roots.values()))[1]
        result.append(dict(id=identifier, name=meta.get('name', identifier), version=meta.get('version', ''),
                           available=len(roots) == 1, reason='' if len(roots) == 1 else '存在同名模组，请先停用重复版本'))
    return dict(mods=sorted(result, key=lambda row: row['name']))


def _mod_files(identifier):
    roots = _mod_roots().get(_mod_id(identifier), {})
    if len(roots) != 1:raise ValueError('地图模组未启用或存在重复版本：' + identifier)
    root, metadata = next(iter(roots.values()));files = {};excluded = [];stamps = {}
    def visit(folder):
        for item in sorted(folder.iterdir()):
            relative = item.relative_to(root).as_posix()
            _safe(root, relative)
            if item.is_dir():
                if item.name.casefold() in EXCLUDED_DIRS:excluded.append(relative + '/');continue
                visit(item)
            elif item.is_file():
                if item.suffix.casefold() in EXCLUDED_SUFFIXES or item.name.casefold() in {'exceptionlog.txt', 'consolelog.txt', 'logoutput.txt'}:
                    excluded.append(relative);continue
                if item.stat().st_size > packages.MAX_UNCOMPRESSED:raise ValueError('地图文件体积超限：' + relative)
                before = item.stat();data = item.read_bytes();after = item.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or len(data) != after.st_size:raise ValueError('导出期间地图文件发生变化：' + relative)
                stamps[item] = (after.st_size, after.st_mtime_ns);_privacy_check(relative, data)
                files[relative] = data
                if len(files) > packages.MAX_FILES or sum(map(len, files.values())) > packages.MAX_UNCOMPRESSED:raise ValueError('地图模组体积超限')
    visit(root)
    for file, stamp in stamps.items():
        _safe(root, file.relative_to(root).as_posix());current = file.stat()
        if stamp != (current.st_size, current.st_mtime_ns):raise ValueError('导出期间地图文件发生变化：' + file.relative_to(root).as_posix())
    metadata = packages._read_json(files['modinfo.json'], 'modinfo.json')
    if metadata.get('id') != identifier:raise ValueError('导出期间地图模组编号发生变化')
    return metadata, files, excluded


def _privacy_check(relative, data):
    name = Path(relative).name.casefold()
    if name == '.env' or name.startswith('.env.') or name in {'id_rsa', 'id_ed25519', 'credentials.json'} or b'-----BEGIN PRIVATE KEY-----' in data:
        raise ValueError('地图文件可能包含私人信息，请检查：' + relative)


    if Path(relative).suffix.lower() not in {'.json', '.txt', '.xml', '.yaml', '.yml', '.ini', '.cfg', '.cs', '.py', '.js', '.md'}:return
    try:text = data.decode('utf-8-sig')
    except UnicodeDecodeError:return
    paths = re.search(r'(?i)[a-z]:[\\/]+Users[\\/]+[^\\/\s"<>]+|/home/[^/\s"<>]+/|/Users/[^/\s"<>]+/', text)
    secret = re.search(r'(?i)["\']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password)["\']?\s*[:=]\s*["\']([^"\'\r\n]{8,})["\']', text)
    if paths or secret and not re.fullmatch(r'(?i)(?:example|placeholder|your[_ -].*|\*+|x+|<.*>)', secret[1]):
        raise ValueError('地图文件可能包含私人信息，请检查：' + relative)


def inspect_mods(request):
    if request.get('externalMods') == []:return dict(mods=[])
    _, identifiers = _ids(dict(projects=[], externalMods=request.get('externalMods', [])))
    result = []
    for identifier in identifiers:
        metadata, files, excluded = _mod_files(identifier)
        result.append(dict(id=identifier, name=metadata.get('name', identifier), files=len(files), bytes=sum(map(len, files.values())), excluded=excluded))
    return dict(mods=result)


def _ids(request):
    values = request.get('projects', [request['projectId']] if request.get('projectId') else [])
    external = request.get('externalMods', [])
    if not isinstance(values, list) or len(values) > 100 or any(not isinstance(value, str) for value in values) or len(set(values)) != len(values):raise ValueError('请选择有效项目')
    values = [storage.valid_id(value) for value in values]
    if not isinstance(external, list) or len(external) > 20 or any(not isinstance(value, str) for value in external) or len(set(external)) != len(external):raise ValueError('请选择有效的地图模组')
    external = [_mod_id(value) for value in external]
    if not values and not external:raise ValueError('请选择要导出的项目')
    return values, external


def package_info(request, default_name=''):
    name = request.get('packageName', default_name)
    version = request.get('packageVersion', '0.1.0')
    if not isinstance(name, str) or not name.strip() or len(name) > 100 or any(ord(char) < 32 or char in '\\/:*?"<>|' for char in name) or name.endswith(('.', ' ')) or re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', name, re.I):raise ValueError('请输入有效的项目包名称')
    if not isinstance(version, str) or not SEMVER.fullmatch(version):raise ValueError('版本格式为 0.1.0')
    return dict(name=name, version=version)


def _raw(file):
    file = _safe(storage.DATA, Path(file).relative_to(storage.DATA).as_posix())
    return packages._read_json(file.read_bytes(), file.name)


def _associations(request, ids, rooms):
    files = {};metadata = {};selected = set(ids);room_set = set(rooms)
    for key in ('pearls', 'broadcasts', 'projections', 'workPearls'):
        if type(request.get(key, False)) is not bool:raise ValueError('导出选项无效')
    if request.get('pearls'):
        import pearl_projects
        catalog_file = pearl_projects.metadata_path()
        catalog = _raw(catalog_file) if catalog_file.is_file() else dict(projects=[dict(id='legacy', name='珍珠')], activeId='legacy')
        cid = pearl_projects.valid_id(request.get('pearlCollectionId') or catalog.get('activeId'))
        entry = next((row for row in catalog['projects'] if row['id'] == cid), None)
        if entry is None:raise ValueError('请选择有效的珍珠项目')
        base = storage.DATA / ('pearls' if cid == 'legacy' and not catalog_file.exists() else 'pearl-projects/' + cid + '/pearls')
        for file in sorted(base.glob('*/pearl.json')):
            value = _raw(file)
            if not (selected.intersection(value.get('spawnProjects', [])) or room_set.intersection(value.get('spawnRooms', [])) or any(row.get('projectId') in selected for row in value.get('readers', []))):continue
            relative = 'pearl-projects/' + cid + '/pearls/' + value['id'] + '/pearl.json'
            raw = file.read_bytes() if 'collectionId' in value else None
            value = copy.deepcopy(value);value.setdefault('collectionId', cid)
            files[relative] = raw if raw is not None else packages._json(value);metadata[cid] = copy.deepcopy(entry)
    if request.get('broadcasts'):
        for file in sorted((storage.DATA / 'broadcasts').glob('*/broadcast.json')):
            value = _raw(file)
            if value.get('room') in room_set:files['broadcasts/' + value['id'] + '/broadcast.json'] = file.read_bytes()
    if request.get('projections'):
        for file in sorted((storage.DATA / 'projections').glob('*/projection.json')):
            value = _raw(file)
            if value.get('projectId') in selected:files['projections/' + value['uid'] + '/projection.json'] = file.read_bytes()
        for pid in ids:
            file = _safe(storage.DATA, 'projections/project-settings/' + pid + '.json')
            if file.is_file():files['projections/project-settings/' + pid + '.json'] = file.read_bytes()
    return files, list(metadata.values())


def _zip(files):
    if len(files) > packages.MAX_FILES or sum(map(len, files.values())) > packages.MAX_UNCOMPRESSED:raise ValueError('项目包体积超限')
    content = io.BytesIO()
    with zipfile.ZipFile(content, 'w', zipfile.ZIP_DEFLATED) as archive:
        for relative, data in sorted(files.items()):archive.writestr(packages._relative(relative), data)
    payload = content.getvalue()
    if len(payload) > packages.MAX_COMPRESSED:raise ValueError('项目包压缩体积超限')
    return payload


def export_package(request, server):
    ids, external = _ids(request)
    if 'packageName' in request:package_info(request)
    extras = request.get('extraRooms', [])
    if not isinstance(extras, list) or any(not isinstance(name, str) or not room_bindings.ROOM_RE.fullmatch(name) for name in extras) or len(set(extras)) != len(extras):raise ValueError('额外房间选择无效')
    if extras and not ids:raise ValueError('额外房间需要选择一个迭代器项目')
    import audio_assets
    documents = [storage.load_project(pid) for pid in ids]
    associated = any(request.get(key, False) for key in ('pearls', 'broadcasts', 'projections'))
    if len(ids) == 1 and not external and not associated and not audio_assets.references(documents) and 'packageName' not in request and 'packageVersion' not in request:return packages.export_package(ids[0], extras, server)
    files = {};projects = [];mods = [];rooms = [];pending_connections=[]
    required = set()
    for pid in ids:
        binding = room_bindings.binding(storage.load_project(pid));required.update((binding['ai'], binding['entry']))
    extras = [name for name in extras if name not in required]
    for index, pid in enumerate(ids):
        result = packages.export_package(pid, extras if index == 0 else [], server, available_rooms=required|set(extras))
        artifact = _safe(storage.EXPORTS, Path(result['url']).name)
        try:payload = artifact.read_bytes()
        finally:artifact.unlink(missing_ok=True)
        relative = 'projects/' + pid + '.zip';files[relative] = payload
        projects.append(dict(projectId=pid, name=result['name'], path=relative))
        if result.get('connectionsPending'):pending_connections.append(pid)
        rooms.extend(row['name'] for row in result['rooms'])
    content, collections = _associations(request, ids, rooms)
    documents.extend(packages._read_json(data, name) for name, data in content.items())
    for asset in audio_assets.references(documents):
        source = _safe(storage.DATA, 'audio/' + asset + '.mp3')
        if not source.is_file():raise ValueError('找不到已导入的音乐：' + asset[:12])
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != asset or audio_assets.parse_mp3(data)[0] != data:raise ValueError('音乐资源校验失败')
        content['audio/' + asset + '.mp3'] = data
    for relative, data in content.items():files['content/' + relative] = data
    for identifier in external:
        metadata, entries, excluded = _mod_files(identifier)
        prefix = 'external-mods/' + identifier + '/'
        for relative, data in entries.items():files[prefix + relative] = data
        mods.append(dict(id=identifier, name=metadata.get('name', identifier), version=metadata.get('version', ''), path=prefix[:-1], excluded=excluded))
    info = package_info(request, projects[0]['name'] if projects else mods[0]['name'])
    manifest = dict(schema=SCHEMA, package=info, projects=projects, externalMods=mods, pearlCollections=collections,
                    components={key:request.get(key, False) for key in ('pearls', 'broadcasts', 'projections', 'workPearls')}, files=packages._records(files))
    files['bundle.json'] = packages._json(manifest);payload = _zip(files)
    _inspect(payload, server, check_destination=False)
    filename = info['name'] + '-' + info['version'] + '-' + uuid.uuid4().hex[:8] + '.zip';target = _safe(storage.EXPORTS, filename)
    target.parent.mkdir(parents=True, exist_ok=True);temporary = target.with_suffix('.tmp')
    try:temporary.write_bytes(payload);temporary.replace(target)
    finally:temporary.unlink(missing_ok=True)
    from urllib.parse import quote
    return dict(url='/exports/' + quote(filename), kind='project-bundle', package=info, projects=projects, externalMods=mods, rooms=rooms,
                connectionsPending=bool(pending_connections),pendingConnectionProjects=pending_connections)


def _content_path(relative, data, ids, collections):
    audio = re.fullmatch(r'audio/([a-f0-9]{64}).mp3', relative)
    if audio:
        import audio_assets
        if hashlib.sha256(data).hexdigest() != audio[1] or audio_assets.parse_mp3(data)[0] != data:raise ValueError('音乐资源校验失败')
        return None
    value = packages._read_json(data, relative)
    if not isinstance(value, dict):raise ValueError('关联内容格式无效')
    match = re.fullmatch(r'pearl-projects/(legacy|[a-f0-9]{32})/pearls/([A-Z]{1,4}[0-9]{2,4})/pearl.json', relative)
    if match:
        cid, identifier = match.groups()
        if value.get('schema') != 'moreiterators.pearl.v1' or value.get('collectionId') != cid or value.get('id') != identifier or not UID.fullmatch(value.get('uid', '')) or cid not in collections:raise ValueError('珍珠元数据与清单不一致')
        import pearls
        try:pearls.validate(value, resolve_sources=False)
        except (ValueError, TypeError, KeyError) as error:raise ValueError('珍珠文件 ' + relative + '：' + str(error)) from error
        return value
    match = re.fullmatch(r'broadcasts/([A-Z][A-Z0-9_]{1,31})/broadcast.json', relative)
    if match:
        import broadcasts
        if value.get('id') != match[1]:raise ValueError('广播编号与清单不一致')
        room = value.get('room', '');region = value.get('region', '')
        if room and (not isinstance(room, str) or not room_bindings.ROOM_RE.fullmatch(room) or room.split('_')[0] != region):raise ValueError('广播房间编号无效')
        checked = copy.deepcopy(value);checked.update(room='', region='')
        broadcasts.validate(checked, require_room=False)
        return value
    match = re.fullmatch(r'projections/([a-f0-9]{32})/projection.json', relative)
    if match:
        import projections
        if value.get('uid') != match[1] or value.get('projectId') not in ids:raise ValueError('投影归属与清单不一致')
        projections.validate(value, resolve_sources=False)
        return value
    match = re.fullmatch(r'projections/project-settings/([a-z][a-z0-9-]{0,47}).json', relative)
    if match and match[1] in ids:
        import projections
        if value.get('schema') != 'moreiterators.projection-settings.v1' or value.get('projectId') != match[1] or type(value.get('revision')) is not int or value['revision'] < 0:raise ValueError('投影项目设置无效')
        projections.validate_mask(value.get('mask'))
        return value
    raise ValueError('项目包包含未知关联内容')


def _inspect(payload, server, *, check_destination=True):
    files = packages._archive(payload)
    if 'bundle.json' not in files:return None
    manifest = packages._read_json(files['bundle.json'], 'bundle.json')
    if not isinstance(manifest, dict) or manifest.get('schema') != SCHEMA or set(manifest) != {'schema', 'package', 'projects', 'externalMods', 'pearlCollections', 'components', 'files'}:raise ValueError('项目合集版本不支持')
    if not isinstance(manifest['package'], dict) or set(manifest['package']) != {'name', 'version'}:raise ValueError('项目包信息无效')
    package_info(dict(packageName=manifest['package']['name'], packageVersion=manifest['package']['version']))
    if not isinstance(manifest['components'], dict) or set(manifest['components']) != {'pearls', 'broadcasts', 'projections', 'workPearls'} or any(type(value) is not bool for value in manifest['components'].values()):raise ValueError('项目合集内容选择无效')
    if not isinstance(manifest['pearlCollections'], list) or len(manifest['pearlCollections']) > 100 or not isinstance(manifest['files'], list):raise ValueError('项目合集清单无效')
    if not isinstance(manifest['projects'], list) or not isinstance(manifest['externalMods'], list) or not manifest['projects'] and not manifest['externalMods']:raise ValueError('项目合集为空')
    if len(manifest['projects']) > 100 or len(manifest['externalMods']) > 20:raise ValueError('项目合集数量超限')
    available_rooms=set()
    for entry in manifest['projects']:
        if not isinstance(entry,dict):raise ValueError('项目合集条目无效')
        pid=storage.valid_id(entry.get('projectId'));relative='projects/'+pid+'.zip'
        if entry.get('path')!=relative or relative not in files:raise ValueError('项目合集条目无效')
        inner=packages._archive(files[relative]);room_manifest=packages._read_json(inner.get('manifest.json',b''),'manifest.json')
        rooms=room_manifest.get('rooms') if isinstance(room_manifest,dict) else None
        if not isinstance(rooms,list) or len(rooms)>packages.MAX_ROOMS:raise ValueError('项目房间清单无效')
        for row in rooms:
            name=row.get('name') if isinstance(row,dict) else None
            if not isinstance(name,str) or not room_bindings.ROOM_RE.fullmatch(name):raise ValueError('项目房间清单无效')
            available_rooms.add(name)
    expected = {'bundle.json'};projects = [];ids = set();mod_ids = set();unpacked = sum(map(len, files.values()))
    for entry in manifest['projects']:
        if not isinstance(entry, dict):raise ValueError('项目合集条目无效')
        pid = storage.valid_id(entry.get('projectId'));relative = 'projects/' + pid + '.zip'
        if pid in ids or entry.get('path') != relative or relative not in files:raise ValueError('项目合集条目无效')
        project, room_manifest, room_files = packages._inspect(files[relative], server, available_rooms=available_rooms, check_destination=check_destination)
        if project['projectId'] != pid or project['name'] != entry.get('name'):raise ValueError('项目合集编号不一致')
        unpacked += sum(map(len, room_files.values()))
        if unpacked > packages.MAX_UNCOMPRESSED:raise ValueError('项目合集解压体积超限')
        projects.append((project, room_manifest, room_files));ids.add(pid);expected.add(relative)
    collections = {}
    import pearl_projects
    for entry in manifest['pearlCollections']:
        if not isinstance(entry, dict):raise ValueError('珍珠项目元数据无效')
        cid = pearl_projects.valid_id(entry.get('id'));pearl_projects.valid_name(entry.get('name'))
        if cid in collections:raise ValueError('珍珠项目重复')
        collections[cid] = entry
    for entry in manifest['externalMods']:
        if not isinstance(entry, dict):raise ValueError('地图模组条目无效')
        identifier = _mod_id(entry.get('id'));prefix = 'external-mods/' + identifier + '/'
        if identifier in mod_ids or entry.get('path') != prefix[:-1]:raise ValueError('地图模组条目无效')
        names = [name for name in files if name.startswith(prefix)]
        if prefix + 'modinfo.json' not in names:raise ValueError('地图模组缺少 modinfo.json')
        metadata = packages._read_json(files[prefix + 'modinfo.json'], 'modinfo.json')
        if metadata.get('id') != identifier:raise ValueError('地图模组编号不一致')
        for name in names:
            relative = name[len(prefix):];packages._relative(relative)
            if any(part.casefold() in EXCLUDED_DIRS for part in Path(relative).parts[:-1]) or Path(relative).suffix.casefold() in EXCLUDED_SUFFIXES:raise ValueError('地图模组包含私人数据或临时文件')
        expected.update(names);mod_ids.add(identifier)
    documents = [project for project, _, _ in projects]
    for relative, data in files.items():
        if relative.startswith('content/'):
            document = _content_path(relative[8:], data, ids, collections)
            if document is not None:documents.append(document)
            expected.add(relative)
    import audio_assets
    referenced = {'content/audio/' + asset + '.mp3' for asset in audio_assets.references(documents)}
    if referenced != {name for name in files if name.startswith('content/audio/')}:raise ValueError('音乐资源与项目引用不一致')
    if expected != set(files):raise ValueError('项目合集包含未声明内容')
    indexed = {}
    for row in manifest['files']:
        if not isinstance(row, dict):raise ValueError('项目合集文件清单无效')
        name = packages._relative(row.get('path'))
        if name in indexed or name not in files or name == 'bundle.json' or type(row.get('size')) is not int or row['size'] != len(files[name]) or row.get('sha256') != hashlib.sha256(files[name]).hexdigest():raise ValueError('项目合集文件校验失败')
        indexed[name] = row
    if set(indexed) != set(files) - {'bundle.json'}:raise ValueError('项目合集文件清单不完整')
    return manifest, files, projects


def _summary(inspected):
    manifest, files, projects = inspected;collisions = [];items = [];mods = []
    for project, room_manifest, _ in projects:
        pid = project['projectId'];exists = packages._project_dir(pid).exists()
        items.append(dict(projectId=pid, name=project['name'], collision=exists, rooms=room_manifest['rooms'],connectionsPending=room_manifest.get('connectionState')=='pending'))
        if exists:collisions.append(dict(key='project/' + pid, name=project['name'], kind='project'))
    for entry in manifest['externalMods']:
        exists = _safe(storage.DATA, 'imported-mods/' + entry['id']).exists()
        mods.append(dict(id=entry['id'], name=entry.get('name', entry['id']), collision=exists))
        if exists:collisions.append(dict(key='external/' + entry['id'], name=entry.get('name', entry['id']), kind='external'))
    for relative, data in files.items():
        if not relative.startswith('content/'):continue
        target = _safe(storage.DATA, relative[8:])
        if target.exists() and target.read_bytes() != data:collisions.append(dict(key=relative, name=relative[8:], kind='content'))
    catalog = _safe(storage.DATA, 'pearl-projects.json')
    if catalog.is_file():
        current = packages._read_json(catalog.read_bytes(), catalog.name)
        for incoming in manifest['pearlCollections']:
            old = next((entry for entry in current.get('projects', []) if entry.get('id') == incoming['id']), None)
            if old is not None and old.get('name') != incoming.get('name'):collisions.append(dict(key='collection/'+incoming['id'], name=incoming['name'], kind='content'))
    pending_connections=[item['projectId'] for item in items if item['connectionsPending']]
    return dict(kind='project-bundle', name=manifest['package']['name'], version=manifest['package']['version'], projects=items, externalMods=mods, collisions=collisions, collision=bool(collisions),
                connectionsPending=bool(pending_connections),pendingConnectionProjects=pending_connections)


def inspect_import(payload, server):
    result = _inspect(payload, server)
    return _summary(result) if result else packages.inspect_import(payload, server)


def _project_writes(project, manifest, files):
    pid = project['projectId'];base = packages._project_dir(pid)
    if storage.link(pid) or storage.binding(pid):raise ValueError('项目合集不能写入关联模组或原版项目')
    _safe(base)
    previous = packages.load_metadata(pid)
    writes = {packages._local_path(name):data for name, data in files.items() if name != 'manifest.json'}
    writes['project.json'] = packages._json(project)
    local = dict(schema=packages.LOCAL_SCHEMA, projectId=pid, rooms=manifest['rooms'], regions=manifest['regions'], palettes=manifest['palettes'], importedAtNs=time.time_ns(), files=packages._records({name:data for name, data in writes.items() if name != 'project.json'}))
    writes[packages.LOCAL_MANIFEST] = packages._json(local)
    obsolete = []
    for entry in (previous or {}).get('files', []):
        if entry['path'] not in writes:
            if not packages._local_file(entry['path']):raise ValueError('旧房间清单路径无效')
            obsolete.append(_safe(base, entry['path']))
    return {_safe(base, relative):data for relative, data in writes.items()}, obsolete


def import_package(payload, server, replace=False, choices=None):
    if type(replace) is not bool or choices is not None and not isinstance(choices, dict):raise ValueError('导入选择无效')
    with server.LOCK:
        result = _inspect(payload, server)
        if result is None:return packages.import_package(payload, server, replace)
        manifest, files, projects = result;summary = _summary(result);choices = choices or {}
        if any(value not in ('keep', 'replace', 'copy') for value in choices.values()):raise ValueError('导入选择无效')
        for item in summary['collisions']:
            if item['key'] not in choices:return dict(ok=False, **summary)
            if choices[item['key']] == 'copy' and item['kind'] != 'external':raise ValueError('此项需要选择保留或替换')
        incoming_uids = {}
        for relative, data in files.items():
            if not relative.startswith('content/') or choices.get(relative) == 'keep' or not relative.endswith(('/pearl.json', '/broadcast.json')):continue
            value = packages._read_json(data, relative);key = (value['schema'], value['uid'])
            if key in incoming_uids and incoming_uids[key] != relative:raise ValueError('关联内容内部编号重复：' + value.get('name', value['uid']))
            incoming_uids[key] = relative
        if incoming_uids:
            candidates = [*storage.DATA.glob('pearl-projects/*/pearls/*/pearl.json'), *storage.DATA.glob('pearls/*/pearl.json'), *storage.DATA.glob('broadcasts/*/broadcast.json')]
            for file in candidates:
                if file.parent.parent == storage.DATA/'pearls':
                    migrated=_safe(storage.DATA,'pearl-projects/legacy/pearls/'+file.parent.name+'/pearl.json')
                    if migrated.is_file():continue
                value = _raw(file);relative = incoming_uids.get((value.get('schema'), value.get('uid')))
                target=_safe(storage.DATA,relative[8:]) if relative else None
                legacy_target=_safe(storage.DATA,'pearl-projects/legacy/pearls/'+file.parent.name+'/pearl.json') if file.parent.parent == storage.DATA/'pearls' else None
                if relative and target.resolve() not in {file.resolve(),legacy_target.resolve() if legacy_target else None}:raise ValueError('关联内容内部编号已用于其他文件：' + value.get('name', value['uid']))
        writes = {};obsolete = [];included = [];external = [];plans = [];pending_connections=[]
        def add(target, data):
            if target in writes and writes[target] != data:raise ValueError('所选项目的文件互相冲突')
            writes[target] = data
        owned = {}
        for project, room_manifest, room_files in projects:
            pid = project['projectId']
            if choices.get('project/' + pid) == 'keep':continue
            for row in room_manifest['rooms']:
                if row['kind'] not in ('ai', 'entry') or row['kind'] == 'entry' and room_bindings.binding(project)['entryMode'] != 'copy':continue
                if row['name'] in owned and owned[row['name']] != pid:raise ValueError('所选项目的房间编号重复：' + row['name'])
                owned[row['name']] = pid
            planned, removed = _project_writes(project, room_manifest, room_files)
            for target, data in planned.items():add(target, data)
            obsolete.extend(removed);included.append(project)
            if room_manifest.get('connectionState')=='pending':
                pending_connections.append(pid)
                obsolete.append(_safe(packages._project_dir(pid),'room-binding-plan.json'))
            elif project.get('roomBinding'):plans.append((project, _safe(packages._project_dir(pid), 'room-binding-plan.json')))
        for relative, data in files.items():
            if relative.startswith('content/') and choices.get(relative) != 'keep':add(_safe(storage.DATA, relative[8:]), data)
        if manifest['pearlCollections']:
            import pearl_projects
            catalog_path = _safe(storage.DATA, 'pearl-projects.json')
            catalog = packages._read_json(catalog_path.read_bytes(), catalog_path.name) if catalog_path.exists() else dict(schema=pearl_projects.SCHEMA, projects=[], activeId=manifest['pearlCollections'][0]['id'])
            for entry in manifest['pearlCollections']:
                old = next((row for row in catalog['projects'] if row['id'] == entry['id']), None)
                if old is None:catalog['projects'].append(copy.deepcopy(entry))
                elif choices.get('collection/'+entry['id']) == 'replace':catalog['projects'][catalog['projects'].index(old)] = copy.deepcopy(entry)
            pearl_projects._validate_catalog(catalog);add(catalog_path, packages._json(catalog))
        for entry in manifest['externalMods']:
            identifier = entry['id'];choice = choices.get('external/' + identifier)
            if choice == 'keep':continue
            name = identifier if choice != 'copy' else identifier + '-' + uuid.uuid4().hex[:8]
            destination = _safe(storage.DATA, 'imported-mods/' + name);prefix = 'external-mods/' + identifier + '/'
            for relative, data in files.items():
                if relative.startswith(prefix):add(_safe(destination, relative[len(prefix):]), data)
            if choice == 'replace' and destination.exists():
                for file in destination.rglob('*'):
                    _safe(destination, file.relative_to(destination).as_posix())
                    if file.is_file() and file not in writes:obsolete.append(file)
            external.append(dict(id=identifier, name=entry.get('name', identifier), directory=str(destination)))
        transaction = room_migration.Files();created = set()
        for target in [*writes, *obsolete, *(target for _, target in plans)]:
            current = target.parent
            while not current.exists():created.add(current);current = current.parent
            transaction.watch(target)
        try:
            for target, data in writes.items():transaction.write(target, data)
            for target in obsolete:transaction.remove(target)
            for project, target in plans:
                if project.get('roomConnections'):
                    import room_workflow
                    plan = room_workflow.import_plan(project)
                else:plan = room_bindings.plan(project, project['roomBinding'])
                transaction.json(target, plan)
        except Exception:
            transaction.rollback()
            for directory in sorted(created, key=lambda value: len(value.parts), reverse=True):
                if directory.is_dir() and not any(directory.iterdir()):directory.rmdir()
            raise
        return dict(ok=True, kind='project-bundle', projects=included, project=included[0] if included else None, externalMods=external, requiresApply=bool(included),connectionsPending=bool(pending_connections),pendingConnectionProjects=pending_connections)
