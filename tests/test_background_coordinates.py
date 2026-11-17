from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class BackgroundCoordinateTests(unittest.TestCase):
    def test_scoped_runtime_coordinates_and_hook_lifecycle(self):
        compiler=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.is_file():self.skipTest('Local C# compiler unavailable')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);exe=root/'background-check.exe'
            result=subprocess.run([str(compiler),'/nologo','/r:System.Web.Extensions.dll','/out:'+str(exe),str(ROOT/'src/CreatorBackgroundCoordinates.cs'),str(ROOT/'tests/background_coordinates_check.cs')],capture_output=True,text=True,errors='replace')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=subprocess.run([str(exe),str(root/'assets')],capture_output=True,text=True,errors='replace')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('background coordinate checks passed',result.stdout)

if __name__=='__main__':unittest.main()
