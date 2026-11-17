"""Read-only diagnostics for failures that can occur before the plugin loads."""
from pathlib import Path
import re
import datetime
import traceback
import os
import stat
import io
import json
import sys
import threading
import urllib.parse
import hashlib
from types import SimpleNamespace
import storage
import install_picker

MAX_LOG_BYTES = 131072
MI_LOG_SOURCES = frozenset(('更多迭代器', 'More Iterators', 'MoreIterators', 'moreiterators.core'))
_VERSION_FILE = Path(__file__).resolve().parent.parent/'version.json'
_SERVER_FILE = Path(__file__).resolve().with_name('server.py')
_LOG_LOCK = threading.Lock()

def disk_version():
    try:
        value = json.loads(_VERSION_FILE.read_text('utf-8-sig')).get('version')
        return value if isinstance(value, str) and re.fullmatch(r'[0-9][0-9A-Za-z.+-]{0,63}', value) else 'unknown'
    except (OSError, ValueError, AttributeError, TypeError):
        return 'unknown'

def disk_server_sha256():
    try:
        return hashlib.sha256(_SERVER_FILE.read_bytes()).hexdigest()
    except OSError:
        return 'unknown'

_RUNTIME_VERSION = disk_version()
_RUNTIME_SERVER_SHA256 = disk_server_sha256()
_RUNTIME_STARTED = datetime.datetime.now(datetime.timezone.utc).isoformat()
_RUNTIME_PID = os.getpid()

def runtime_info():
    return dict(version=_RUNTIME_VERSION, serverSha256=_RUNTIME_SERVER_SHA256, startedAt=_RUNTIME_STARTED, pid=_RUNTIME_PID,
                pythonVersion=sys.version.split()[0], frontendVersion='unknown', browserVersion='unknown')

def request_path(value):
    try:
        path = urllib.parse.urlsplit(str(value)).path
        return (''.join(c for c in path if ord(c) >= 32 and ord(c) != 127).rstrip('/') or '/')[:2048]
    except ValueError:
        return '/api/invalid-path'

def raw_request_path(value):
    try:
        value = ''.join(c for c in str(value) if ord(c) >= 32 and ord(c) != 127)
        parts = urllib.parse.urlsplit(value)
        path = parts.path
        if '?' in value.split('#', 1)[0]:
            query = '&'.join(part.partition('=')[0]+('=[redacted]' if '=' in part else '') for part in parts.query.split('&'))
            path += '?'+query
        return path[:2048]
    except ValueError:
        return '/api/invalid-path'

def _record(event, **fields):
    return dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(), event=event,
                runtime=runtime_info(), diskVersion=disk_version(), **fields)

def _append(record):
    try:
        line = json.dumps(record, ensure_ascii=False)+'\n'
        with _LOG_LOCK:
            directory = storage.archive_root()/'logs'
            directory.mkdir(parents=True, exist_ok=True)
            with (directory/'studio-errors.log').open('a', encoding='utf-8') as log:
                log.write(line)
        return True
    except Exception:
        return False

def record_http_failure(method, path, status):
    try:
        raw_path = raw_request_path(path)
        path = request_path(path)
        if not path.startswith('/api/') or status < 400:return False
        method = method if isinstance(method, str) and re.fullmatch(r'[A-Z]{1,16}', method) else 'UNKNOWN'
        return _append(_record('http-failure', method=method, path=path, rawPath=raw_path, normalizedPath=path, status=int(status)))
    except Exception:
        return False

class _Download:
    def __init__(self, header, stream):
        self.header = io.BytesIO(header)
        self.stream = stream

    def read(self, size=-1):
        chunk = self.header.read(size)
        if self.stream is None or size >= 0 and len(chunk) == size:return chunk
        return chunk+self.stream.read(-1 if size < 0 else size-len(chunk))

    def close(self):
        self.header.close()
        if self.stream is not None:self.stream.close()

    def __enter__(self):return self
    def __exit__(self, *args):self.close()

def _download(stream, name, details=None):
    header = (json.dumps(_record('diagnostic-download', source='editor' if name == 'studio-errors.log' else 'game',
                                logAvailable=details is not None and details.st_size > 0), ensure_ascii=False)+'\n').encode('utf-8')
    size = details.st_size if details is not None else 0
    modified = details.st_mtime if details is not None else datetime.datetime.now(datetime.timezone.utc).timestamp()
    return _Download(header, stream), name, SimpleNamespace(st_size=len(header)+size, st_mtime=modified)

class DiagnosticLogError(ValueError):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.code = code
        self.status = status

def _log_source(source):
    if source == 'editor':
        return storage.archive_root()/'logs/studio-errors.log', 'studio-errors.log'
    if source == 'game':
        if not Path(storage.GAME).is_absolute():
            return None, 'LogOutput.txt'
        candidates = [storage.GAME/'BepInEx/LogOutput.log', storage.GAME/'BepInEx/LogOutput.txt']
        return next((p for p in candidates if p.is_file()), candidates[0]), 'LogOutput.txt'
    raise DiagnosticLogError('diagnostics.invalidSource')

def open_download(source='game', include_runtime=False):
    path, name = _log_source(source)
    missing = 'diagnostics.editorUnavailable' if source == 'editor' else 'diagnostics.unavailable'
    if path is None:
        raise DiagnosticLogError(missing, 404)
    if path.is_symlink():
        raise DiagnosticLogError('diagnostics.readFailed', 400)
    try:
        stream = path.open('rb')
    except FileNotFoundError:
        if source == 'editor' and include_runtime:return _download(None, name)
        raise DiagnosticLogError(missing, 404) from None
    try:
        details = os.fstat(stream.fileno())
        if not stat.S_ISREG(details.st_mode):
            raise DiagnosticLogError('diagnostics.readFailed', 400)
        if not details.st_size:
            if source == 'editor' and include_runtime:return _download(stream, name, details)
            raise DiagnosticLogError(missing, 404)
        if include_runtime:return _download(stream, name, details)
        return stream, name, details
    except BaseException:
        stream.close()
        raise

def _is_mi_issue(source, message):
    marker=re.match(r'^\[MI-DIAG\]\s+(?:session=\S+\s+)?code=(\S+)',message)
    if marker and marker.group(1) in ('EXTERNAL-LOG','EXTERNAL-UNITY'):
        return False
    if source in MI_LOG_SOURCES:
        return True
    
    
    record=re.match(r'^\[MI-DIAG\] session=([0-9a-f]{12}) code=MI[-_][A-Z0-9_-]+ node=\S+ issue=\1-[1-9][0-9]* source=MI severity=(?:Error|Warning|Fatal) count=[1-9][0-9]* kind=\S+(?: |$)',message)
    return bool(record) or message == '[MI-DIAG] code=MI-DIAGNOSTIC-UI node=notification'

def snapshot(source='game'):
    log, name = _log_source(source)
    result = dict(available=False, logPath=str(log) if log is not None else '', downloadName=name, modified=None, errors=[], tail='', truncated=False)
    try:
        stream, name, details = open_download(source)
    except DiagnosticLogError as error:
        if error.status == 404:
            if source == 'editor':
                result.update(available=True, logAvailable=False, runtime=runtime_info(),
                              tail=json.dumps(_record('diagnostic-download', source='editor', logAvailable=False), ensure_ascii=False)+'\n')
            return result
        raise
    with stream:
        size=details.st_size
        stream.seek(max(0, size-MAX_LOG_BYTES))
        text=stream.read(min(size,MAX_LOG_BYTES)).decode('utf-8',errors='replace')
    if size>MAX_LOG_BYTES:
        boundary=text.find('\n')
        if boundary>=0:text=text[boundary+1:]
    result.update(available=True,modified=datetime.datetime.fromtimestamp(details.st_mtime,datetime.timezone.utc).isoformat(),tail=text,truncated=size>MAX_LOG_BYTES)
    if source == 'editor':
        return result
    entries=[]
    current=None
    for line in text.splitlines():
        header=re.match(r'^\[\s*(Error|Fatal|Warning)\s*:\s*([^\]]+)\]\s*(.*)$',line,re.I)
        if header:
            source=header.group(2).strip()
            current=dict(source=source,text=line) if _is_mi_issue(source,header.group(3)) else None
            if current is not None:entries.append(current)
        elif re.match(r'^\[\s*[A-Za-z]+\s*:',line):
            current=None
        elif current is not None:
            current['text']+='\n'+line
    result['errors']=entries[-30:]
    return result

def record_server_error(error, operation):
    try:
        trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        trace = re.sub(r'(?i)([a-z]:[\\/](?:users|documents and settings)[\\/])[^\\/\s\"\']+', r'\1<user>', trace)
        return _append(_record('server-error', path=request_path(operation), exception=type(error).__name__, traceback=trace))
    except Exception:
        return False

def error_payload(error, operation):
    operation=request_path(operation)
    invalid=isinstance(error,(ValueError,KeyError,TypeError))
    code='error.request.invalid' if invalid else 'error.request.io' if isinstance(error,OSError) else 'error.request.internal'
    if isinstance(error, install_picker.PickerError):code=error.code
    import room_source_choices
    if isinstance(error,room_source_choices.RoomChoiceError):code=error.code
    import room_bindings
    params=dict(operation=operation)
    if isinstance(error,room_bindings.RoomBindingError):code=error.code;params.update(error.params)
    import export_file_import
    if isinstance(error,export_file_import.ImportFileError):code=error.code;params.update(error.params)
    record_server_error(error,operation)
    return dict(code=code,params=params,error=str(error),details=str(error))
