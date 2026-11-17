from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'editor'))
import csharp_source


def declaration(source, pattern):
    items = csharp_source.tokens(source)
    wanted = [(item.kind,item.value) for item in csharp_source.tokens(pattern)]
    positions = [index for index in range(len(items)-len(wanted)+1)
                 if [(item.kind,item.value) for item in items[index:index+len(wanted)]] == wanted]
    if len(positions) != 1:
        raise AssertionError('Expected one declaration: '+pattern)
    start = positions[0]
    body = start+len(wanted)
    if items[body].value != '{':
        raise AssertionError('Missing declaration body')
    end = csharp_source._matching(items,body)
    return source[items[start].start:items[end].end]


class MediaReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if not compiler.exists():
            raise unittest.SkipTest('The existing .NET Framework compiler is required')
        cls.temporary = tempfile.TemporaryDirectory(prefix='mi-media-review-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.work = Path(cls.temporary.name)
        broadcasts = (ROOT/'src/CreatorBroadcasts.cs').read_text('utf-8')
        catalog = csharp_source.extract_class(broadcasts,'CreatorBroadcastCatalog')
        runtime = csharp_source.extract_class(broadcasts,'CreatorBroadcastRuntime')
        audio = csharp_source.extract_class((ROOT/'src/CreatorAudio.cs').read_text('utf-8'),'CreatorAudio')
        prefix = 'using System;using System.IO;using System.Collections.Generic;using System.Runtime.CompilerServices;using System.Security.Cryptography;using System.Text.RegularExpressions;using MoreSlugcats;using UnityEngine;using Music;namespace MoreIterators {\n'
        product = cls.work/'media-product.cs'
        product.write_text(prefix+catalog+'\n'+runtime+'\n'+audio+'\n}', 'utf-8')
        source = (ROOT/'src/CreatorBroadcastDisplay.cs').read_text('utf-8')
        display = cls.work/'display-check.cs'
        display.write_text((ROOT/'tests/media_display_input_check.cs').read_text('utf-8').replace('__DRAW__',declaration(source,'public override void Draw(float timeStacker)')), 'utf-8')
        background = cls.work/'background-host.cs'
        original = (ROOT/'tests/background_coordinates_check.cs').read_text('utf-8')
        background.write_text(original.split('public static class BackgroundCoordinatesCheck {',1)[0], 'utf-8')
        groups = {
            'media': [product, ROOT/'tests/media_review_check.cs'],
            'input': [display],
            'background': [background, ROOT/'src/CreatorBackgroundCoordinates.cs',ROOT/'tests/media_background_install_check.cs'],
        }
        for name,files in groups.items():
            if name not in os.environ.get('MI_MEDIA_GROUPS','media,input,background').split(','):
                continue
            result = subprocess.run([str(compiler),'/nologo','/utf8output','/langversion:5','/r:System.Web.Extensions.dll','/out:'+str(cls.work/(name+'.exe')),*map(str,files)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
            if result.returncode:
                raise AssertionError(name+' compiler failed\n'+result.stdout+result.stderr)

    def run_group(self, executable, scenario):
        folder = self.work/scenario
        folder.mkdir()
        command = [str(self.work/(executable+'.exe'))]
        if executable == 'media':
            command += [scenario,str(folder)]
        elif executable == 'background':
            command += [str(folder)]
        result = subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('checks passed:',result.stdout)

    def test_broadcast_cache_reload_deletion_and_registration(self):
        self.run_group('media','cache')

    def test_partial_token_revision_and_deletion_are_safe(self):
        self.run_group('media','token')

    def test_audio_hash_cache_and_runtime_ownership(self):
        self.run_group('media','asset')

    def test_audio_snapshot_reuse_and_mutation_safety(self):
        self.run_group('media','snapshot')

    def test_broadcast_uses_native_mapped_acceleration_input(self):
        self.run_group('input','mapped-input')

    def test_background_install_and_cleanup_are_idempotent(self):
        self.run_group('background','install')


if __name__ == '__main__':
    unittest.main()
