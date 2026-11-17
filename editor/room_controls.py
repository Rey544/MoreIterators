
from pathlib import Path
import re

MODES = {
    'roomPaletteMode': ('mi', 'room'),
    'roomGravityMode': ('mi', 'room'),
    'entryGravityMode': ('zero', 'room'),
}


def validate(design):
    for field, values in MODES.items():
        value = design.get(field, values[0])
        if value not in values:
            raise ValueError('Invalid room control: ' + field)
        design[field] = value
    return design


def room_palette(project):
    return project.get('design', {}).get('roomPaletteMode', 'mi') == 'room'


def room_gravity(project):
    return project.get('design', {}).get('roomGravityMode', 'mi') == 'room'


def entry_gravity(project):
    return project.get('design', {}).get('entryGravityMode', 'zero') == 'room'


def copy_owned_room(project, source, directory, name, kind, server, replace=False):
    
    import project_packages
    source = Path(source);directory = Path(directory)
    settings = project_packages.selected_room_settings(project, name, source)
    setting_files = project_packages.room_settings_files(project, name, settings)
    setting_bytes = {filename: project_packages._file(path) for filename,path in setting_files.items()}
    for filename,content in setting_bytes.items():project_packages._text(content,filename)
    text = setting_bytes[name+'_settings.txt'].decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
    target = directory / (name + '_settings.txt')
    update = replace or not target.exists() or (kind == 'ai' and room_palette(project)) or (kind == 'entry' and entry_gravity(project))
    server.copy_room(source, directory, name, replace=replace)
    if update:
        if kind == 'ai' and not room_palette(project):
            text = re.sub(r'(?m)^Palette:.*', 'Palette: 26', text)
        target.write_text(text, 'utf-8')
    for filename,content in setting_bytes.items():
        if filename == name+'_settings.txt':continue
        variant = directory/filename
        if update or not variant.exists():variant.write_bytes(content)
    if kind == 'entry' and not entry_gravity(project):server.zero_gravity(target)
    return target


def require_portable_subset(text, name):
    
    effects = re.search(r'(?m)^Effects:[ \t]*([^\r\n]*)', text)
    if effects and any(float(match[1]) > 0 for match in re.finditer(r'(?:^|,\s*)AboveCloudsView-([0-9.]+)-', effects[1])):
        raise ValueError('房间 ' + name + ' 的天空远景依赖完整区域坐标，请使用整片区域导出。')


def effective_palette_settings(project, source):
    
    import room_bindings
    source = Path(source);name = source.name.upper();region = name.split('_')[0]
    if project.get('projectId'):
        import project_packages
        settings = project_packages.selected_room_settings(project, name, source)
    else:settings = Path(str(source) + '_settings.txt')
    text = settings.read_text('utf-8-sig') if settings.is_file() else ''
    def region_file(filename):
        if project.get('projectId'):
            import standalone
            return standalone._room_region_file(project, source, name, filename)
        for root in room_bindings.enabled_asset_roots():
            folder = root / 'world' / region.lower()
            if folder.is_dir():
                found = [p for p in folder.iterdir() if p.name.casefold() == filename.casefold() and p.is_file()]
                if len(found) == 1:return found[0]
        return None
    template = re.search(r'(?m)^Template:[ \t]*([^ \t\r\n][^\r\n]*)', text)
    template_name = template[1].strip() if template else ''
    if not template_name:
        properties = region_file('properties.txt')
        names = re.search(r'(?m)^Room Setting Templates:[ \t]*([^ \t\r\n][^\r\n]*)', properties.read_text('utf-8-sig')) if properties else None
        if names:template_name = region.lower() + '_settingstemplate_' + names[1].split(',')[0].strip()
    palette = 0
    if template_name and template_name.upper() != 'NONE':
        if not re.fullmatch(r'[A-Za-z0-9]+_[Ss][Ee][Tt][Tt][Ii][Nn][Gg][Ss][Tt][Ee][Mm][Pp][Ll][Aa][Tt][Ee]_[A-Za-z0-9-]+', template_name):
            raise ValueError('房间模板名称无效：' + template_name)
        file = region_file(template_name.lower() + '.txt')
        if file is None:raise ValueError('房间模板缺失：' + template_name)
        inherited = re.search(r'(?m)^Palette:[ \t]*(\d+)\b', file.read_text('utf-8-sig'))
        if inherited:palette = int(inherited[1])
    direct = re.search(r'(?m)^Palette:[ \t]*(\d+)\b', text)
    if direct:palette = int(direct[1])
    fade = re.search(r'(?m)^FadePalette:[ \t]*([^ \t\r\n][^\r\n]*)', text)
    return dict(palette=palette, fade=fade[1].split(',') if fade else [], text=text)
