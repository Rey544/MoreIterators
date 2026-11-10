import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class SpriteDiagnosticsTests(unittest.TestCase):
    def test_readonly_health_changes_are_logged_without_frame_spam(self):
        compiler=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.exists():self.skipTest('Windows compiler required')
        with tempfile.TemporaryDirectory(prefix='mi-sprite-diagnostics-') as tmp:
            exe=Path(tmp)/'check.exe'
            result=subprocess.run([str(compiler),'/nologo','/utf8output','/out:'+str(exe),str(ROOT/'src/OracleSpriteDiagnostics.cs'),str(ROOT/'src/OracleRenderReport.cs'),str(ROOT/'tests/sprite_diagnostics_check.cs')],cwd=tmp,capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=subprocess.run([str(exe),tmp],cwd=tmp,capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_snapshot_follows_complete_clothing_draw(self):
        source=(ROOT/'src/MoreIteratorsPlugin.cs').read_text(encoding='utf-8-sig')
        self.assertIn('CreatorWardrobe.Draw(self,s,n,d,camera,stack,up,right);\n                OracleSpriteDiagnostics.Observe(self,s,n,d);',source)
if __name__=='__main__':unittest.main()
