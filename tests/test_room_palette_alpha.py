import os
from pathlib import Path
import subprocess
import tempfile
import unittest
try:
    from .csharp_sources import code_index, extract_block, extract_statements, replace_code
except ImportError:
    from csharp_sources import code_index, extract_block, extract_statements, replace_code


ROOT = Path(__file__).resolve().parents[1]


class RoomPaletteAlphaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.exists():
            raise unittest.SkipTest('Windows compiler required')
        cls.temporary = tempfile.TemporaryDirectory(prefix='mi-room-palette-alpha-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        source = (ROOT / 'src/CreatorRuntime.cs').read_text('utf-8-sig')
        method = extract_block(source, 'public static void Palette(Texture2D t,RoomCamera cam,int palette)')
        harness = (ROOT / 'tests/room_palette_alpha_check.cs').read_text('utf-8')
        plugin = (ROOT / 'src/MoreIteratorsPlugin.cs').read_text('utf-8-sig')
        neck = extract_statements(plugin, 'neck.color=', 2)
        code_index(neck, 'neck.alpha=1;')
        cls.executables = {}
        for variant in ('actual', 'legacy'):
            selected = method if variant == 'actual' else replace_code(method, 'tint.a=c.a;', '', 'legacy palette alpha removal')
            unit = cls.directory / (variant + '.cs')
            neck_code = neck if variant == 'actual' else 'neck.color=head.color*.88f; neck.alpha=1;'
            unit.write_text(harness.replace('__PALETTE_METHOD__', selected).replace('__NECK_COLOR__', neck_code), 'utf-8')
            executable = cls.directory / (variant + '.exe')
            result = subprocess.run(
                [str(compiler), '/nologo', '/utf8output', '/out:' + str(executable), str(unit)],
                cwd=cls.directory, capture_output=True, text=True, encoding='utf-8', timeout=30)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            cls.executables[variant] = executable

    def run_check(self, mode, variant='actual'):
        return subprocess.run([str(self.executables[variant]), mode], cwd=self.directory,
                              capture_output=True, text=True, timeout=15)

    def assert_passes(self, mode):
        result = self.run_check(mode)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preserves_original_alpha_for_both_palette_banks(self):
        self.assert_passes('alpha')

    def test_preserves_existing_rgb_exactly(self):
        self.assert_passes('rgb')

    def test_leaves_control_pixels_and_external_room_mode_unchanged(self):
        self.assert_passes('scope')

    def test_keeps_level_color_palette_sample_opaque(self):
        self.assert_passes('shader')

    def test_neck_shading_keeps_color_alpha_and_original_rgb(self):
        self.assert_passes('neck')

    def test_old_neck_method_reproduces_partial_transparency(self):
        result = self.run_check('neck', 'legacy')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Neck alpha changed', result.stdout + result.stderr)

    def test_old_method_reproduces_palette_alpha_corruption(self):
        result = self.run_check('alpha', 'legacy')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Palette alpha changed', result.stdout + result.stderr)
        result = self.run_check('shader', 'legacy')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('LevelColor sample became translucent', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
