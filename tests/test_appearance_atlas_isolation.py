import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
try:
    from .csharp_sources import before_code
except ImportError:
    from csharp_sources import before_code

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'editor'))
import standalone
import storage


class AppearanceAtlasIsolationTests(unittest.TestCase):
    def run_fixture(self, legacy=False):
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.exists():
            self.skipTest('Windows compiler required')
        with tempfile.TemporaryDirectory(prefix='mi-atlas-isolation-') as directory:
            root = Path(directory)
            appearance = [ROOT / 'src/CreatorAppearance.cs']
            namespaces = []
            with patch.object(storage, 'WORKSPACE', ROOT):
                for index in (1, 2):
                    target = root / ('export-' + str(index))
                    target.mkdir()
                    sources, suffix = standalone.compiler_sources(target, {
                        'id': 'test.atlas.' + str(index), 'name': 'Atlas fixture', 'version': '0.0.1'
                    })
                    appearance.append(next(path for path in sources if path.name == 'CreatorAppearance.cs'))
                    namespaces.append('IteratorContent_' + suffix)
            inputs = []
            for index, source in enumerate(appearance):
                text = before_code(source.read_text('utf-8-sig'), 'public static void PaintMesh(') + '\n}\n}\n'
                if legacy:
                    import re
                    text = re.sub(r'"(?:moreiterators|ic_[0-9a-f]{12})_creator_"', '"mi_creator_"', text)
                target = root / ('appearance-' + str(index) + '.cs')
                target.write_text(text, 'utf-8')
                inputs.append(str(target))
            harness = root / 'check.cs'
            text = (ROOT / 'tests/appearance_atlas_isolation_check.cs').read_text('utf-8')
            harness.write_text(text.replace('__FIRST__', namespaces[0]).replace('__SECOND__', namespaces[1]), 'utf-8')
            exe = root / 'check.exe'
            build = subprocess.run([str(compiler), '/nologo', '/utf8output', '/out:' + str(exe), *inputs, str(harness)],
                                   cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=30)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            return subprocess.run([str(exe)], cwd=root, capture_output=True, text=True, timeout=15)

    def test_core_and_two_actual_export_runtimes_keep_texture_ownership(self):
        result = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS: core and two exported runtimes', result.stdout)

    def test_old_atlas_prefix_reproduces_cross_runtime_conflict(self):
        result = self.run_fixture(legacy=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('runtime atlas names collided', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
