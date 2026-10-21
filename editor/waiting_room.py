"""Bundled, editable waiting room and conservative upgrades from the old default.

Only an untouched SS_D07 room pair is eligible for automatic replacement. This
module never treats the existence of a rendered cache as proof of authorship.
Every legacy byte (except the generated room name/line endings) is checked.
"""
from pathlib import Path
import copy
import datetime
import hashlib
import json
import re
import uuid
import storage

ROOT = Path(__file__).resolve().parents[1] / 'templates/rooms/waiting'
FIELD = 'waitingRoomTemplate'
ID = 'mi-waiting'


def manifest():
    value = json.loads((ROOT / 'manifest.json').read_text('utf-8'))
    for relative, digest in value['files'].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('等待房间模板校验失败，请重新安装模组。')
    return value


def rendered():
    return ROOT / manifest()['renderedBase']


def source():
    return ROOT / manifest()['sourceBase']


def editable_source(project, name):
    """A renamed copy of our exact render may reuse the matching editor source."""
    if storage.binding(project['projectId']):
        return None
    value = manifest()
    template = ROOT / value['renderedBase']
    expected = _sha(_normalized(template.with_suffix('.txt'), True))
    for base in _bases(project['projectId'], name):
        if not base.with_suffix('.txt').is_file():
            continue
        try:
            if (_sha(_normalized(base.with_suffix('.txt'), True)) == expected and
                    _sha(Path(str(base) + '_1.png').read_bytes()) == value['files']['entry_1.png'] and
                    len(list(base.parent.glob(base.name + '_*.png'))) == 1):
                return ROOT / value['sourceBase']
        except (OSError, UnicodeError):
            pass
        # The first existing source is authoritative; never bypass a custom cache.
        return None
    return None


def _bases(pid, name):
    relative = Path('world') / (name.split('_')[0].lower() + '-rooms') / name
    return [storage.project_file(pid).parent / 'rooms/rendered' / name,
            storage.target_mod(pid) / relative, storage.installed_mod(pid) / relative]


def default_node(project, name):
    if project.get(FIELD) == ID:
        return 0
    # Existing unversioned rooms retain their original node until an exact
    # legacy proof succeeds. Custom template configuration is also preserved.
    if storage.settings.get('entryRoomTemplate') or any(base.with_suffix('.txt').exists() for base in _bases(project['projectId'], name)):
        return 1
    return 0


def _sha(content):
    return hashlib.sha256(content).hexdigest()


def _normalized(file, body=False):
    lines = file.read_text('utf-8-sig').splitlines()
    return ('\n'.join(lines[1:] if body else lines) + '\n').encode('utf-8')


def _files(base):
    return [file for file in base.parent.glob(base.name + '*') if file.is_file() and
            (file.name in (base.name + '.txt', base.name + '_settings.txt') or
             re.fullmatch(re.escape(base.name) + r'_\d+\.png', file.name))]


def _legacy(base, spec):
    try:
        if _sha(_normalized(base.with_suffix('.txt'), True)) != spec['geometryBodySha256']:
            return False
        if _sha(_normalized(Path(str(base) + '_settings.txt'))) not in (
                spec['settingsNormalizedSha256'], spec['deployedSettingsNormalizedSha256']):
            return False
        expected = {base.name + '.txt', base.name + '_settings.txt'}
        for number, digest in spec['cameraSha256'].items():
            file = Path(str(base) + '_' + number + '.png')
            expected.add(file.name)
            if _sha(file.read_bytes()) != digest:
                return False
        return {file.name for file in _files(base)} == expected
    except (OSError, UnicodeError, ValueError):
        return False


def _worlds(pid):
    for root in (storage.DATA / 'local-mod', storage.installed_mod(pid)):
        for pattern in ('world/*/world_*.txt', 'modify/world/*/world_*.txt'):
            yield from root.glob(pattern)


def _isolated_pair(pid, ai, entry):
    import room_bindings
    for file in _worlds(pid):
        text = file.read_text('utf-8-sig')
        for row in room_bindings.parse_world(text, file.parent.name.upper()):
            if row['name'] in (ai, entry):
                other = entry if row['name'] == ai else ai
                if row['conditional'] or any(link not in ('DISCONNECTED', other) for link in row['connections']):
                    return False
                if row['connections'] != ['DISCONNECTED', other]:
                    return False
            elif ai in row['connections'] or entry in row['connections']:
                return False
    return True


def prepare(project):
    """Seed a fresh default, or archive and replace a proven old default.

    Call while holding the studio write lock. Returns the authoritative project.
    Custom/linked/external room projects are deliberately left alone.
    """
    import room_bindings
    import room_migration
    pid = project['projectId']
    if storage.binding(pid) or storage.settings.get('entryRoomTemplate') or project.get(FIELD) == ID:
        return project
    binding = room_bindings.binding(project)
    explicit = bool(project.get('roomBinding'))
    if explicit:
        key = hashlib.sha256(pid.encode()).hexdigest()[:10].upper()
        legacy_binding = dict(region='TEST', ai='TEST_' + key + '_AI', entry='TEST_' + key + '_ENTRY',
                              oracleId='test_' + key.lower(), entryMode='copy', aiNode=1, entryNode=1)
        if binding != legacy_binding:
            return project
    ai, entry = binding['ai'], binding['entry']
    source_file = storage.project_file(pid).parent / 'rooms' / (entry + '.txt')
    if source_file.exists() or source_file.with_suffix('.png').exists():
        return project
    bases = _bases(pid, entry)
    occupied = [base for base in bases if _files(base)]
    value = manifest()
    if explicit and not occupied:
        return project
    if occupied:
        if not all(_legacy(base, value['legacy']) for base in occupied):
            return project
        if not _isolated_pair(pid, ai, entry):
            raise ValueError('旧等待房间存在额外连接，未自动替换；请先在房间工程中确认并保存连接。')
    changed = copy.deepcopy(project)
    changed[FIELD] = ID
    if explicit:
        changed['roomBinding']['entryNode'] = 0
        ai_source = room_bindings.source_for(project, 'ai')
        ai_exits = room_bindings.geometry(ai_source.with_suffix('.txt'))['exitCount']
        if ai_exits < 2:
            return project
    template = ROOT / value['renderedBase']
    editable = ROOT / value['sourceBase']
    writes = {source_file: editable.with_suffix('.txt').read_bytes(),
              source_file.with_suffix('.png'): editable.with_suffix('.png').read_bytes()}
    room_text = template.with_suffix('.txt').read_text('utf-8-sig').splitlines()
    room_text[0] = entry
    # The cache is always written after the source, preserving ensure_synced's
    # newer-source guard for subsequent actual edits in Rained.
    for base in dict.fromkeys([bases[0], *occupied]):
        writes[base.with_suffix('.txt')] = ('\n'.join(room_text) + '\n').encode('utf-8')
        for suffix in ('_1.png', '_settings.txt'):
            writes[Path(str(base) + suffix)] = Path(str(template) + suffix).read_bytes()
    writes[storage.project_file(pid)] = json.dumps(changed, ensure_ascii=False, indent=2).encode('utf-8')
    if explicit:
        ai_links = ['DISCONNECTED'] * ai_exits
        ai_links[1] = entry
        plan = dict(binding=changed['roomBinding'], warnings=[], requiresRestart=True,
                    worldFiles={'world/test/world_test.txt': 'ROOMS\n' + ai + ' : ' + ', '.join(ai_links) + '\n' + entry + ' : ' + ai + '\nEND ROOMS\n\nCREATURES\nEND CREATURES\n'},
                    roomCopies=[dict(kind='ai', name=ai, source=str(ai_source)), dict(kind='entry', name=entry, source=str(bases[0]))],
                    connectionChanges=[dict(room=entry, node=1, fromRoom=ai, to='DISCONNECTED'), dict(room=entry, node=0, fromRoom='DISCONNECTED', to=ai)])
        writes[storage.project_file(pid).parent / 'room-binding-plan.json'] = json.dumps(plan, ensure_ascii=False, indent=2).encode('utf-8')
    removes = []
    for base in occupied:
        removes.extend(_files(base))
    if occupied:
        # Commit geometry and its node metadata together. A later appearance
        # compilation failure must not leave a new one-exit room on old node 1.
        for file in _worlds(pid):
            text = file.read_text('utf-8-sig')
            updated = re.sub(r'(?m)^' + re.escape(entry) + r'\s*:\s*DISCONNECTED\s*,\s*' + re.escape(ai) + r'(?=\s*(?::|$))', entry + ' : ' + ai, text)
            if updated != text:
                writes[file] = updated.encode('utf-8')
        registry = storage.RUNTIME / 'creator/registry.json'
        if registry.is_file():
            records = json.loads(registry.read_text('utf-8'))
            for record in records:
                if record.get('projectId') == pid and record.get('ownerMod') == 'moreiterators.local':
                    record.update(exitNode=1, entryNode=0)
                    if explicit:
                        record['roomBinding'] = changed['roomBinding']
            writes[registry] = json.dumps(records, ensure_ascii=False, indent=2).encode('utf-8')
    # Protect all write/delete destinations, including junctions, before writing.
    permitted = [storage.DATA.resolve(), storage.installed_mod(pid).resolve()]
    for file in [*writes, *removes]:
        if not any(file.resolve().is_relative_to(root) for root in permitted):
            raise ValueError('等待房间迁移路径越界，未修改房间。')
    transaction = room_migration.Files()
    for file in [*removes, *writes]:
        transaction.watch(file)
    if occupied:
        archive = storage.project_file(pid).parent / 'room-template-backups' / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8])
        evidence = []
        for index, (file, content) in enumerate(transaction.original.items()):
            if content is None:
                continue
            target = archive / (str(index) + '.bin')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            evidence.append(dict(path=str(file), file=target.name, sha256=_sha(content)))
        (archive / 'manifest.json').write_text(json.dumps(dict(template=ID, files=evidence), ensure_ascii=False, indent=2), 'utf-8')
    try:
        for file in removes:
            transaction.remove(file)
        for file, content in writes.items():
            transaction.write(file, content)
    except Exception:
        transaction.rollback()
        raise
    return changed
