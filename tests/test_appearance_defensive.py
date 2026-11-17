import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    from .csharp_sources import before_code, between_code, extract_block, replace_code, tokens
except ImportError:
    from csharp_sources import before_code, between_code, extract_block, replace_code, tokens

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'editor'))
import standalone
import storage


class AppearanceDefensiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not cls.compiler.exists():
            raise unittest.SkipTest('Windows compiler required')
        cls.temporary = tempfile.TemporaryDirectory(prefix='mi-appearance-defensive-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.executables = {}
        arms = (ROOT / 'src/CreatorArms.cs').read_text('utf-8-sig')
        appearance = (ROOT / 'src/CreatorAppearance.cs').read_text('utf-8-sig')
        mesh = extract_block(arms, 'static TriangleMesh CopyMesh(')
        hem = between_code(appearance, 'string[] profile =', 's.sprites[n+4].isVisible')
        harness = (ROOT / 'tests/appearance_mesh_reuse_check.cs').read_text('utf-8')
        cls.build('mesh', [harness.replace('__COPY_MESH__', mesh).replace('__HEM_BODY__', hem)])
        old_mesh = replace_code(mesh, '|| mesh.verticeColors == null || mesh.verticeColors.Length != source.vertices.Length', '', 'legacy mesh reuse')
        cls.build('old-mesh', [harness.replace('__COPY_MESH__', old_mesh).replace('__HEM_BODY__', hem)])
        exported = []
        namespaces = []
        with patch.object(storage, 'WORKSPACE', ROOT):
            for index in (1, 2):
                target = cls.directory / ('export-' + str(index))
                target.mkdir()
                sources, suffix = standalone.compiler_sources(target, {'id': 'test.appearance.' + str(index), 'name': 'Fixture', 'version': '0.0.1'})
                exported.append({file.name: file.read_text('utf-8-sig') for file in sources})
                namespaces.append('IteratorContent_' + suffix)
        palette = extract_block(exported[0]['CreatorRuntime.cs'], 'public static void Palette(')
        main_palette = extract_block((ROOT / 'src/CreatorRuntime.cs').read_text('utf-8-sig'), 'public static void Palette(')
        if [(t.kind, t.value) for t in tokens(palette)] != [(t.kind, t.value) for t in tokens(main_palette)]:
            raise AssertionError('Exported Palette algorithm differs from main runtime')
        palette_harness = (ROOT / 'tests/room_palette_alpha_check.cs').read_text('utf-8')
        palette_harness = palette_harness.replace('__NECK_COLOR__', 'neck.color=head.color;neck.alpha=1;')
        cls.build('palette', [palette_harness.replace('__PALETTE_METHOD__', palette)])
        old_palette = replace_code(palette, 'tint.a=c.a;', '', 'legacy standalone alpha')
        cls.build('old-palette', [palette_harness.replace('__PALETTE_METHOD__', old_palette)])
        texture_sources = [appearance, exported[0]['CreatorAppearance.cs'], exported[1]['CreatorAppearance.cs']]
        texture_sources = [before_code(text, 'public static void PaintMesh(') + '\n}\n}\n' for text in texture_sources]
        host = (ROOT / 'tests/appearance_atlas_isolation_check.cs').read_text('utf-8').split('public static class Check {', 1)[0]
        host = host.replace('public bool failNextLookup;', 'public string failUnload; public bool failNextLookup;')
        host = host.replace('public void UnloadAtlas(string name){', 'public void UnloadAtlas(string name){if(name==failUnload)throw new InvalidOperationException("Release failed");')
        release = (ROOT / 'tests/appearance_release_check.cs').read_text('utf-8')
        release = release.replace('__FIRST__', namespaces[0]).replace('__SECOND__', namespaces[1])
        cls.build('release', [*texture_sources, host + release])

    @classmethod
    def build(cls, name, units):
        files = []
        for index, code in enumerate(units):
            path = cls.directory / (name + '-' + str(index) + '.cs')
            path.write_text(code, 'utf-8')
            files.append(str(path))
        executable = cls.directory / (name + '.exe')
        run = subprocess.run([str(cls.compiler), '/nologo', '/utf8output', '/langversion:5', '/out:' + str(executable), *files],
                             cwd=cls.directory, capture_output=True, text=True, encoding='utf-8', timeout=30)
        if run.returncode:
            raise AssertionError(run.stdout + run.stderr)
        cls.executables[name] = executable

    def run_check(self, executable, mode='', expected=0, message=''):
        result = subprocess.run([str(self.executables[executable]), mode], cwd=self.directory,
                                capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        if message:
            self.assertIn(message, result.stdout + result.stderr)

    def test_replaces_mesh_with_missing_or_short_colors(self):
        for mode in ('null-colors', 'short-colors'):
            with self.subTest(mode=mode):
                self.run_check('mesh', mode)

    def test_preserves_valid_reuse_source_colors_alpha_and_white_fallback(self):
        for mode in ('reuse', 'white', 'different-size'):
            with self.subTest(mode=mode):
                self.run_check('mesh', mode)

    def test_old_mesh_reuse_reproduces_missing_color_failure(self):
        self.run_check('old-mesh', 'null-colors', 1, 'NullReferenceException')
        self.run_check('old-mesh', 'short-colors', 1, 'IndexOutOfRangeException')

    def test_null_profile_is_neutral_and_existing_profile_values_are_preserved(self):
        self.run_check('mesh', 'hem')

    def test_actual_export_preserves_palette_alpha_rgb_and_external_room_bypass(self):
        for mode in ('alpha', 'rgb', 'scope', 'shader'):
            with self.subTest(mode=mode):
                self.run_check('palette', mode)

    def test_old_export_reproduces_alpha_corruption(self):
        self.run_check('old-palette', 'alpha', 1, 'Palette alpha changed')

    def test_texture_cleanup_owns_only_its_runtime_and_retries_failed_release(self):
        self.run_check('release')


if __name__ == '__main__':
    unittest.main()
