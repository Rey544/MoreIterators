from pathlib import Path
import ast
import datetime
import json
import os
import subprocess
import tempfile
import unittest
try:
    from .test_media_review import declaration
except ImportError:
    from test_media_review import declaration

ROOT = Path(__file__).resolve().parents[1]


class CreatorLiveStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='mi-live-status-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        tree=ast.parse((ROOT/'editor/server.py').read_text('utf-8'))
        names={'live_snapshot','file_age','creator_status'}
        selected=ast.Module(body=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names],type_ignores=[])
        self.globals={'DESIGNS':self.root,'LIVE_CACHE':{},'json':json,'datetime':datetime}
        exec(compile(selected,str(ROOT/'editor/server.py'),'exec'),self.globals)
        self.now=datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(milliseconds=200)

    def write(self,name,project='sample',room='TEST_AI',age=0,**extra):
        value=dict(project=project,room=room,time=(self.now-datetime.timedelta(seconds=age)).isoformat(),**extra)
        path=self.root/'creator'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value),'utf-8')
        return path,value

    def status(self):
        return self.globals['creator_status']()

    def test_fresh_matching_identity_merges_without_mutating_cache(self):
        path,status=self.write('status.json',dialogueLine='作者原文',revision=7)
        self.write('heartbeat.json',paused=True,panel=False)
        (self.root/'studio-frame.png').write_bytes(b'fixture')
        merged=self.status()
        self.assertEqual(merged['dialogueLine'],'作者原文')
        self.assertEqual(merged['revision'],7)
        self.assertTrue(merged['online'] and merged['frameOnline'] and merged['paused'])
        self.assertNotIn('paused',self.globals['LIVE_CACHE'][path])
        self.assertEqual(json.loads(path.read_text('utf-8')),status)

    def test_different_project_or_room_never_carries_old_dialogue(self):
        self.write('status.json',dialogueLine='previous',revision=99)
        for project,room in [('other','TEST_AI'),('sample','TEST_ENTRY')]:
            with self.subTest(project=project,room=room):
                self.write('heartbeat.json',project=project,room=room,paused=False)
                merged=self.status()
                self.assertEqual((merged['project'],merged['room']),(project,room))
                self.assertNotIn('dialogueLine',merged)
                self.assertNotIn('revision',merged)
                self.assertTrue(merged['online'])

    def test_stale_status_is_not_refreshed_by_new_matching_heartbeat(self):
        self.write('status.json',age=30,dialogueLine='stale')
        self.write('heartbeat.json',paused=True)
        self.assertNotIn('dialogueLine',self.status())
        self.assertTrue(self.status()['online'])

    def test_stale_heartbeat_does_not_replace_fresh_status(self):
        self.write('status.json',dialogueLine='current')
        self.write('heartbeat.json',project='old',room='OLD_AI',age=30,paused=True)
        value=self.status()
        self.assertEqual(value['project'],'sample')
        self.assertEqual(value['dialogueLine'],'current')
        self.assertNotIn('paused',value)
        self.assertTrue(value['online'])

    def test_partial_recent_file_cannot_make_stale_cached_snapshot_online(self):
        path,_=self.write('heartbeat.json',age=30)
        self.assertFalse(self.status()['online'])
        path.write_text('{partial','utf-8')
        value=self.status()
        self.assertFalse(value['online'] or value['frameOnline'])
        self.assertEqual(path.read_text('utf-8'),'{partial')


class CreatorControlRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='mi-control-retry-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name)
        text=(ROOT/'src/CreatorRuntime.cs').read_text('utf-8')
        get=declaration(text,'static T Get<T>(Dictionary<string, object> d, string k, T fallback)')
        tick=declaration(text,'public static void Tick(RainWorldGame g)')
        fixture=(ROOT/'tests/creator_control_retry_check.cs').read_text('utf-8').replace('__GET__',get).replace('__TICK__',tick)
        source=cls.root/'control.cs';source.write_text(fixture,'utf-8')
        cls.exe=cls.root/'control.exe'
        compiler=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        result=subprocess.run([str(compiler),'/nologo','/utf8output','/langversion:5','/r:System.Web.Extensions.dll','/out:'+str(cls.exe),str(source)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)

    def run_case(self,name):
        folder=self.root/name
        result=subprocess.run([str(self.exe),name,str(folder)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('control checks passed:',result.stdout)

    def test_invalid_control_text_is_retried_until_valid(self):self.run_case('parse')
    def test_failed_pose_apply_does_not_consume_unchanged_command(self):self.run_case('apply')
    def test_absent_game_camera_or_room_returns_safely(self):self.run_case('empty')


if __name__=='__main__':unittest.main()
