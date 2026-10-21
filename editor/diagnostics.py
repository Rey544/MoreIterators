"""Read-only diagnostics for failures that can occur before the plugin loads."""
from pathlib import Path
import re
import datetime
import traceback
import storage

MAX_LOG_BYTES = 131072

def snapshot():
    candidates = [storage.GAME/'BepInEx/LogOutput.log', storage.GAME/'BepInEx/LogOutput.txt']
    log = next((p for p in candidates if p.is_file()), candidates[0])
    result = dict(available=False, logPath=str(log), modified=None, errors=[], tail='')
    if not log.is_file():
        return result
    with log.open('rb') as stream:
        size=log.stat().st_size
        stream.seek(max(0, size-MAX_LOG_BYTES))
        text=stream.read(MAX_LOG_BYTES).decode('utf-8',errors='replace')
    if size>MAX_LOG_BYTES:
        text=text.partition('\n')[2]
    entries=[]
    current=None
    for line in text.splitlines():
        header=re.match(r'^\[\s*(Error|Fatal|Warning)\s*:\s*([^\]]+)\]',line,re.I)
        if header:
            current=dict(source=header.group(2).strip(),text=line)
            entries.append(current)
        elif re.match(r'^\[\s*[A-Za-z]+\s*:',line):
            current=None
        elif current is not None:
            current['text']+='\n'+line
    result.update(available=True,modified=datetime.datetime.fromtimestamp(log.stat().st_mtime,datetime.timezone.utc).isoformat(),errors=entries[-30:],tail=text,truncated=size>MAX_LOG_BYTES)
    return result

def record_server_error(error, operation):
    directory=storage.archive_root()/'logs'
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'studio-errors.log').open('a',encoding='utf-8') as log:
        log.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+' operation='+operation+'\n')
        log.write(''.join(traceback.format_exception(type(error),error,error.__traceback__)))

def error_payload(error, operation):
    # Human-readable overview is localized by code, while the original exception
    # and stack remain available for maintenance. No submitted project is logged.
    invalid=isinstance(error,(ValueError,KeyError,TypeError))
    code='error.request.invalid' if invalid else 'error.request.io' if isinstance(error,OSError) else 'error.request.internal'
    record_server_error(error,operation)
    return dict(code=code,params=dict(operation=operation),error=str(error),details=str(error))
