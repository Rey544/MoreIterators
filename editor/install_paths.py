"""Bounded, read-only discovery and explicit installation-path configuration."""
from pathlib import Path
import json
import os
import re
import tempfile
import threading

_CONFIG_LOCK = threading.RLock()
_MAX_VDF_BYTES = 2 * 1024 * 1024


def read_settings(config):
    config = Path(config)
    if not config.exists():
        return {}
    value = json.loads(config.read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError('The existing configuration must be a JSON object; no changes were written.')
    return value


def _path(value):
    if not isinstance(value, (str, os.PathLike)):
        return None
    value = str(value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1].strip()
    if not value or '\0' in value:
        return None
    try:
        return Path(os.path.expandvars(value)).expanduser().resolve()
    except (OSError, ValueError, RuntimeError):
        return None


def game_root(value):
    path = _path(value)
    if path is not None and path.name.lower() == 'rainworld.exe':
        path = path.parent
    try:
        return path if path is not None and (path / 'RainWorld.exe').is_file() else None
    except OSError:
        return None


def rained_executable(value):
    path = _path(value)
    try:
        if path is not None and path.is_dir():
            path = path / 'Rained.exe'
        return path if path is not None and path.name.lower() == 'rained.exe' and path.is_file() else None
    except OSError:
        return None


def _vdf(path):
    """Read Steam's quoted-key format, including old and current library lists."""
    try:
        path = Path(path)
        if path.stat().st_size > _MAX_VDF_BYTES:
            return {}
        text = path.read_text(encoding='utf-8-sig')
        tokens = re.findall(r'"(?:\\.|[^"\\])*"|//[^\r\n]*|[{}]|[^\s{}"]+', text)
        tokens = [token for token in tokens if not token.startswith('//')]
        position = 0

        def atom(token):
            if token.startswith('"'):
                return re.sub(r'\\([\\"])', r'\1', token[1:-1])
            return token

        def section(depth=0):
            nonlocal position
            if depth > 8:
                raise ValueError('Unexpected Steam configuration nesting')
            value = {}
            while position < len(tokens):
                key = tokens[position]
                position += 1
                if key == '}':
                    return value
                if key == '{' or position >= len(tokens):
                    raise ValueError('Incomplete Steam configuration')
                item = tokens[position]
                position += 1
                if item == '}':
                    raise ValueError('Incomplete Steam configuration')
                value[atom(key).lower()] = section(depth + 1) if item == '{' else atom(item)
            return value

        return section()
    except (OSError, UnicodeError, ValueError):
        return {}


def _registered_paths():
    result = {'steam': [], 'rained': []}
    if os.name != 'nt':
        return result
    import winreg

    def get(hive, subkey, name='', view=0):
        try:
            with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | view) as key:
                value = winreg.QueryValueEx(key, name)[0]
                return value if isinstance(value, str) else ''
        except OSError:
            return ''

    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            for name in ('SteamPath', 'InstallPath', 'SteamExe'):
                value = get(hive, r'Software\Valve\Steam', name, view)
                if value:
                    path = _path(value)
                    if path is not None:
                        result['steam'].append(path.parent if path.suffix.lower() == '.exe' else path)
            value = get(hive, r'Software\Microsoft\Windows\CurrentVersion\App Paths\Rained.exe', view=view)
            if value:
                result['rained'].append(value)
            uninstall = r'Software\Microsoft\Windows\CurrentVersion\Uninstall'
            try:
                with winreg.OpenKey(hive, uninstall, 0, winreg.KEY_READ | view) as key:
                    count = min(winreg.QueryInfoKey(key)[0], 4096)
                    for index in range(count):
                        subkey = uninstall + '\\' + winreg.EnumKey(key, index)
                        if re.match(r'^Rained(?:\b|[_-])', get(hive, subkey, 'DisplayName', view), re.I):
                            location = get(hive, subkey, 'InstallLocation', view)
                            if location:
                                result['rained'].append(Path(location) / 'Rained.exe')
            except OSError:
                pass
    return result


def _unique_paths(values):
    seen = set()
    for value in values:
        path = _path(value)
        if path is None:
            continue
        key = os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            yield path


def steam_libraries(workspace, environ=None, registered=None):
    environ = os.environ if environ is None else environ
    registered = _registered_paths() if registered is None else registered
    workspace = Path(workspace).resolve()
    roots = [parent.parent for parent in (workspace, *workspace.parents) if parent.name.lower() == 'steamapps']
    roots += list(registered.get('steam', []))
    for key in ('STEAM_PATH', 'STEAM_HOME'):
        if environ.get(key):
            roots.append(environ[key])
    for key in ('ProgramFiles(x86)', 'PROGRAMFILES(X86)', 'ProgramFiles', 'PROGRAMFILES', 'LOCALAPPDATA'):
        if environ.get(key):
            roots.append(Path(environ[key]) / 'Steam')
    libraries = list(_unique_paths(roots))
    for steam in libraries[:]:
        for file in (steam / 'steamapps/libraryfolders.vdf', steam / 'config/libraryfolders.vdf'):
            values = _vdf(file).get('libraryfolders', {})
            if not isinstance(values, dict):
                continue
            for key, item in values.items():
                if key.isdigit():
                    path = item.get('path') if isinstance(item, dict) else item
                    if path:
                        libraries.append(path)
    return list(_unique_paths(libraries))


def _result(configured, entries, validator):
    valid_configured = validator(configured)
    candidates = []
    seen = set()
    for value, source in entries:
        path = validator(value)
        if path is None:
            continue
        key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        candidates.append({'path': str(path), 'source': source})
    first = candidates[0] if candidates else {'path': '', 'source': ''}
    return dict(found=bool(candidates), path=first['path'], source=first['source'],
                configuredPath=str(configured) if isinstance(configured, (str, os.PathLike)) else '',
                configuredValid=valid_configured is not None, candidates=candidates)


def discover_game(settings, workspace, environ=None, registered=None):
    environ = os.environ if environ is None else environ
    registered = _registered_paths() if registered is None else registered
    entries = [(settings.get('gameRoot'), 'configured'), (environ.get('RAIN_WORLD_ROOT'), 'environment')]
    workspace = Path(workspace).resolve()
    entries += [(folder, 'package') for folder in (workspace, *workspace.parents)]
    for library in steam_libraries(workspace, environ, registered):
        common = library / 'steamapps/common'
        install = _vdf(library / 'steamapps/appmanifest_312520.acf').get('appstate', {})
        name = install.get('installdir') if isinstance(install, dict) else None
        if isinstance(name, str) and name not in ('', '.', '..') and not re.search(r'[\\/:]', name):
            entries.append((common / name, 'steam'))
        entries.append((common / 'Rain World', 'steam'))
    return _result(settings.get('gameRoot'), entries, game_root)


def _nearby_rained(base):
    """Only named portable-editor locations; never recursively walk a disk."""
    yield base / 'Rained.exe'
    for folder in (base, base / 'Tools', base / 'tools', base / '工具'):
        yield folder / 'Rained/Rained.exe'
        try:
            matches = sorted(folder.glob('Rained*'), key=lambda path: path.name.casefold())[:32]
        except OSError:
            continue
        for match in matches:
            yield match / 'Rained.exe'


def discover_rained(settings, workspace, game=None, environ=None, registered=None):
    environ = os.environ if environ is None else environ
    registered = _registered_paths() if registered is None else registered
    entries = [(settings.get('rainedExecutable'), 'configured')]
    entries += [(path, 'registered') for path in registered.get('rained', [])]
    workspace = Path(workspace).resolve()
    nearby = [workspace, workspace.parent]
    if game and game.get('found'):
        root = Path(game['path'])
        nearby += [root, root.parent]
    for library in steam_libraries(workspace, environ, registered):
        nearby += [library, library / 'steamapps/common']
    home = _path(environ.get('USERPROFILE') or environ.get('HOME'))
    if home is not None:
        nearby += [home / 'Downloads', home / 'Desktop', home / 'Documents']
    for key in ('ProgramFiles', 'PROGRAMFILES', 'ProgramFiles(x86)', 'PROGRAMFILES(X86)'):
        if environ.get(key):
            nearby.append(Path(environ[key]))
    if environ.get('LOCALAPPDATA'):
        nearby.append(Path(environ['LOCALAPPDATA']) / 'Programs')
    for base in _unique_paths(nearby):
        entries.extend((path, 'nearby') for path in _nearby_rained(base))
    return _result(settings.get('rainedExecutable'), entries, rained_executable)


def discover(settings, workspace, environ=None, registered=None):
    registered = _registered_paths() if registered is None else registered
    game = discover_game(settings, workspace, environ, registered)
    return dict(game=game, rained=discover_rained(settings, workspace, game, environ, registered))


def save_selection(config, selections):
    """Only an explicit selection writes config; retain every unrelated field."""
    if not isinstance(selections, dict) or not selections or set(selections) - {'gameRoot', 'rainedExecutable'}:
        raise ValueError('Select a Rain World or Rained installation path.')
    changes = {}
    for name, value in selections.items():
        path = game_root(value) if name == 'gameRoot' else rained_executable(value)
        if path is None:
            filename = 'RainWorld.exe' if name == 'gameRoot' else 'Rained.exe'
            raise ValueError('Select the existing ' + filename + ' file or its containing folder.')
        changes[name] = str(path)
    config = Path(config)
    with _CONFIG_LOCK:
        value = read_settings(config)
        value.update(changes)
        config.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                             prefix='.' + config.name + '-', suffix='.tmp',
                                             dir=config.parent, delete=False) as file:
                temporary = Path(file.name)
                json.dump(value, file, ensure_ascii=False, indent=2)
                file.write('\n')
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, config)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
        return value
