"""Start the independent local editor before opening a requested studio page."""
from pathlib import Path
from contextlib import contextmanager
import argparse,json,os,subprocess,sys,time,traceback,urllib.error,urllib.parse,urllib.request,webbrowser
import localization
from localization import text
storage_error=None
try:
    import storage
except Exception as error:
    storage=None
    storage_error=error
ROOT=Path(__file__).resolve().parent
PORT=storage.STUDIO_PORT if storage is not None else 18747
BASE='http://127.0.0.1:'+str(PORT)
PAGES={'appearance':'/','dialogue':'/dialogue','pearls':'/pearls','broadcasts':'/broadcasts'}
HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}))

def page_url(page,project=''):
    path=PAGES[page]
    if project:path+='?'+urllib.parse.urlencode({'project':storage.valid_id(project)})
    return BASE+path

def online():
    try:
        with HTTP.open(BASE+'/api/health',timeout=.7) as response:data=json.load(response)
    except urllib.error.HTTPError as error:raise RuntimeError(text('startup.wrong_service',port=PORT)) from error
    except (urllib.error.URLError,TimeoutError,OSError):return False
    except (ValueError,TypeError) as error:raise RuntimeError(text('startup.invalid_status',port=PORT)) from error
    if not isinstance(data,dict):raise RuntimeError(text('startup.invalid_status',port=PORT))
    if data.get('service')!='more-iterators-studio' or data.get('protocol')!=1:raise RuntimeError(text('startup.port_busy',port=PORT))
    if Path(data.get('dataDirectory','')).resolve()!=storage.DATA.resolve() or Path(data.get('editorDirectory','')).resolve()!=ROOT:
        raise RuntimeError(text('startup.other_directory',port=PORT))
    return True

@contextmanager
def startup_lock():
    logs=storage.archive_root()/'logs';logs.mkdir(parents=True,exist_ok=True)
    with (logs/'studio-start.lock').open('a+b') as lock:
        lock.seek(0,2)
        if lock.tell()==0:lock.write(b'0');lock.flush()
        deadline=time.monotonic()+35
        if os.name=='nt':
            import msvcrt
            while True:
                try:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);break
                except OSError:
                    if time.monotonic()>deadline:raise RuntimeError(text('startup.lock_timeout'))
                    time.sleep(.15)
            try:yield
            finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
            try:yield
            finally:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)

def ensure_server():
    if online():return
    with startup_lock():
        if online():return
        log_path=storage.archive_root()/'logs/server-startup.log'
        flags=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0
        with log_path.open('ab') as log:
            child=subprocess.Popen([sys.executable,'-B',str(ROOT/'server.py')],cwd=ROOT,
                stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=flags,start_new_session=os.name!='nt')
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if online():return
            if child.poll() is not None:raise RuntimeError(text('startup.failed',path=log_path))
            time.sleep(.15)
        raise RuntimeError(text('startup.timeout',path=log_path))

def register_game_launcher():
    config=storage.GAME/'BepInEx/config/moreiterators.paths.json'
    if not config.parent.is_dir():return
    with startup_lock():
        # The earlier startup check may already be stale. Never replace a game's
        # registration with paths from a different editor occupying this port.
        if not online():raise RuntimeError(text('startup.failed',path=storage.archive_root()/'logs/server-startup.log'))
        value=json.loads(config.read_text('utf-8-sig')) if config.exists() else {}
        if not isinstance(value,dict):raise ValueError(text('startup.config'))
        value.update(editorDirectory=str(ROOT),pythonExecutable=sys.executable,runtimeDirectory=str(storage.RUNTIME.resolve()))
        temporary=config.with_name(config.name+'.'+str(os.getpid())+'.tmp')
        temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        os.replace(temporary,config)

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--page',choices=PAGES,default='appearance')
    parser.add_argument('--project',default='')
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--lang',choices=['zh-CN','en'])
    args=parser.parse_args(argv)
    if args.lang:localization.set_language(args.lang)
    if storage_error is not None:raise RuntimeError(text('startup.config')) from storage_error
    url=page_url(args.page,args.project)
    if args.lang:url+=('&' if '?' in url else '?')+urllib.parse.urlencode({'lang':args.lang})
    ensure_server();register_game_launcher()
    if not args.no_browser and not webbrowser.open(url):raise RuntimeError(text('startup.browser',url=url))
    return url

def run():
    try:
        url=main()
        if sys.stdout:print(url)
        return 0
    except Exception as error:
        logs=(storage.archive_root() if storage is not None else Path(os.environ.get('MORE_ITERATORS_DATA',str(Path.home()/'.moreiterators'))))/'logs'
        log_path=logs/'studio-launch-error.log'
        try:
            logs.mkdir(parents=True,exist_ok=True)
            with log_path.open('a',encoding='utf-8') as log:
                log.write(time.strftime('%Y-%m-%d %H:%M:%S')+'\n'+traceback.format_exc()+'\n')
            message=str(error)+'\n\n'+text('startup.details',path=log_path)
        except OSError as log_error:
            message=str(error)+'\n\n'+text('startup.log_failed',detail=log_error)
        if '--no-browser' not in sys.argv and os.name=='nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,message,text('startup.title'),0x10)
        elif sys.stderr:print(message,file=sys.stderr)
        return 1

if __name__=='__main__':sys.exit(run())
