
from pathlib import Path, PurePosixPath
import copy
import hashlib
import io
import json
import os
import re
import stat
import time
import zipfile
import uuid
from PIL import Image
import room_bindings
import room_editor
import room_migration
import storage
import room_asset_dependencies

SCHEMA = 'moreiterators.project-package.v1'
LOCAL_SCHEMA = 'moreiterators.project-package.local.v1'
LOCAL_MANIFEST = 'room-package.json'
MAX_COMPRESSED = 128 * 1024 * 1024
MAX_UNCOMPRESSED = 256 * 1024 * 1024
MAX_FILES = 4096
MAX_ROOMS = 256
MAX_PIXELS = 64 * 1024 * 1024
OUTPUT_MANIFEST = '.mi-project-package-assets.json'
OUTPUT_SCHEMA = 'moreiterators.project-package-assets.v1'
OUTPUT_PATH = re.compile(r'world/[a-z0-9]+-rooms/[A-Z][A-Z0-9]{1,7}_[A-Z0-9_]{1,64}(?:\.txt|_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|_[1-9][0-9]*\.png)|palettes/palette\d+\.png|'+room_asset_dependencies.PATH_PATTERN)


def _local_file(relative):
    return bool(re.fullmatch(r'rooms/(?:rendered/[A-Z0-9_]+(?:_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|\.txt|\.png)|[A-Z0-9_]+\.(?:txt|png)|palettes/palette\d+\.png|regions/[A-Z0-9]+/(?:properties|displayname|map_[a-z0-9]+)\.txt)',relative) or
                relative.startswith('rooms/assets/') and room_asset_dependencies.PATH.fullmatch(relative[len('rooms/assets/'):]))


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')


def _read_json(content, label):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:raise ValueError('重复的 JSON 字段：' + key)
            result[key] = value
        return result
    try:
        return json.loads(content.decode('utf-8-sig'), object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ValueError('项目包 JSON 无效：' + label) from error


def _relative(path):
    if not isinstance(path, str) or not path or len(path) > 240 or '\\' in path or ':' in path or '\x00' in path:
        raise ValueError('项目包路径无效')
    parts = path.split('/')
    if any(part in ('', '.', '..') or part.endswith((' ', '.')) for part in parts) or PurePosixPath(path).is_absolute():
        raise ValueError('项目包路径越界')
    return path


def _safe(base, relative):
    base = Path(base).resolve()
    path = base / _relative(relative)
    current = path
    while current != base:
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            raise ValueError('项目包路径不能经过链接')
        current = current.parent
    if not path.resolve().is_relative_to(base):raise ValueError('项目包路径越界')
    return path


def _file(path):
    path = Path(path)
    if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
        raise ValueError('房间素材不能是链接：' + path.name)
    if not path.is_file():raise ValueError('缺少房间文件：' + path.name)
    if path.stat().st_size > MAX_UNCOMPRESSED:raise ValueError('房间文件体积超限：' + path.name)
    return path.read_bytes()


def _png(content, label):
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.format != 'PNG' or image.width * image.height > MAX_PIXELS:
                raise ValueError('Invalid PNG')
            image.verify()
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise ValueError('房间图片无效：' + label) from error


def _text(content, label):
    try:text = content.decode('utf-8-sig')
    except UnicodeError as error:raise ValueError('房间文本编码无效：' + label) from error
    if not text.strip() or '\x00' in text:raise ValueError('房间文本无效：' + label)
    return text


def _geometry(content, name):
    rows = _text(content, name).splitlines()
    try:
        if len(rows) < 10 or rows[0].strip().upper() != name:raise ValueError()
        size = rows[1].split('|')[0].split('*')
        width, height = map(int, size)
        if not 0 < width <= 10000 or not 0 < height <= 10000:raise ValueError()
        cameras = [value.strip() for value in rows[3].split('|') if value.strip()]
        if not cameras or len(cameras) > 256 or any(not re.fullmatch(r'-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?', value) for value in cameras):raise ValueError()
        if rows[9] == '0':
            return len(cameras), room_bindings.geometry(None, content=content)['exitCount']
        nodes = rows[9].split('|');count = int(nodes[1])
        if int(nodes[0]) < 0 or not 0 < count <= 1024 or len(nodes) < count + 3:raise ValueError()
        types = [int(value.split(',')[0]) for value in nodes[3:3 + count]]
        exits = next((index for index, kind in enumerate(types) if kind != 0), count)
        if 0 in types[exits:]:raise ValueError()
        return len(cameras), exits
    except (ValueError, IndexError, TypeError) as error:
        raise ValueError('房间地形或相机数据无效：' + name) from error


def _sibling(prefix, suffix):
    
    expected = Path(prefix).name + suffix
    parent = Path(prefix).parent
    matches = [path for path in parent.iterdir() if path.name.casefold() == expected.casefold()] if parent.is_dir() else []
    if len(matches) > 1:raise ValueError('房间文件大小写冲突：' + expected)
    return matches[0] if matches else parent / expected


def _collect_render(source, settings, name, setting_files=None):
    
    if not isinstance(name, str) or not room_bindings.ROOM_RE.fullmatch(name):raise ValueError('房间编号无效')
    geometry = _file(_sibling(source, '.txt'))
    cameras, _ = _geometry(geometry, name)
    setting_bytes = _file(settings)
    _text(setting_bytes, name + '_settings.txt')
    files = {name + '.txt': geometry, name + '_settings.txt': setting_bytes}
    for filename,path in (setting_files or {}).items():
        if not re.fullmatch(re.escape(name)+r'(?:_settings(?:-[A-Za-z0-9_-]+)?|_properties)\.txt',filename):raise ValueError('房间设置文件名称无效')
        content=_file(path);_text(content,filename);files[filename]=content
    for index in range(1, cameras + 1):
        filename = name + '_' + str(index) + '.png'
        content = _file(_sibling(source, '_' + str(index) + '.png'))
        _png(content, filename);files[filename] = content
    return files


def _records(files):
    return [dict(path=path, size=len(content), sha256=hashlib.sha256(content).hexdigest()) for path, content in sorted(files.items())]


def _project_dir(pid):
    return storage.project_file(storage.valid_id(pid)).parent


def load_metadata(pid):
    path = _safe(_project_dir(pid), LOCAL_MANIFEST)
    if not path.is_file():return None
    value = _read_json(_file(path), LOCAL_MANIFEST)
    if not isinstance(value, dict) or value.get('schema') != LOCAL_SCHEMA or value.get('projectId') != pid:
        raise ValueError('项目房间清单无效')
    if not isinstance(value.get('rooms'), list) or not isinstance(value.get('files'), list):raise ValueError('项目房间清单无效')
    seen = set()
    for row in value['rooms']:
        if not isinstance(row, dict):raise ValueError('项目房间清单无效')
        name = row.get('name');links = row.get('connections');tags = row.get('tags', '')
        if not isinstance(name, str) or not room_bindings.ROOM_RE.fullmatch(name) or name in seen or row.get('region') != name.split('_')[0] or row.get('kind') not in ('ai', 'entry', 'extra'):
            raise ValueError('项目房间清单编号无效')
        if not isinstance(links, list) or len(links) > 1024 or any(not isinstance(link, str) or link != 'DISCONNECTED' and not room_bindings.ROOM_RE.fullmatch(link) for link in links):raise ValueError('项目房间连接清单无效')
        if not isinstance(tags, str) or len(tags) > 1024 or any(c in tags for c in '\r\n\x00'):raise ValueError('项目房间标签无效')
        if type(row.get('sourceAvailable')) is not bool:raise ValueError('项目房间源工程标记无效')
        seen.add(name)
    paths = set()
    for item in value['files']:
        if not isinstance(item, dict):raise ValueError('项目房间清单无效')
        path = item.get('path')
        _safe(_project_dir(pid), path)
        if path in paths or not _local_file(path):raise ValueError('项目房间文件清单无效')
        paths.add(path)
    return value


def rendered_source(pid, name):
    if not isinstance(name, str) or not room_bindings.ROOM_RE.fullmatch(name):raise ValueError('房间编号无效')
    metadata = load_metadata(pid)
    if not metadata or not any(row.get('name') == name for row in metadata['rooms']):return None
    base = _safe(_project_dir(pid), 'rooms/rendered/' + name)
    return base if _sibling(base, '.txt').is_file() else None


def asset_source(pid,relative):
    if not room_asset_dependencies.PATH.fullmatch(relative):raise ValueError('项目房间素材路径无效')
    import room_source_choices
    selected=room_source_choices.selected_asset(pid,relative)
    if selected is not None:return selected
    metadata=load_metadata(pid);local='rooms/assets/'+relative
    if not metadata or not any(item.get('path')==local for item in metadata['files']):return None
    path=_safe(_project_dir(pid),local)
    return path if path.is_file() else None


def palette_source(pid, index):
    if type(index) is not int or not 0 <= index <= 1000000:raise ValueError('调色板编号无效')
    import room_source_choices
    selected=room_source_choices.selected_asset(pid,'palettes/palette'+str(index)+'.png')
    if selected is not None:return selected
    path = _safe(_project_dir(pid), 'rooms/palettes/palette' + str(index) + '.png')
    return path if path.is_file() else None


def region_file(pid, region, filename):
    if not isinstance(region, str) or not room_bindings.REGION_RE.fullmatch(region):raise ValueError('区域编号无效')
    if filename not in ('properties.txt', 'displayname.txt', 'map_' + region.lower() + '.txt'):raise ValueError('区域文件无效')
    path = _safe(_project_dir(pid), 'rooms/regions/' + region + '/' + filename)
    return path if path.is_file() else None


def _catalog_rows():
    result = {}
    for region in room_bindings.catalog().get('regions', []):
        for row in region.get('rooms', []):
            name = row.get('name', '')
            if room_bindings.ROOM_RE.fullmatch(name):
                if name in result:result[name]['conditional'] = True
                else:result[name] = copy.deepcopy(row)
    return result


def _owned_source(project, name):
    pid = project['projectId']
    room_editor.ensure_synced(pid, name)
    candidates = [_project_dir(pid) / 'rooms/rendered' / name,
                  storage.target_mod(pid) / 'world' / (name.split('_')[0].lower() + '-rooms') / name]
    installed = storage.installed_mod(pid, required=False)
    if installed is not None:candidates.append(installed / 'world' / (name.split('_')[0].lower() + '-rooms') / name)
    candidates = [candidate for candidate in candidates if _sibling(candidate, '.txt').is_file()]
    if candidates:
        def modified(candidate):
            
            
            files = [file for file in candidate.parent.iterdir() if re.fullmatch(re.escape(candidate.name) + r'(?:\.txt|_[1-9][0-9]*\.png)', file.name, re.I)]
            return max(file.stat().st_mtime_ns for file in files)
        return max(candidates, key=modified)
    raise ValueError('当前房间缺少已同步素材：' + name + '；请先同步房间，不会使用默认模板。')


def _source(project, name, rows):
    import room_source_choices
    selected = room_source_choices.selected_source(project['projectId'], name)
    if selected is not None:return selected
    binding = room_bindings.binding(project)
    owned = name == binding['ai'] or name == binding['entry'] and binding['entryMode'] == 'copy'
    if owned:return _owned_source(project, name)
    imported = rendered_source(project['projectId'], name)
    if imported:return _owned_source(project, name)
    row = rows.get(name)
    if row is None or row.get('conditional'):raise ValueError('房间不存在或包含未支持的条件连接：' + name)
    return room_bindings.resolve_room_source(name)


def selected_room_source(project, name, rows=None):
    
    if not isinstance(name, str) or not room_bindings.ROOM_RE.fullmatch(name):raise ValueError('房间编号无效')
    return _source(project, name, _catalog_rows() if rows is None else rows)


def _settings(project, name, source):
    import room_source_choices
    selected = room_source_choices.selected_settings(project['projectId'], name)
    if selected is not None:return selected
    binding = room_bindings.binding(project)
    owned = name == binding['ai'] or name == binding['entry'] and binding['entryMode'] == 'copy'
    if owned or rendered_source(project['projectId'], name):
        installed = storage.installed_mod(project['projectId'], required=False)
        folders = ([installed] if installed is not None else []) + [storage.target_mod(project['projectId'])]
        candidates = []
        for folder in folders:
            candidate = folder / 'world' / (name.split('_')[0].lower() + '-rooms') / name
            value = _sibling(candidate, '_settings.txt')
            if value.is_file():candidates.append(value)
        
        cached = _safe(_project_dir(project['projectId']), 'rooms/rendered/' + name)
        cached_settings = _sibling(cached, '_settings.txt')
        if cached_settings.is_file():candidates.append(cached_settings)
        source_settings = _sibling(source, '_settings.txt')
        if source_settings.is_file():candidates.append(source_settings)
        if candidates:return max(candidates, key=lambda path: path.stat().st_mtime_ns)
    return _sibling(source, '_settings.txt')


def selected_room_settings(project, name, source):
    if not isinstance(name, str) or not room_bindings.ROOM_RE.fullmatch(name):raise ValueError('房间编号无效')
    return _settings(project, name, source)


def room_settings_files(project,name,settings):
    import room_source_choices
    selected=room_source_choices.selected_settings_files(project['projectId'],name)
    if selected:return selected
    settings=Path(settings)
    result={name+'_settings.txt':settings}
    pattern=re.compile(re.escape(name)+r'(?P<suffix>_settings-[A-Za-z0-9_-]+|_properties)\.txt',re.I)
    seen={}
    for candidate in sorted(settings.parent.iterdir()) if settings.parent.is_dir() else []:
        match=pattern.fullmatch(candidate.name)
        if not match:continue
        suffix=match['suffix'];suffix='_properties' if suffix.casefold()=='_properties' else '_settings-'+suffix.split('-',1)[1]
        filename=name+suffix+'.txt';key=filename.casefold()
        if key in seen:raise ValueError('房间文件大小写冲突：'+filename)
        path=_safe(settings.parent,candidate.name)
        if not path.is_file():raise ValueError('缺少房间设置变体：'+candidate.name)
        seen[key]=path;result[filename]=path
    root=_project_dir(project['projectId']);cached=root/'rooms/rendered'
    folders=[cached,storage.target_mod(project['projectId'])/'world'/(name.split('_')[0].lower()+'-rooms')]
    installed=storage.installed_mod(project['projectId'],required=False)
    if installed is not None:folders.append(installed/'world'/(name.split('_')[0].lower()+'-rooms'))
    if settings.parent.resolve() not in {folder.resolve() for folder in folders}:return result
    metadata=load_metadata(project['projectId'])
    for item in (metadata or {}).get('files',[]):
        relative=item['path']
        if re.fullmatch('rooms/rendered/'+re.escape(name)+r'(?:_settings-[A-Za-z0-9_-]+|_properties)\.txt',relative):
            filename=Path(relative).name
            if filename.casefold() not in seen:raise ValueError('缺少房间设置变体：'+filename)
    return result


def _origin(project, path):
    path = Path(path).resolve();pid = project['projectId']
    if path.is_relative_to(_project_dir(pid).resolve()):return 'project'
    installed = storage.installed_mod(pid, required=False)
    if installed is not None and path.is_relative_to(installed.resolve()):return 'installed'
    if path.is_relative_to(storage.target_mod(pid).resolve()):return 'local'
    return 'enabled'


def _connections(project, name, source, rows):
    pid = project['projectId'];region = name.split('_')[0]
    
    roots = [storage.target_mod(pid)]
    installed = storage.installed_mod(pid, required=False)
    if installed is not None:roots.insert(0, installed)
    if source.parent.parent.name.lower() == 'world':roots.append(source.parent.parent.parent)
    candidates = []
    for root in roots:
        file = root / 'world' / region.lower() / ('world_' + region.lower() + '.txt')
        if not file.is_file():continue
        matches = [row for row in room_bindings.parse_world(_text(_file(file), file.name), region) if row['name'] == name]
        if len(matches) == 1 and not matches[0].get('conditional'):
            candidates.append((file.stat().st_mtime_ns, matches[0]['connections'], matches[0].get('tags', '')))
            continue
        if matches:raise ValueError('房间包含条件连接，不能简化导出：' + name)
    metadata = load_metadata(pid)
    if metadata:
        previous = next((row for row in metadata['rooms'] if row.get('name') == name), None)
        if previous:
            stamp = previous.get('updatedAtNs', metadata.get('importedAtNs'))
            if stamp is None:stamp = (_project_dir(pid) / LOCAL_MANIFEST).stat().st_mtime_ns
            if type(stamp) is not int or stamp < 0:raise ValueError('项目房间导入时间无效')
            candidates.append((stamp, list(previous['connections']), previous.get('tags', '')))
    if candidates:
        _, connections, tags = max(candidates, key=lambda value: value[0])
        return list(connections), tags
    if name in rows and rows[name].get('connections') is not None:
        return list(rows[name]['connections']), rows[name].get('tags', '')
    binding = room_bindings.binding(project)
    _, count = _geometry(_file(_sibling(source, '.txt')), name)
    links = ['DISCONNECTED'] * count
    if name in (binding['ai'], binding['entry']):
        key = 'ai' if name == binding['ai'] else 'entry';node = binding[key + 'Node']
        if node >= count:raise ValueError('房间出口与项目连接不一致：' + name)
        links[node] = binding['entry' if key == 'ai' else 'ai']
    return links, ''


def selected_room_connections(project, name, source, rows=None):
    return _connections(project, name, source, _catalog_rows() if rows is None else rows)


def inspect_choices(pid, server):
    project = storage.load_project(storage.valid_id(pid));binding = room_bindings.binding(project)
    rows = _catalog_rows();metadata = load_metadata(pid)
    for row in (metadata or {}).get('rooms', []):rows.setdefault(row['name'], row)
    required = {binding['ai']: 'ai', binding['entry']: 'entry'}
    names = sorted(set(rows) | set(required));result = []
    for name in names:
        kind = required.get(name, 'extra');available = True;reason = ''
        try:
            if name in required or any(row['name'] == name for row in (metadata or {}).get('rooms', [])):
                source = _source(project, name, rows)
                available = _sibling(source, '.txt').is_file() and _settings(project, name, source).is_file()
            else:
                row = rows[name];path = row.get('geometryPath')
                available = bool(path and not row.get('conditional') and Path(path).is_file())
        except (OSError, ValueError) as error:available = False;reason = str(error)
        row = dict(name=name, region=name.split('_')[0], kind=kind, required=name in required,
                   available=available, sourceAvailable=_safe(_project_dir(pid), 'rooms/' + name + '.txt').is_file())
        if reason:row['reason'] = reason
        result.append(row)
    return dict(projectId=pid, rooms=result, extraRooms=[row['name'] for row in (metadata or {}).get('rooms', []) if row.get('kind') == 'extra'])


def _region_source(project, region, source, filename):
    own = region == room_bindings.binding(project)['region']
    roots = []
    if own:
        installed = storage.installed_mod(project['projectId'], required=False)
        if installed is not None:roots.append(installed)
        roots.append(storage.target_mod(project['projectId']))
    if source.parent.parent.name.lower() == 'world':roots.append(source.parent.parent.parent)
    candidates = []
    for root in roots:
        path = root / 'world' / region.lower() / filename
        if path.is_file():candidates.append(path)
    imported = region_file(project['projectId'], region, filename)
    if imported is not None:candidates.append(imported)
    return max(candidates, key=lambda path: path.stat().st_mtime_ns) if candidates else None


def _map_subset(content, names):
    rows = _text(content, 'map').splitlines()
    kept = [row for row in rows if row.split(':', 1)[0].strip().upper() in names]
    return ('\n'.join(kept) + '\n').encode('utf-8') if kept else None


def _check_template(text, label, properties=False):
    pattern = r'(?m)^Room Setting Templates:\s*([^\r\n]+)' if properties else r'(?m)^Template:\s*([^\r\n]+)'
    value = re.search(pattern, text)
    if value and value[1].strip().upper() != 'NONE':
        raise ValueError('房间 ' + label + ' 包含尚未支持完整迁移的模板依赖：' + value[1].strip() + '；不会修改为 NONE 或导出不完整的项目包。')


def collect_rooms(project, selections, server):
    
    import standalone
    import room_controls
    if not isinstance(selections, list) or not 2 <= len(selections) <= MAX_ROOMS:raise ValueError('请选择有效房间')
    rows = _catalog_rows();metadata = load_metadata(project['projectId'])
    for row in (metadata or {}).get('rooms', []):rows.setdefault(row['name'], row)
    names = [row.get('name') for row in selections]
    if len(set(names)) != len(names):raise ValueError('房间选择重复')
    files, records, regions, palette_ids = {}, [], {}, set()
    for item in selections:
        name = item.get('name');kind = item.get('kind')
        if not isinstance(name, str) or not room_bindings.ROOM_RE.fullmatch(name) or kind not in ('ai', 'entry', 'extra'):
            raise ValueError('房间选择无效')
        source = _source(project, name, rows);settings = _settings(project, name, source)
        setting_files=room_settings_files(project,name,settings)
        rendered = _collect_render(source, settings, name, setting_files)
        for filename in setting_files:
            _check_template(_text(rendered[filename], filename), filename)
            room_controls.require_portable_subset(_text(rendered[filename], filename),filename)
        for filename, content in rendered.items():files['rooms/' + name + '/rendered/' + filename] = content
        connections, tags = _connections(project, name, source, rows)
        _, exits = _geometry(rendered[name + '.txt'], name)
        if len(connections) != exits:raise ValueError('房间出口数量与世界连接不一致：' + name)
        editable = _safe(_project_dir(project['projectId']), 'rooms/' + name + '.txt')
        import room_source_choices
        chosen = room_source_choices.selected_version(project['projectId'], name)
        source_available = editable.is_file() and (chosen is None or chosen.get('pairedSource', False))
        if source_available:
            content = _file(editable)
            if not _text(content, editable.name).lstrip().startswith('[[['):raise ValueError('Rained 源工程无效：' + name)
            files['rooms/' + name + '/source/' + name + '.txt'] = content
            light = editable.with_suffix('.png')
            if light.is_file():
                content = _file(light);_png(content, light.name)
                files['rooms/' + name + '/source/' + name + '.png'] = content
        region = name.split('_')[0]
        records.append(dict(name=name, kind=kind, region=region, connections=connections, tags=tags,
                            sourceAvailable=source_available, sourceOrigin=_origin(project, source),
                            settingsOrigin=_origin(project, settings)))
        texts = [(_text(rendered[filename], filename), path) for filename,path in setting_files.items()]
        if region not in regions:
            region_files = []
            for filename in ('properties.txt', 'displayname.txt', 'map_' + region.lower() + '.txt'):
                asset = _region_source(project, region, source, filename)
                if asset is None:continue
                content = _file(asset)
                if filename.startswith('map_'):
                    content = _map_subset(content, set(names))
                    if content is None:continue
                _text(content, filename)
                if filename == 'properties.txt':_check_template(_text(content, filename), region, properties=True)
                files['regions/' + region + '/' + filename] = content;region_files.append(filename)
                if filename == 'properties.txt':texts.append((_text(content, filename), source))
            regions[region] = dict(code=region, files=region_files)
        for text, palette_owner in texts:
            for index in standalone.room_palette_ids(text):
                asset = palette_source(project['projectId'], index) if _origin(project, palette_owner) == 'project' else None
                if asset is None:asset = standalone.room_palette_source(project, palette_owner, index)
                content = _file(asset);_png(content, asset.name);key = 'palettes/palette' + str(index) + '.png'
                if key in files and files[key] != content:raise ValueError('房间使用同号但内容不同的调色板：' + str(index))
                files[key] = content;palette_ids.add(index)
            for relative,asset in standalone.room_settings_assets(project,palette_owner,text).items():
                content=_file(asset);key='assets/'+relative
                if key in files and files[key]!=content:raise ValueError('房间使用同名但内容不同的素材：'+relative)
                files[key]=content
    if sum(map(len, files.values())) > MAX_UNCOMPRESSED:raise ValueError('项目包解压后体积超限')
    return records, files, list(regions.values()), sorted(palette_ids)


def _summary(project, manifest, compressed, unpacked):
    rooms = [{key: row[key] for key in ('name', 'kind', 'region', 'sourceAvailable', 'sourceOrigin', 'settingsOrigin') if key in row} for row in manifest['rooms']]
    exists = storage.project_file(project['projectId']).exists() or _project_dir(project['projectId']).exists()
    return dict(projectId=project['projectId'], name=project['name'], exists=exists, collision=exists, rooms=rooms,
                missingSources=[row['name'] for row in rooms if not row['sourceAvailable']],
                compressedBytes=compressed, uncompressedBytes=unpacked)


def export_package(pid, extra_rooms, server):
    pid = storage.valid_id(pid);project = copy.deepcopy(storage.load_project(pid));server.validate(copy.deepcopy(project))
    import room_source_choices
    project=room_source_choices.export_project(project)
    if storage.binding(pid):raise ValueError('原版或关联模组固定项目不能导出为可覆盖的项目包')
    if not isinstance(extra_rooms, list) or any(not isinstance(name, str) for name in extra_rooms):raise ValueError('额外房间选择无效')
    binding = room_bindings.binding(project)
    if len(set(extra_rooms)) != len(extra_rooms) or set(extra_rooms) & {binding['ai'], binding['entry']}:
        raise ValueError('房间选择重复')
    selected = [dict(name=binding['ai'], kind='ai'), dict(name=binding['entry'], kind='entry')]
    selected += [dict(name=name, kind='extra') for name in extra_rooms]
    rooms, files, regions, palettes = collect_rooms(project, selected, server)
    files['project.json'] = _json(project)
    manifest = dict(schema=SCHEMA, projectId=pid, rooms=rooms, regions=regions, palettes=palettes, files=_records(files))
    files['manifest.json'] = _json(manifest)
    if len(files) > MAX_FILES or sum(map(len, files.values())) > MAX_UNCOMPRESSED:raise ValueError('项目包体积超限')
    content = io.BytesIO()
    with zipfile.ZipFile(content, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):archive.writestr(name, data)
    payload = content.getvalue()
    if len(payload) > MAX_COMPRESSED:raise ValueError('项目包压缩体积超限')
    
    _inspect(payload, server)
    storage.EXPORTS.mkdir(parents=True, exist_ok=True)
    filename = pid + '-project-' + uuid.uuid4().hex[:12] + '.zip'
    destination = storage.EXPORTS / filename
    temporary = destination.with_suffix('.zip.tmp')
    try:temporary.write_bytes(payload);temporary.replace(destination)
    finally:temporary.unlink(missing_ok=True)
    summary = _summary(project, manifest, len(payload), sum(map(len, files.values())))
    return dict(url='/exports/' + filename, **summary)


def _archive(payload):
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_COMPRESSED:raise ValueError('项目包压缩体积超限')
    if not payload.startswith(b'PK\x03\x04'):raise ValueError('请选择项目 ZIP 文件')
    files = {}
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            items = archive.infolist()
            if len(items) > MAX_FILES:raise ValueError('项目包文件过多')
            total = 0;names = set()
            for item in items:
                name = _relative(item.filename)
                if name.casefold() in names:raise ValueError('项目包包含重复文件：' + name)
                names.add(name.casefold())
                mode = item.external_attr >> 16
                if item.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG) or item.flag_bits & 1:
                    raise ValueError('项目包不能包含目录、链接或加密文件')
                if item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):raise ValueError('项目包压缩方式不支持')
                total += item.file_size
                if item.file_size < 0 or total > MAX_UNCOMPRESSED:raise ValueError('项目包解压后体积超限')
            for item in items:
                with archive.open(item) as source:data = source.read(item.file_size + 1)
                if len(data) != item.file_size:raise ValueError('项目包文件长度不符')
                files[item.filename] = data
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError) as error:
        raise ValueError('项目 ZIP 已损坏或不受支持') from error
    return files


def _inspect(payload, server):
    files = _archive(payload)
    if 'manifest.json' not in files or 'project.json' not in files:raise ValueError('不是完整的 MI 项目包')
    manifest = _read_json(files['manifest.json'], 'manifest.json');project = _read_json(files['project.json'], 'project.json')
    if not isinstance(manifest, dict) or manifest.get('schema') != SCHEMA:raise ValueError('项目包版本不支持')
    if set(manifest) != {'schema', 'projectId', 'rooms', 'regions', 'palettes', 'files'}:raise ValueError('项目包清单字段无效')
    if not isinstance(project, dict):raise ValueError('项目数据无效')
    pid = storage.valid_id(project.get('projectId'))
    if manifest.get('projectId') != pid:raise ValueError('项目编号与清单不一致')
    if storage.binding(pid):raise ValueError('项目包不能覆盖原版或关联模组的固定项目')
    project = server.validate(copy.deepcopy(project))
    rooms = manifest.get('rooms');regions = manifest.get('regions');palettes = manifest.get('palettes');entries = manifest.get('files')
    if not isinstance(rooms, list) or not 2 <= len(rooms) <= MAX_ROOMS or not isinstance(regions, list) or not isinstance(palettes, list) or not isinstance(entries, list):raise ValueError('项目房间清单无效')
    expected = {'project.json'};room_names = set();kinds = {};required_palettes = set();asset_references=[];optional_asset_references=[]
    import standalone
    for row in rooms:
        if not isinstance(row, dict) or set(row) - {'name', 'kind', 'region', 'connections', 'tags', 'sourceAvailable', 'sourceOrigin', 'settingsOrigin'} or not {'name', 'kind', 'region', 'connections', 'tags', 'sourceAvailable'}.issubset(row):raise ValueError('房间清单字段无效')
        if any(row.get(key, 'project') not in ('project', 'installed', 'local', 'enabled') for key in ('sourceOrigin', 'settingsOrigin')):raise ValueError('房间素材来源标记无效')
        name = row['name'];kind = row['kind'];region = row['region']
        if not isinstance(name, str) or not room_bindings.ROOM_RE.fullmatch(name) or name in room_names or kind not in ('ai', 'entry', 'extra') or region != name.split('_')[0]:raise ValueError('房间清单编号无效')
        if type(row['sourceAvailable']) is not bool or not isinstance(row['tags'], str) or len(row['tags']) > 1024 or any(c in row['tags'] for c in '\r\n\x00'):raise ValueError('房间清单字段无效')
        room_names.add(name);kinds.setdefault(kind, []).append(name)
        prefix = 'rooms/' + name + '/rendered/' + name
        for path in (prefix + '.txt', prefix + '_settings.txt'):
            if path not in files:raise ValueError('项目包缺少房间文件：' + path)
        expected.update((prefix + '.txt', prefix + '_settings.txt'))
        cameras, exits = _geometry(files[prefix + '.txt'], name)
        from room_controls import require_portable_subset
        setting_paths=[path for path in files if re.fullmatch(re.escape(prefix)+r'(?:_settings(?:-[A-Za-z0-9_-]+)?|_properties)\.txt',path)]
        for path in setting_paths:
            expected.add(path);settings=_text(files[path],path)
            _check_template(settings,path);require_portable_subset(settings,path)
            required_palettes.update(standalone.room_palette_ids(settings))
            asset_references.extend(room_asset_dependencies.references(settings,path))
            optional_asset_references.extend(room_asset_dependencies.optional_references(settings,path))
        links = row['connections']
        if not isinstance(links, list) or len(links) != exits or any(not isinstance(link, str) or link != 'DISCONNECTED' and not room_bindings.ROOM_RE.fullmatch(link) for link in links):raise ValueError('房间连接数据无效：' + name)
        for index in range(1, cameras + 1):
            path = prefix + '_' + str(index) + '.png';expected.add(path)
            if path not in files:raise ValueError('项目包缺少相机图片：' + path)
            _png(files[path], path)
        source = 'rooms/' + name + '/source/' + name
        if row['sourceAvailable']:
            expected.add(source + '.txt')
            if source + '.txt' not in files or not _text(files[source + '.txt'], name).lstrip().startswith('[[['):raise ValueError('项目包缺少有效 Rained 源工程：' + name)
            if source + '.png' in files:expected.add(source + '.png');_png(files[source + '.png'], source + '.png')
    binding = room_bindings.binding(project)
    if kinds.get('ai') != [binding['ai']] or kinds.get('entry') != [binding['entry']]:raise ValueError('项目的演算室或等待房间与清单不一致')
    catalogue_rows = _catalog_rows()
    for row in rooms:
        if row['kind'] == 'ai' or row['kind'] == 'entry' and binding['entryMode'] == 'copy':
            _assert_extra_available(project, row, catalogue_rows)
    region_codes = set()
    for row in regions:
        if not isinstance(row, dict) or set(row) != {'code', 'files'}:raise ValueError('区域清单无效')
        region = row['code'];names = row['files']
        if not isinstance(region, str) or not room_bindings.REGION_RE.fullmatch(region) or region in region_codes or region not in {r['region'] for r in rooms}:raise ValueError('区域清单无效')
        if not isinstance(names, list) or len(names) != len(set(names)) or any(name not in ('properties.txt', 'displayname.txt', 'map_' + region.lower() + '.txt') for name in names):raise ValueError('区域文件清单无效')
        region_codes.add(region)
        for name in names:
            path = 'regions/' + region + '/' + name;expected.add(path)
            if path not in files:raise ValueError('项目包缺少区域文件：' + path)
            text = _text(files[path], path)
            if name == 'properties.txt':
                _check_template(text, region, properties=True)
                required_palettes.update(standalone.room_palette_ids(text))
                asset_references.extend(room_asset_dependencies.references(text,path))
                optional_asset_references.extend(room_asset_dependencies.optional_references(text,path))
            if name.startswith('map_') and any(line.strip() and line.split(':', 1)[0].strip().upper() not in room_names for line in text.splitlines()):raise ValueError('地图包含未选择的房间')
    if any(type(index) is not int or not 0 <= index <= 1000000 for index in palettes) or len(set(palettes)) != len(palettes) or set(palettes) != required_palettes:raise ValueError('调色板清单与房间引用不一致')
    for index in palettes:
        path = 'palettes/palette' + str(index) + '.png';expected.add(path)
        if path not in files:raise ValueError('项目包缺少调色板：' + path)
        _png(files[path], path)
    for candidates in asset_references:
        present=[name for name in candidates if 'assets/'+name in files]
        if not present and room_asset_dependencies.has_native_ambient_reference(candidates):continue
        if len(present)!=1:raise ValueError('项目包房间素材缺失或来源不明确：'+candidates[0])
        relative=present[0];path='assets/'+relative;expected.add(path)
        room_asset_dependencies.validate(relative,files[path])
    for candidates in optional_asset_references:
        for relative in candidates:
            path='assets/'+relative
            if path not in files:continue
            room_asset_dependencies.validate(relative,files[path]);expected.add(path)
    if set(files) != expected | {'manifest.json'}:raise ValueError('项目包包含未声明文件或缺少文件')
    indexed = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'path', 'size', 'sha256'}:raise ValueError('文件校验清单无效')
        name = _relative(entry['path'])
        if name in indexed or name not in expected or type(entry['size']) is not int or entry['size'] != len(files[name]) or entry['sha256'] != hashlib.sha256(files[name]).hexdigest():raise ValueError('项目包文件校验失败：' + name)
        indexed[name] = entry
    if set(indexed) != expected:raise ValueError('项目包文件清单不完整')
    return project, manifest, files


def inspect_import(payload, server):
    project, manifest, files = _inspect(payload, server)
    return _summary(project, manifest, len(payload), sum(map(len, files.values())))


def _local_path(path):
    if path == 'project.json':return path
    match = re.fullmatch(r'rooms/([A-Z0-9_]+)/(rendered|source)/([A-Z0-9_]+(?:_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|\.txt|\.png))', path)
    if match:
        name, kind, filename = match.groups()
        return 'rooms/' + ('rendered/' if kind == 'rendered' else '') + filename
    if path.startswith('palettes/'):return 'rooms/' + path
    if path.startswith('regions/'):return 'rooms/' + path
    if path.startswith('assets/') and room_asset_dependencies.PATH.fullmatch(path[7:]):return 'rooms/' + path
    raise ValueError('项目包本地路径无效：' + path)


def import_package(payload, server, replace=False):
    if type(replace) is not bool:raise ValueError('覆盖选项无效')
    with server.LOCK:
        project, manifest, files = _inspect(payload, server)
        pid = project['projectId'];summary = _summary(project, manifest, len(payload), sum(map(len, files.values())))
        if summary['exists'] and not replace:return dict(ok=False, **summary)
        base = _project_dir(pid)
        
        if storage.link(pid) or storage.binding(pid):raise ValueError('项目包不能写入关联模组或原版项目')
        if base.is_symlink() or getattr(base, 'is_junction', lambda: False)():raise ValueError('项目目录不能是链接')
        previous = load_metadata(pid)
        writes = {_local_path(path): data for path, data in files.items() if path != 'manifest.json'}
        writes['project.json'] = _json(project)
        local = dict(schema=LOCAL_SCHEMA, projectId=pid, rooms=manifest['rooms'], regions=manifest['regions'],
                     palettes=manifest['palettes'], importedAtNs=time.time_ns(),
                     files=_records({p: data for p, data in writes.items() if p != 'project.json'}))
        destinations = {path: _safe(base, path) for path in writes}
        obsolete = []
        for entry in (previous or {}).get('files', []):
            relative = entry['path']
            if relative not in writes:
                
                if not _local_file(relative):raise ValueError('旧房间清单路径无效')
                obsolete.append(_safe(base, relative))
        all_targets = list(destinations.values()) + obsolete + [_safe(base, LOCAL_MANIFEST), _safe(base, 'room-binding-plan.json')]
        timestamps = {path: (path.stat().st_atime_ns, path.stat().st_mtime_ns) for path in all_targets if path.is_file()}
        created_dirs = set()
        for target in all_targets:
            directory = target.parent
            while directory.is_relative_to(base) and not directory.exists():
                created_dirs.add(directory);directory = directory.parent
        transaction = room_migration.Files()
        try:
            
            for relative in sorted(writes, key=lambda path: ('/rendered/' in path, path)):
                transaction.write(destinations[relative], writes[relative])
            for path in obsolete:transaction.remove(path)
            transaction.json(_safe(base, LOCAL_MANIFEST), local)
            
            
            if project.get('roomBinding'):
                plan = room_bindings.plan(project, project['roomBinding'])
                transaction.json(_safe(base, 'room-binding-plan.json'), plan)
        except Exception:
            transaction.rollback()
            for path, times in timestamps.items():
                if path.is_file():os.utime(path, ns=times)
            for directory in sorted(created_dirs, key=lambda path: len(path.parts), reverse=True):
                if directory.is_dir() and not any(directory.iterdir()):directory.rmdir()
            raise
        return dict(ok=True, project=project, rooms=summary['rooms'], missingSources=summary['missingSources'], requiresApply=True)


def _assert_extra_available(project, room, rows):
    name = room['name'];pid = project['projectId']
    for file in storage.project_files():
        if file.parent.name == pid:continue
        other = _read_json(_file(file), file.name);binding = room_bindings.binding(other)
        names = {binding['ai'], binding['entry']}
        names.update(row['name'] for row in (load_metadata(other['projectId']) or {}).get('rooms', []))
        if name in names:raise ValueError('房间编号属于其他项目：' + name)
    current = rows.get(name)
    if current:
        path = current.get('geometryPath')
        roots = [storage.target_mod(pid)]
        installed = storage.installed_mod(pid, required=False)
        if installed is not None:roots.append(installed)
        if not path or not any(Path(path).resolve().is_relative_to(root.resolve()) for root in roots):
            raise ValueError('房间与已启用内容重名：' + name + '；请先修改房间编号，不会覆盖原版或其他模组。')


def before_deploy(project, server):
    
    pid = storage.valid_id(project['projectId']);metadata = load_metadata(pid)
    if not metadata:return dict(projectId=pid, files={}, rooms=[], worldFiles={})
    import standalone
    binding = room_bindings.binding(project);rows = _catalog_rows();files = {};owned = [];palette_refs = [];region_sources = {};asset_refs=[]
    if binding != room_bindings.binding(storage.load_project(pid)):
        raise ValueError('房间绑定已改变，请先在区域连接保存后再应用项目')
    for kind in ('ai', 'entry'):
        if [row['name'] for row in metadata['rooms'] if row['kind'] == kind] != [binding[kind]]:
            raise ValueError('房间编号已改变，导入房间清单尚未迁移；已停止应用，避免写回旧房间。')
    for room in metadata['rooms']:
        name = room['name']
        if room['kind'] == 'entry' and binding['entryMode'] == 'existing':continue
        _assert_extra_available(project, room, rows)
        source = selected_room_source(project, name, rows)
        region_sources.setdefault(room['region'], source)
        settings = selected_room_settings(project, name, source)
        setting_files=room_settings_files(project,name,settings)
        rendered = _collect_render(source, settings, name, setting_files)
        for filename in setting_files:_check_template(_text(rendered[filename],filename),filename)
        for filename, content in rendered.items():
            files['world/' + room['region'].lower() + '-rooms/' + filename] = content
        for filename,path in setting_files.items():
            text=_text(rendered[filename],filename)
            palette_refs.extend((index,path) for index in standalone.room_palette_ids(text))
            asset_refs.append((path,text))
        owned.append(name)
    for region in metadata['regions']:
        region_source = region_sources.get(region['code'], _project_dir(pid) / 'rooms/rendered')
        properties = _region_source(project, region['code'], region_source, 'properties.txt')
        if properties:
            text = _text(_file(properties), properties.name);_check_template(text, region['code'], properties=True)
            palette_owner = properties if _origin(project, properties) != 'project' else _project_dir(pid) / 'rooms/rendered'
            palette_refs.extend((index, palette_owner) for index in standalone.room_palette_ids(text))
            asset_refs.append((palette_owner,text))
    for index, source in palette_refs:
        asset = palette_source(pid, index) if _origin(project, source) == 'project' else None
        if asset is None:asset = standalone.room_palette_source(project, source, index)
        content = _file(asset);_png(content, asset.name)
        relative = 'palettes/palette' + str(index) + '.png'
        if relative in files and files[relative] != content:raise ValueError('房间使用同号但内容不同的调色板：' + str(index))
        files[relative] = content
    for source,text in asset_refs:
        for relative,asset in standalone.room_settings_assets(project,source,text).items():
            content=_file(asset)
            if relative in files and files[relative]!=content:raise ValueError('房间使用同名但内容不同的素材：'+relative)
            files[relative]=content
    target = storage.target_mod(pid)
    previous = output_manifest(target)
    owners = {path: owner for owner, paths in previous['projects'].items() for path in paths}
    core = {binding['ai'], binding['entry']}
    borrowed = set()
    for relative, content in files.items():
        path = _safe(target, relative)
        if relative in owners and owners[relative] != pid:
            if not path.is_file() or _file(path) != content:raise ValueError('项目包素材与其他作品冲突：' + relative)
        if path.is_file() and relative not in owners:
            is_core = any(relative.startswith('world/' + binding['region'].lower() + '-rooms/' + name) for name in core)
            if not is_core and _file(path) != content:raise ValueError('本地已有未归属本项目的素材：' + relative)
            if not is_core:borrowed.add(relative)
    registry = storage.RUNTIME / 'creator/registry.json'
    records = _read_json(_file(registry), registry.name) if registry.is_file() else []
    if not isinstance(records, list) or any(not isinstance(record, dict) or 'projectId' not in record for record in records):raise ValueError('运行项目目录无效')
    records = [record for record in records if record['projectId'] != pid]
    records.append(storage.registry_record(project, binding['ai'], binding['entry'], binding['oracleId']))
    worlds = room_bindings.compile_worlds(records)
    installed = storage.installed_mod(pid, required=False)
    installed_previous = output_manifest(installed) if installed is not None else None
    return dict(projectId=pid, files=files, rooms=owned, worldFiles=worlds, previous=previous,
                installedPrevious=installed_previous, borrowed=sorted(borrowed))


def write_deploy_assets(prepared):
    
    if not prepared.get('files'):return dict(files=[], removed=[])
    pid = storage.valid_id(prepared['projectId']);root = storage.target_mod(pid)
    marker = root / OUTPUT_MANIFEST
    current = output_manifest(root)
    if current != prepared['previous']:raise ValueError('项目包输出已改变，请重试应用')
    borrowed = set(prepared.get('borrowed', []))
    previous = set(current['projects'].get(pid, []));new = set(prepared['files']) - borrowed
    referenced = {path for owner, paths in current['projects'].items() if owner != pid for path in paths}
    removed = previous - new - referenced
    installed = storage.installed_mod(pid, required=False)
    installed_manifest = output_manifest(installed) if installed is not None else None
    if installed_manifest != prepared.get('installedPrevious'):raise ValueError('已安装项目包输出已改变，请重试应用')
    installed_removed = set()
    if installed is not None:
        installed_owned = set(installed_manifest['projects'].get(pid, []))
        installed_shared = {path for owner, paths in installed_manifest['projects'].items() if owner != pid for path in paths}
        for relative in removed - installed_shared:
            target = _safe(installed, relative)
            if target.is_file():
                if relative not in installed_owned:raise ValueError('旧安装文件缺少项目归属，未自动删除：' + relative)
                installed_removed.add(relative)
    transaction = room_migration.Files()
    try:
        for relative, content in prepared['files'].items():
            if relative not in borrowed:transaction.write(_safe(root, relative), content)
        for relative in removed:transaction.remove(_safe(root, relative))
        for relative in installed_removed:transaction.remove(_safe(installed, relative))
        current['projects'][pid] = sorted(new);transaction.json(marker, current)
        metadata = load_metadata(pid)
        if metadata:
            metadata['deployedFiles'] = sorted(new)
            transaction.json(_safe(_project_dir(pid), LOCAL_MANIFEST), metadata)
    except Exception:transaction.rollback();raise
    return dict(files=sorted(new), removed=sorted(removed), installedRemoved=sorted(installed_removed))


def output_manifest(root):
    marker = _safe(root, OUTPUT_MANIFEST)
    value = _read_json(_file(marker), marker.name) if marker.is_file() else dict(schema=OUTPUT_SCHEMA, projects={})
    if not isinstance(value, dict) or value.get('schema') != OUTPUT_SCHEMA or not isinstance(value.get('projects'), dict):raise ValueError('项目包输出记录无效')
    for owner, paths in value['projects'].items():
        storage.valid_id(owner)
        if not isinstance(paths, list) or len(paths) != len(set(paths)) or any(not isinstance(path, str) or not OUTPUT_PATH.fullmatch(path) for path in paths):raise ValueError('项目包输出路径无效')
    return value


def archived_metadata(pid):
    
    active = load_metadata(pid)
    if active is not None:return active
    import project_lifecycle
    source = project_lifecycle.reference_file(pid, LOCAL_MANIFEST)
    if source is None:return None
    value = _read_json(_file(source), LOCAL_MANIFEST)
    if not isinstance(value, dict) or value.get('schema') != LOCAL_SCHEMA or value.get('projectId') != pid:raise ValueError('归档房间清单无效')
    return value


def deployed_paths(pid):
    metadata = archived_metadata(pid)
    paths = (metadata or {}).get('deployedFiles', [])
    if not isinstance(paths, list) or any(not isinstance(path, str) or not OUTPUT_PATH.fullmatch(path) for path in paths):raise ValueError('项目包输出路径无效')
    return set(paths)


def _replace_world_rows(text, replacements):
    lines = text.splitlines();in_rooms = False;inserted = set();result = []
    for line in lines:
        if line == 'ROOMS':in_rooms = True
        if line == 'END ROOMS':
            result.extend(replacements[name] for name in replacements if name not in inserted)
            in_rooms = False
        name = line.split(':', 1)[0].strip()
        if in_rooms and name in replacements:result.append(replacements[name]);inserted.add(name)
        else:result.append(line)
    if 'ROOMS' not in lines:raise ValueError('项目世界文件缺少 ROOMS 段')
    return '\n'.join(result) + '\n'


def augment_worlds(records, files):
    
    files = dict(files);rows = None;region_owners = {}
    for record in records:
        if record.get('ownerMod') == 'moreiterators.local':region_owners.setdefault(record['ai'].split('_')[0], set()).add(record['projectId'])
    chosen_region_files = {};added_regions = set()
    for record in records:
        pid = record['projectId']
        if record.get('ownerMod') != 'moreiterators.local' or storage.binding(pid):continue
        metadata = load_metadata(pid)
        if not metadata:continue
        project = storage.load_project(pid);binding = room_bindings.binding(project)
        
        
        if record.get('ai') != binding['ai'] or record.get('entry') != binding['entry']:continue
        if rows is None:rows = _catalog_rows()
        updates = {};region_sources = {}
        for room in metadata['rooms']:
            name = room['name'];region = room['region']
            if room['kind'] == 'entry' and binding['entryMode'] == 'existing':continue
            if room['kind'] == 'extra':_assert_extra_available(project, room, rows)
            source = selected_room_source(project, name, rows)
            region_sources.setdefault(region, source)
            links, tags = selected_room_connections(project, name, source, rows)
            _, exits = _geometry(_file(_sibling(source, '.txt')), name)
            if len(links) != exits:raise ValueError('额外房间出口数量不一致：' + name)
            if room['kind'] in ('ai', 'entry'):
                key = room['kind'];node = binding[key + 'Node']
                if node >= len(links):raise ValueError('项目绑定出口超出实际房间：' + name)
                links[node] = binding['entry' if key == 'ai' else 'ai']
            line = name + ' : ' + ', '.join(links) + (' : ' + tags if tags else '')
            prefix = 'modify/' if binding['entryMode'] == 'existing' and region == binding['region'] else ''
            
            existing_region = any(row.get('region') == region for row in rows.values())
            if region != binding['region'] and existing_region:prefix = 'modify/'
            relative = prefix + 'world/' + region.lower() + '/world_' + region.lower() + '.txt'
            updates.setdefault(relative, {})[name] = line
            if not prefix:added_regions.add(region)
        for relative, replacements in updates.items():
            template = ('[MERGE]\n' if relative.startswith('modify/') else '') + 'ROOMS\nEND ROOMS\n\nCREATURES\nEND CREATURES\n'
            files[relative] = _replace_world_rows(files.get(relative, template), replacements)
        for region in metadata['regions']:
            code = region['code']
            if code not in added_regions:continue
            for filename in region['files']:
                source = _region_source(project, code, region_sources.get(code, _project_dir(pid) / 'rooms/rendered'), filename)
                if source is None:raise ValueError('导入区域文件缺失：' + code + '/' + filename)
                relative = 'world/' + code.lower() + '/' + filename;text = _text(_file(source), filename).replace('\r\n', '\n')
                if filename.startswith('map_'):
                    combined = {}
                    selected = {room['name'] for room in metadata['rooms']}
                    subset = _map_subset(text.encode('utf-8'), selected)
                    text = subset.decode('utf-8') if subset else ''
                    for line in (files.get(relative, '') + '\n' + text).splitlines():
                        if line.strip():combined[line.split(':', 1)[0].strip()] = line
                    files[relative] = '\n'.join(combined.values()) + '\n';continue
                if relative in chosen_region_files and chosen_region_files[relative] != text:raise ValueError('所选项目区域设置冲突：' + relative)
                if len(region_owners.get(code, set())) > 1 and relative in files and files[relative] != text:
                    raise ValueError('区域被多个项目共用，不能覆盖其他作品的设置：' + code)
                chosen_region_files[relative] = text;files[relative] = text
    registration = set(line for line in files.get('modify/world/regions.txt', '').splitlines() if line)
    registration.update('[ADD]' + region for region in added_regions)
    if registration:files['modify/world/regions.txt'] = '\n'.join(sorted(registration)) + '\n'
    return files
