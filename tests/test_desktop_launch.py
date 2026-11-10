from pathlib import Path
from unittest.mock import patch
import os,subprocess,sys,tempfile,types,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'editor'))
import desktop_launch

@unittest.skipUnless(os.name=='nt','Windows desktop broker')
class DesktopLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'StudioShell.exe').touch()
        scope=patch.object(desktop_launch,'ROOT',self.root);scope.start();self.addCleanup(scope.stop)

    def test_url_passed_as_one_argument_without_shell(self):
        url='http://127.0.0.1:18747/?project=a&lang=zh-CN'
        with patch.object(desktop_launch.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stderr=b'')) as run:
            self.assertTrue(desktop_launch.open_url(url))
        args,kwargs=run.call_args
        self.assertEqual(args[0],[str(self.root/'StudioShell.exe'),'url',url])
        self.assertFalse(kwargs.get('shell',False));self.assertEqual(kwargs['timeout'],15)

    def test_room_filename_stays_a_distinct_argument(self):
        exe=self.root/'Rained.exe';room=self.root/'room & name.txt'
        with patch.object(desktop_launch.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stderr=b'')) as run:
            desktop_launch.open_rained(exe,room)
        self.assertEqual(run.call_args.args[0],[str(self.root/'StudioShell.exe'),'rained',str(exe),str(room)])

    def test_missing_or_failed_broker_does_not_launch_as_game_child(self):
        with patch.object(desktop_launch.subprocess,'run',return_value=types.SimpleNamespace(returncode=1,stderr=b'injected')),patch.object(desktop_launch.webbrowser,'open') as direct:
            with self.assertRaises(OSError):desktop_launch.open_url('http://127.0.0.1:18747/')
            direct.assert_not_called()
        (self.root/'StudioShell.exe').unlink()
        with self.assertRaises(FileNotFoundError):desktop_launch.open_url('http://127.0.0.1:18747/')

if __name__=='__main__':unittest.main()
