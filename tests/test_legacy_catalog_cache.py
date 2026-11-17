import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LegacyCatalogCacheTests(unittest.TestCase):
    def test_legacy_template_identity_cache_and_hook_lifecycle(self):
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        game = Path(os.environ.get('RAIN_WORLD_ROOT', ''))
        core = game / 'BepInEx/core'
        if not compiler.is_file() or not (core / 'MonoMod.RuntimeDetour.dll').is_file():
            self.skipTest('Windows compiler and RAIN_WORLD_ROOT game references are required')
        with tempfile.TemporaryDirectory(prefix='mi-legacy-catalog-test-') as folder:
            work = Path(folder)
            exe = work / 'LegacyCatalogCacheCheck.exe'
            names = ('MonoMod.RuntimeDetour.dll', 'MonoMod.Utils.dll', 'Mono.Cecil.dll')
            for name in names:
                shutil.copy2(core / name, work / name)
            command = [str(compiler), '/nologo', '/utf8output', '/optimize+', '/r:System.Web.Extensions.dll', '/out:' + str(exe)]
            command += ['/r:' + str(core / name) for name in names]
            command += [str(ROOT / 'src/LegacyCatalogCache.cs'), str(ROOT / 'tests/legacy_catalog_cache_check.cs')]
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            fixture = work / 'IteratorContent_aaaaaaaaaaaa.dll'
            references = [game / 'RainWorld_Data/Managed/Assembly-CSharp.dll', game / 'RainWorld_Data/Managed/UnityEngine.dll', game / 'RainWorld_Data/Managed/UnityEngine.CoreModule.dll', core / 'BepInEx.dll']
            command = [str(compiler), '/nologo', '/utf8output', '/optimize+', '/target:library', '/out:' + str(fixture)]
            command += ['/r:' + str(path) for path in references]
            command += [str(ROOT / 'tests/legacy_catalog_template.cs')]
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(exe), str(game), str(work), str(fixture)], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('legacy catalogue assertions', result.stdout)
            print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
