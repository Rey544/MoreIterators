import base64
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'evidence/export-ui'
OUT.mkdir(parents=True,exist_ok=True)
editor=ROOT/'editor'
source=(editor/'index.html').read_text('utf-8')
dialog=re.search(r'<dialog id="exportDialog"[\s\S]*?</dialog>',source).group()
css='\n'.join((editor/name).read_text('utf-8') for name in ('style.css','studio-theme.css','export-dialog.css','scene-assets.css'))
def embed_font(match):
    path=editor/'fonts'/match[1]
    return "url('data:font/woff2;base64,"+base64.b64encode(path.read_bytes()).decode()+"')" if path.is_file() else match[0]
css=re.sub(r"url\('/fonts/([^']+)'\)",embed_font,css)
catalogs={lang:json.loads((editor/'locales'/(lang+'.json')).read_text('utf-8')) for lang in ('zh-CN','en')}
fixture=Path(__file__).with_name('export_ui_fixture.js').read_text('utf-8')
i18n=(editor/'i18n.js').read_text('utf-8')
script=(editor/'scene-assets.js').read_text('utf-8')+'\n'+(editor/'standalone.js').read_text('utf-8')
for lang,name,playable in [('zh-CN','导出面板中文预览.html',False),('en','Export preview English.html',False),('zh-CN','导出完整地图模组中文预览.html',True),('zh-CN','封面与场景中文预览.html','scene')]:
    document='<!doctype html><html lang="'+lang+'"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MI export preview</title><style>'+css+'</style><body class="appearance-studio mi-studio"><header><button id="export">'+('导出' if lang=='zh-CN' else 'Export')+'</button><a id="roomStudio" hidden></a></header>'+dialog+'<script>const CATALOGS='+json.dumps(catalogs,ensure_ascii=False)+';\n'+fixture+'\n'+i18n+'\n'+script+'\nwindow.previewReady=MI18n.ready.then(async()=>{MI18n.setLocale('+json.dumps(lang)+',false);await resetPreview();await document.fonts.ready;return true;});</script></body></html>'
    if playable=='scene':document=document.replace('await resetPreview();await document.fonts.ready;return true;',"await prepareScenePreview();return true;")
    elif playable:document=document.replace('await resetPreview();await document.fonts.ready;return true;',"await resetPreview();await pick(document.querySelector('[name=exportFormat][value=playable]'));await document.fonts.ready;return true;")
    (OUT/name).write_text(document,'utf-8')
print(OUT)
