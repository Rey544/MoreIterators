




import argparse
import ctypes
import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
SELECTORS = (
    'test_content_asset_cache',
    'test_content_assets',
    'test_standalone_catalog',
    'test_runtime_ownership',
    'test_runtime_boundaries.RuntimeBoundaryTests.test_registry_display_names_share_one_fallback',
    'test_runtime_boundaries.RuntimeBoundaryTests.test_design_path_changes_reload_same_timestamp_assets_and_fall_back',
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--output', required=True)
    parser.add_argument('selectors', nargs='*')
    args = parser.parse_args()
    selectors = args.selectors or SELECTORS
    if any(selector not in SELECTORS for selector in selectors):
        raise ValueError('Only the reviewed asset runtime selectors are allowed')
    if not args.execute:
        print(json.dumps({'selectors': selectors, 'executed': False}, indent=2))
        return 0
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix='mi-reviewed-asset-hosts-')).resolve()
    for key in ('TEMP', 'TMP', 'APPDATA', 'LOCALAPPDATA', 'USERPROFILE', 'MORE_ITERATORS_DATA'):
        target = scratch / key.lower()
        target.mkdir()
        os.environ[key] = str(target)
    tempfile.tempdir = str(scratch / 'temp')
    compiler = (Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe').resolve()
    compiled = set()
    calls = []
    violations = []
    split_command = ctypes.windll.shell32.CommandLineToArgvW
    split_command.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    split_command.restype = ctypes.POINTER(ctypes.c_wchar_p)
    release_command = ctypes.windll.kernel32.LocalFree
    release_command.argtypes = [ctypes.c_void_p]
    release_command.restype = ctypes.c_void_p

    def canonical(path):
        return os.path.normcase(os.path.realpath(os.fsdecode(path)))

    roots = tuple(canonical(path) + os.sep for path in (scratch, output))

    def writable(path):
        if isinstance(path, int):
            return False
        value = canonical(path)
        return any(value == root[:-1] or value.startswith(root) for root in roots)

    def deny(event, value):
        violations.append({'event': event, 'value': str(value)})
        raise PermissionError('Asset runtime check denied ' + event + ': ' + str(value))

    def audit(event, values):
        if event == 'open':
            path, mode, flags = values
            if any(flag in str(mode) for flag in ('w', 'a', 'x', '+')) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                if not writable(path):
                    deny(event, path)
        elif event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.utime', 'os.truncate'):
            if not writable(values[0]):
                deny(event, values[0])
        elif event in ('os.rename', 'os.replace', 'os.link', 'os.symlink'):
            if not all(writable(path) for path in values[:2]):
                deny(event, values[:2])
        elif event in ('os.system', 'os.startfile', 'os.startfile/2', 'os.kill', 'os.killpg', 'socket.connect', 'socket.bind'):
            deny(event, values)
        elif event == 'subprocess.Popen':
            executable, command, cwd, environment = values
            if isinstance(command, str):
                count = ctypes.c_int()
                words = split_command(command, ctypes.byref(count))
                if not words:
                    deny(event, command)
                try:
                    command = [words[index] for index in range(count.value)]
                finally:
                    release_command(words)
            if not isinstance(command, (list, tuple)):
                deny(event, command)
            executable = canonical(executable or command[0])
            if executable == canonical(compiler):
                destinations = [arg[5:] for arg in command if isinstance(arg, str) and arg.lower().startswith('/out:')]
                if len(destinations) != 1 or not writable(destinations[0]) or Path(destinations[0]).suffix.lower() != '.exe':
                    deny(event, command)
                for arg in command[1:]:
                    if arg.startswith(('@', '/addmodule:', '/win32res:', '/win32icon:')):
                        deny(event, arg)
                    if arg.startswith('/') and not arg.lower().startswith(('/out:', '/r:', '/resource:', '/define:', '/nologo', '/utf8output')):
                        deny(event, arg)
                    if not arg.startswith('/') and not Path(arg).is_file():
                        deny(event, arg)
                compiled.add(canonical(destinations[0]))
            elif executable in compiled:
                
                if any(not writable(arg) for arg in command[2:]):
                    deny(event, command)
            else:
                deny(event, command)
            calls.append([str(arg) for arg in command])

    sys.dont_write_bytecode = True
    sys.addaudithook(audit)
    os.chdir(scratch)
    sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
    package = types.ModuleType('tests')
    package.__path__ = [str(ROOT / 'tests')]
    sys.modules['tests'] = package
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(selector) for selector in selectors)
    started = datetime.datetime.now().isoformat()
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    record = dict(started=started, scratch=str(scratch), source=str(ROOT), selectors=selectors,
                  tests=result.testsRun, failures=[(str(test), trace) for test, trace in result.failures],
                  errors=[(str(test), trace) for test, trace in result.errors],
                  skipped=[(str(test), reason) for test, reason in result.skipped],
                  calls=calls, violations=violations, passed=result.wasSuccessful() and not violations,
                  scope='Python writes restricted; fixed reviewed native fixture hosts, not OS sandboxed')
    (output / 'asset-runtime-results.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), 'utf-8')
    print('RESULT ' + str(output / 'asset-runtime-results.json'))
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
