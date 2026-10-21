"""Named pearl collections; authoring identity is separate from the active runtime."""
import copy
import datetime
import json
import os
import re
import threading
import uuid
import storage

SCHEMA = 'moreiterators.pearl-projects.v1'
LEGACY = 'legacy'
LOCK = threading.RLock()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def metadata_path():
    return storage.DATA / 'pearl-projects.json'


def valid_id(value):
    if not isinstance(value, str) or not (value == LEGACY or re.fullmatch(r'[a-f0-9]{32}', value)):
        raise ValueError('珍珠项目内部编号无效')
    return value


def valid_name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 100 or any(ord(c) < 32 for c in value):
        raise ValueError('珍珠项目名称应为 1—100 个字符')
    return value.strip()


def atomic(file, value):
    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_name(file.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_bytes(json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8'))
        os.replace(temporary, file)
    finally:
        if temporary.exists():
            temporary.unlink()


def _directory(cid):
    valid_id(cid)
    base = (storage.DATA / 'pearl-projects').resolve()
    result = base / cid / 'pearls'
    if not result.resolve().is_relative_to(base):
        raise ValueError('珍珠项目目录不能指向数据目录以外')
    return result


def _validate_catalog(data):
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or not isinstance(data.get('projects'), list):
        raise ValueError('珍珠项目目录格式无效')
    seen = set()
    for item in data['projects']:
        if not isinstance(item, dict):
            raise ValueError('珍珠项目目录条目无效')
        cid = valid_id(item.get('id'))
        valid_name(item.get('name'))
        if cid in seen:
            raise ValueError('珍珠项目内部编号重复')
        seen.add(cid)
    if not seen or data.get('activeId') not in seen:
        raise ValueError('当前珍珠项目不存在')
    return data


def _entry(cid, name):
    stamp = now()
    return dict(id=cid, name=name, createdAt=stamp, updatedAt=stamp)


def _ensure():
    file = metadata_path()
    data = _validate_catalog(json.loads(file.read_text('utf-8'))) if file.exists() else None
    legacy_files = sorted((storage.DATA / 'pearls').glob('*/pearl.json'))
    has_legacy = data is not None and any(p['id'] == LEGACY for p in data['projects'])
    if legacy_files and not has_legacy:
        # Preflight every record before writing anything. Originals are retained;
        # the committed catalog is the one-time migration marker.
        planned = []
        uids = set()
        if data:
            for project in data['projects']:
                for existing in _directory(project['id']).glob('*/pearl.json'):
                    uid = json.loads(existing.read_text('utf-8')).get('uid')
                    if uid:
                        uids.add(uid)
        for original in legacy_files:
            item = json.loads(original.read_text('utf-8'))
            if not isinstance(item, dict) or item.get('schema') != 'moreiterators.pearl.v1':
                raise ValueError('旧珍珠文件格式无效：' + original.name)
            pid = item.get('id')
            uid = item.get('uid')
            if not isinstance(pid, str) or not re.fullmatch(r'[A-Z]{1,4}[0-9]{2,4}', pid) or original.parent.name != pid:
                raise ValueError('旧珍珠编号与目录不一致')
            if not isinstance(uid, str) or not re.fullmatch(r'[a-f0-9]{32}', uid) or uid in uids:
                raise ValueError('旧珍珠内部编号无效或与其他项目重复')
            if item.get('collectionId', LEGACY) != LEGACY:
                raise ValueError('旧珍珠文件已有其他项目归属，无法自动迁移')
            uids.add(uid)
            item['collectionId'] = LEGACY
            destination = _directory(LEGACY) / pid / 'pearl.json'
            if destination.exists() and json.loads(destination.read_text('utf-8')) != item:
                raise ValueError('已有珍珠迁移目标发生冲突；原文件已保留')
            planned.append((destination, item))
        for destination, item in planned:
            if not destination.exists():
                atomic(destination, item)
        if data is None:
            data = dict(schema=SCHEMA, activeId=LEGACY, projects=[])
        data['projects'].append(_entry(LEGACY, '已有珍珠'))
        atomic(file, data)
    if data is None:
        cid = uuid.uuid4().hex
        data = dict(schema=SCHEMA, activeId=cid, projects=[_entry(cid, '珍珠项目 1')])
        atomic(file, data)
    return data


def catalog():
    with LOCK:
        return copy.deepcopy(_ensure())


def resolve(collection_id=None):
    with LOCK:
        data = _ensure()
        cid = data['activeId'] if collection_id is None else valid_id(collection_id)
        if not any(p['id'] == cid for p in data['projects']):
            raise ValueError('珍珠项目不存在，请重新选择')
        return cid


def ensure_legacy():
    """Old editor documents without collectionId always belong to legacy."""
    with LOCK:
        data = _ensure()
        if not any(p['id'] == LEGACY for p in data['projects']):
            data['projects'].append(_entry(LEGACY, '已有珍珠'))
            atomic(metadata_path(), data)
        return LEGACY


def directory(collection_id=None):
    return _directory(resolve(collection_id))


def save(document):
    """Create without id; rename a known immutable id. Returns the full catalog."""
    if not isinstance(document, dict):
        raise ValueError('珍珠项目格式无效')
    name = valid_name(document.get('name'))
    with LOCK:
        data = _ensure()
        if 'id' in document:
            cid = valid_id(document['id'])
            item = next((p for p in data['projects'] if p['id'] == cid), None)
            if item is None:
                raise ValueError('不能修改不存在的珍珠项目内部编号')
            item['name'] = name
            item['updatedAt'] = now()
        else:
            data['projects'].append(_entry(uuid.uuid4().hex, name))
        atomic(metadata_path(), data)
        return copy.deepcopy(data)


def activate(collection_id, roomnames):
    """Publish a whole collection; changing authoring selection alone never mixes runtime files."""
    import pearls
    with LOCK:
        cid = resolve(collection_id)
        return pearls.publish_collection(cid, roomnames)
