
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
try:
    from .csharp_sources import extract_block
except ImportError:
    from csharp_sources import extract_block

ROOT=Path(__file__).resolve().parents[1]

class ShutdownCleanupTests(unittest.TestCase):
    def test_core_and_playback_cleanup_failures_do_not_block_native_shutdown(self):
        compiler=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.is_file():self.skipTest('Windows compiler required')
        plugin=(ROOT/'src/MoreIteratorsPlugin.cs').read_text('utf-8-sig')
        panel=(ROOT/'src/CreatorControlPanel.cs').read_text('utf-8-sig')
        methods='\n'.join(extract_block(plugin,signature) for signature in ('void StopCapture()','void RemoveHooks()','void OnDisable()'))
        game='public static void GameClose(Action<RainWorldGame> orig,RainWorldGame g)'+extract_block(plugin,'var registeredHook35=',body_only=True)
        actual='using System;namespace MoreIterators { public partial class ShutdownPlugin {'+methods+game+'} public static partial class CreatorControlPanel {'+extract_block(panel,'public static void Close()')+'}}'
        with tempfile.TemporaryDirectory(prefix='mi-shutdown-cleanup-') as folder:
            extracted=Path(folder)/'ActualShutdown.cs';extracted.write_text(actual,'utf-8')
            for mode in ('core','playback'):
                exe=Path(folder)/(mode+'.exe')
                args=[str(compiler),'/nologo','/debug','/main:ShutdownCleanupCheck','/out:'+str(exe),str(ROOT/'src/MiDiagnostics.cs'),str(ROOT/'tests/hook_diagnostics_check.cs'),str(ROOT/'tests/shutdown_cleanup_check.cs'),str(extracted)]
                if mode=='playback':args.append('/define:PLAYBACK')
                result=subprocess.run(args,capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=15)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('shutdown cleanup assertions passed',result.stdout)
                print(mode+': '+result.stdout.strip())

if __name__=='__main__':unittest.main()
