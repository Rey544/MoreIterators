import base64
import hashlib
import json
from pathlib import Path
import re
import shutil


SOURCE = Path(__file__).resolve().parents[1] / 'editor'
WORK = SOURCE.parents[2]
BACKUP = WORK / 'mi-041/candidate/MoreIterators/editor'
OUT = WORK / 'mi-041/evidence/room-ux-final-comparison'
OUT.mkdir(parents=True, exist_ok=True)


def read(root, name):
    path = root / name
    return (path if path.is_file() else SOURCE / name).read_text('utf-8')


def font(match):
    path = SOURCE / 'fonts' / match[1]
    return "url('data:font/woff2;base64," + base64.b64encode(path.read_bytes()).decode() + "')" if path.is_file() else match[0]


fixture = Path(__file__).with_name('room_picker_fixture.js').read_text('utf-8')
fixture = fixture.replace('ZZ_POOL', 'PL_WATER').replace('ZZ_ENTRY', 'PL_POOL').replace('ZZ', 'PL')
fixture = fixture.replace("name:'房间连接测试'", "name:'PL'")
ready = '''
window.comparisonReady=MI18n.ready.then(async()=>{
 MI18n.setLocale('zh-CN',false);await waitFor(()=>document.querySelector('#region')?.value==='PL'&&!document.querySelector('#bindingFields').disabled);
 await document.fonts.ready;return {ok:true,errors:roomErrors};
});
document.addEventListener('click',event=>{if(event.target.closest('a'))event.preventDefault();});
'''
sources = {}
for name, root in [('old', BACKUP), ('new', SOURCE)]:
    html = read(root, 'rooms.html')
    body = re.search(r'<body[^>]*>([\s\S]*?)</body>', html)[1]
    body = re.sub(r'<script[^>]*>[\s\S]*?</script>|<link[^>]*>', '', body)
    css = '\n'.join(read(root, file) for file in ('dialogue.css', 'rooms.css', 'room-picker.css', 'studio-theme.css'))
    css = re.sub(r"url\('/fonts/([^']+)'\)", font, css)
    catalogs = {locale: json.loads(read(root, 'locales/' + locale + '.json')) for locale in ('zh-CN', 'en')}
    workflow_fixture = Path(__file__).with_name('room_workflow_fixture.js').read_text('utf-8') if name == 'new' else ''
    script = 'const CATALOGS=' + json.dumps(catalogs, ensure_ascii=False) + ';\n' + fixture + '\n' + workflow_fixture
    script += '\n' + '\n'.join(read(root, file) for file in ('i18n.js', 'room-picker.js', 'rooms.js')) + '\n' + ready
    policy = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'"
    document = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="' + policy + '"><title>' + ('旧版' if name == 'old' else '新版') + '</title><style>' + css + '</style></head><body class="mi-studio">' + body + '<script>' + script + '</script></body></html>'
    (OUT / (name + '.html')).write_text(document, 'utf-8')
    sources[name] = {'source': str(root), 'roomFiles': {file: hashlib.sha256((root / file).read_bytes()).hexdigest() for file in ('rooms.html', 'rooms.js', 'rooms.css')}, 'example': {'region': 'PL', 'ai': 'PL_AI', 'entry': 'PL_POOL'}, 'writes': 'in-memory fixtures only; network forbidden by CSP'}
(OUT / 'sources.json').write_text(json.dumps(sources, ensure_ascii=False, indent=2), 'utf-8')
real = WORK / 'mi-041/evidence/room-workflow-ui-real'
for original, destination in [('actual-reloaded.png', 'new-real.png'), ('actual-pending.png', 'new-pending.png')]:
    shutil.copyfile(real / original, OUT / destination)
(OUT / 'index.html').write_text('''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>界面对比</title><style>html,body{margin:0;background:#111;color:#ddd;font:14px system-ui,sans-serif}header{position:sticky;top:0;padding:12px 20px;display:flex;gap:12px;background:#111;border-bottom:1px solid #333}button{font:inherit;color:inherit;background:transparent;border:1px solid #666;border-radius:4px;padding:7px 22px;cursor:pointer}button[aria-pressed=true]{background:#ddd;color:#111}[hidden]{display:none!important}main{max-width:1440px;margin:auto}img{display:block;width:100%;height:auto}img+img{margin-top:18px;border-top:1px solid #444}</style></head><body><header><button data-page="old" aria-pressed="true">改前</button><button data-page="new" aria-pressed="false">改后</button></header><main><div id="old"><img src="old-real.png" alt="改前"></div><div id="new" hidden><img src="new-real.png" alt="改后常态"><img src="new-pending.png" alt="改后待重新连接"></div></main><script>for(const button of document.querySelectorAll('button'))button.onclick=()=>{for(const page of document.querySelectorAll('main>div'))page.hidden=page.id!==button.dataset.page;for(const other of document.querySelectorAll('button'))other.setAttribute('aria-pressed',String(other===button));window.scrollTo(0,0);};</script></body></html>''', 'utf-8')

print(OUT)
