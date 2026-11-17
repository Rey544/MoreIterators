import base64
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / 'editor'
OUT = ROOT.parent / 'evidence/room-picker'
OUT.mkdir(parents=True, exist_ok=True)
css = '\n'.join((EDITOR / name).read_text('utf-8') for name in ('dialogue.css', 'rooms.css', 'broadcasts.css', 'studio-theme.css', 'room-picker.css'))
def embed_font(match):
    file = EDITOR / 'fonts' / match[1]
    return "url('data:font/woff2;base64," + base64.b64encode(file.read_bytes()).decode() + "')" if file.is_file() else match[0]
css = re.sub(r"url\('/fonts/([^']+)'\)", embed_font, css)
catalogs = {lang: json.loads((EDITOR / 'locales' / (lang + '.json')).read_text('utf-8')) for lang in ('zh-CN', 'en')}
fixture = Path(__file__).with_name('room_picker_fixture.js').read_text('utf-8')
base_script = 'const CATALOGS=' + json.dumps(catalogs, ensure_ascii=False) + ';\n' + fixture + '\n' + (EDITOR / 'i18n.js').read_text('utf-8') + '\n' + (EDITOR / 'room-picker.js').read_text('utf-8')
body = re.search(r'<body[^>]*>([\s\S]*?)</body>', (EDITOR / 'rooms.html').read_text('utf-8')).group(1)
body = re.sub(r'<script[^>]*>[\s\S]*?</script>|<link[^>]*>', '', body)
for locale in ('zh-CN', 'en'):
    for kind in ('picker', 'connection', 'broadcast'):
        if kind == 'broadcast':
            markup = re.search(r'<body[^>]*>([\s\S]*?)</body>', (EDITOR / 'broadcasts.html').read_text('utf-8')).group(1)
            markup = re.sub(r'<script[^>]*>[\s\S]*?</script>|<link[^>]*>', '', markup)
        else:markup = body if kind == 'connection' else '<button onclick="resetRoomPreview()">' + ('地图选房' if locale == 'zh-CN' else 'Choose on map') + '</button>'
        script = base_script + ('\n' + Path(__file__).with_name('room_workflow_fixture.js').read_text('utf-8') if kind == 'connection' else '') + ('\n' + (EDITOR / ('rooms.js' if kind == 'connection' else 'broadcasts.js')).read_text('utf-8') if kind != 'picker' else '')
        ready = "await waitFor(()=>document.querySelector('#ai')?.value==='ZZ_AI');" if kind == 'connection' else "await waitFor(()=>document.querySelector('#room')?.value==='ZZ_POOL');document.querySelector('.broadcast-placement').open=true;" if kind == 'broadcast' else "resetRoomPreview();await waitFor(()=>document.querySelector('.rp-hint')?.textContent===MI18n.text('相机预览'));"
        script += "\nwindow.resetRoomPreview=()=>MIRoomPicker.open({room:'ZZ_POOL',region:'ZZ',pickPoint:true,point:{x:.45,y:.35}});window.previewReady=MI18n.ready.then(async()=>{MI18n.setLocale(" + json.dumps(locale) + ",false);" + ready + "await document.fonts.ready;return true;});"
        document = '<!doctype html><html lang="' + locale + '"><meta charset="utf-8"><title>MI isolated room preview</title><style>' + css + '</style><body class="mi-studio">' + markup + '<script>' + script + '</script></body></html>'
        (OUT / (kind + '-' + locale + '.html')).write_text(document, 'utf-8')
print(OUT)
