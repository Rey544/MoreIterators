from pathlib import Path
import copy
import hashlib
import io
import json
import uuid
import re
import datetime
import time
from PIL import Image
import default_text
import room_bindings
import room_editor
import room_migration
import storage
import waiting_room
import chamber_sizes

ROOT = Path(__file__).resolve().parents[1] / 'templates/rooms/chambers'
SCHEMA = 'moreiterators.chamber-presets.v1'


def fail(key):
    raise ValueError(default_text.text('chamberPresets.error.' + key))


def checked_file(root, relative):
    if not isinstance(relative, str) or '\\' in relative or Path(relative).is_absolute():fail('invalid')
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()) or not result.is_file():fail('invalid')
    return result


def templates():
    index = json.loads((ROOT / 'manifest.json').read_text('utf-8'))
    if index.get('schema') != SCHEMA or not isinstance(index.get('presets'), list):fail('invalid')
    result = []
    for folder in index['presets']:
        if folder not in ('pebbles', 'moon', 'broken', 'irregular', 'multi-screen'):fail('invalid')
        directory = ROOT / folder
        value = json.loads((directory / 'manifest.json').read_text('utf-8'))
        if value.get('id') != 'mi-chamber-' + folder or not isinstance(value.get('files'), dict):fail('invalid')
        result.append((directory, value))
    if not result or len({value['id'] for _, value in result}) != len(result):fail('invalid')
    return result


def get(preset_id):
    result = next(((root, value) for root, value in templates() if value['id'] == preset_id), None)
    if result is None:fail('unknown')
    return result


def listing():
    return {'presets': [dict(id=value['id'], name=value['name'], width=value['width'], height=value['height'],
                             cameraCount=value['cameraCount'], sizes=chamber_sizes.options(value), preview='/api/chamber-preset-preview?id=' + value['id'])
                        for _, value in templates()]}


def preview(preset_id):
    root, value = get(preset_id)
    file = checked_file(root, value.get('preview', 'thumbnail.png'))
    if hashlib.sha256(file.read_bytes()).hexdigest() != value['files'].get(file.relative_to(root).as_posix()):fail('invalid')
    return file.read_bytes()


def validated_assets(root, value):
    for relative, digest in value['files'].items():
        file = checked_file(root, relative)
        if hashlib.sha256(file.read_bytes()).hexdigest() != digest:fail('invalid')
    source = checked_file(root, value['sourceBase'] + '.txt')
    if not source.read_text('utf-8-sig').lstrip().startswith('[[['):fail('invalid')
    rendered = checked_file(root, value['renderedBase'] + '.txt')
    geometry = room_bindings.geometry(rendered)
    node = value.get('aiNode', value.get('entryNode'))
    if type(node) is not int or not 0 <= node < geometry['exitCount']:fail('invalid')
    if geometry['width'] != value['width'] or geometry['height'] != value['height']:fail('invalid')
    lines = rendered.read_text('utf-8-sig').splitlines()
    cameras = [camera for camera in lines[3].split('|') if camera.strip()]
    if len(cameras) != value['cameraCount']:fail('invalid')
    assets = {'source': {'.txt': source.read_bytes()}, 'rendered': {'.txt': rendered.read_bytes()}}
    light = checked_file(root, value['sourceBase'] + '.png')
    assets['source']['.png'] = light.read_bytes()
    assets['rendered']['_settings.txt'] = checked_file(root, value['renderedBase'] + '_settings.txt').read_bytes()
    for relative in value['files']:
        if re.fullmatch(re.escape(value['renderedBase'])+r'_settings-[A-Za-z0-9_-]+\.txt',relative):assets['rendered'][relative[len(value['renderedBase']):]]=checked_file(root,relative).read_bytes()
    for number in range(1, len(cameras) + 1):
        suffix = '_' + str(number) + '.png'
        content = checked_file(root, value['renderedBase'] + suffix).read_bytes()
        with Image.open(io.BytesIO(content)) as image:
            if image.format != 'PNG':fail('invalid')
            image.verify()
        assets['rendered'][suffix] = content
    return assets


def create(request, server):
    if not isinstance(request, dict) or set(request) - {'presetId', 'name', 'sizeId'}:fail('invalid')
    root, value = get(request.get('presetId'))
    assets,value = chamber_sizes.render(validated_assets(root, value),value,request.get('sizeId','original'))
    entry_spec = waiting_room.manifest()
    entry_assets = validated_assets(waiting_room.ROOT, entry_spec)
    catalogue = room_bindings.catalog()
    reserved = set(catalogue.get('reservedRooms', []))
    reserved.update(row['name'] for region in catalogue.get('regions', []) for row in region.get('rooms', []))
    for existing in storage.project_files():
        binding = room_bindings.binding(json.loads(existing.read_text('utf-8')))
        reserved.update((binding['ai'], binding['entry']))
    import project_templates
    for _ in range(20):
        project = project_templates.create(server.default())
        project['projectId'] = 'oc-' + uuid.uuid4().hex
        destination = storage.project_file(project['projectId']).parent
        binding = room_bindings.binding(project)
        if destination.exists() or storage.purge_marker(project['projectId']).exists() or storage.binding(project['projectId']):continue
        if {binding['ai'], binding['entry']} & reserved:continue
        break
    else:fail('occupied')
    if not destination.resolve().is_relative_to(storage.PROJECTS.resolve()):fail('invalid')
    name = request.get('name')
    if name is None:name = default_text.text('chamberPresets.projectName').replace('{name}', default_text.text('chamberPresets.' + value['id']))
    project['name'] = name
    binding.update(aiNode=value['aiNode'], entryNode=entry_spec['entryNode'])
    project['roomBinding'] = binding
    project['chamberPreset'] = value['id']
    project['chamberSize'] = request.get('sizeId','original')
    project['design'].update(value.get('roomDefaults',{}))
    project[waiting_room.FIELD] = waiting_room.ID
    project = server.validate(copy.deepcopy(project))
    import dialogue
    project['dialogue'] = dialogue.profile(project)
    transaction = room_migration.Files()
    try:
        for kind, files in (('ai', assets), ('entry', entry_assets)):
            room = binding[kind]
            for suffix, content in files['source'].items():transaction.write(destination / 'rooms' / (room + suffix), content)
            for suffix, content in files['rendered'].items():
                if suffix == '.txt':
                    lines = content.decode('utf-8-sig').splitlines();lines[0] = room
                    content = ('\n'.join(lines) + '\n').encode('utf-8')
                transaction.write(destination / 'rooms/rendered' / (room + suffix), content)
        plan = room_bindings.plan(project, binding, catalogue=catalogue)
        transaction.json(destination / 'room-binding-plan.json', plan)
        transaction.json(destination / 'project.json', project)
        import room_source_choices
        for kind in ('ai', 'entry'):
            room = binding[kind]
            transaction.json(destination / 'rooms/rendered' / (room + '.source.json'), room_source_choices.pairing_record(project['projectId'], room))
    except Exception:
        transaction.rollback()
        if destination.exists():
            for directory in sorted((p for p in destination.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
                if directory.resolve().is_relative_to(destination.resolve()) and not any(directory.iterdir()):directory.rmdir()
            if not any(destination.iterdir()):destination.rmdir()
        raise
    return dict(ok=True, project=project, requiresApply=True)


def room_files(project):
    pid=project['projectId'];room=room_bindings.binding(project)['ai'];directory=storage.project_file(pid).parent
    pattern=re.compile(re.escape(room)+r'(?:\.(?:txt|png|source\.json)|_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|_[1-9][0-9]*\.png)$',re.I)
    result=[]
    for root in (directory/'rooms',directory/'rooms/rendered'):
        if root.is_dir():result.extend(file for file in root.iterdir() if file.is_file() and pattern.fullmatch(file.name))
    return result


def state(pid):
    pid=storage.valid_id(pid);project=storage.load_project(pid)
    hashes={str(file):hashlib.sha256(file.read_bytes()).hexdigest() for file in [storage.project_file(pid),*room_files(project),*(file for _,file in room_versions(project))]}
    token=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    return dict(token=token,replaceable=not bool(storage.binding(pid)))


def room_versions(project):
    pid=project['projectId'];room=room_bindings.binding(project)['ai'];relative=Path('world')/(room.split('_')[0].lower()+'-rooms')
    roots=[('local',storage.target_mod(pid)/relative)]
    installed=storage.installed_mod(pid,required=False)
    if installed is not None:roots.append(('installed',installed/relative))
    try:roots.append(('rained',room_editor.rained_data_root()/'Levels'))
    except ValueError:pass
    pattern=re.compile(re.escape(room)+r'(?:\.txt|_settings(?:-[A-Za-z0-9_-]+)?\.txt|_properties\.txt|_[1-9][0-9]*\.png)$',re.I)
    return [(label,file) for label,root in roots if root.is_dir() for file in root.iterdir() if file.is_file() and pattern.fullmatch(file.name)]


def replace(request,server):
    if not isinstance(request,dict) or set(request)-{'project','presetId','sizeId','token'}:fail('invalid')
    incoming=copy.deepcopy(request.get('project'))
    if not isinstance(incoming,dict):fail('invalid')
    pid=storage.valid_id(incoming.get('projectId'));before=storage.load_project(pid);current=state(pid)
    if not current['replaceable']:fail('fixed')
    if request.get('token')!=current['token'] or incoming.get('updatedAt')!=before.get('updatedAt'):fail('stale')
    root,spec=get(request.get('presetId'))
    assets,spec=chamber_sizes.render(validated_assets(root,spec),spec,request.get('sizeId','original'))
    if state(pid)['token']!=current['token']:fail('stale')
    project=server.validate(incoming)
    for key in ('roomBinding','dialogue','dialogueRevision','overseer','overseerRevision',waiting_room.FIELD):
        if key in before:project[key]=copy.deepcopy(before[key])
        else:project.pop(key,None)
    binding=room_bindings.binding(before);binding['aiNode']=spec['aiNode'];project['roomBinding']=binding
    project['chamberPreset']=spec['id'];project['chamberSize']=request.get('sizeId','original')
    project['design'].update(spec.get('roomDefaults',{}))
    directory=storage.project_file(pid).parent;room=binding['ai'];transaction=room_migration.Files()
    backup=directory/'room-history'/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'-'+uuid.uuid4().hex[:8])
    originals=room_files(before)+[storage.project_file(pid)]
    for name in ('room-binding-plan.json','room-package.json'):
        file=directory/name
        if file.is_file():originals.append(file)
    try:
        for file in originals:transaction.write(backup/file.relative_to(directory),file.read_bytes())
        for label,file in room_versions(before):transaction.write(backup/'versions'/label/file.name,file.read_bytes())
        for file in room_files(before):transaction.remove(file)
        for suffix,content in assets['source'].items():transaction.write(directory/'rooms'/(room+suffix),content)
        for suffix,content in assets['rendered'].items():
            if suffix=='.txt':
                lines=content.decode('utf-8-sig').splitlines();lines[0]=room;content=('\n'.join(lines)+'\n').encode('utf-8')
            transaction.write(directory/'rooms/rendered'/(room+suffix),content)
        plan=room_bindings.plan(project,binding)
        transaction.json(directory/'room-binding-plan.json',plan)
        import room_source_choices,project_packages
        metadata=project_packages.load_metadata(pid)
        stamp=time.time_ns()
        if metadata is None:metadata=dict(schema=project_packages.LOCAL_SCHEMA,projectId=pid,importedAtNs=stamp,rooms=[],files=[])
        elif metadata.get('importedAtNs') is None:metadata['importedAtNs']=(directory/project_packages.LOCAL_MANIFEST).stat().st_mtime_ns
        row=next((item for item in metadata['rooms'] if item['name']==room),None)
        if row is None:
            row=dict(name=room,kind='ai',region=binding['region']);metadata['rooms'].append(row)
        planned=next(item for text in plan['worldFiles'].values() for item in room_bindings.parse_world(text,binding['region']) if item['name']==room)
        row.update(sourceAvailable=True,connections=list(planned['connections']),tags=planned.get('tags',''),updatedAtNs=stamp)
        old_paths={file.relative_to(directory).as_posix() for file in originals}
        metadata['files']=[item for item in metadata['files'] if item['path'] not in old_paths]
        metadata['files'].extend(project_packages._records({file.relative_to(directory).as_posix():file.read_bytes() for file in room_files(project) if project_packages._local_file(file.relative_to(directory).as_posix())}))
        transaction.json(directory/project_packages.LOCAL_MANIFEST,metadata)
        transaction.json(storage.project_file(pid),project)
        transaction.json(directory/'rooms/rendered'/(room+'.source.json'),room_source_choices.pairing_record(pid,room))
    except Exception:
        transaction.rollback();raise
    return dict(ok=True,project=project,requiresApply=True,requiresRestart=True,backup=str(backup))
