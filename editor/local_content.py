"""Read-only readiness for the generated local content mod. Never enables mods."""
from pathlib import Path
import os
import xml.etree.ElementTree as ET
import storage

def options_path():
    # Unity's native Windows save root is independent of the editor's DATA root.
    # An author workspace or isolated editor profile must not be treated as a save.
    if os.name=='nt':return Path.home()/'AppData/LocalLow/Videocult/Rain World/options'
    return None

def enabled_mods(path):
    """Read the saved native selection; None means it could not be established."""
    if path is None:return None
    try:
        # Native saves can have UTF-8 BOM and unused NUL bytes after the XML.
        text=Path(path).read_text('utf-8-sig').rstrip('\0\r\n\t ')
        if '<!DOCTYPE' in text or '<!ENTITY' in text:return None
        root=ET.fromstring(text)
        def named(tag):return [node for node in root if node.tag.rsplit('}',1)[-1]==tag]
        keys,values=named('Keys'),named('Values')
        if len(keys)!=1 or len(values)!=1:return None
        keys,values=list(keys[0]),list(values[0])
        if len(keys)!=len(values):return None
        rows=[value for key,value in zip(keys,values) if key.text=='options']
        if len(rows)!=1 or len(rows[0]):return None
        fields=[entry.split('<optB>',1)[1] for entry in (rows[0].text or '').split('<optA>') if entry.startswith('EnabledMods<optB>')]
        if len(fields)!=1 or '<optB>' in fields[0]:return None
        return {entry.strip() for entry in fields[0].split('<optC>') if entry.strip()}
    except (OSError,UnicodeError,ET.ParseError,ValueError):return None

def status(project):
    pid=project['projectId']
    if storage.binding(pid):return dict(state='not-required')
    installed=storage.installed_mod(pid)
    result=dict(modId='moreiterators.local',name='更多迭代器 · 本地作品',installed=(installed/'modinfo.json').is_file(),state='unknown')
    # MultiFolderLoader's enabledMods.txt lists DLL-loading folders, not every
    # enabled content mod. Only the native options EnabledMods IDs are suitable.
    selected=enabled_mods(options_path())
    if selected is None:return result
    result['state']='enabled' if result['modId'] in selected else 'needs-enable'
    # This is the saved enable selection, not a claim that the running process
    # has reloaded newly generated room files.
    result['selectionSource']='options.EnabledMods';result['restartForNewRooms']=True
    return result
