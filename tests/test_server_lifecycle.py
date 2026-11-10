from pathlib import Path
from http.server import BaseHTTPRequestHandler
from http.client import HTTPConnection
from unittest.mock import patch
import ctypes
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

EDITOR = Path(__file__).resolve().parents[1] / 'editor'
sys.path.insert(0, str(EDITOR))
import server_lifecycle as lifecycle


class FakeOwner:
    pid = 123
    def __init__(self): self.done = threading.Event()
    def exited(self, timeout=0): return self.done.wait(timeout)
    def require_alive(self):
        if self.exited(): raise lifecycle.GameClosed()


class DrainTests(unittest.TestCase):
    def test_owned_error_dialog_releases_launcher_when_game_exits(self):
        owner=FakeOwner();shown=threading.Event();dismiss=threading.Event()
        def show():shown.set();dismiss.wait(4)
        launcher=threading.Thread(target=lambda:lifecycle.dialog_until_exit(owner,show));launcher.start()
        try:
            self.assertTrue(shown.wait(2));owner.done.set();launcher.join(1)
            self.assertFalse(launcher.is_alive())
        finally:dismiss.set();launcher.join(2)

    def test_shutdown_cancels_owned_interaction_before_drain(self):
        owner=FakeOwner();cancelled=threading.Event()
        server=lifecycle.EditorServer(('127.0.0.1',0),BaseHTTPRequestHandler,owner,on_close=cancelled.set)
        thread=threading.Thread(target=server.run);thread.start()
        owner.done.set();thread.join(2)
        self.assertTrue(cancelled.is_set());self.assertFalse(thread.is_alive())

    def test_shutdown_finishes_accepted_save_and_rejects_new_save(self):
        owner=FakeOwner();entered=threading.Event();release=threading.Event();saved=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def reply(self, status, value):
                payload=json.dumps(value).encode();self.send_response(status)
                self.send_header('Content-Length', str(len(payload)));self.end_headers();self.wfile.write(payload)
            @lifecycle.request
            def do_POST(self):
                entered.set();release.wait(5);saved.append('complete');self.reply(200, {'ok': True})
            @lifecycle.request
            def do_GET(self): self.reply(200, {'closing': self.server.closing})
        http=lifecycle.EditorServer(('127.0.0.1',0),Handler,owner)
        thread=threading.Thread(target=http.run);thread.start()
        result=[]
        def send(method):
            conn=HTTPConnection('127.0.0.1',http.server_address[1],timeout=4)
            try:
                conn.request(method,'/save');response=conn.getresponse();response.read();return response.status
            finally: conn.close()
        client=threading.Thread(target=lambda: result.append(send('POST')));client.start()
        try:
            self.assertTrue(entered.wait(2));owner.done.set()
            deadline=time.monotonic()+2
            while not http.closing and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(http.closing);self.assertTrue(thread.is_alive())
            self.assertEqual(send('POST'),503);self.assertEqual(saved,[])
            release.set();client.join(3);thread.join(3)
            self.assertEqual(result,[200]);self.assertEqual(saved,['complete']);self.assertFalse(thread.is_alive())
        finally:
            release.set();owner.done.set();client.join(5);thread.join(5)

    def test_idle_connection_does_not_hold_shutdown_forever(self):
        owner=FakeOwner()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
        http=lifecycle.EditorServer(('127.0.0.1',0),Handler,owner);http.request_timeout=.2
        thread=threading.Thread(target=http.run);thread.start()
        connection=socket.create_connection(http.server_address)
        try:
            time.sleep(.1);owner.done.set();thread.join(3);self.assertFalse(thread.is_alive())
        finally: connection.close();owner.done.set();thread.join(3)

    def test_request_failure_releases_drain_count(self):
        server=lifecycle.EditorServer(('127.0.0.1',0),BaseHTTPRequestHandler)
        try:
            with self.assertRaisesRegex(RuntimeError,'injected'):
                with server.request_scope() as accepted:
                    self.assertTrue(accepted);raise RuntimeError('injected')
            self.assertEqual(server.active,0)
        finally: server.server_close()


@unittest.skipUnless(os.name=='nt','Windows game process handle integration')
class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.children=[];self.addCleanup(self.stop_children)
        game=self.root/'game';game.mkdir();(game/'RainWorld.exe').touch()
        data=self.root/'data';data.mkdir()
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
        (data/'config.json').write_text(json.dumps({'gameRoot':str(game),'studioPort':self.port}),'utf-8')
        self.env=dict(os.environ,MORE_ITERATORS_DATA=str(data));self.data=data

    def stop_children(self):
        for child in reversed(self.children):
            if child.poll() is None: child.terminate()
            child.wait(5)
            if child.stdin: child.stdin.close()

    def spawn(self,args):
        child=subprocess.Popen(args,env=self.env,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        self.children.append(child);return child

    def owner(self):
        from ctypes import wintypes
        child=self.spawn([sys.executable,'-B','-c','import sys; sys.stdin.buffer.read(1)'])
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
        times=[wintypes.FILETIME() for _ in range(4)]
        self.assertTrue(api.GetProcessTimes(int(child._handle),*(ctypes.byref(v) for v in times)))
        started=times[0].dwLowDateTime|(times[0].dwHighDateTime<<32)
        return child,started

    def health(self):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=.4)
        try:
            conn.request('GET','/api/health');reply=conn.getresponse();return json.loads(reply.read())
        except (OSError,http.client.HTTPException):return None
        finally:conn.close()

    def ready(self):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            value=self.health()
            if value:return value
            time.sleep(.05)
        self.fail('Server did not start')

    def test_real_server_stops_after_exact_owner_exits(self):
        owner,started=self.owner()
        child=self.spawn([sys.executable,'-B',str(EDITOR/'server.py'),'--game-pid',str(owner.pid),'--game-start',str(started)])
        self.assertEqual(self.ready()['pid'],child.pid)
        owner.stdin.close();owner.wait(5);self.assertEqual(child.wait(12),0);self.assertIsNone(self.health())
        events=[json.loads(x)['event'] for x in (self.data/'archive/logs/server-lifecycle.log').read_text('utf-8').splitlines()]
        self.assertEqual(events,['server-started','game-exited','server-stopped'])

    def test_existing_desktop_server_is_not_taken_over(self):
        desktop=self.spawn([sys.executable,'-B',str(EDITOR/'server.py')]);self.ready()
        owner,started=self.owner()
        launcher=self.spawn([sys.executable,'-B',str(EDITOR/'studio_launcher.py'),'--no-browser',
            '--game-pid',str(owner.pid),'--game-start',str(started)])
        self.assertEqual(launcher.wait(8),0)
        owner.stdin.close();owner.wait(5);time.sleep(.4)
        self.assertIsNone(desktop.poll());self.assertEqual(self.health()['pid'],desktop.pid)

    def test_pid_with_wrong_creation_time_cannot_own_server(self):
        owner,started=self.owner()
        child=self.spawn([sys.executable,'-B',str(EDITOR/'server.py'),'--game-pid',str(owner.pid),'--game-start',str(started+1)])
        self.assertEqual(child.wait(8),0);self.assertIsNone(self.health())
        self.assertFalse((self.data/'projects').exists())

    def test_launcher_does_not_start_server_after_owner_exit(self):
        owner,started=self.owner();owner.stdin.close();owner.wait(5)
        child=self.spawn([sys.executable,'-B',str(EDITOR/'studio_launcher.py'),'--no-browser',
            '--game-pid',str(owner.pid),'--game-start',str(started)])
        self.assertEqual(child.wait(8),0);self.assertIsNone(self.health())
        self.assertFalse((self.data/'projects').exists())

    def test_game_exit_interrupts_a_wait_for_another_launcher_lock(self):
        import msvcrt
        owner,started=self.owner()
        file=self.data/'archive/logs/studio-start.lock';file.parent.mkdir(parents=True)
        with file.open('w+b') as lock:
            lock.write(b'0');lock.flush();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            try:
                child=self.spawn([sys.executable,'-B',str(EDITOR/'studio_launcher.py'),'--no-browser',
                    '--game-pid',str(owner.pid),'--game-start',str(started)])
                time.sleep(.5);self.assertIsNone(child.poll());owner.stdin.close();owner.wait(5)
                self.assertEqual(child.wait(3),0);self.assertIsNone(self.health())
            finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

    def test_game_owned_launcher_starts_owned_server(self):
        owner,started=self.owner()
        child=self.spawn([sys.executable,'-B',str(EDITOR/'studio_launcher.py'),'--no-browser',
            '--game-pid',str(owner.pid),'--game-start',str(started)])
        self.assertEqual(child.wait(8),0);self.ready()
        owner.stdin.close();owner.wait(5)
        deadline=time.monotonic()+12
        while self.health() and time.monotonic()<deadline:time.sleep(.1)
        self.assertIsNone(self.health())
        log=self.data/'archive/logs/server-lifecycle.log'
        self.assertIn('server-stopped',log.read_text('utf-8'))


if __name__=='__main__':unittest.main()
