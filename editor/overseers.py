"""Independently revisioned, project-owned overseer settings."""
import copy
import datetime
import json
import math
import os
import re
import threading
import unicodedata
import uuid
import room_bindings
import storage

LOCK = threading.RLock()
RUNTIME_FIELD = 'overseerJson'


def defaults():
    # Runtime field names are shared with CreatorOverseers' configuration model.
    return dict(enabled=False, ownerAbbreviation='', bodyColors=['#72E6C4'], tipColors=['#B4FFF2'],
                eyeWhite='#FFFFFF', eyePupil='#000000', probabilities=dict(lens=.35, GateScene=.2, Angry=0.0),guests=[])


def normalize(value=None, _guest=False):
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError('监视器配置必须是对象。')
    result = defaults()
    allowed=set(result)|{'rooms','ownerProjectId'}
    if _guest:allowed=(allowed-{'guests'})|{'id','name'}
    if set(value) - allowed:
        raise ValueError('监视器配置包含未知字段。')
    if _guest:result.pop('guests')
    result.update(copy.deepcopy(value))
    if _guest:
        if not isinstance(result.get('id'),str) or not re.fullmatch('[a-f0-9]{32}',result['id']):raise ValueError('监视器配置编号无效。')
        if not isinstance(result.get('name'),str) or not 1<=len(result['name'].strip())<=60 or any(unicodedata.category(ch) in ('Cc','Cs') or ch in '<>' for ch in result['name']):raise ValueError('监视器名称应为 1—60 个字符。')
        result['name']=result['name'].strip();result.setdefault('rooms',[]);result.setdefault('ownerProjectId','')
    if 'ownerProjectId' in result:
        owner_id=result['ownerProjectId']
        if owner_id!='':storage.valid_id(owner_id)
    if 'rooms' in result:
        rooms=result['rooms']
        if not isinstance(rooms,list) or len(rooms)>64 or any(not isinstance(room,str) or not re.fullmatch('[A-Z0-9_]{1,80}',room) for room in rooms) or len(rooms)!=len(set(rooms)):raise ValueError('监视器出现房间无效，最多选择 64 个不同房间。')
    if type(result['enabled']) is not bool:
        raise ValueError('监视器开关无效。')
    owner = result['ownerAbbreviation']
    if not isinstance(owner, str):
        raise ValueError('监视器所属者缩写无效。')
    # Validate before stripping so newline/control input cannot disappear.
    if any(unicodedata.category(ch) in ('Cc', 'Cs') or ch in '<>' for ch in owner):
        raise ValueError('监视器所属者缩写不能包含控制字符或尖括号。')
    owner = owner.strip()
    if len(owner) > 12:
        raise ValueError('监视器所属者缩写最多 12 个字符。')
    result['ownerAbbreviation'] = owner
    def color(value):
        if not isinstance(value, str) or not re.fullmatch(r'#[A-Fa-f0-9]{6}', value):
            raise ValueError('监视器颜色须为 #RRGGBB。')
        return value.upper()
    for key in ('bodyColors', 'tipColors'):
        values = result[key]
        if not isinstance(values, list) or len(values) not in (1, 2):
            raise ValueError('监视器本体和尖端分别需要 1 或 2 个颜色。')
        result[key] = [color(value) for value in values]
    for key in ('eyeWhite', 'eyePupil'):
        result[key] = color(result[key])
    chances = result['probabilities']
    expected = defaults()['probabilities']
    if not isinstance(chances, dict) or set(chances) - set(expected):
        raise ValueError('监视器行为概率字段无效。')
    expected.update(chances)
    for value in expected.values():
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('监视器行为概率应为 0—1 的有限数值。')
    result['probabilities'] = expected
    if not _guest:
        guests=result['guests']
        if not isinstance(guests,list) or len(guests)>16:raise ValueError('最多设置 16 个访客监视器。')
        result['guests']=[normalize(guest,True) for guest in guests]
        ids=[guest['id'] for guest in result['guests']]
        if len(ids)!=len(set(ids)):raise ValueError('监视器配置编号不能重复。')
    return result


def validate_locations(config,project):
    previous=normalize(project.get('overseer'))
    old={'default':previous,**{guest['id']:guest for guest in previous['guests']}}
    binding=room_bindings.binding(project)
    known={binding['ai'],binding['entry']}
    known.update(room['name'] for region in room_bindings.catalog().get('regions',[]) for room in region.get('rooms',[]) if room.get('verified') and not room.get('conditional'))
    for key,profile in [('default',config)]+[(guest['id'],guest) for guest in config['guests']]:
        for room in profile.get('rooms',[]):
            if room not in known and room not in old.get(key,{}).get('rooms',[]):raise ValueError('监视器出现房间尚未确认存在：'+room)
        owner=profile.get('ownerProjectId','')
        if owner and owner!=old.get(key,{}).get('ownerProjectId',''):
            try:storage.load_project(owner)
            except (OSError,ValueError):raise ValueError('监视器所属迭代器不存在，请重新选择。')


def _revision(project):
    value = project.get('overseerRevision', 0)
    if type(value) is not int or value < 0:
        raise ValueError('监视器保存版本无效。')
    return value


def decode(value):
    if not isinstance(value, str):
        raise ValueError('监视器运行配置必须是 JSON 文本。')
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError('监视器配置必须是对象。')
    return normalize(parsed)


def _runtime_file(project):
    oid = room_bindings.binding(project)['oracleId']
    return storage.design_path(project['projectId'], oid)


def describe(project):
    config = normalize(project.get('overseer'))
    revision = _revision(project)
    result = dict(projectId=project['projectId'], config=config, revision=revision,
                  appliedRevision=-1, editable=True, warnings=[])
    path = _runtime_file(project)
    result['canApply'] = path.is_file()
    if path.is_file():
        try:
            runtime = json.loads(path.read_text('utf-8'))
            if not isinstance(runtime, dict):
                result['canApply'] = False
                raise ValueError('运行设计无效')
            if runtime.get('projectId') != project['projectId']:
                result['canApply'] = False
                result['warnings'].append('已应用的设计不属于此项目，不能覆盖。')
            elif decode(runtime.get(RUNTIME_FIELD, '{}')) == config:
                result['appliedRevision'] = revision
        except (OSError, ValueError, TypeError):
            result['warnings'].append('已应用的监视器配置无法读取；可以重新应用已保存的配置。')
    return result


def read(project_id):
    return describe(storage.load_project(storage.valid_id(project_id)))


def _atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _commit(changes):
    originals = {path: path.read_bytes() if path.exists() else None for path in changes}
    done = []
    try:
        for path, value in changes.items():
            _atomic(path, value)
            done.append(path)
    except Exception:
        for path in reversed(done):
            original = originals[path]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                temporary = path.with_name(path.name + '.rollback-' + uuid.uuid4().hex)
                try:
                    temporary.write_bytes(original)
                    os.replace(temporary, path)
                finally:
                    temporary.unlink(missing_ok=True)
        raise


def save(project_id, config, revision, apply=False):
    """Publish only this independent section; never redeploy other project drafts."""
    storage.valid_id(project_id)
    if not isinstance(config, dict):
        raise ValueError('监视器配置必须是对象。')
    config = normalize(config)
    if type(revision) is not int or revision < 0:
        raise ValueError('监视器保存版本无效，请重新打开项目。')
    with LOCK:
        project = storage.load_project(project_id)
        if revision != _revision(project):
            raise ValueError('监视器设置已在另一页面保存，请重新打开此项目后再修改。')
        validate_locations(config,project)
        project = copy.deepcopy(project)
        project['overseer'] = config
        project['overseerRevision'] = revision + 1
        project['updatedAt'] = datetime.datetime.now().isoformat(timespec='seconds')
        changes = {storage.project_file(project_id): project}
        if apply:
            runtime_file = _runtime_file(project)
            if not runtime_file.exists():
                raise ValueError('请先在外观调整应用此项目，再应用监视器设置；本次修改尚未保存。')
            runtime = json.loads(runtime_file.read_text('utf-8'))
            if not isinstance(runtime, dict) or runtime.get('projectId') != project_id:
                raise ValueError('已应用的设计不属于此项目，不能覆盖。')
            runtime[RUNTIME_FIELD] = json.dumps(config, ensure_ascii=False)
            changes[runtime_file] = runtime
            if storage.link(project_id) and storage.installed_mod(project_id).exists():
                destination = storage.installed_mod(project_id) / 'designs' / runtime_file.name
                if destination.exists():
                    installed = json.loads(destination.read_text('utf-8'))
                    if not isinstance(installed, dict) or installed.get('projectId') != project_id:
                        raise ValueError('已安装的设计属于另一项目，不能覆盖。')
                    installed[RUNTIME_FIELD] = runtime[RUNTIME_FIELD]
                    changes[destination] = installed
                else:
                    raise ValueError('已安装模组缺少此设计，请先重新应用项目。')
        _commit(changes)
        return dict(describe(project), ok=True, applied=apply)
