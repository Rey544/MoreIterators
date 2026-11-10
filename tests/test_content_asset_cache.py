
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ContentAssetCacheTests(unittest.TestCase):
    def test_native_asset_order_owner_isolation_and_bounded_cache_invalidation(self):
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.is_file():
            self.skipTest('Windows .NET Framework compiler is required')
        with tempfile.TemporaryDirectory(prefix='mi-content-cache-test-') as folder:
            work = Path(folder)
            executable = work / 'ContentAssetCacheCheck.exe'
            command = [str(compiler), '/nologo', '/utf8output', '/r:System.Web.Extensions.dll',
                       '/out:' + str(executable), str(ROOT / 'src/ContentAssets.cs'),
                       str(ROOT / 'src/RuntimePaths.cs'), str(ROOT / 'tests/content_asset_cache_check.cs')]
            result = subprocess.run(command, capture_output=True, text=True,
                                    encoding='utf-8', errors='replace', timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            environment = dict(os.environ, TEMP=str(work), TMP=str(work))
            result = subprocess.run([str(executable)], env=environment, capture_output=True,
                                    text=True, encoding='utf-8', errors='replace', timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS 192 actual-method assertions', result.stdout)
            fixture_line = next(line for line in result.stdout.splitlines() if line.startswith('FIXTURE '))
            fixture = Path(fixture_line.removeprefix('FIXTURE ')).resolve()
            self.assertTrue(fixture.is_relative_to(work.resolve()), 'Native host must use the test temporary directory')
            print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
