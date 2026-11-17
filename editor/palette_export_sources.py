from pathlib import Path
import hashlib
import re


REFERENCE = re.compile(r'palettes/palette(\d{1,7})\.png')


def _linked(path):
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def output_locations(relative, enabled_roots):
    match = REFERENCE.fullmatch(relative) if isinstance(relative, str) else None
    if match is None or int(match[1]) > 1000000:
        return []
    filename = 'OutputPalettes/palette' + match[1] + '.png'
    result, seen = [], set()
    for candidate in enabled_roots:
        root = Path(candidate).absolute()
        if _linked(root):
            raise ValueError('Saved palette folders cannot be links.')
        key = root.resolve()
        if key not in seen:
            result.append((root, filename))
            seen.add(key)
    return result


def saved_files(index, enabled_roots):
    if type(index) is not int or not 0 <= index <= 1000000:
        raise ValueError('Palette number is invalid.')
    result, seen = [], set()
    for root, relative in output_locations('palettes/palette' + str(index) + '.png', enabled_roots):
        path = root
        for name in relative.split('/'):
            if not path.is_dir():
                path = path / name
                continue
            matches = [item for item in path.iterdir() if item.name.casefold() == name.casefold()]
            if len(matches) > 1:
                raise ValueError('Saved palette filenames differ only in letter case.')
            path = matches[0] if matches else path / name
            if _linked(path):
                raise ValueError('Saved palette files cannot be links.')
        resolved = path.resolve()
        if not resolved.is_relative_to(root.resolve()):
            raise ValueError('Saved palettes must remain inside their source folder.')
        if path.is_file() and resolved not in seen:
            result.append(path)
            seen.add(resolved)
    return result


def is_saved_palette(path, index, enabled_roots):
    source = Path(path).resolve()
    return any(candidate.resolve() == source for candidate in saved_files(index, enabled_roots))


def choose(index, enabled_roots, preferred=None, review=False):
    saved = saved_files(index, enabled_roots)
    if not saved:
        return preferred
    candidates = ([Path(preferred)] if preferred is not None else []) + saved
    versions = {}
    for path in candidates:
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('Saved palette file is too large.')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        versions.setdefault(digest, path)
    if len(versions) > 1 and not review:
        raise ValueError('Choose a version for palette' + str(index) + '.png before exporting.')
    return next(iter(versions.values()))
