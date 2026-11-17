from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import io
import json
import re
from PIL import Image
import room_bindings
import room_asset_dependencies
import palette_export_sources
import rtm_room_sources
import storage

SCHEMA = 'moreiterators.room-source-choices.v1'
PAIR_SCHEMA = 'moreiterators.room-source-pair.v1'
LOCAL_SCHEMA = 'moreiterators.project-package.local.v1'
MAX_FILE = 256 * 1024 * 1024
MAX_METADATA = 4 * 1024 * 1024
ERRORS = {
    'room_choices_invalid': 'Room version choices are invalid.',
    'room_choices_required': 'Choose a version for each conflicting room before exporting.',
    'room_choices_stale': 'Room files changed. Review the available versions again.',
    'room_choices_incomplete': 'The selected room version is incomplete or unreadable.',
    'room_choices_missing': 'No complete room version is available for export.',
    'room_choices_needs_sync': 'Sync the saved room changes before exporting.',
    'room_choices_unsafe_path': 'Room files must remain inside their configured source folders.',
    'room_choices_duplicate_owner': 'A selected room is owned by more than one project.',
}
_selection = ContextVar('mi_room_source_choices', default=None)
_policies = ContextVar('mi_room_export_policies', default=None)


class RoomChoiceError(ValueError):
    def __init__(self, code, report=None):
        super().__init__(ERRORS[code])
        self.code = code
        self.report = report


def _fail(code, report=None):
    raise RoomChoiceError(code, report)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def _safe(root, relative):
    root = Path(root).absolute()
    if root.is_symlink() or getattr(root, 'is_junction', lambda: False)():
        _fail('room_choices_unsafe_path')
    path = root / relative
    current = path
    while current != root:
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            _fail('room_choices_unsafe_path')
        current = current.parent
    if not path.resolve().is_relative_to(root.resolve()):
        _fail('room_choices_unsafe_path')
    return path


def _fingerprint(path, keep=False, limit=MAX_FILE):
    if not path.is_file():
        return None, None
    try:
        before = path.stat()
        if before.st_size > limit:
            return {'path': str(path), 'resolved': str(path.resolve()), 'size': before.st_size, 'mtime': before.st_mtime_ns, 'invalid': 'file_too_large'}, None
        digest = hashlib.sha256()
        chunks = []
        with path.open('rb') as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                if keep:
                    chunks.append(chunk)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            _fail('room_choices_stale')
        return {'path': str(path), 'resolved': str(path.resolve()), 'size': after.st_size, 'mtime': after.st_mtime_ns, 'sha256': digest.hexdigest()}, b''.join(chunks) if keep else None
    except OSError:
        _fail('room_choices_stale')


def _text(content):
    value = content.decode('utf-8-sig')
    if not value.strip() or '\x00' in value:
        raise ValueError()
    return value


def _png(content):
    with Image.open(io.BytesIO(content)) as picture:
        if picture.format != 'PNG' or picture.width * picture.height > 64 * 1024 * 1024:
            raise ValueError()
        picture.verify()


def _geometry(content, name, path):
    rows = _text(content).splitlines()
    if len(rows) < 10 or rows[0].strip().upper() != name:
        raise ValueError()
    width, height = map(int, rows[1].split('|')[0].split('*'))
    cameras = [value.strip() for value in rows[3].split('|') if value.strip()]
    if not 0 < width <= 10000 or not 0 < height <= 10000 or not 1 <= len(cameras) <= 256:
        raise ValueError()
    if any(not re.fullmatch(r'-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?', value) for value in cameras):
        raise ValueError()
    room_bindings.geometry(path)
    return len(cameras)


def _modified(records):
    stamp = max((item.get('mtime', 0) for item in records if item), default=0)
    return datetime.fromtimestamp(stamp / 1000000000, timezone.utc).isoformat(timespec='milliseconds') if stamp else None


def _modified_ns(version):
    return version.get('modifiedNs', max((record.get('mtime', 0) for record in version['records'] if record), default=0))


def _recommended(versions):
    complete = [version for version in versions if version['meta']['complete']]
    return max(complete, key=lambda version: (_modified_ns(version), version['meta']['id'])) if complete else None


def _saved_settings(versions):
    complete = [version for version in versions if version['meta']['complete']]
    return max(complete, key=lambda value: next((record.get('mtime', 0) for record in value['records'] if record and record.get('path') == str(value['path'])), 0)) if complete else None


def _folder(root, relative, name):
    base = _safe(root, relative)
    files = {}
    if base.parent.is_dir():
        for file in base.parent.iterdir():
            if re.fullmatch(re.escape(name) + r'(?:\.txt|_settings(?:-[a-z0-9_-]+)?\.txt|_properties\.txt|_[1-9][0-9]*\.png)', file.name, re.I):
                path = _safe(root, file.relative_to(root))
                files.setdefault(file.name.casefold(), []).append(path)
    return base, files


def _candidate(origin, root, relative, name, expected_settings=(), geometry_name=None, supplement=None):
    base, found = _folder(root, relative, name)
    supplemental = {key: paths for key, paths in (supplement or {}).items()
                    if re.fullmatch(re.escape(name) + r'(?:\.txt|_settings(?:-[a-z0-9_-]+)?\.txt|_properties\.txt|_[1-9][0-9]*\.png)', key, re.I)}
    found = {key: values for key, values in found.items()}
    for key, values in supplemental.items():
        found.setdefault(key, values)
    if not found and not expected_settings:
        return None, None, []
    records = []
    def read(suffix):
        key = (name + suffix).casefold()
        matches = found.get(key, [])
        if len(matches) > 1:
            records.extend({'path': str(path), 'duplicate': True} for path in matches)
            return None, None, 'case_collision'
        path = matches[0] if matches else _safe(root, Path(relative).parent / (name + suffix))
        original = _safe(root, Path(relative).parent / (name + suffix))
        if path in supplemental.get(key, []) and not original.exists():
            records.append({'path': str(original), 'missing': True, 'supplemented': True})
        record, data = _fingerprint(path, keep=True)
        records.append(record or {'path': str(path), 'missing': True})
        return record, data, None if record and data is not None else 'missing_file' if record is None else record['invalid']
    render = None
    if any(re.fullmatch(re.escape(name) + r'(?:\.txt|_[1-9][0-9]*\.png)', key, re.I) for key in found):
        geometry, content, issue = read('.txt')
        issues = [issue] if issue else []
        invalid_files = [name + '.txt'] if issue and geometry else []
        count = 0
        if not issue:
            try:
                count = _geometry(content, geometry_name or name, Path(geometry['path']))
            except (ValueError, UnicodeError, OSError, IndexError, Image.DecompressionBombError):
                issues.append('invalid_geometry')
                invalid_files.append(name + '.txt')
        hashes = {name + '.txt': geometry.get('sha256') if geometry else None}
        paths = [Path(geometry['path'])] if geometry else []
        for index in range(1, count + 1):
            suffix = '_' + str(index) + '.png'
            record, content, issue = read(suffix)
            hashes[name + suffix] = record.get('sha256') if record else None
            if record:
                paths.append(Path(record['path']))
            if issue:
                issues.append(issue)
                if record:invalid_files.append(name + suffix)
            else:
                try:
                    _png(content)
                except (OSError, ValueError, Image.DecompressionBombError):
                    issues.append('invalid_camera')
                    invalid_files.append(name + suffix)
        render_records = copy.deepcopy(records)
        render_hash = _digest(hashes)
        render = {'meta': dict(id='render-' + render_hash, origin=origin, origins=[origin], modifiedAt=_modified(render_records),
                               hash=render_hash, complete=not issues, issues=sorted(set(issues)), cameraCount=count,
                               missing=sorted(Path(record['path']).name for record in render_records if record and record.get('missing') and not record.get('supplemented')),
                               invalidFiles=sorted(set(invalid_files)),
                               sourceAvailable=False, pairedSource=False),
                  'path': base, 'records': render_records, 'hashes': hashes, 'paths': paths,
                  'files': {name + path.name[len(name):].lower(): path for path in paths},
                  'modifiedNs': max((record.get('mtime', 0) for record in render_records if record), default=0)}
    settings = None
    setting_suffixes = sorted(set(key[len(name):] for key in found if re.fullmatch(re.escape(name) + r'(?:_settings(?:-[a-z0-9_-]+)?|_properties)\.txt', key, re.I)) | set(expected_settings))
    if setting_suffixes:
        start = len(records)
        hashes, files, issues, invalid_files, errors = {}, {}, [], [], []
        for suffix in sorted(set(['_settings.txt'] + setting_suffixes)):
            record, content, issue = read(suffix)
            if not issue:
                try:
                    text = _text(content)
                    room_asset_dependencies.references(text, name + suffix)
                except (UnicodeError, ValueError) as error:
                    issue = 'invalid_settings'
                    errors.append(str(error))
            hashes[name + suffix] = record.get('sha256') if record else None
            if record:
                path = Path(record['path'])
                filename = name + (path.name[len(name):] if suffix != '_settings.txt' else suffix)
                files[filename] = path
            if issue:
                issues.append(issue)
                if record:invalid_files.append(Path(record['path']).name)
        settings_hash = _digest(hashes)
        settings = {'meta': dict(id='settings-' + settings_hash, origin=origin, origins=[origin], modifiedAt=_modified(records[start:]),
                                 hash=settings_hash, complete=not issues, issues=sorted(set(issues)), variantCount=len(setting_suffixes) - ('_settings.txt' in setting_suffixes), files=sorted(files),
                                 missing=sorted(Path(record['path']).name for record in records[start:] if record and record.get('missing') and not record.get('supplemented'))),
                    'path': files.get(name + '_settings.txt', base.with_name(name + '_settings.txt')), 'files': files, 'records': copy.deepcopy(records[start:]),
                    'modifiedNs': max((record.get('mtime', 0) for record in records[start:] if record), default=0)}
        settings['meta'].update(invalidFiles=sorted(set(invalid_files)), errors=errors)
    return render, settings, records


def _json_record(path):
    record, data = _fingerprint(path, keep=True, limit=MAX_METADATA)
    if data is None:
        return record, None
    try:
        value = json.loads(_text(data))
        return record, value if isinstance(value, dict) else None
    except (ValueError, UnicodeError, RecursionError):
        return record, None


def _metadata(pid):
    root = storage.project_file(pid).parent
    record, value = _json_record(_safe(root, 'room-package.json'))
    if value and (value.get('schema') != LOCAL_SCHEMA or value.get('projectId') != pid or not isinstance(value.get('rooms'), list) or not isinstance(value.get('files'), list)):
        value = None
    return record, value


def _source_info(pid, name):
    root = storage.project_file(pid).parent
    path = _safe(root, 'rooms/' + name + '.txt')
    record, content = _fingerprint(path, keep=True)
    records = [record or {'path': str(path), 'missing': True}]
    hashes = {}
    available = False
    if content is not None:
        try:
            available = _text(content).lstrip().startswith('[[[')
        except (UnicodeError, ValueError):
            pass
        hashes[name + '.txt'] = record['sha256']
    path = _safe(root, 'rooms/' + name + '.png')
    record, content = _fingerprint(path, keep=True)
    records.append(record or {'path': str(path), 'missing': True})
    if record:
        hashes[name + '.png'] = record.get('sha256')
        try:
            _png(content)
        except (OSError, ValueError, TypeError, Image.DecompressionBombError):
            available = False
    return available, hashes, records


def _paired(pid, name, render, source_hashes, metadata, certificate):
    if not render['meta']['complete'] or not source_hashes:
        return False
    if certificate and certificate.get('schema') == PAIR_SCHEMA and certificate.get('projectId') == pid and certificate.get('room') == name and certificate.get('sourceHashes') == source_hashes and certificate.get('renderHash') == render['meta']['hash']:
        return True
    if not metadata or not any(isinstance(row, dict) and row.get('name') == name and row.get('sourceAvailable') is True for row in metadata['rooms']):
        return False
    records = {}
    for item in metadata['files']:
        if not isinstance(item, dict) or not isinstance(item.get('path'), str) or item['path'] in records:
            return False
        records[item['path']] = item.get('sha256')
    expected = {'rooms/' + filename: digest for filename, digest in source_hashes.items()}
    expected.update({'rooms/rendered/' + filename: digest for filename, digest in render['hashes'].items()})
    source_names = {path for path in records if path in ('rooms/' + name + '.txt', 'rooms/' + name + '.png')}
    render_names = {path for path in records if re.fullmatch('rooms/rendered/' + re.escape(name) + r'(?:\.txt|_[1-9][0-9]*\.png)', path)}
    return source_names | render_names == set(expected) and all(records.get(path) == digest for path, digest in expected.items())


def _saved_source_hashes(pid, name, metadata, certificate):
    def valid(hashes):
        return isinstance(hashes, dict) and name + '.txt' in hashes and set(hashes) <= {name + '.txt', name + '.png'} and all(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) for value in hashes.values())
    if certificate and certificate.get('schema') == PAIR_SCHEMA and certificate.get('projectId') == pid and certificate.get('room') == name and valid(certificate.get('sourceHashes')):
        return certificate['sourceHashes']
    if not metadata or not any(isinstance(row, dict) and row.get('name') == name and row.get('sourceAvailable') is True for row in metadata['rooms']):
        return None
    hashes = {}
    for item in metadata['files']:
        if not isinstance(item, dict) or item.get('path') not in ('rooms/' + name + '.txt', 'rooms/' + name + '.png'):
            continue
        key = item['path'].split('/')[-1]
        if key in hashes:return None
        hashes[key] = item.get('sha256')
    return hashes if valid(hashes) else None


def _room_state(pid, name, renders, settings, source_available, source_hashes, source_records, metadata, certificate):
    render, setting = _recommended(renders), _recommended(settings)
    missing = []
    if render is None:
        missing.extend(item for version in renders for item in version['meta'].get('missing', []))
        if not renders:missing.append(name + '.txt')
    if setting is None:
        missing.extend(item for version in settings for item in version['meta'].get('missing', []))
        if not settings:missing.append(name + '_settings.txt')
    state, reason = 'ready', None
    saved_hashes = _saved_source_hashes(pid, name, metadata, certificate)
    if saved_hashes is not None and source_hashes and saved_hashes != source_hashes:
        state, reason = 'needs_sync', 'source_changed'
    elif source_available:
        source_stamp = max((record.get('mtime', 0) for record in source_records if record), default=0)
        if render is None:
            state, reason = 'needs_sync', 'render_required'
        elif saved_hashes is None and source_stamp > _modified_ns(render):
            state, reason = 'needs_sync', 'source_newer_than_render'
    if state == 'ready' and (render is None or setting is None):
        state = 'missing'
        if render is None:
            reason = 'render_invalid' if renders and not missing else 'render_missing'
        else:
            reason = 'settings_invalid' if settings and not missing else 'settings_missing'
    return dict(state=state, reason=reason, missing=sorted(set(missing)),
                recommendedSourceId=render['meta']['id'] if render else None,
                recommendedSettingsId=setting['meta']['id'] if setting else None)


def _rained_levels():
    executable = storage.install_paths.rained_executable(storage.settings.get('rainedExecutable'))
    if executable is None:return None
    import room_editor
    try:
        return _safe(room_editor.rained_data_root(executable), 'Levels')
    except (OSError, ValueError):
        return None


def _dedupe(versions):
    result = {}
    for version in versions:
        key = (version['meta']['id'], version['meta']['complete'])
        if key not in result:
            result[key] = version
        else:
            previous = result[key]
            origins = list(dict.fromkeys(previous['meta']['origins'] + version['meta']['origins']))
            project_ids = sorted(set(previous['meta'].get('projectIds', []) + version['meta'].get('projectIds', [])))
            providers = {provider['id']: provider for provider in previous['meta'].get('providers', []) + version['meta'].get('providers', [])}
            if _modified_ns(version) > _modified_ns(previous):
                result[key] = version
            result[key]['meta']['origins'] = origins
            if project_ids:
                result[key]['meta']['projectIds'] = project_ids
            if providers:
                result[key]['meta']['providers'] = [providers[key] for key in sorted(providers)]
    return list(result.values())


def _asset_references(settings):
    result = set()
    for version in settings:
        if not version['meta']['complete']:
            continue
        for path in version['files'].values():
            text = path.read_text('utf-8-sig')
            result.update('palettes/palette' + str(int(value)) + '.png' for value in re.findall(r'(?m)^(?:Palette|FadePalette|MorePalette[0-9]+):[ \t]*(\d+)\b', text))
            try:
                for group in room_asset_dependencies.references(text) + room_asset_dependencies.optional_references(text):
                    result.update(group)
            except ValueError:
                pass
    return result


def _asset_file(root, relative):
    current = _safe(root, '.')
    for part in relative.split('/'):
        if not current.is_dir():
            return _safe(root, relative)
        matches = [path for path in current.iterdir() if path.name.casefold() == part.casefold()]
        if len(matches) > 1:
            _fail('room_choices_invalid')
        if not matches:
            return _safe(root, relative)
        current = _safe(root, matches[0].relative_to(root))
    return current


def _provider(root):
    records = []
    for folder in (root, root.parent):
        path = _safe(folder, 'modinfo.json')
        record, content = _fingerprint(path, keep=True, limit=128 * 1024)
        records.append(record or {'path': str(path), 'missing': True})
        if content is None:
            continue
        try:
            value = json.loads(content.decode('utf-8-sig'))
            identifier, name = value.get('id'), value.get('name')
            if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', identifier):
                break
            if not isinstance(name, str) or not name.strip() or len(name) > 200 or re.search(r'[\r\n\x00]|[A-Za-z]:[/\\]|^[/\\]', name):
                break
            return [dict(id=identifier, name=name.strip())], records
        except (ValueError, UnicodeError, AttributeError, RecursionError):
            break
    return [], records


def _asset_versions(pid, relative, enabled_roots, preferred=None, rtm_sources=(), keep_enabled=False):
    if preferred is None:
        project = storage.project_file(pid).parent
        cached = 'rooms/' + relative if relative.startswith('palettes/') else 'rooms/assets/' + relative
        roots = [('project', project, cached), ('local', storage.target_mod(pid), relative)]
        installed = storage.installed_mod(pid, required=False)
        if installed is not None:
            roots.append(('installed', installed, relative))
        known = {Path(root).resolve() for _, root, _ in roots}
        roots.extend(('enabled', root, relative) for root in enabled_roots if Path(root).resolve() not in known)
    else:
        roots = []
        for path in preferred:
            path = Path(path)
            origin = 'enabled'
            if pid is not None and path.resolve().is_relative_to(storage.project_file(pid).parent.resolve()):origin = 'project'
            elif pid is not None and path.resolve().is_relative_to(storage.target_mod(pid).resolve()):origin = 'local'
            game = storage.available_game_root()
            if game is not None and path.parent.resolve() == (game / 'RainWorld_Data/StreamingAssets/palettes').resolve():origin = 'game'
            roots.append((origin, path.parent, path.name))
    routed = []
    route_records = []
    for source in rtm_sources:
        path = _asset_file(source['regionRoot'], relative)
        if not path.is_file():continue
        routed.append(('enabled', source['root'], path.relative_to(source['root']).as_posix()))
        route_records.extend(source['metadataRecords'])
    if routed:
        providers = {source['root'].resolve() for source in rtm_sources}
        roots = [item for item in roots if item[0] in ('project', 'local', 'installed') or keep_enabled and Path(item[1]).resolve() not in providers]
        roots.extend(routed)
    else:
        roots.extend(('palette_output', root, candidate) for root, candidate in palette_export_sources.output_locations(relative, enabled_roots))
    versions, records = [], []
    seen = set()
    for origin, root, candidate in roots:
        root = Path(root)
        providers = []
        if origin == 'enabled':
            game = storage.available_game_root()
            if game is not None and root.resolve() == (game / 'RainWorld_Data/StreamingAssets').resolve():
                origin = 'game'
        path = _asset_file(root, candidate)
        if path.resolve() in seen:
            continue
        seen.add(path.resolve())
        record, content = _fingerprint(path, keep=True, limit=64 * 1024 * 1024)
        records.append(record or {'path': str(path), 'missing': True})
        if record is None:
            continue
        if origin == 'enabled':
            providers, provider_records = _provider(root)
            records.extend(provider_records)
        issue = record.get('invalid')
        builtin = origin == 'game' and room_asset_dependencies.native_ambient_reference(relative, path)
        if not issue:
            try:
                if relative.startswith('palettes/'):
                    _png(content)
                elif not builtin:
                    room_asset_dependencies.validate(relative, content)
            except (OSError, ValueError, Image.DecompressionBombError):
                issue = 'invalid_asset'
        digest = record.get('sha256') or _digest({'path': relative, 'invalid': issue, 'size': record['size']})
        versions.append({'meta': dict(id='asset-' + digest, hash=digest, origin=origin, origins=[origin],
                                     modifiedAt=_modified([record]), complete=issue is None, builtin=builtin, issues=[issue] if issue else [], projectIds=[pid] if pid is not None else [], providers=providers),
                         'path': path, 'records': [record] + [item for item in route_records if item]})
    records.extend(route_records)
    return _dedupe(versions), records


def _inputs(projects, extra_rooms):
    if not isinstance(projects, (list, tuple)) or len(projects) > 256 or not isinstance(extra_rooms, list) or len(extra_rooms) > 256:
        _fail('room_choices_invalid')
    if any(not isinstance(name, str) or not room_bindings.ROOM_RE.fullmatch(name) for name in extra_rooms):
        _fail('room_choices_invalid')
    enabled = []
    seen = set()
    for project in projects:
        if not isinstance(project, dict):
            _fail('room_choices_invalid')
        pid = project.get('projectId')
        try:
            storage.valid_id(pid)
        except ValueError:
            _fail('room_choices_invalid')
        if pid in seen:
            _fail('room_choices_invalid')
        seen.add(pid)
        if isinstance(project.get('editor'), dict) and project['editor'].get('externalRoomTools') is True:
            enabled.append(project)
    return enabled, sorted(set(extra_rooms))


def _parameter_kinds(text):
    kinds = set()
    if re.search(r'(?m)^(?:Palette|FadePalette|MorePalette[0-9]+|TerrainPalette|TerrainFadePalette):[ \t]*\S', text):
        kinds.add('palette')
    effects = re.findall(r'(?m)^Effects:[ \t]*([^\r\n]*)', text)
    if any(re.search(r'(?:^|,\s*)(?:ZeroG|BrokenZeroG)-', value) for value in effects):
        kinds.add('gravity')
    return kinds


def _parameter_signals(pid, name, version):
    setting_texts = {filename: path.read_text('utf-8-sig') for filename, path in version['files'].items()}
    texts = list(setting_texts.values())
    kinds = set().union(*(_parameter_kinds(text) for text in texts))
    region = name.split('_')[0]
    roots = [(storage.project_file(pid).parent, 'rooms/regions/' + region + '/'),
             (storage.target_mod(pid), 'world/' + region.lower() + '/')]
    installed = storage.installed_mod(pid, required=False)
    if installed is not None:
        roots.append((installed, 'world/' + region.lower() + '/'))
    records, inherited = [], []
    def read(filename):
        found = []
        for root, folder in roots:
            path = _asset_file(Path(root), folder + filename)
            record, content = _fingerprint(path, keep=True, limit=MAX_METADATA)
            records.append(record or {'path': str(path), 'missing': True})
            if content is not None:
                try:
                    found.append(_text(content))
                except (UnicodeError, ValueError):
                    pass
        return found
    properties = read('properties.txt')
    for text in properties:
        kinds.update(_parameter_kinds(text))
    templates = set()
    implicit = False
    for filename, text in setting_texts.items():
        if not re.fullmatch(re.escape(name) + r'_settings(?:-[A-Za-z0-9_-]+)?\.txt', filename):
            continue
        match = re.search(r'(?m)^Template:[ \t]*([^\r\n]+)', text)
        if match:
            value = match[1].strip()
            if value.upper() != 'NONE' and re.fullmatch(r'[A-Za-z0-9]+_settingstemplate_[A-Za-z0-9-]+', value, re.I):
                templates.add(value.lower())
        else:
            implicit = True
    if implicit:
        for text in properties:
            match = re.search(r'(?m)^Room Setting Templates:[ \t]*([^\r\n]+)', text)
            value = match[1].split(',')[0].strip() if match else ''
            if re.fullmatch(r'[A-Za-z0-9-]+', value):
                templates.add(region.lower() + '_settingstemplate_' + value.lower())
    for template in sorted(templates):
        inherited.extend(read(template + '.txt'))
    for text in inherited:
        kinds.update(_parameter_kinds(text))
    return kinds, records


def _parameter_conflicts(project, binding, name, settings):
    design = project.get('design') if isinstance(project.get('design'), dict) else {}
    modes = {}
    if name == binding['ai']:
        modes = dict(palette=design.get('roomPaletteMode', 'mi'), gravity=design.get('roomGravityMode', 'mi'))
    elif name == binding['entry']:
        modes = dict(gravity=design.get('entryGravityMode', 'zero'))
    modes = {kind: mode for kind, mode in modes.items() if mode != 'room'}
    identifiers = {kind: [] for kind in modes}
    records = []
    if modes:
        for version in settings:
            if not version['meta']['complete']:
                continue
            kinds, inherited = _parameter_signals(project['projectId'], name, version)
            records.extend(inherited)
            version['records'].extend(inherited)
            for kind in modes.keys() & kinds:
                identifiers[kind].append(version['meta']['id'])
    conflicts = [dict(projectId=project['projectId'], room=name, kind=kind, certainty='potential', sourceMode=modes[kind], settingsVersionIds=sorted(set(values)))
                 for kind, values in identifiers.items() if values]
    return conflicts, records


def region_palette_key(region):
    return 'region:' + region


def _saved_palette_references(project, extras, enabled_roots, room_versions):
    import project_packages
    import standalone
    pid = project['projectId']
    binding = room_bindings.binding(project)
    names = sorted(set([binding['ai'], binding['entry']] + list(extras)))
    references, preferred, records = set(), {}, []
    for name in names:
        if not room_bindings.ROOM_RE.fullmatch(name):continue
        available = room_versions.get(pid + '/' + name)
        if available is None:continue
        settings = _saved_settings(available['settings'])
        if settings is None:continue
        render = _recommended(available['source'])
        source = render['path'] if render is not None else storage.project_file(pid).parent / 'rooms/rendered' / name
        files = list(settings['files'].values())
        try:
            _, region_paths = project_packages._collect_region(project, name.split('_')[0], source, names)
            files.extend(path for filename, path in region_paths.items()
                         if filename == 'properties.txt' or '_settingstemplate_' in filename)
        except (OSError, ValueError):
            pass
        for path in files:
            record, content = _fingerprint(path, keep=True, limit=MAX_METADATA)
            if content is None:continue
            try:indices = standalone.room_palette_ids(_text(content))
            except (ValueError, UnicodeError):continue
            for index in indices:
                if not palette_export_sources.saved_files(index, enabled_roots):continue
                relative = 'palettes/palette' + str(index) + '.png'
                references.add(relative)
                records.append(record)
                try:standard = standalone.room_palette_source(project, path, index, include_saved=False)
                except (OSError, ValueError):standard = None
                if standard is not None:preferred.setdefault(relative, []).append(standard)
                else:preferred.setdefault(relative, [])
    return references, preferred, records


def _missing_file(pid, name, relative, kind, reason='missing_file'):
    if relative.startswith('rooms/' + name + '/rendered/'):
        target = 'rooms/rendered/' + relative.rsplit('/', 1)[1]
    elif relative.startswith(('palettes/', 'assets/', 'regions/')):
        target = 'rooms/' + relative
    else:
        _fail('room_choices_invalid')
    if any(part in ('', '.', '..') for part in relative.split('/')) or '\\' in relative or ':' in relative:
        _fail('room_choices_invalid')
    return dict(id=_digest(dict(projectId=pid, room=name, relative=relative, kind=kind)),
                projectId=pid, room=name, name=relative.rsplit('/', 1)[1], relative=relative,
                kind=kind, reason=reason, targetRelative=target)


def _supplements(pid):
    root = storage.project_file(pid).parent
    folder = _safe(root, 'rooms/rendered/.mi-export-imports')
    result, records = {}, []
    if not folder.is_dir():return result, records
    manifests = sorted(folder.glob('*.json'))
    if len(manifests) > 4096:_fail('room_choices_invalid')
    for path in manifests:
        _safe(root, path.relative_to(root))
        record, value = _json_record(path)
        records.append(record)
        if not value or value.get('schema') != 'moreiterators.export-file-import.v1' or not isinstance(value.get('files'), list):
            _fail('room_choices_invalid')
        for item in value['files']:
            relative = item.get('path') if isinstance(item, dict) else None
            digest = item.get('sha256') if isinstance(item, dict) else None
            if not isinstance(relative, str) or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                _fail('room_choices_invalid')
            if not re.fullmatch(r'rooms/rendered/[A-Z0-9_]+(?:\.txt|_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|_[1-9][0-9]*\.png)', relative):continue
            target = _safe(root, relative)
            current, _ = _fingerprint(target)
            records.append(current or {'path': str(target), 'missing': True})
            if current and current.get('sha256') == digest:
                result[target.name.casefold()] = [target]
    return result, records


def _complete_settings_groups(versions, supplements):
    result = []
    imported = {path for paths in supplements.values() for path in paths}
    for version in versions:
        files = set(version['files'].values())
        hashes = version['hashes'] if 'hashes' in version else {name: next((record.get('sha256') for record in version['records'] if record and record.get('path') == str(path)), None) for name, path in version['files'].items()}
        if files and files <= imported:
            supersets = [other for other in versions if other is not version and other['meta']['complete'] and set(hashes) < set(other['files'])]
            if any(all(next((record.get('sha256') for record in other['records'] if record and record.get('path') == str(other['files'][name])), None) == digest for name, digest in hashes.items()) for other in supersets):
                continue
        result.append(version)
    return result


def _room_missing(pid, name, renders, settings):
    result = []
    for versions, kind, fallback in ((renders, 'render', name + '.txt'), (settings, 'settings', name + '_settings.txt')):
        if _recommended(versions) is not None:continue
        version = max(versions, key=_modified_ns) if versions else None
        missing = version['meta'].get('missing', []) if version else [fallback]
        invalid = version['meta'].get('invalidFiles', []) if version else []
        for filename, reason in [(value, 'missing_file') for value in missing] + [(value, 'invalid_file') for value in invalid]:
            result.append(_missing_file(pid, name, 'rooms/' + name + '/rendered/' + filename, kind, reason))
    return result


def _required_references(version):
    groups = []
    if version is None:return groups
    for path in version['files'].values():
        text = path.read_text('utf-8-sig')
        groups.extend(('palettes/palette' + str(int(value)) + '.png',) for value in re.findall(r'(?m)^(?:Palette|FadePalette|MorePalette[0-9]+):[ \t]*(\d+)\b', text))
        groups.extend(room_asset_dependencies.references(text, path.name))
    return list(dict.fromkeys(groups))


def _region_requirements(project, name, source, names, metadata):
    import project_packages
    import room_package_dependencies
    region = name.split('_')[0]
    records, paths, missing = [], {}, []
    expected = set()
    prefix = 'rooms/regions/' + region + '/'
    for item in (metadata or {}).get('files', []):
        relative = item.get('path', '') if isinstance(item, dict) else ''
        if relative.startswith(prefix) and room_package_dependencies.region_filename(region, relative[len(prefix):]):
            expected.add(relative[len(prefix):])
    for filename in ('properties.txt', 'displayname.txt', 'map_' + region.lower() + '.txt'):
        path = project_packages._region_source(project, region, source, filename, required_rooms=names)
        if path is None:
            if filename in expected:missing.append(filename)
            continue
        record, content = _fingerprint(path, keep=True)
        records.append(record)
        if content is not None:paths[filename] = path
        if filename == 'properties.txt' and content is not None:
            expected.update(room_package_dependencies.template_files(region, _text(content)))
    for filename in sorted(expected - paths.keys() - set(missing)):
        path = project_packages._region_source(project, region, source, filename, required_rooms=names)
        if path is None:
            missing.append(filename)
        else:
            record, content = _fingerprint(path, keep=True)
            records.append(record)
            if content is not None:paths[filename] = path
    files = [_missing_file(project['projectId'], name, 'regions/' + region + '/' + filename, 'region') for filename in missing]
    return paths, records, files


def _scan(projects, extra_rooms, region=None):
    enabled, extras = _inputs(projects, extra_rooms)
    rows = []
    internal = {}
    snapshot = {'projects': [], 'extras': extras, 'files': []}
    owners = {}
    references = {}
    rtm_assets = {}
    ordinary_assets = {}
    parameters = []
    rained_levels = _rained_levels() if enabled else None
    enabled_roots = room_bindings.enabled_asset_roots()
    metadata_by_id = {project['projectId']: _metadata(project['projectId']) for project in projects}
    extra_owners = {}
    for project in projects:
        metadata = metadata_by_id[project['projectId']][1]
        for item in (metadata or {}).get('rooms', []):
            if isinstance(item, dict) and item.get('name') in extras:extra_owners.setdefault(item['name'], project['projectId'])
    for name in extras:
        if projects:extra_owners.setdefault(name, projects[0]['projectId'])
    for project in projects:
        pid = project['projectId']
        external = project in enabled
        binding = room_bindings.binding(project)
        manifest_record, metadata = metadata_by_id[pid]
        supplements, supplement_records = _supplements(pid)
        design = project.get('design') if isinstance(project.get('design'), dict) else {}
        snapshot['projects'].append({'projectId': pid, 'binding': binding,
                                     'parameters': {key: value for key, value in design.items() if key.startswith('room') or key == 'entryGravityMode'}})
        snapshot['files'].append(manifest_record)
        snapshot['files'].extend(supplement_records)
        references[pid] = set()
        ordinary_assets[pid] = set()
        names = [binding['ai'], binding['entry']]
        imported = {row.get('name') for row in (metadata or {}).get('rooms', []) if isinstance(row, dict) and isinstance(row.get('name'), str) and room_bindings.ROOM_RE.fullmatch(row['name'])}
        names += [name for name in extras if extra_owners.get(name) == pid and name not in names]
        for name in sorted(set(names)):
            if not isinstance(name, str) or not room_bindings.ROOM_RE.fullmatch(name):
                _fail('room_choices_invalid')
            kind = 'ai' if name == binding['ai'] else 'entry' if name == binding['entry'] else 'extra'
            owned = not storage.binding(pid) and (kind == 'ai' or kind == 'entry' and binding.get('entryMode') == 'copy')
            if owned and name in owners and owners[name] != pid:
                _fail('room_choices_duplicate_owner')
            if owned:owners[name] = pid
            root = storage.project_file(pid).parent
            roots = [('project', root, 'rooms/rendered/' + name),
                     ('local', storage.target_mod(pid), 'world/' + name.split('_')[0].lower() + '-rooms/' + name)]
            installed = storage.installed_mod(pid, required=False)
            if installed is not None:
                roots.append(('installed', installed, 'world/' + name.split('_')[0].lower() + '-rooms/' + name))
            if rained_levels is not None and owned and external:
                roots.append(('rained', rained_levels, name))
            if not owned:
                for folder in enabled_roots:
                    relative = 'world/' + name.split('_')[0].lower() + '-rooms/' + name
                    roots.append(('enabled', folder, relative))
                try:
                    resolved = room_bindings.resolve_room_source(name)
                    roots.append(('enabled', resolved.parent, resolved.name))
                except (ValueError, OSError):
                    pass
            routed = rtm_room_sources.room_sources(name, enabled_roots)
            route_records = []
            if routed:
                mirrors = {(item['root'] / 'world' / (name.split('_')[0].lower() + '-rooms') / name).resolve() for item in routed}
                roots = [item for item in roots if (Path(item[1]) / item[2]).resolve() not in mirrors]
                for item in routed:
                    roots.append(('enabled', item['root'], item['base'].relative_to(item['root']).as_posix()))
                    route_records.extend(item['metadataRecords'])
                snapshot['files'].extend(route_records)
            renders, settings = [], []
            source_available, source_hashes, source_records = _source_info(pid, name)
            certificate_record, certificate = _json_record(_safe(root, 'rooms/rendered/' + name + '.source.json'))
            snapshot['files'].extend(source_records + [certificate_record])
            seen_roots = set()
            for origin, folder, relative in roots:
                identity = str((Path(folder) / relative).absolute()).casefold()
                if identity in seen_roots:continue
                seen_roots.add(identity)
                snapshot['files'].append({'origin': origin, 'base': str(Path(folder) / relative)})
                expected = []
                if origin == 'project':
                    for item in (metadata or {}).get('files', []):
                        path = item.get('path', '') if isinstance(item, dict) else ''
                        if re.fullmatch('rooms/rendered/' + re.escape(name) + r'(?:_settings(?:-[A-Za-z0-9_-]+)?|_properties)\.txt', path):
                            expected.append(path.rsplit('/', 1)[1][len(name):])
                render, setting, records = _candidate(origin, Path(folder), relative, name, expected,
                    supplement=supplements if origin in ('local', 'installed', 'enabled') else None)
                snapshot['files'].extend(records)
                if render:
                    render['records'] += route_records
                    render['meta']['sourceAvailable'] = source_available
                    render['meta']['pairedSource'] = source_available and _paired(pid, name, render, source_hashes, metadata, certificate)
                    render['records'] += source_records + [certificate_record, manifest_record] + supplement_records
                    renders.append(render)
                if setting:
                    setting['records'] += route_records
                    setting['records'] += supplement_records
                    settings.append(setting)
            template = False
            if not renders and owned and not project.get('roomBinding'):
                try:
                    base = room_bindings.source_for(project, kind)
                    header = base.with_suffix('.txt').read_text('utf-8-sig').splitlines()[0].strip().upper()
                    render, setting, records = _candidate('template', base.parent, base.name, base.name.upper(), geometry_name=header)
                    snapshot['files'].extend(records)
                    if render:renders.append(render)
                    if setting:settings.append(setting)
                    template = render is not None
                except (OSError, ValueError, IndexError):
                    pass
            renders, settings = _dedupe(renders), _dedupe(_complete_settings_groups(settings, supplements))
            conflicts, inherited_records = _parameter_conflicts(project, binding, name, settings) if external else ([], [])
            parameters.extend(conflicts)
            snapshot['files'].extend(inherited_records)
            checked_settings = settings if external else ([_saved_settings(settings)] if _saved_settings(settings) is not None else [])
            for version in checked_settings:
                linked = [item for item in routed if version['path'].resolve().is_relative_to(item['regionRoot'].resolve())]
                for relative in _asset_references([version]):
                    if not linked:ordinary_assets[pid].add(relative)
                    for item in linked:
                        source_owners = rtm_assets.setdefault((pid, relative), [])
                        if item not in source_owners:source_owners.append(item)
            references[pid].update(_asset_references(checked_settings))
            key = pid + '/' + name
            row = dict(projectId=pid, room=name, kind=kind, required=kind != 'extra', owned=owned,
                       syncable=owned and not template, sourceToken=_digest(source_hashes), sourceAvailable=source_available,
                       renderVersions=[version['meta'] for version in renders], settingsVersions=[version['meta'] for version in settings])
            row['sourceConflict'] = external and sum(v['meta']['complete'] for v in renders) > 1
            row['settingsConflict'] = external and sum(v['meta']['complete'] for v in settings) > 1
            row.update(_room_state(pid, name, renders, settings, source_available, source_hashes, source_records, metadata, certificate))
            row['missingFiles'] = _room_missing(pid, name, renders, settings)
            source = _recommended(renders)
            setting = _recommended(settings) if external else _saved_settings(settings)
            if setting is not None:row['recommendedSettingsId'] = setting['meta']['id']
            required_refs = _required_references(setting)
            if source is not None:
                paths, region_records, region_missing = _region_requirements(project, name, source['path'], set(names), metadata)
                snapshot['files'].extend(region_records)
                row['missingFiles'].extend(region_missing)
                inherited = {'files': {filename: path for filename, path in paths.items() if filename == 'properties.txt' or '_settingstemplate_' in filename}}
                inherited_refs = _required_references(inherited)
                required_refs.extend(inherited_refs)
                linked = [item for item in routed if source['path'].resolve().is_relative_to(item['regionRoot'].resolve())]
                for group in inherited_refs:
                    for relative in group:
                        if not linked:ordinary_assets[pid].add(relative)
                        for item in linked:
                            source_owners = rtm_assets.setdefault((pid, relative), [])
                            if item not in source_owners:source_owners.append(item)
                references[pid].update(relative for group in required_refs for relative in group)
            rows.append(row)
            internal[key] = {'source': renders, 'settings': settings, 'automatic': not external, 'template': template, 'requirements': required_refs}
    assets, asset_versions, asset_owners, palette_preferred = [], {}, {}, {}
    has_saved = any(_asset_file(root, 'OutputPalettes').is_dir() for root in enabled_roots)
    if has_saved:
        checked = {project['projectId'] for project in enabled}
        for project in projects:
            pid = project['projectId']
            if pid in checked:continue
            found, preferred, records = _saved_palette_references(project, extras, enabled_roots, internal)
            if not found:continue
            references.setdefault(pid, set()).update(found)
            palette_preferred.update({(pid, relative): paths for relative, paths in preferred.items()})
            snapshot['files'].extend(records)
    if region is not None:
        if not isinstance(region, str) or not room_bindings.REGION_RE.fullmatch(region):_fail('room_choices_invalid')
        snapshot['region'] = region
        if has_saved:
            import region_packages
            found, paths, standard = region_packages.palette_references(region, [project['projectId'] for project in projects])
            key = region_palette_key(region)
            references[key] = set()
            for index in found:
                if not palette_export_sources.saved_files(index, enabled_roots):continue
                relative = 'palettes/palette' + str(index) + '.png'
                references[key].add(relative)
                palette_preferred[(key, relative)] = [standard[index]] if standard[index] is not None else []
            if references[key]:
                snapshot['files'].extend(_fingerprint(path)[0] for path in paths)
    for pid, relatives in references.items():
        for relative in sorted(relatives):
            versions, records = _asset_versions(None if pid.startswith('region:') else pid, relative, enabled_roots,
                                               palette_preferred.get((pid, relative)), rtm_assets.get((pid, relative), ()),
                                               relative in ordinary_assets.get(pid, ()))
            snapshot['files'].extend(records)
            asset_versions.setdefault(relative, []).extend(versions)
            asset_owners.setdefault(relative, []).append(pid)
    for relative, versions in asset_versions.items():
        versions = _dedupe(versions)
        asset_versions[relative] = versions
        owners = sorted(pid for pid in asset_owners[relative] if not pid.startswith('region:'))
        row = dict(key=relative, projectId=owners[0] if owners else '', projectIds=owners, relative=relative, versions=[version['meta'] for version in versions],
                           conflict=sum(version['meta']['complete'] for version in versions) > 1,
                           missing=not any(version['meta']['complete'] for version in versions))
        if region is not None and region_palette_key(region) in asset_owners[relative]:row['region'] = region
        assets.append(row)
    for row in rows:
        for group in internal[row['projectId'] + '/' + row['room']]['requirements']:
            if any(any(version['meta']['complete'] for version in asset_versions.get(relative, [])) for relative in group):continue
            if room_asset_dependencies.has_native_ambient_reference(group):continue
            relative = group[0]
            invalid = any(asset_versions.get(value) for value in group)
            path = relative if relative.startswith('palettes/') else 'assets/' + relative
            row['missingFiles'].append(_missing_file(row['projectId'], row['room'], path, 'asset', 'invalid_file' if invalid else 'missing_file'))
        row['missingFiles'] = list({value['id']: value for value in row['missingFiles']}.values())
        if row['missingFiles'] and row['state'] == 'ready':
            row['state'], row['reason'] = 'missing', 'dependency_missing'
    issues = [dict(projectId=row['projectId'], room=row['room'], code='room_choices_missing', kind=kind)
              for row in rows for kind, field in [('source', 'renderVersions'), ('settings', 'settingsVersions')]
              if row['state'] != 'needs_sync' and not any(version['complete'] for version in row[field])]
    issues.extend(dict(projectId=row['projectId'], room=row['room'], code='room_choices_needs_sync', reason=row['reason']) for row in rows if row['state'] == 'needs_sync')
    missing_files = list({item['id']: item for row in rows for item in row['missingFiles']}.values())
    report = dict(schema=SCHEMA, snapshotToken=_digest(snapshot), requiresChoices=any(row['sourceConflict'] or row['settingsConflict'] for row in rows) or any(row['conflict'] for row in assets), rooms=rows, assets=assets, missingFiles=missing_files, parameterConflicts=[], parameterModes=parameters, issues=issues)
    return report, internal, asset_versions


def preflight(projects, extraRooms=None, region=None):
    report, _, _ = _scan(projects, [] if extraRooms is None else extraRooms, region)
    return copy.deepcopy(report)


def _validate_records(records, contents=True):
    for record in records:
        if record is None:
            continue
        path = Path(record['path'])
        if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
            _fail('room_choices_stale')
        if not contents:
            if record.get('missing'):
                if path.exists():
                    _fail('room_choices_stale')
            else:
                try:
                    stamp = path.stat()
                    if (stamp.st_size, stamp.st_mtime_ns, str(path.resolve())) != (record['size'], record['mtime'], record['resolved']):
                        _fail('room_choices_stale')
                except OSError:
                    _fail('room_choices_stale')
            continue
        current, _ = _fingerprint(path)
        if record.get('missing'):
            if current is not None:
                _fail('room_choices_stale')
        elif current != record:
            _fail('room_choices_stale')


@contextmanager
def resolution_scope(projects, payload=None, region=None):
    if payload is None:
        payload = {}
    if not isinstance(payload, dict) or set(payload) - {'snapshotToken', 'choices', 'assetChoices', 'extraRooms', 'policies'}:
        _fail('room_choices_invalid')
    choices = payload.get('choices', {})
    asset_choices = payload.get('assetChoices', {})
    policies = payload.get('policies', {})
    if not isinstance(choices, dict) or not isinstance(asset_choices, dict) or not isinstance(policies, dict):
        _fail('room_choices_invalid')
    enabled, _ = _inputs(projects, payload.get('extraRooms', []))
    if set(policies) - {project['projectId'] for project in enabled}:
        _fail('room_choices_invalid')
    bindings = {project['projectId']: room_bindings.binding(project) for project in enabled}
    for pid, value in policies.items():
        if not isinstance(value, dict) or set(value) - {'palette', 'gravity'}:
            _fail('room_choices_invalid')
        if 'palette' in value and value['palette'] not in ('project', 'room'):
            _fail('room_choices_invalid')
        gravity = value.get('gravity', {})
        if isinstance(gravity, dict):
            if set(gravity) - {bindings[pid]['ai'], bindings[pid]['entry']} or any(mode not in ('project', 'room') for mode in gravity.values()):
                _fail('room_choices_invalid')
        elif gravity not in ('project', 'room'):
            _fail('room_choices_invalid')
    report, versions, assets = _scan(projects, payload.get('extraRooms', []), region)
    token = payload.get('snapshotToken')
    if token is not None and token != report['snapshotToken']:
        _fail('room_choices_stale', report)
    if any(row['state'] == 'needs_sync' for row in report['rooms']):
        _fail('room_choices_needs_sync', report)
    if (report['requiresChoices'] or choices or asset_choices) and not token:
        _fail('room_choices_required', report)
    if set(choices) - set(versions) or set(asset_choices) - set(assets):
        _fail('room_choices_invalid', report)
    selected = {}
    for key, available in versions.items():
        choice = choices.get(key, {})
        if not isinstance(choice, dict) or set(choice) - {'source', 'settings'}:
            _fail('room_choices_invalid', report)
        selected[key] = {}
        for kind in ('source', 'settings'):
            complete = [value for value in available[kind] if value['meta']['complete']]
            identifier = choice.get(kind)
            if identifier is not None:
                matches = [value for value in available[kind] if value['meta']['id'] == identifier]
                if not matches:
                    _fail('room_choices_invalid', report)
                candidate = next((value for value in matches if value['meta']['complete']), None)
                if candidate is None:
                    _fail('room_choices_incomplete', report)
            elif not complete:
                _fail('room_choices_missing', report)
            elif len(complete) > 1:
                if available.get('automatic'):
                    candidate = _recommended(complete)
                    if kind == 'settings':
                        candidate = _saved_settings(complete)
                else:
                    _fail('room_choices_required', report)
            else:
                candidate = complete[0]
            selected[key][kind] = candidate
        if available.get('template'):selected.pop(key)
    policies = copy.deepcopy(policies)
    active_conflicts = [conflict for conflict in report['parameterModes']
                        if conflict['projectId'] + '/' + conflict['room'] in selected and selected[conflict['projectId'] + '/' + conflict['room']]['settings']['meta']['id'] in conflict['settingsVersionIds']]
    for pid, policy in policies.items():
        gravity = policy.get('gravity', {})
        if gravity == 'project':
            policy['gravity'] = {name: 'project' for name in (bindings[pid]['ai'], bindings[pid]['entry'])}
        elif gravity == 'room':
            rooms = {conflict['room'] for conflict in active_conflicts if conflict['projectId'] == pid and conflict['kind'] == 'gravity'}
            if len(rooms) != 1:
                _fail('room_choices_required', report)
            policy['gravity'] = {next(iter(rooms)): 'room'}
    for key, available in assets.items():
        complete = [value for value in available if value['meta']['complete']]
        identifier = asset_choices.get(key)
        if identifier is not None:
            matches = [value for value in available if value['meta']['id'] == identifier]
            if not matches:
                _fail('room_choices_invalid', report)
            candidate = next((value for value in matches if value['meta']['complete']), None)
            if candidate is None:
                _fail('room_choices_incomplete', report)
        elif len(complete) > 1:
            _fail('room_choices_required', report)
        elif complete:
            candidate = complete[0]
        else:
            continue
        row = next(row for row in report['assets'] if row['key'] == key)
        owners = list(row['projectIds'])
        if row.get('region') is not None:owners.append(region_palette_key(row['region']))
        for pid in owners:
            selected[pid + '/' + key] = {'asset': candidate}
    context = _selection.set(selected)
    policy_context = _policies.set(copy.deepcopy(policies))
    try:
        yield copy.deepcopy(report)
        for selected_row in selected.values():
            for version in selected_row.values():
                _validate_records(version['records'])
    finally:
        _selection.reset(context)
        _policies.reset(policy_context)


def _selected(pid, room, kind):
    state = _selection.get()
    value = state.get(str(pid) + '/' + str(room), {}).get(kind) if state is not None else None
    if value:
        _validate_records(value['records'], contents=False)
    return value


def selected_source(pid, room):
    value = _selected(pid, room, 'source')
    return value['path'] if value else None


def selected_region_sources(pid, region):
    result = []
    prefix = str(pid) + '/' + str(region) + '_'
    for key, kinds in (_selection.get() or {}).items():
        if not key.startswith(prefix):continue
        value = kinds.get('source')
        if value is None:continue
        _validate_records(value['records'], contents=False)
        result.append(value['path'])
    return result


def selected_settings(pid, room):
    value = _selected(pid, room, 'settings')
    return value['path'] if value else None


def selected_settings_files(pid, room):
    value = _selected(pid, room, 'settings')
    return dict(value['files']) if value else {}


def selected_render_files(room, source):
    result = None
    for key, selected in (_selection.get() or {}).items():
        value = selected.get('source')
        if value is None or key.rsplit('/', 1)[-1] != room or value['path'].resolve() != Path(source).resolve():continue
        _validate_records(value['records'], contents=False)
        files = value.get('files', {})
        if result is not None and result != files:_fail('room_choices_invalid')
        result = files
    return dict(result or {})


def selected_version(pid, room):
    value = _selected(pid, room, 'source')
    return copy.deepcopy(value['meta']) if value else None


def selected_asset(pid, relative):
    value = _selected(pid, relative, 'asset')
    return value['path'] if value else None


def export_project(project):
    result = copy.deepcopy(project)
    policy = (_policies.get() or {}).get(project.get('projectId'), {})
    gravity = policy.get('gravity', {})
    if policy.get('palette') == 'room' or 'room' in gravity.values():
        if not isinstance(result.get('design'), dict):
            _fail('room_choices_invalid')
        if policy.get('palette') == 'room':
            result['design']['roomPaletteMode'] = 'room'
        binding = room_bindings.binding(project)
        if gravity.get(binding['ai']) == 'room':
            result['design']['roomGravityMode'] = 'room'
        if gravity.get(binding['entry']) == 'room':
            result['design']['entryGravityMode'] = 'room'
    return result


def pairing_record(pid, room):
    storage.valid_id(pid)
    if not isinstance(room, str) or not room_bindings.ROOM_RE.fullmatch(room):
        _fail('room_choices_invalid')
    root = storage.project_file(pid).parent
    available, hashes, records = _source_info(pid, room)
    render, _, _ = _candidate('project', root, 'rooms/rendered/' + room, room)
    if not available or render is None or not render['meta']['complete']:
        _fail('room_choices_incomplete')
    _validate_records(records + render['records'])
    return dict(schema=PAIR_SCHEMA, projectId=pid, room=room, sourceHashes=hashes, renderHash=render['meta']['hash'])
