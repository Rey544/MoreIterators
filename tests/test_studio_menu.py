




import os
from pathlib import Path
import subprocess
import tempfile
import unittest
try:
    from .csharp_sources import code_index, extract_block
except ImportError:
    from csharp_sources import code_index, extract_block


class StudioMenuTests(unittest.TestCase):
    def test_signal_transition_gate_precedes_gallery_and_native_dispatch(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'src/MoreIteratorsPlugin.cs').read_text('utf-8-sig')
        signal = extract_block(source, 'public void Signal(')
        guard = 'if(CreatorStudioMenu.IsTransitioning(self))return;'
        guard_index = code_index(signal, guard)
        for dispatch in ('CreatorBroadcastGallery.Signal(', 'CreatorPearlGallery.Signal(',
                         'CreatorRuntime.Signal(', 'IteratorIntegrations.Signal(', 'orig(self,sender,message)'):
            self.assertLess(guard_index, code_index(signal, dispatch))

    def test_menu_lifecycle_navigation_catalog_and_preview_settings(self):
        root = Path(__file__).resolve().parents[1]
        compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.exists():
            self.skipTest('C# compiler required')
        with tempfile.TemporaryDirectory(prefix='mi-studio-menu-') as folder:
            exe = Path(folder) / 'menu.exe'
            gallery = (root / 'src/CreatorBroadcastGallery.cs').read_text('utf-8-sig')
            text_lines = extract_block(gallery, 'internal static List<string> TextLines(')
            helper = Path(folder) / 'GalleryText.cs'
            diagnostics = (root / 'src/MiDiagnostics.cs').read_text('utf-8-sig')
            cleanup_methods=[]
            for signature in ('public static void Cleanup(', 'public static void CloseProcess('):
                cleanup_methods.append(extract_block(diagnostics,signature))
            helper.write_text('using System; using System.Collections.Generic; namespace MoreIterators { public static class CreatorBroadcastGallery {' + text_lines + '} public static partial class MiDiagnostics {'+'\n'.join(cleanup_methods)+'} }', encoding='utf-8')
            compile_result = subprocess.run([
                str(compiler), '/nologo', '/utf8output', '/r:System.Web.Extensions.dll', '/out:' + str(exe),
                str(root / 'src/CreatorStudioMenu.cs'), str(root / 'src/CreatorMenuScrollBar.cs'), str(helper),
                str(root / 'src/UiText.cs'), str(root / 'tests/native_translation_stub.cs'),
                '/resource:' + str(root / 'mod/text/text_eng/strings.txt') + ',mi.ui.eng.strings.txt',
                str(root / 'tests/studio_menu_check.cs')], capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=30)
            self.assertEqual(compile_result.returncode, 0, compile_result.stdout + compile_result.stderr)
            result = subprocess.run([str(exe), 'Chinese', 'English', 'TraditionalChinese'], capture_output=True, text=True,
                                    encoding='utf-8', errors='replace', timeout=30,
                                    env=dict(os.environ, MI_TEST_NATIVE_TEXT_ROOT=str(root / 'mod/text')))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('studio menu assertions passed', result.stdout)
            print(result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
