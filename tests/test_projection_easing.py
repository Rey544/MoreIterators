import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'editor'))
import projections


class ProjectionEasingTests(unittest.TestCase):
    def test_all_native_choices_validate_without_changing_authored_frames(self):
        source=(ROOT/'src/ProjectionTimeline.cs').read_text('utf-8-sig')
        names=dict(re.findall(r'case "(\w+)":return RWCustom.Custom.(\w+)\(',source))
        self.assertEqual(len(names),16)
        value=dict(schema=projections.SCHEMA,uid='a'*32,projectId='example',name='example',revision=0,enabled=True,loop=True,
                   trigger=dict(kind='work',source='',pearlUid='',startLineId='',endLineId=''),images=[],
                   tracks=[dict(id='track1',name='track',kind='circle',imageId='',delay=0,color='#ffffff',frames=[])])
        frame=dict(duration=1,x=.5,y=.5,scale=1,rotation=0,opacity=.5,brightness=1,flicker=0)
        for name in ['linear','smooth','step',*names]:
            value['tracks'][0]['frames']=[dict(frame,ease=name)]
            before=copy.deepcopy(value)
            checked=projections.validate(value,resolve_sources=False)
            self.assertEqual(checked['tracks'][0]['frames'],value['tracks'][0]['frames'])
            self.assertEqual(value,before)
        value['tracks'][0]['frames'][0]['ease']='unknown'
        with self.assertRaises(ValueError):projections.validate(value,resolve_sources=False)
        value['tracks'][0]['frames'][0].update(ease='linear',duration=0)
        before=copy.deepcopy(value)
        with self.assertRaises(ValueError):projections.validate(value,resolve_sources=False)
        self.assertEqual(value,before)

    def test_native_labels_keep_original_method_names_in_both_languages(self):
        source=(ROOT/'src/ProjectionTimeline.cs').read_text('utf-8-sig')
        names=dict(re.findall(r'case "(\w+)":return RWCustom.Custom.(\w+)\(',source))
        html=(ROOT/'editor/projections.html').read_text('utf-8-sig')
        for lang in ('en','zh-CN'):
            catalog=json.loads((ROOT/'editor/locales'/f'{lang}.json').read_text('utf-8-sig'))
            for key,name in names.items():
                label=catalog['projection.ease.'+key]
                self.assertIn(name,label)
                self.assertNotEqual(label,name)
                self.assertTrue(catalog['projection.ease.'+key+'.description'])
                self.assertRegex(html,r'value="'+key+r'"[^>]*>[^<]*'+name+r'[^<]*</option>')

    def test_all_curve_samples_boundaries_and_authored_values(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node is unavailable for timeline verification')
        result=subprocess.run([node,str(ROOT/'tests/projection_easing_check.js')],capture_output=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['curves'],19)
        self.assertGreater(report['checks'],700)

    def test_actual_browser_easing_preview_controls_and_parameter_redraw(self):
        node=shutil.which('node')
        chrome=shutil.which('chrome') or 'C:/Program Files/Google/Chrome/Application/chrome.exe'
        if not node or not Path(chrome).is_file():self.skipTest('Chrome and Node are required for browser verification')
        editor=ROOT/'editor'
        catalogs={locale:json.loads((editor/'locales'/f'{locale}.json').read_text('utf-8-sig')) for locale in ('zh-CN','en')}
        html=(editor/'projections.html').read_text('utf-8-sig')
        markup=re.search(r'<body[^>]*>([\s\S]*?)</body>',html).group(1)
        markup=re.sub(r'<script[^>]*>[\s\S]*?</script>','',markup)
        scripts='const EASING_CATALOGS='+json.dumps(catalogs,ensure_ascii=False)+';\n'
        scripts+=(ROOT/'tests/projection_easing_browser.js').read_text('utf-8-sig')+'\n'
        scripts+='\n'.join((editor/name).read_text('utf-8-sig') for name in ('i18n.js','studio-undo.js','projections.js'))
        scripts+='\nrunProjectionEasingTests().then(result=>document.getElementById("result").textContent=JSON.stringify(result)).catch(error=>document.getElementById("result").textContent=JSON.stringify({ok:false,error:error.stack}));'
        css='\n'.join((editor/name).read_text('utf-8-sig') for name in ('projections.css','studio-theme.css'))
        document='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>'+css+'</style></head><body class="projection-studio mi-studio">'+markup+'<pre id="result">PENDING</pre><script>'+scripts+'</script></body></html>'
        with tempfile.TemporaryDirectory(prefix='mi-easing-preview-') as temporary:
            folder=Path(temporary);page=folder/'test.html';page.write_text(document,'utf-8')
            result=subprocess.run([node,str(ROOT/'tests/await_browser_result.mjs'),chrome,str(page),str(folder/'profile')],capture_output=True,encoding='utf-8',timeout=60)
            self.assertEqual(result.returncode,0,result.stderr[-5000:])
            report=json.loads(result.stdout)
            self.assertTrue(report['ok'],report)
            self.assertEqual(report['curves'],19)
            self.assertGreater(report['checks'],250)


if __name__=='__main__':unittest.main()
