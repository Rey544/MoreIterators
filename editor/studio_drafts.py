"""Persist unfinished room edits without changing effective world bindings."""
import copy,json
import storage,room_bindings,project_lifecycle

SCHEMA='moreiterators.room-draft.v1'

def _project(pid):
    pid=storage.valid_id(pid);project_lifecycle.assert_active(pid)
    return storage.load_project(pid)

def _path(pid):return project_lifecycle._safe_path(storage.project_file(pid).parent,'editor-drafts/room-binding.json')

def _binding(value):
    if value is None:return None
    if not isinstance(value,dict) or set(value)!=room_bindings.BINDING_KEYS:raise ValueError('房间草稿格式无效')
    for key in ('region','ai','entry','oracleId'):
        if not isinstance(value[key],str) or len(value[key])>128:raise ValueError('房间草稿字段过长或类型无效')
    if value['entryMode'] not in ('copy','existing'):raise ValueError('房间草稿入口类型无效')
    for key in ('aiNode','entryNode'):
        if type(value[key]) is not int or not -1<=value[key]<=63:raise ValueError('房间草稿出口编号无效')
    return copy.deepcopy(value)

def _stored(pid):
    file=_path(pid)
    if not file.exists():return dict(schema=SCHEMA,projectId=pid,revision=0,binding=None)
    if file.stat().st_size>8192:raise ValueError('房间草稿文件过大')
    value=json.loads(file.read_text('utf-8'))
    if not isinstance(value,dict) or value.get('schema')!=SCHEMA or value.get('projectId')!=pid or type(value.get('revision')) is not int or value['revision']<0:raise ValueError('房间草稿文件损坏')
    value['binding']=_binding(value.get('binding'));return value

def load(pid):
    project=_project(pid);value=_stored(pid)
    # An explicitly applied preview is no longer a pending draft. This also
    # handles a lost HTTP response after the world migration completed.
    if value['binding']==room_bindings.binding(project):value['binding']=None
    return value

def save(data,atomic):
    project=_project(data.get('projectId'));pid=project['projectId']
    if storage.binding(pid) or storage.link(pid) or project.get('fixedProject'):raise ValueError('固定项目不能保存房间连接草稿')
    previous=_stored(pid)
    if type(data.get('revision')) is not int or data['revision']!=previous['revision']:raise ValueError('房间草稿已在其他页面更新，请重新打开后再修改')
    binding=_binding(data.get('binding'))
    value=dict(schema=SCHEMA,projectId=pid,revision=previous['revision']+1,binding=binding)
    atomic(_path(pid),value);return load(pid)
