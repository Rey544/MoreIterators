import base64
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
EDITOR=ROOT/'editor'
OUT=ROOT.parent/'evidence/controls'
OUT.mkdir(parents=True,exist_ok=True)
catalogs={lang:json.loads((EDITOR/'locales'/(lang+'.json')).read_text('utf-8')) for lang in ('zh-CN','en')}
base_script='const CONTROL_CATALOGS='+json.dumps(catalogs,ensure_ascii=False)+';\n'+Path(__file__).with_name('controls_preview_fixture.js').read_text('utf-8')+'\n'+(EDITOR/'i18n.js').read_text('utf-8')
app=(EDITOR/'app.js').read_text('utf-8');wardrobe=(EDITOR/'wardrobe.js').read_text('utf-8')
actual_room_code=app[app.index('const sections='):app.index('function composite(')]
actual_helpers=wardrobe[wardrobe.index('function garmentField('):wardrobe.index('function garmentButton(')]+wardrobe[wardrobe.index('function settingDependency('):wardrobe.index('function wardrobeSettings(')]
design=json.loads((ROOT/'templates/default-project.json').read_text('utf-8'))['design']
design.update(roomPaletteMode='mi',roomGravityMode='mi',entryGravityMode='zero',rearGlowEnabled=True)
room_stubs='''const $=id=>document.getElementById(id);let settingsConditions=[];const run=fn=>(...args)=>fn(...args);function changed(){}function syncLayerOrder(){}const Eyes={settings(){}},HeadSegments={settings(){},targets(){}},AudioSettings={settings(){}},VoiceSettings={settings(){}},PuppetArms={settings(){}};function wardrobeSettings(){}function buildNecklaceSettings(){}function buildPearlAccessorySettings(){}function buildGradientSettings(){}const project={design:DESIGN_FIXTURE};'''.replace('DESIGN_FIXTURE',json.dumps(design,ensure_ascii=False))
def embed_font(match):
    file=EDITOR/'fonts'/match[1]
    return "url('data:font/woff2;base64,"+base64.b64encode(file.read_bytes()).decode()+"')" if file.is_file() else match[0]
for locale in ('zh-CN','en'):
    for kind in ('room','projection'):
        if kind=='room':
            markup='<aside class="settings"><div id="groups"></div></aside>'
            styles=['style.css','studio-theme.css']
            extra_css='body.appearance-studio{display:block;padding:20px}.settings{width:420px;max-width:calc(100vw - 40px)}#groups>.settings-category:not([data-section-id="room"]){display:none}'
            script=base_script+'\n'+room_stubs+'\n'+actual_helpers+'\n'+actual_room_code
            ready="buildSettings();const category=document.querySelector('[data-section-id=room]');category.open=true;for(const item of category.querySelectorAll('details'))item.open=true;"
            klass='appearance-studio mi-studio'
        else:
            markup=re.search(r'<body[^>]*>([\s\S]*?)</body>',(EDITOR/'projections.html').read_text('utf-8')).group(1)
            markup=re.sub(r'<script[^>]*>[\s\S]*?</script>','',markup)
            styles=['projections.css','studio-theme.css'];extra_css=''
            script=base_script+'\n'+(EDITOR/'projections.js').read_text('utf-8')
            ready="await controlWait(()=>document.querySelectorAll('#frameList button').length===2);"
            klass='projection-studio mi-studio'
        css='\n'.join((EDITOR/name).read_text('utf-8') for name in styles)
        css=re.sub(r"url\('/fonts/([^']+)'\)",embed_font,css)+extra_css
        script+='\nwindow.previewReady=MI18n.ready.then(async()=>{MI18n.setLocale('+json.dumps(locale)+',false);'+ready+'await document.fonts.ready;return true;});'
        (OUT/(kind+'-'+locale+'.html')).write_text('<!doctype html><html lang="'+locale+'"><meta charset="utf-8"><title>MI isolated controls preview</title><style>'+css+'</style><body class="'+klass+'">'+markup+'<script>'+script+'</script></body></html>','utf-8')
print(OUT)
