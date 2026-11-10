import http.client
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'editor'))
import server


class StudioCaptureTests(unittest.TestCase):
    def test_real_capture_coroutine_only_runs_for_live_consumers(self):
        compiler=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.is_file():self.skipTest('C# compiler required')
        with tempfile.TemporaryDirectory(prefix='mi-capture-check-') as folder:
            exe=Path(folder)/'capture.exe'
            result=subprocess.run([str(compiler),'/nologo','/utf8output','/out:'+str(exe),str(ROOT/'src/StudioRuntime.cs'),str(ROOT/'tests/studio_capture_check.cs')],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=subprocess.run([str(exe),str(Path(folder)/'runtime')],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('actual coroutine passed',result.stdout)

    def test_actual_frame_route_requests_capture_even_before_first_image(self):
        with tempfile.TemporaryDirectory(prefix='mi-frame-http-') as folder:
            runtime=Path(folder)/'runtime';runtime.mkdir()
            project=Path(folder)/'project.json';project.write_bytes(b'unchanged project')
            httpd=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);port=httpd.server_address[1]
            thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
            def get(path):
                client=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
                try:
                    client.request('GET',path);response=client.getresponse();return response.status,response.read()
                finally:client.close()
            try:
                with patch.object(server,'PORT',port),patch.object(server,'DESIGNS',runtime),patch.object(server,'FRAME_REQUESTS',{}):
                    self.assertEqual(get('/api/status')[0],200)
                    marker=runtime/'studio-frame-request';self.assertFalse(marker.exists())
                    self.assertEqual(get('/api/frame.png')[0],404);self.assertTrue(marker.is_file())
                    (runtime/'studio-frame.png').write_bytes(b'frame')
                    before=marker.stat().st_mtime_ns
                    self.assertEqual(get('/api/frame.png'),(200,b'frame'))
                    self.assertEqual(marker.stat().st_mtime_ns,before)
                    with patch.object(server.time,'monotonic',return_value=server.FRAME_REQUESTS[marker]+1.1):
                        os.utime(marker,(0,0));self.assertEqual(get('/api/frame.png')[0],200)
                    self.assertGreater(marker.stat().st_mtime,0)
                    self.assertEqual(project.read_bytes(),b'unchanged project')
                    self.assertEqual({p.name for p in runtime.iterdir()},{'studio-frame-request','studio-frame.png'})
            finally:httpd.shutdown();httpd.server_close();thread.join(timeout=2)


if __name__=='__main__':unittest.main()
