
from pathlib import Path
import base64
import io
import math
import re
from PIL import Image
import room_bindings
import storage


def _asset(relative, roots=None):
    roots = room_bindings.enabled_asset_roots() if roots is None else roots
    for root in roots:
        path = Path(root)
        for part in Path(relative).parts:
            direct = path / part
            if direct.exists():
                path = direct
            elif path.is_dir():
                path = next((p for p in path.iterdir() if p.name.casefold() == part.casefold()), direct)
            else:
                path = direct
        if path.is_file() and room_bindings.is_enabled_asset(path, roots):
            return path
    return None


def _project(project_id):
    return storage.load_project(project_id) if project_id else None


def _own_rooms(project):
    if not project:
        return []
    binding = room_bindings.binding(project)
    result = []
    for kind, key in [('ai', 'ai'), ('entry', 'entry')]:
        if kind == 'entry' and binding.get('entryMode') == 'existing':
            continue
        name = binding[key]
        try:
            source = room_bindings.source_for(project, kind)
            if source.with_suffix('.txt').is_file():
                result.append(dict(name=name, region=binding['region'], connections=[], project=True))
        except (ValueError, OSError):
            pass
    return result


def _source(name, project):
    name = str(name).upper()
    if not room_bindings.ROOM_RE.fullmatch(name):
        raise ValueError('Invalid room name')
    if project:
        binding = room_bindings.binding(project)
        for key, kind in [('ai', 'ai'), ('entry', 'entry')]:
            if name == binding[key]:
                return room_bindings.source_for(project, kind), kind
    return room_bindings.resolve_room_source(name), None


def _region_names(regions, locale, roots):
    translations = {}
    language = 'chi' if str(locale).lower().startswith('zh') else 'eng'
    if language == 'chi':
        
        for root in reversed(roots):
            file = _asset('text/text_chi/strings.txt', [root])
            if not file:
                continue
            text = file.read_text('utf-8-sig', errors='replace')
            if text.startswith('1'):
                continue
            if text.startswith('0'):
                text = text[1:]
            for line in text.splitlines():
                if '|' in line:
                    key, value = line.split('|', 1)
                    translations[key] = value
    result = {}
    for region in regions:
        file = _asset('world/' + region + '/displayname-' + language + '.txt', roots)
        file = file or _asset('world/' + region + '/displayname.txt', roots)
        name = file.read_text('utf-8-sig', errors='replace').strip().splitlines()[0] if file and file.stat().st_size else region
        result[region] = translations.get(name, name)
    return result


def map_catalog(region='', project_id='', locale='zh-CN'):
    project = _project(project_id)
    catalog = room_bindings.catalog()
    groups = {item['name']: [dict(r, region=item['name']) for r in item['rooms']] for item in catalog.get('regions', [])}
    for own in _own_rooms(project):
        group = groups.setdefault(own['region'], [])
        if not any(item['name'] == own['name'] for item in group):
            group.append(own)
    roots = room_bindings.enabled_asset_roots()
    names = _region_names(groups, locale, roots)
    choices = [dict(id=key, name=names[key], count=len(groups[key])) for key in sorted(groups)]
    region = str(region).upper()
    if region and not room_bindings.REGION_RE.fullmatch(region):
        raise ValueError('Invalid region name')
    if region not in groups:
        preferred = room_bindings.binding(project)['region'] if project else ''
        region = preferred if preferred in groups else (choices[0]['id'] if choices else '')
    positions = {}
    map_file = _asset('world/' + region + '/map_' + region + '.txt', roots) if region else None
    if map_file:
        for line in map_file.read_text('utf-8-sig', errors='replace').splitlines():
            name, sep, raw = line.partition(':')
            parts = raw.strip().split('><')
            if not sep or len(parts) < 2:
                continue
            try:
                x, y = float(parts[0]), float(parts[1])
                if math.isfinite(x) and math.isfinite(y):
                    positions[name.strip().upper()] = [x, y]
            except ValueError:
                pass
    rooms = []
    for item in groups.get(region, []):
        name = item['name']
        rooms.append(dict(name=name, region=region, position=positions.get(name),
                          connections=list(item.get('connections', [])),
                          project=bool(item.get('project')), tags=item.get('tags', [])))
    return dict(regions=choices, region=region, name=names.get(region, region), rooms=rooms,
                layout='map' if any(room['position'] for room in rooms) else 'connections')


def geometry(source):
    rows = source.with_suffix('.txt').read_text('utf-8-sig').splitlines()
    if len(rows) < 12:
        raise ValueError('Room geometry is incomplete')
    width, height = map(int, rows[1].split('|')[0].split('*'))
    if min(width, height) < 1 or max(width, height) > 4096 or width * height > 4_000_000:
        raise ValueError('Invalid room dimensions')
    solids, shortcuts = [], []
    for i, value in enumerate(rows[11].split('|')[:width * height]):
        tile = value.split(',')[0].strip()
        position = [i // height, height - 1 - i % height]
        if tile == '1':
            solids.append(position)
        elif tile == '4':
            shortcuts.append(position)
    cameras = []
    for pair in rows[3].split('|'):
        try:
            x, y = map(float, pair.split(','))
            if math.isfinite(x) and math.isfinite(y):
                cameras.append([x, y])
        except ValueError:
            pass
    return dict(width=width, height=height, solids=solids, shortcuts=shortcuts, cameras=cameras)


def preview(name, project_id=''):
    project = _project(project_id)
    source, kind = _source(name, project)
    data = geometry(source)
    result = dict(data, room=str(name).upper(), image=None)
    width, height = data['width'] * 20, data['height'] * 20
    if width * height > 32_000_000 or max(width, height) > 8192:
        return result
    import projections
    appearance = project if kind == 'ai' else dict(design=dict(roomPaletteMode='room', roomPalette=0))
    if kind == 'entry' and project:
        appearance['projectId'] = project['projectId']
    canvas = Image.new('RGBA', (width, height), (20, 20, 20, 255))
    count = 0
    for i, (x, y) in enumerate(data['cameras']):
        camera = Path(str(source) + '_' + str(i + 1) + '.png')
        if not camera.is_file():
            continue
        with Image.open(camera) as image:
            if image.width > 4096 or image.height > 4096:
                continue
            try:
                palette = projections.room_palette(appearance, source, i)
            except (ValueError, OSError):
                continue
            art = projections.decode_room_image(image, palette, appearance.get('design', {}))
        canvas.alpha_composite(art, (round(x), round(y)))
        count += 1
    if count:
        canvas.thumbnail((1600, 1200), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        canvas.save(output, 'PNG')
        result['image'] = 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')
    return result
