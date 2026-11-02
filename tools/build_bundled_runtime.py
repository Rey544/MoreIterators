"""Build the private Windows x64 runtime from pinned upstream archives."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import shutil
import stat
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'moreiterators.runtime.v1'
PYTHON_VERSION = '3.13.17'
PILLOW_VERSION = '12.3.0'
PYTHON = {
    'filename': 'python-3.13.17-embed-amd64.zip',
    'url': 'https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip',
    'sha256': '9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38',
}
PILLOW = {
    'filename': 'pillow-12.3.0-cp313-cp313-win_amd64.whl',
    'url': 'https://files.pythonhosted.org/packages/a6/9b/7a58e61d62be561da3a356fe2384d4059a6345fc130e23ef1c36a5b81d24/pillow-12.3.0-cp313-cp313-win_amd64.whl',
    'sha256': '1cca606cd25738df4ed873d5ad46bbdb3d83b5cbca291f6b4ff13a4df6b0bbe8',
}
PTH = 'python313.zip\n.\nLib/site-packages\n../../editor\n'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative_path(name):
    if not name or '\\' in name or ':' in name or '\x00' in name:
        raise ValueError('Unsafe archive path: ' + repr(name))
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ('', '.', '..') or part.endswith((' ', '.'))
                                for part in name.rstrip('/').split('/')):
        raise ValueError('Unsafe archive path: ' + repr(name))
    devices = {'CON', 'PRN', 'AUX', 'NUL'} | {'COM'+str(i) for i in range(1, 10)} | {'LPT'+str(i) for i in range(1, 10)}
    if any(part.split('.')[0].upper() in devices for part in path.parts):
        raise ValueError('Reserved archive path: ' + name)
    return path


def safe_extract(archive, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as package:
        entries = package.infolist()
        if len(entries) > 4000 or sum(item.file_size for item in entries) > 256 * 1024 * 1024:
            raise ValueError('Runtime archive exceeds size limits')
        names = set()
        targets = []
        for item in entries:
            name = relative_path(item.filename)
            key = name.as_posix().casefold()
            if key in names or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Duplicate path or symlink in runtime archive: ' + item.filename)
            names.add(key)
            target = destination.joinpath(*name.parts)
            if not target.resolve().is_relative_to(destination):
                raise ValueError('Runtime archive escapes destination')
            targets.append((item, target))
        for item, target in targets:
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with package.open(item) as source, target.open('xb') as output:
                shutil.copyfileobj(source, output)


def obtain(spec, cache, offline=False):
    cache = Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / spec['filename']
    if target.is_file():
        if digest(target) != spec['sha256']:
            raise ValueError('Archive checksum mismatch: ' + target.name)
        return target
    if offline:
        raise ValueError('Pinned archive is absent from offline cache: ' + target.name)
    request = urllib.request.Request(spec['url'], headers={'User-Agent': 'MoreIterators-runtime-builder/1'})
    with tempfile.NamedTemporaryFile(dir=cache, suffix='.download', delete=False) as temporary:
        partial = Path(temporary.name)
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                if not response.url.startswith(('https://www.python.org/', 'https://files.pythonhosted.org/')):
                    raise ValueError('Unexpected runtime download host')
                received = 0
                while chunk := response.read(1024 * 1024):
                    received += len(chunk)
                    if received > 64 * 1024 * 1024:
                        raise ValueError('Runtime download exceeds size limit')
                    temporary.write(chunk)
            temporary.flush()
        except BaseException:
            temporary.close()
            partial.unlink(missing_ok=True)
            raise
    try:
        if digest(partial) != spec['sha256']:
            raise ValueError('Downloaded archive checksum mismatch: ' + target.name)
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)
    return target


def verify_runtime(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text('utf-8'))
    if (manifest.get('schema') != SCHEMA or manifest.get('platform') != 'win_amd64'
            or manifest.get('python', {}).get('version') != PYTHON_VERSION
            or manifest.get('pillow', {}).get('version') != PILLOW_VERSION
            or manifest['python'].get('source') != PYTHON or manifest['pillow'].get('source') != PILLOW
            or manifest['python'].get('executable') != 'python313/python.exe'
            or manifest['python'].get('windowlessExecutable') != 'python313/pythonw.exe'):
        raise ValueError('Unexpected runtime manifest or dependency pins')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('Missing runtime file inventory')
    actual = set()
    for path in directory.rglob('*'):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('Runtime must not contain links')
        if path.is_file() and path.relative_to(directory).as_posix() != 'manifest.json':
            actual.add(path.relative_to(directory).as_posix())
    if actual != set(files):
        raise ValueError('Runtime file inventory does not match its contents')
    for name, expected in files.items():
        relative_path(name)
        if digest(directory / name) != expected:
            raise ValueError('Runtime file checksum mismatch: ' + name)
    if (directory / 'python313/python313._pth').read_text('utf-8') != PTH:
        raise ValueError('Runtime module path is not isolated')
    if not manifest.get('licenses') or any(name not in files for name in manifest['licenses']):
        raise ValueError('Runtime licenses are missing')
    return manifest


def build(destination, cache, offline=False):
    destination = Path(destination).resolve()
    if destination.exists():
        return verify_runtime(destination)
    archives = [(spec, obtain(spec, cache, offline)) for spec in (PYTHON, PILLOW)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.mi-runtime-', dir=destination.parent) as temporary:
        stage = Path(temporary) / 'runtime'
        python = stage / 'python313'
        safe_extract(archives[0][1], python)
        safe_extract(archives[1][1], python / 'Lib/site-packages')
        (python / 'python313._pth').write_text(PTH, 'utf-8')
        licenses = ['python313/LICENSE.txt'] + sorted(
            path.relative_to(stage).as_posix() for path in (python / 'Lib/site-packages').rglob('*')
            if path.is_file() and ('licenses' in path.parts or path.name.upper().startswith(('LICENSE', 'COPYING'))))
        if len(licenses) < 2 or any(not (stage / name).is_file() for name in licenses):
            raise ValueError('Upstream runtime licenses are missing')
        manifest = {
            'schema': SCHEMA, 'platform': 'win_amd64',
            'python': {'version': PYTHON_VERSION, 'executable': 'python313/python.exe',
                       'windowlessExecutable': 'python313/pythonw.exe', 'source': PYTHON},
            'pillow': {'version': PILLOW_VERSION, 'source': PILLOW},
            'licenses': licenses,
            'files': {path.relative_to(stage).as_posix(): digest(path)
                      for path in sorted(stage.rglob('*')) if path.is_file()},
        }
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + '\n', 'utf-8')
        verify_runtime(stage)
        stage.rename(destination)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'runtime')
    parser.add_argument('--cache', type=Path, default=Path(tempfile.gettempdir()) / 'mi-runtime-downloads')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    manifest = verify_runtime(args.output) if args.verify else build(args.output, args.cache, args.offline)
    print(json.dumps({'runtime': str(args.output.resolve()), 'python': manifest['python']['version'],
                      'pillow': manifest['pillow']['version'], 'files': len(manifest['files'])}))


if __name__ == '__main__':
    main()
