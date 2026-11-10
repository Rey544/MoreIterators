
from contextlib import contextmanager
from functools import wraps
from http.server import ThreadingHTTPServer
import json
import os
import threading
import time


class GameClosed(RuntimeError):
    pass


class GameProcess:
    def __init__(self, pid, started):
        if os.name != 'nt':
            raise ValueError('Game process ownership is only available on Windows.')
        import ctypes
        from ctypes import wintypes
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self.api.GetProcessTimes.restype = wintypes.BOOL
        self.api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.api.WaitForSingleObject.restype = wintypes.DWORD
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.pid = int(pid)
        self.started = int(started)
        if self.pid <= 0 or self.started <= 0:
            raise ValueError('Invalid game process identity.')
        self.handle = self.api.OpenProcess(0x00100000 | 0x1000, False, self.pid)
        if not self.handle:
            code = ctypes.get_last_error()
            if code == 87:
                raise GameClosed('The game has already exited.')
            raise ctypes.WinError(code)
        try:
            values = [wintypes.FILETIME() for _ in range(4)]
            if not self.api.GetProcessTimes(self.handle, *(ctypes.byref(v) for v in values)):
                raise ctypes.WinError(ctypes.get_last_error())
            actual = values[0].dwLowDateTime | (values[0].dwHighDateTime << 32)
            if actual != self.started or self.exited():
                raise GameClosed('The original game process is no longer running.')
        except BaseException:
            self.close()
            raise

    def exited(self, timeout=0):
        result = self.api.WaitForSingleObject(self.handle, int(timeout * 1000))
        if result == 0:
            return True
        if result == 258:
            return False
        import ctypes
        raise ctypes.WinError(ctypes.get_last_error())

    def require_alive(self):
        if self.exited():
            raise GameClosed('The game has already exited.')

    def arguments(self):
        return ['--game-pid', str(self.pid), '--game-start', str(self.started)]

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def add_arguments(parser):
    parser.add_argument('--game-pid', type=int)
    parser.add_argument('--game-start', type=int)


@contextmanager
def owner_from(args):
    if args.game_pid is None and args.game_start is None:
        yield None
        return
    if args.game_pid is None or args.game_start is None:
        raise ValueError('Incomplete game process identity.')
    owner = GameProcess(args.game_pid, args.game_start)
    try:
        yield owner
    finally:
        owner.close()


def record(path, event, **details):
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as out:
            out.write(json.dumps(dict(time=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                pid=os.getpid(), event=event, **details), ensure_ascii=False) + '\n')
    except OSError:
        
        pass


class EditorServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True
    request_timeout = 10

    def __init__(self, address, handler, owner=None, log_path=None, on_close=None):
        self.owner = owner
        self.log_path = log_path
        self.on_close = on_close
        self.closing = False
        self.active = 0
        self.condition = threading.Condition()
        self.stopped = threading.Event()
        super().__init__(address, handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(self.request_timeout)
        return connection, address

    @contextmanager
    def request_scope(self):
        with self.condition:
            accepted = not self.closing
            if accepted:
                self.active += 1
        try:
            yield accepted
        finally:
            if accepted:
                with self.condition:
                    self.active -= 1
                    self.condition.notify_all()

    def watch_game(self):
        try:
            while not self.stopped.is_set():
                if self.owner.exited(.25):
                    self.drain('game-exited', gamePid=self.owner.pid)
                    return
        except Exception as error:
            self.drain('owner-watch-error', error=str(error))

    def drain(self, event, **details):
        with self.condition:
            self.closing = True
            record(self.log_path, event, activeRequests=self.active, **details)
        if self.on_close:
            try:self.on_close()
            except Exception as error:record(self.log_path, 'cancel-interaction-error', error=str(error))
        with self.condition:
            while self.active and not self.stopped.is_set():
                self.condition.wait(.25)
        if not self.stopped.is_set():
            self.shutdown()

    def run(self):
        watcher = None
        try:
            if self.owner:
                self.owner.require_alive()
                watcher = threading.Thread(target=self.watch_game, name='MI game lifetime', daemon=True)
                watcher.start()
            record(self.log_path, 'server-started', gamePid=self.owner.pid if self.owner else None)
            self.serve_forever(poll_interval=.1)
        finally:
            self.stopped.set()
            with self.condition:
                self.closing = True
                self.condition.notify_all()
            if self.on_close:
                try:self.on_close()
                except Exception as error:record(self.log_path, 'cancel-interaction-error', error=str(error))
            self.server_close()
            if watcher:
                watcher.join(1)
            record(self.log_path, 'server-stopped', activeRequests=self.active)


def dialog_until_exit(owner, show):
    
    if owner is None:
        show()
        return
    owner.require_alive()
    finished=threading.Event()
    def display():
        try:show()
        finally:finished.set()
    threading.Thread(target=display, name='MI startup error', daemon=True).start()
    while not finished.wait(.2):
        if owner.exited():return


def request(handler):
    @wraps(handler)
    def call(self, *args, **kwargs):
        scope = getattr(self.server, 'request_scope', None)
        if scope is None or self.path == '/api/health':
            return handler(self, *args, **kwargs)
        with scope() as accepted:
            if not accepted:
                import default_text
                return self.reply(503, {'error': default_text.text('startup.game_closed')})
            return handler(self, *args, **kwargs)
    return call
