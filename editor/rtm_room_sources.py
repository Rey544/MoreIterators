import hashlib
import json
from pathlib import Path, PureWindowsPath
import re


_NAME = re.compile(r'[A-Za-z0-9_-]+')
_CODE = re.compile(r'[A-Za-z0-9]{1,12}')
_SETTINGS = re.compile(r'_settings(?:-.*)?\.txt$', re.IGNORECASE)
_MAX_JSON = 4 * 1024 * 1024


def _safe(root, relative):
    try:
        root = Path(root).absolute()
        relative = str(relative).replace('\\', '/')
        if not relative or PureWindowsPath(relative).root or PureWindowsPath(relative).drive:
            return None
        if any(part in ('', '.', '..') for part in relative.split('/')):
            return None
        path = root / relative
        current = path
        while True:
            if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
                return None
            if current == root:
                break
            current = current.parent
        if not path.resolve().is_relative_to(root.resolve()):
            return None
        return path
    except (OSError, ValueError, RuntimeError):
        return None


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def _json(path, records=None):
    if path is None:
        return None
    try:
        if not path.is_file():
            return None
        before = path.stat()
        if before.st_size > _MAX_JSON:
            return None
        content = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            return None
        value = json.loads(content.decode('utf-8-sig'), object_pairs_hook=_pairs)
        if isinstance(value, dict) and records is not None:
            records.append(dict(path=str(path), resolved=str(path.resolve()), size=after.st_size,
                                mtime=after.st_mtime_ns, sha256=hashlib.sha256(content).hexdigest()))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, UnicodeError, RecursionError):
        return None


def _mod_roots(roots):
    found = {}
    for value in roots:
        try:
            root = Path(value).absolute()
            path = _safe(root, 'modinfo.json')
            records = []
            info = _json(path, records)
            if not info or info.get('id') != 'octooltestmod':
                continue
            found.setdefault(str(root.resolve()).casefold(), (root, records))
        except (OSError, ValueError):
            continue
    return list(found.values()) if len(found) == 1 else []


def _regions(root, provider_records=()):
    manifest_file = _safe(root, 'manifest.json')
    if manifest_file is None:
        return []
    manifest_records = []
    if manifest_file.exists():
        manifest = _json(manifest_file, manifest_records)
    else:
        manifest = {'schemaVersion': 1}
        manifest_records.append(dict(path=str(manifest_file), missing=True))
    if not manifest or type(manifest.get('schemaVersion')) is not int or manifest['schemaVersion'] != 1:
        return []
    relative = manifest.get('templatesPath')
    if relative is None or isinstance(relative, str) and not relative.strip():
        relative = 'templates'
    if not isinstance(relative, str):
        return []
    directory = _safe(root, relative)
    if directory is None or not directory.is_dir():
        return []
    try:
        folders = sorted((p for p in directory.iterdir() if p.is_dir()), key=lambda p: str(p).casefold())[:256]
    except OSError:
        return []
    values = []
    for folder in folders:
        config = _safe(root, str(folder.relative_to(root) / 'region.json'))
        spec_records = []
        spec = _json(config, spec_records)
        if not spec or spec.get('enabled') is False:
            continue
        if spec.get('enabled') is not None and type(spec['enabled']) is not bool:
            continue
        if type(spec.get('schemaVersion')) is not int or spec['schemaVersion'] != 1:
            continue
        code = spec.get('code')
        ident = spec.get('id')
        if ident is None or isinstance(ident, str) and not ident.strip():
            ident = folder.name
        if not isinstance(code, str) or not _CODE.fullmatch(code):
            continue
        if not isinstance(ident, str) or not _NAME.fullmatch(ident):
            continue
        rooms = spec.get('rooms')
        if rooms is None:
            rooms = []
        if not isinstance(rooms, list) or len(rooms) > 500:
            continue
        configured = {}
        valid = True
        for room in rooms:
            name = room.get('name') if isinstance(room, dict) else None
            if not isinstance(name, str) or not _NAME.fullmatch(name) or name.casefold() in configured:
                valid = False
                break
            configured[name.casefold()] = room
        if not valid:
            continue
        room_dir = _safe(root, str(folder.relative_to(root) / 'rooms'))
        if room_dir is None or not room_dir.is_dir():
            continue
        try:
            files = [p for p in room_dir.iterdir() if p.is_file() and p.suffix.lower() == '.txt' and not _SETTINGS.search(p.name)]
        except OSError:
            continue
        if len(files) > 500:
            continue
        values.append(dict(root=root, regionRoot=folder, manifest=config, region=code.upper(), id=ident,
                           files=files, configured=configured, records=[root / 'modinfo.json', manifest_file, config],
                           metadataRecords=list(provider_records) + manifest_records + spec_records))
    codes = {}
    ids = {}
    for row in values:
        codes[row['region']] = codes.get(row['region'], 0) + 1
        ident = row['id'].casefold()
        ids[ident] = ids.get(ident, 0) + 1
    return [row for row in values if codes[row['region']] == 1 and ids[row['id'].casefold()] == 1]


def registered_rooms(roots):
    result = []
    for root, provider_records in _mod_roots(roots):
        for row in _regions(root, provider_records):
            counts = {}
            for path in row['files']:
                key = path.stem.casefold()
                counts[key] = counts.get(key, 0) + 1
            for path in row['files']:
                name = path.stem
                if not _NAME.fullmatch(name) or not name.upper().startswith((row['region'] + '_', 'GATE_')):
                    continue
                if counts[name.casefold()] != 1:
                    continue
                path = _safe(root, str(path.relative_to(root)))
                if path is None:
                    continue
                spec = row['configured'].get(name.casefold(), {})
                links = spec.get('connections')
                tags = spec.get('tags')
                if links is None:links = []
                if tags is None:tags = []
                if not isinstance(links, list) or not isinstance(tags, list):
                    continue
                links = ['DISCONNECTED' if item is None else item.upper() if isinstance(item, str) else '' for item in links]
                tags = [item.upper() if isinstance(item, str) else '' for item in tags]
                if any(not _NAME.fullmatch(item) for item in links) or any(item not in ('SHELTER', 'GATE') for item in tags):
                    continue
                result.append({key: value for key, value in row.items() if key not in ('files', 'configured')} |
                              dict(base=path.with_suffix(''), name=name.upper(), connections=links, tags=' : '.join(tags)))
    return result


def room_sources(name, roots):
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        return []
    return [row for row in registered_rooms(roots) if row['name'].casefold() == name.casefold()]


def region_root_for_source(source, roots):
    try:
        base = Path(source).absolute()
        if base.suffix.lower() == '.txt':
            base = base.with_suffix('')
        matches = room_sources(base.name, roots)
        matches = [row for row in matches if row['base'].resolve() == base.resolve()]
        return matches[0]['regionRoot'] if len(matches) == 1 else None
    except (OSError, ValueError):
        return None
