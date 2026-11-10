
from pathlib import Path
import os
import subprocess
import webbrowser
import localization

ROOT=Path(__file__).resolve().parent


def _shell(arguments):
    helper=ROOT/'StudioShell.exe'
    if not helper.is_file():
        raise FileNotFoundError(localization.text('startup.shell_missing'))
    try:
        result=subprocess.run([str(helper)]+arguments,cwd=ROOT,stdin=subprocess.DEVNULL,
            capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=15)
    except (OSError,subprocess.TimeoutExpired) as error:
        raise OSError(localization.text('startup.external_failed')) from error
    if result.returncode:
        detail=result.stderr.decode('utf-8',errors='replace').strip()
        raise OSError(localization.text('startup.external_failed')) from RuntimeError(detail)


def open_url(url):
    if os.name=='nt':
        _shell(['url',url])
        return True
    return webbrowser.open(url)


def open_rained(executable,room):
    executable=Path(executable).resolve();room=Path(room).resolve()
    if os.name=='nt':
        _shell(['rained',str(executable),str(room)])
    else:
        subprocess.Popen([str(executable),str(room)],cwd=executable.parent,start_new_session=True)
