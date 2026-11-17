import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from PIL import Image

import project_packages
import room_asset_dependencies
import room_bindings
import room_package_dependencies
import room_source_choices
import storage

MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_FILES = 64
_EXECUTABLE = {'.exe', '.dll', '.com', '.bat', '.cmd', '.ps1', '.psm1', '.vbs', '.vbe', '.js', '.jse', '.wsf', '.wsh', '.hta', '.msi', '.msp', '.scr', '.cpl', '.lnk', '.url', '.py', '.pyw', '.sh', '.so', '.dylib'}


class ImportFileError(ValueError):
    def __init__(self, code, **params):
        self.code = 'export.fileImport.' + code
        self.params = params
        super().__init__(self.code)


def _fail(code, **params):
    raise ImportFileError(code, **params)


def _relative(value):
    if not isinstance(value, str):_fail('unsafe')
    try:project_packages._relative(value)
    except ValueError:_fail('unsafe')
    for part in value.split('/'):
        if re.search(r'[<>:"\\|?*\x00-\x1f]', part) or re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part, re.I):_fail('unsafe')
    return value


def _no_links(path):
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():_fail('unsafe')


def _destination(row, selected, forbidden):
    pid, room = row.get('projectId'), row.get('room', '')
    if pid not in selected:_fail('unmatched')
    try:storage.valid_id(pid)
    except ValueError:_fail('unsafe')
    relative = _relative(row.get('relative'))
    target = _relative(row.get('targetRelative'))
    if relative.startswith('rooms/'):
        if not isinstance(room, str) or not room_bindings.ROOM_RE.fullmatch(room):_fail('unsafe')
        prefix = 'rooms/' + room + '/rendered/'
        if not relative.startswith(prefix):_fail('unsafe')
        name = relative[len(prefix):]
        if '/' in name or not re.fullmatch(re.escape(room) + r'(?:\.txt|_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|_[1-9][0-9]*\.png)', name):_fail('unsafe')
        expected = 'rooms/rendered/' + name
    elif relative.startswith('palettes/'):
        if not re.fullmatch(r'palettes/palette\d+\.png', relative):_fail('unsafe')
        expected = 'rooms/' + relative
    elif relative.startswith('assets/'):
        if len(relative.split('/')) < 3:_fail('unsafe')
        expected = 'rooms/' + relative
    elif relative.startswith('regions/'):
        parts = relative.split('/')
        if len(parts) != 3 or not room_bindings.REGION_RE.fullmatch(parts[1]) or not room_package_dependencies.region_filename(parts[1], parts[2]):_fail('unsafe')
        expected = 'rooms/' + relative
    else:_fail('unsafe')
    if expected != target:_fail('unsafe')
    root = storage.project_file(pid).parent.absolute()
    _no_links(root)
    if not root.is_dir() or not (root / 'project.json').is_file():_fail('unmatched')
    _no_links(root / 'project.json')
    if any(root.resolve().is_relative_to(folder.resolve()) for folder in forbidden):_fail('unsafe')
    destination = root / target
    _no_links(destination)
    if not destination.resolve().is_relative_to(root.resolve()):_fail('unsafe')
    return root, destination


def _existing(path):
    if path.exists() or path.is_symlink():return True
    if not path.parent.is_dir():return False
    return any(item.name.casefold() == path.name.casefold() for item in path.parent.iterdir())


def _validate_content(row, content):
    relative = row['relative']
    name = relative.rsplit('/', 1)[-1]
    suffix = Path(name).suffix.lower()
    pe_offset = int.from_bytes(content[60:64], 'little') if len(content) >= 64 and content[:2] == b'MZ' else -1
    executable = pe_offset >= 64 and content[pe_offset:pe_offset + 4] == b'PE\0\0'
    if suffix in _EXECUTABLE or executable or content.startswith((b'\x7fELF', b'#!')):_fail('invalidFile', name=name)
    try:
        if relative.startswith('rooms/'):
            if suffix == '.png':project_packages._png(content, name)
            elif name == row['room'] + '.txt':project_packages._geometry(content, row['room'])
            else:project_packages._text(content, name)
        elif relative.startswith('palettes/'):
            project_packages._png(content, name)
        elif relative.startswith('regions/'):
            text = project_packages._region_text(content, name)
            region = relative.split('/')[1]
            if name == 'properties.txt':room_package_dependencies.template_files(region, text)
            elif name.startswith('map_'):room_package_dependencies.map_positions(text, {row.get('room', '')})
        elif relative.startswith('assets/'):
            asset = relative[len('assets/'):]
            if room_asset_dependencies.PATH.fullmatch(asset):room_asset_dependencies.validate(asset, content)
            elif suffix == '.png':project_packages._png(content, name)
            elif suffix == '.json':project_packages._read_json(content, name)
            elif suffix in ('.txt', '.csv', '.xml'):project_packages._text(content, name)
    except (ValueError, OSError, TypeError, IndexError, OverflowError, Image.DecompressionBombError) as error:
        raise ImportFileError('invalidFile', name=name) from error


def _resolve_file(value, data, rows):
    identifier = value.get('missingFileId')
    location = {key: value[key] for key in ('projectId', 'room', 'relative') if key in value}
    if not identifier and not location:
        identifier = data.get('missingFileId')
        location = {key: data[key] for key in ('projectId', 'room', 'relative') if key in data}
    matches = [row for row in rows if (not identifier or row.get('id') == identifier) and all(row.get(key, '') == item for key, item in location.items())]
    if not identifier and set(location) != {'projectId', 'room', 'relative'}:_fail('unmatched')
    if len(matches) != 1:_fail('unmatched')
    row = matches[0]
    expected = row['relative'].rsplit('/', 1)[-1]
    if value['name'].casefold() != expected.casefold():_fail('nameMismatch', expected=expected)
    return row


def _write_file(path, content, created):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    stamp = os.fstat(descriptor)
    created.append((path, stamp.st_dev, stamp.st_ino))
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _write_all(plans):
    created, directories = [], []
    try:
        for root, path, row, content in plans:
            _no_links(path)
            missing = []
            parent = path.parent
            while parent != root:
                if parent.exists():
                    if not parent.is_dir():_fail('unsafe')
                    break
                missing.append(parent)
                parent = parent.parent
            for directory in reversed(missing):
                _no_links(directory)
                try:directory.mkdir();directories.append(directory)
                except FileExistsError:
                    if not directory.is_dir():_fail('unsafe')
            _no_links(path)
            if _existing(path):_fail('existing', name=path.name)
            _write_file(path, content, created)
    except Exception as error:
        failures = []
        for path, device, inode in reversed(created):
            try:
                _no_links(path)
                stamp = path.stat()
                if (stamp.st_dev, stamp.st_ino) != (device, inode):raise OSError('created file changed')
                path.unlink()
            except FileNotFoundError:pass
            except Exception:failures.append(path.name)
        for directory in reversed(directories):
            try:directory.rmdir()
            except FileNotFoundError:pass
            except OSError:failures.append(directory.name)
        if failures:raise ImportFileError('rollbackFailed') from error
        if isinstance(error, ImportFileError):raise
        raise ImportFileError('writeFailed') from error


def import_missing(data, server):
    allowed = {'projects', 'extraRooms', 'scope', 'region', 'snapshotToken', 'missingFileId', 'projectId', 'room', 'relative', 'files'}
    if not isinstance(data, dict) or set(data) - allowed:_fail('invalid')
    files = data.get('files')
    if not isinstance(files, list):_fail('invalid')
    if not files:return {'ok': True, 'cancelled': True, 'imported': []}
    if len(files) > MAX_FILES:_fail('tooLarge')
    encoded_total = 0
    for value in files:
        if not isinstance(value, dict) or set(value) - {'name', 'base64', 'missingFileId', 'projectId', 'room', 'relative'}:_fail('invalid')
        if not isinstance(value.get('name'), str) or '/' in value['name'] or '\\' in value['name']:_fail('invalid')
        _relative(value['name'])
        encoded = value.get('base64')
        if not isinstance(encoded, str):_fail('invalid')
        encoded_total += len(encoded)
        if len(encoded) > (MAX_FILE + 2) // 3 * 4 or encoded_total > (MAX_TOTAL + MAX_FILES * 2) // 3 * 4:_fail('tooLarge')
    if data.get('scope', 'project') not in ('project', 'region'):_fail('invalid')
    selected = server.export_projects(data.get('projects', []))
    ids = {project['projectId'] for project in selected}
    extras = server.export_checked_rooms(data, selected)
    report = room_source_choices.preflight(selected, extras, region=data.get('region') if data.get('scope') == 'region' else None)
    token = data.get('snapshotToken')
    if not isinstance(token, str) or not token or token != report.get('snapshotToken'):_fail('stale')
    rows = report.get('missingFiles', [])
    if not isinstance(rows, list):_fail('unmatched')
    forbidden = [Path(root) for root in room_bindings.enabled_asset_roots()]
    game = storage.available_game_root()
    if game is not None:forbidden.append(Path(game))
    forbidden.extend(Path(storage.target_mod(pid)) for pid in ids)
    plans, targets, total = [], set(), 0
    for value in files:
        row = _resolve_file(value, data, rows)
        root, destination = _destination(row, ids, forbidden)
        if row.get('reason') != 'missing_file' or _existing(destination):_fail('existing', name=destination.name)
        identity = str(destination).casefold()
        if identity in targets:_fail('invalid')
        targets.add(identity)
        try:content = base64.b64decode(value['base64'], validate=True)
        except (ValueError, binascii.Error) as error:raise ImportFileError('invalidFile', name=destination.name) from error
        total += len(content)
        if len(content) > MAX_FILE or total > MAX_TOTAL:_fail('tooLarge')
        _validate_content(row, content)
        plans.append((root, destination, row, content))
    markers = {}
    for root, path, row, content in plans:
        markers.setdefault(root, []).append({'path': row['targetRelative'], 'sha256': hashlib.sha256(content).hexdigest()})
    writes = list(plans)
    for root, files in markers.items():
        path = root / 'rooms/rendered/.mi-export-imports' / (uuid.uuid4().hex + '.json')
        marker = {'schema': 'moreiterators.export-file-import.v1', 'files': sorted(files, key=lambda item: item['path'])}
        writes.append((root, path, {}, json.dumps(marker, ensure_ascii=False, separators=(',', ':')).encode('utf-8')))
    _write_all(writes)
    return {'ok': True, 'imported': [dict(projectId=row['projectId'], room=row.get('room', ''), relative=row['relative'], name=path.name) for _, path, row, _ in plans]}
