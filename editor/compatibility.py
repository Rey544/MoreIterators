"""Optional editor adapters are loaded only from locally associated workspaces."""
import importlib.util
import storage

_adapter=None
for _link in storage.LINKS:
    _path=storage.Path(_link['workspace'])/'editor/legacy.py'
    if _path.exists():
        _spec=importlib.util.spec_from_file_location('linked_editor_adapter',_path)
        _adapter=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_adapter)
        break
IDS=_adapter.IDS if _adapter else {}
def oracle(project):return _adapter.oracle(project) if _adapter else ''
def compile_flags(project,design):
    if _adapter:_adapter.compile_flags(project,design)
def dialogue_profile(project,result):
    if _adapter and hasattr(_adapter,'dialogue_profile'):return _adapter.dialogue_profile(project,result)
    return result
