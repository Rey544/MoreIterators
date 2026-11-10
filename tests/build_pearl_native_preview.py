import base64
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
EDITOR=ROOT/'editor';OUT=ROOT.parent/'evidence/native-readers';OUT.mkdir(parents=True,exist_ok=True)
catalogs={lang:json.loads((EDITOR/'locales'/(lang+'.json')).read_text('utf-8')) for lang in ('zh-CN','en')}
base='const PEARL_CATALOGS='+json.dumps(catalogs,ensure_ascii=False)+';\n'+Path(__file__).with_name('pearl_native_fixture.js').read_text('utf-8')
scripts='\n'.join((EDITOR/name).read_text('utf-8') for name in ('i18n.js','line-actions.js','audio-settings.js','pearl-icons.js','pearl-workspace.js','room-picker.js','pearls.js'))
markup=re.search(r'<body[^>]*>([\s\S]*?)</body>',(EDITOR/'pearls.html').read_text('utf-8')).group(1)
markup=re.sub(r'<script[^>]*>[\s\S]*?</script>','',markup)
css='\n'.join((EDITOR/name).read_text('utf-8') for name in ('pearls.css','studio-theme.css','room-picker.css'))
def embed(match):
    file=EDITOR/'fonts'/match[1]
    return "url('data:font/woff2;base64,"+base64.b64encode(file.read_bytes()).decode()+"')" if file.is_file() else match[0]
css=re.sub(r"url\('/fonts/([^']+)'\)",embed,css)
for locale in ('zh-CN','en'):
    ready="window.previewReady=MI18n.ready.then(async()=>{MI18n.setLocale("+json.dumps(locale)+",false);await pearlWait(()=>document.getElementById('readers').options.length>=1&&!document.getElementById('save').disabled);if(!new URLSearchParams(location.search).has('test')){selectReader(4);document.getElementById('lines').querySelector('details').open=true;}await document.fonts.ready;return true;});"
    document='<!doctype html><html lang="'+locale+'"><meta charset="utf-8"><title>MI isolated native reader preview</title><style>'+css+'</style><body class="pearl-studio mi-studio">'+markup+'<script>'+base+'\n'+scripts+'\n'+ready+'</script></body></html>'
    (OUT/('pearls-'+locale+'.html')).write_text(document,'utf-8')
print(OUT)
