import base64
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / 'editor'
OUT = ROOT.parent / 'evidence/export-ui'
css = '\n'.join((EDITOR / name).read_text('utf-8') for name in ('style.css', 'studio-theme.css'))
def embed(match):
    font = EDITOR / 'fonts' / match[1]
    return "url('data:font/woff2;base64," + base64.b64encode(font.read_bytes()).decode() + "')" if font.is_file() else match[0]
css = re.sub(r"url\('/fonts/([^']+)'\)", embed, css)
globals_js = Path(__file__).with_name('paint_clipping_browser.js').read_text('utf-8').split('(async()=>{let checks=0;')[0]
scripts = '\n'.join((EDITOR / name).read_text('utf-8') for name in ('paint-composite.js', 'paint-layers.js'))
fixture = '''
const base=canvas(128,128),b=base.getContext('2d');b.fillStyle='#aaa';b.beginPath();b.ellipse(64,58,36,42,0,0,Math.PI*2);b.fill();b.beginPath();b.moveTo(42,86);b.lineTo(35,111);b.quadraticCurveTo(64,119,93,111);b.lineTo(86,86);b.fill();
const color=canvas(128,128),c=color.getContext('2d'),gradient=c.createLinearGradient(0,0,128,128);gradient.addColorStop(0,'#b6c3b9');gradient.addColorStop(1,'#617e78');c.fillStyle=gradient;c.fillRect(0,0,128,128);
const shade=canvas(128,128),s=shade.getContext('2d');s.fillStyle='#1b2e36';s.globalAlpha=.55;s.beginPath();s.moveTo(80,0);s.quadraticCurveTo(24,64,98,128);s.lineTo(128,128);s.lineTo(128,0);s.fill();
reset([{name:'底图'},{name:'颜色',clipToBelow:true},{name:'阴影',clipToBelow:true}],'face',[base,color,shade]);dimensions.face=[128,128];activeLayer=2;updateTarget();
const output=document.getElementById('previewCanvas'),context=output.getContext('2d');context.imageSmoothingEnabled=false;context.drawImage(PaintComposite.compose(project.textures.face.layers,canvases.face,canvas,[128,128]),0,0,256,256);
window.previewReady=document.fonts.ready.then(()=>{const row=document.querySelector('[data-layer-id="layer2"]'),box=row.getBoundingClientRect();row.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:box.right+8,clientY:box.top+6}));return true;});
'''
markup='''<div class="preview-layout"><div class="sample-canvas"><canvas id="previewCanvas" width="256" height="256"></canvas></div><aside id="paintLayers" class="paint-layers"><div class="layer-heading"><h3>贴图图层</h3><div class="layer-actions"><button id="layerAdd" type="button">＋</button><button id="layerDelete" type="button">−</button></div></div><div id="layerList"></div></aside></div>'''
document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>图层右键菜单预览</title><style>'+css+'''\nbody{padding:48px 32px}.preview-layout{display:flex;gap:18px;align-items:flex-start;width:530px}.sample-canvas{display:grid;place-items:center;width:320px;height:330px;border:1px solid #444;border-radius:4px;background-color:#242424;background-image:linear-gradient(45deg,#333 25%,transparent 25%,transparent 75%,#333 75%),linear-gradient(45deg,#333 25%,transparent 25%,transparent 75%,#333 75%);background-position:0 0,12px 12px;background-size:24px 24px}#previewCanvas{image-rendering:pixelated;width:256px;height:256px}.appearance-studio #paintLayers{position:static;width:180px;height:330px;padding:8px;max-height:none;overflow:visible}.appearance-studio .layer-heading h3{font-size:14px}body>main{display:none}</style><body class="appearance-studio mi-studio">'''+markup+'<script>'+scripts+'\n'+globals_js+'\n'+fixture+'</script></body></html>'
(OUT/'图层右键菜单预览.html').write_text(document,'utf-8')
print(OUT/'图层右键菜单预览.html')
