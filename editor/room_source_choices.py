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


def _folder(root, relative, name):
    base = _safe(root, relative)
    files = {}
    if base.parent.is_dir():
        for file in base.parent.iterdir():
            if re.fullmatch(re.escape(name) + r'(?:\.txt|_settings(?:-[a-z0-9_-]+)?\.txt|_properties\.txt|_[1-9][0-9]*\.png)', file.name, re.I):
                path = _safe(root, file.relative_to(root))
                files.setdefault(file.name.casefold(), []).append(path)
    return base, files


def _candidate(origin, root, relative, name):
    base, found = _folder(root, relative, name)
    if not found:
        return None, None, []
    records = []
    def read(suffix):
        key = (name + suffix).casefold()
        matches = found.get(key, [])
        if len(matches) > 1:
            records.extend({'path': str(path), 'duplicate': True} for path in matches)
            return None, None, 'case_collision'
        path = matches[0] if matches else _safe(root, Path(relative).parent / (name + suffix))
        record, data = _fingerprint(path, keep=True)
        records.append(record or {'path': str(path), 'missing': True})
        return record, data, None if record and data is not None else 'missing_file' if record is None else record['invalid']
    render = None
    if any(re.fullmatch(re.escape(name) + r'(?:\.txt|_[1-9][0-9]*\.png)', key, re.I) for key in found):
        geometry, content, issue = read('.txt')
        issues = [issue] if issue else []
        count = 0
        if not issue:
            try:
                count = _geometry(content, name, Path(geometry['path']))
            except (ValueError, UnicodeError, OSError, IndexError, Image.DecompressionBombError):
                issues.append('invalid_geometry')
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
            else:
                try:
                    _png(content)
                except (OSError, ValueError, Image.DecompressionBombError):
                    issues.append('invalid_camera')
        render_records = copy.deepcopy(records)
        render_hash = _digest(hashes)
        render = {'meta': dict(id='render-' + render_hash, origin=origin, origins=[origin], modifiedAt=_modified(render_records),
                               hash=render_hash, complete=not issues, issues=sorted(set(issues)), cameraCount=count,
                               sourceAvailable=False, pairedSource=False),
                  'path': base, 'records': render_records, 'hashes': hashes, 'paths': paths}
    settings = None
    setting_suffixes = sorted(key[len(name):] for key in found if re.fullmatch(re.escape(name) + r'(?:_settings(?:-[a-z0-9_-]+)?|_properties)\.txt', key, re.I))
    if setting_suffixes:
        start = len(records)
        hashes, files, issues = {}, {}, []
        for suffix in sorted(set(['_settings.txt'] + setting_suffixes)):
            record, content, issue = read(suffix)
            if not issue:
                try:
                    _text(content)
                except (UnicodeError, ValueError):
                    issue = 'invalid_settings'
            hashes[name + suffix] = record.get('sha256') if record else None
            if record:
                path = Path(record['path'])
                filename = name + (path.name[len(name):] if suffix != '_settings.txt' else suffix)
                files[filename] = path
            if issue:
                issues.append(issue)
        settings_hash = _digest(hashes)
        settings = {'meta': dict(id='settings-' + settings_hash, origin=origin, origins=[origin], modifiedAt=_modified(records[start:]),
                                 hash=settings_hash, complete=not issues, issues=sorted(set(issues)), variantCount=len(setting_suffixes) - ('_settings.txt' in setting_suffixes), files=sorted(files)),
                    'path': files.get(name + '_settings.txt', base.with_name(name + '_settings.txt')), 'files': files, 'records': copy.deepcopy(records[start:])}
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
            if (version['meta']['modifiedAt'] or '') > (previous['meta']['modifiedAt'] or ''):
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


def _asset_versions(pid, relative, enabled_roots):
    project = storage.project_file(pid).parent
    cached = 'rooms/' + relative if relative.startswith('palettes/') else 'rooms/assets/' + relative
    roots = [('project', project, cached), ('local', storage.target_mod(pid), relative)]
    installed = storage.installed_mod(pid, required=False)
    if installed is not None:
        roots.append(('installed', installed, relative))
    known = {Path(root).resolve() for _, root, _ in roots}
    roots.extend(('enabled', root, relative) for root in enabled_roots if Path(root).resolve() not in known)
    versions, records = [], []
    seen = set()
    for origin, root, candidate in roots:
        root = Path(root)
        providers, provider_records = [], []
        if origin == 'enabled':
            game = storage.available_game_root()
            if game is not None and root.resolve() == (game / 'RainWorld_Data/StreamingAssets').resolve():
                origin = 'game'
            else:
                providers, provider_records = _provider(root)
            records.extend(provider_records)
        path = _asset_file(root, candidate)
        if path.resolve() in seen:
            continue
        seen.add(path.resolve())
        record, content = _fingerprint(path, keep=True, limit=64 * 1024 * 1024)
        records.append(record or {'path': str(path), 'missing': True})
        if record is None:
            continue
        issue = record.get('invalid')
        if not issue:
            try:
                if relative.startswith('palettes/'):
                    _png(content)
                else:
                    room_asset_dependencies.validate(relative, content)
            except (OSError, ValueError, Image.DecompressionBombError):
                issue = 'invalid_asset'
        digest = record.get('sha256') or _digest({'path': relative, 'invalid': issue, 'size': record['size']})
        versions.append({'meta': dict(id='asset-' + digest, hash=digest, origin=origin, origins=[origin],
                                     modifiedAt=_modified([record]), complete=issue is None, issues=[issue] if issue else [], projectIds=[pid], providers=providers),
                         'path': path, 'records': [record]})
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


def _scan(projects, extra_rooms):
    enabled, extras = _inputs(projects, extra_rooms)
    rows = []
    internal = {}
    snapshot = {'projects': [], 'extras': extras, 'files': []}
    owners = {}
    references = {}
    parameters = []
    for project in enabled:
        pid = project['projectId']
        binding = room_bindings.binding(project)
        manifest_record, metadata = _metadata(pid)
        design = project.get('design') if isinstance(project.get('design'), dict) else {}
        snapshot['projects'].append({'projectId': pid, 'binding': binding,
                                     'parameters': {key: value for key, value in design.items() if key.startswith('room') or key == 'entryGravityMode'}})
        snapshot['files'].append(manifest_record)
        references[pid] = set()
        names = [] if storage.binding(pid) else [binding['ai']] + ([binding['entry']] if binding.get('entryMode') == 'copy' else [])
        imported = {row.get('name') for row in (metadata or {}).get('rooms', []) if isinstance(row, dict) and isinstance(row.get('name'), str) and room_bindings.ROOM_RE.fullmatch(row['name'])}
        names += [name for name in extras if name in imported]
        for name in sorted(set(names)):
            if not isinstance(name, str) or not room_bindings.ROOM_RE.fullmatch(name):
                _fail('room_choices_invalid')
            if name in owners and owners[name] != pid:
                _fail('room_choices_duplicate_owner')
            owners[name] = pid
            root = storage.project_file(pid).parent
            roots = [('project', root, 'rooms/rendered/' + name),
                     ('local', storage.target_mod(pid), 'world/' + name.split('_')[0].lower() + '-rooms/' + name)]
            installed = storage.installed_mod(pid, required=False)
            if installed is not None:
                roots.append(('installed', installed, 'world/' + name.split('_')[0].lower() + '-rooms/' + name))
            renders, settings = [], []
            source_available, source_hashes, source_records = _source_info(pid, name)
            certificate_record, certificate = _json_record(_safe(root, 'rooms/rendered/' + name + '.source.json'))
            snapshot['files'].extend(source_records + [certificate_record])
            for origin, folder, relative in roots:
                snapshot['files'].append({'origin': origin, 'base': str(Path(folder) / relative)})
                render, setting, records = _candidate(origin, Path(folder), relative, name)
                snapshot['files'].extend(records)
                if render:
                    render['meta']['sourceAvailable'] = source_available
                    render['meta']['pairedSource'] = source_available and _paired(pid, name, render, source_hashes, metadata, certificate)
                    render['records'] += source_records + [certificate_record, manifest_record]
                    renders.append(render)
                if setting:
                    settings.append(setting)
            renders, settings = _dedupe(renders), _dedupe(settings)
            conflicts, inherited_records = _parameter_conflicts(project, binding, name, settings)
            parameters.extend(conflicts)
            snapshot['files'].extend(inherited_records)
            references[pid].update(_asset_references(settings))
            key = pid + '/' + name
            row = dict(projectId=pid, room=name, sourceAvailable=source_available,
                       renderVersions=[version['meta'] for version in renders], settingsVersions=[version['meta'] for version in settings])
            row['sourceConflict'] = sum(v['meta']['complete'] for v in renders) > 1
            row['settingsConflict'] = sum(v['meta']['complete'] for v in settings) > 1
            rows.append(row)
            internal[key] = {'source': renders, 'settings': settings}
    assets, asset_versions, asset_owners = [], {}, {}
    enabled_roots = room_bindings.enabled_asset_roots() if any(references.values()) else []
    for pid, relatives in references.items():
        for relative in sorted(relatives):
            versions, records = _asset_versions(pid, relative, enabled_roots)
            snapshot['files'].extend(records)
            asset_versions.setdefault(relative, []).extend(versions)
            asset_owners.setdefault(relative, []).append(pid)
    for relative, versions in asset_versions.items():
        versions = _dedupe(versions)
        asset_versions[relative] = versions
        owners = sorted(asset_owners[relative])
        assets.append(dict(key=relative, projectId=owners[0], projectIds=owners, relative=relative, versions=[version['meta'] for version in versions],
                           conflict=sum(version['meta']['complete'] for version in versions) > 1,
                           missing=not any(version['meta']['complete'] for version in versions)))
    issues = [dict(projectId=row['projectId'], room=row['room'], code='room_choices_missing', kind=kind)
              for row in rows for kind, field in [('source', 'renderVersions'), ('settings', 'settingsVersions')]
              if not any(version['complete'] for version in row[field])]
    report = dict(schema=SCHEMA, snapshotToken=_digest(snapshot), requiresChoices=bool(parameters) or any(row['sourceConflict'] or row['settingsConflict'] for row in rows) or any(row['conflict'] for row in assets), rooms=rows, assets=assets, parameterConflicts=parameters, issues=issues)
    return report, internal, asset_versions


def preflight(projects, extraRooms=None):
    report, _, _ = _scan(projects, [] if extraRooms is None else extraRooms)
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
def resolution_scope(projects, payload=None):
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
    report, versions, assets = _scan(projects, payload.get('extraRooms', []))
    token = payload.get('snapshotToken')
    if token is not None and token != report['snapshotToken']:
        _fail('room_choices_stale', report)
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
                _fail('room_choices_required', report)
            else:
                candidate = complete[0]
            selected[key][kind] = candidate
    policies = copy.deepcopy(policies)
    active_conflicts = [conflict for conflict in report['parameterConflicts']
                        if selected[conflict['projectId'] + '/' + conflict['room']]['settings']['meta']['id'] in conflict['settingsVersionIds']]
    for pid, policy in policies.items():
        gravity = policy.get('gravity', {})
        if gravity == 'project':
            policy['gravity'] = {name: 'project' for name in (bindings[pid]['ai'], bindings[pid]['entry'])}
        elif gravity == 'room':
            rooms = {conflict['room'] for conflict in active_conflicts if conflict['projectId'] == pid and conflict['kind'] == 'gravity'}
            if len(rooms) != 1:
                _fail('room_choices_required', report)
            policy['gravity'] = {next(iter(rooms)): 'room'}
    for conflict in active_conflicts:
        key = conflict['projectId'] + '/' + conflict['room']
        version = selected[key]['settings']['meta']['id']
        policy = policies.get(conflict['projectId'], {})
        value = policy.get('gravity', {}).get(conflict['room']) if conflict['kind'] == 'gravity' else policy.get(conflict['kind'])
        if version in conflict['settingsVersionIds'] and value not in ('project', 'room'):
            _fail('room_choices_required', report)
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
        owners = next(row['projectIds'] for row in report['assets'] if row['key'] == key)
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


def selected_settings(pid, room):
    value = _selected(pid, room, 'settings')
    return value['path'] if value else None


def selected_settings_files(pid, room):
    value = _selected(pid, room, 'settings')
    return dict(value['files']) if value else {}


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
