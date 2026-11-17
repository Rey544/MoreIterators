from pathlib import Path
import base64
import json
import re
import shutil

source = Path(__file__).resolve().parents[1]
editor = source / 'editor'
out = source.parent / 'evidence/export-multi'
out.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source.parent / 'evidence/export-ui/改前-多个项目.png', out / '改前-多个项目.png')
shutil.copyfile(source.parent / 'evidence/export-ui/改前-多个项目-面板.png', out / '改前-多个项目-面板.png')
html = (editor / 'index.html').read_text('utf-8')
dialog = re.search(r'<dialog id="exportDialog"[\s\S]*?</dialog>', html).group()
css = '\n'.join((editor / file).read_text('utf-8') for file in ('style.css', 'studio-theme.css', 'export-dialog.css', 'scene-assets.css'))
def font(match):
    path = editor / 'fonts' / match[1]
    return "url('data:font/woff2;base64," + base64.b64encode(path.read_bytes()).decode() + "')" if path.is_file() else match[0]
css = re.sub(r"url\('/fonts/([^']+)'\)", font, css)
catalogs = {lang: json.loads((editor / 'locales' / (lang + '.json')).read_text('utf-8')) for lang in ('zh-CN', 'en')}
fixture = r'''
let project,projects=[],draftSettings={},previewErrors=[];
const previewNames=['pool moon','第二个迭代器','等待室和演算室使用同一套区域配色的迭代器作品','横向演算室','破损演算室','Long name THAT_WOULD_OTHERWISE_FORCE_THE_DIALOG_TO_OVERFLOW_1234567890','投影动画','广播练习','水下演算室','珍珠读取','夜间房间','另一份作品'];
function notice(message){document.getElementById('notice').textContent=message;document.getElementById('notice').hidden=false;}
function run(fn){return async(...args)=>{try{return await fn(...args);}catch(error){previewErrors.push(error.message);notice(error.message);}};}
async function save(){}
function serialize(){return structuredClone(project);}
const api=async(path,data)=>{
 if(path==='export-settings'){draftSettings=structuredClone(data);return {ok:true};}
 if(path.startsWith('export-settings?'))return structuredClone(draftSettings);
 if(path==='pearl-projects')return {projects:[],activeId:''};
 if(path==='project-bundle-mods')return {mods:[]};
 if(path.startsWith('project-package-rooms?')){const id=new URLSearchParams(path.split('?')[1]).get('id'),name=id.toUpperCase();return {projectId:id,extraRooms:[],rooms:[{name:'TEST_'+name+'_AI',kind:'ai',required:true,available:true,region:'TEST'},{name:'TEST_'+name+'_ENTRY',kind:'entry',required:true,available:true,region:'TEST'}]};}
 if(path.startsWith('region-package-choices'))return {regions:[{code:'TEST',available:false,reason:'TEST 是共享测试区域'},{code:'PL',available:true}]};
 if(path==='region-package-inspect')return {ok:true,rooms:['PL_AI','PL_ENTRY'],blockers:[],dependencies:[],projectIds:[],includedProjects:[]};
 if(path==='export-room-plan')return {rooms:[]};
 throw Error('Preview API: '+path);
};
window.fetch=async(path,options)=>{
 if(String(path).startsWith('/locales/'))return {ok:true,json:async()=>CATALOGS[String(path).includes('/en.')?'en':'zh-CN']};
 if(path==='/api/export-room-check')return {ok:true,json:async()=>({snapshotToken:'preview',rooms:[],assets:[],parameterConflicts:[],issues:[],requiresChoices:false})};
 if(['/api/export-project-package','/api/export-standalone','/api/export-playable','/api/export-region-package','/api/export'].includes(path))return {ok:true,json:async()=>({url:'#preview-download'})};
 throw Error('Preview fetch: '+path);
};
HTMLAnchorElement.prototype.click=function(){notice('预览完成');};
async function choosePreview(count,format='project'){
 if(document.getElementById('exportDialog').open)await document.querySelector('[data-export-close]').onclick();
 projects=Array.from({length:count},(_,i)=>({projectId:'item'+String(i+1).padStart(2,'0'),name:previewNames[i],editor:{externalRoomTools:true},design:{}}));project=projects[0];
 draftSettings={id:'author.original',name:'本次导出的模组',authors:'原作者',version:'0.4.2',description:'',projects:projects.map(value=>value.projectId),parts:['appearance','textures','room','dialogue'],scope:'project',format,extraRooms:[],startRoom:'TEST_ITEM01_ENTRY',region:'TEST',scene:null,pearls:false,broadcasts:false,workPearls:false,projections:false};
 await document.getElementById('export').onclick();return true;
}
'''
js = 'const CATALOGS=' + json.dumps(catalogs, ensure_ascii=False) + ';\n' + fixture + '\n' + '\n'.join((editor / name).read_text('utf-8') for name in ('i18n.js', 'scene-assets.js', 'standalone.js'))
js += "\nwindow.previewReady=MI18n.ready.then(async()=>{MI18n.setLocale('zh-CN',false);await choosePreview(5);await document.fonts.ready;return true;});"
header = '<header><strong>导出预览</strong><button id="export">导出</button><button onclick="choosePreview(3)">3 个作品</button><button onclick="choosePreview(5)">5 个作品</button><button onclick="choosePreview(12)">12 个作品</button><button onclick="choosePreview(5,\'mod\')">独立游玩模组</button><button onclick="choosePreview(5,\'playable\')">完整地图模组</button><a href="预览.html">截图</a><a id="roomStudio" hidden></a></header><div id="notice" role="status" hidden></div>'
(out / '可操作预览.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>导出预览</title><style>'+css+'</style><body class="appearance-studio mi-studio">'+header+dialog+'<script>'+js+'</script></body></html>', 'utf-8')
views = [('改前', '改前-多个项目-面板.png'), ('改后 3 个作品', '项目ZIP-3个作品-面板.png'), ('改后 5 个作品', '项目ZIP-5个作品-面板.png'), ('改后 12 个作品', '项目ZIP-12个作品-面板.png'), ('独立游玩模组', '独立游玩模组-5个作品-面板.png'), ('完整地图模组', '完整地图模组-5个作品-面板.png'), ('窄屏英文', '独立游玩模组-12个作品-窄屏英文-面板.png')]
buttons = ''.join('<button data-view="'+str(index)+'" aria-pressed="'+('true' if index==2 else 'false')+'">'+label+'</button>' for index, (label, _) in enumerate(views))
preview = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>导出预览</title><style>body{margin:20px;background:#111;color:#ddd;font:15px system-ui}h1{font-size:20px;margin:0 0 16px}nav{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:16px}button,a{font:inherit;color:inherit;background:transparent;border:1px solid #555;border-radius:6px;padding:7px 12px;text-decoration:none;cursor:pointer}button[aria-pressed=true]{border-color:#ddd}a{margin-left:auto}img{display:block;max-width:100%;height:auto;margin:0 auto}.note{font-size:13px;color:#aaa;margin:14px 0}</style><h1>导出预览</h1><nav>'+buttons+'<a href="可操作预览.html">操作界面</a></nav><main><img id="view" src="'+views[2][1]+'" alt="5 个作品"></main><p class="note">改前来自已发布 0.4.2，改后来自候选版。均使用隔离示例数据。</p><script>const views='+json.dumps(views, ensure_ascii=False)+';document.querySelectorAll("[data-view]").forEach(button=>button.onclick=()=>{document.querySelectorAll("[data-view]").forEach(item=>item.setAttribute("aria-pressed",String(item===button)));const [alt,src]=views[Number(button.dataset.view)];document.getElementById("view").src=src;document.getElementById("view").alt=alt;});</script></html>'
(out / '预览.html').write_text(preview, 'utf-8')
(out / '改前改后.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>改前改后</title><style>body{margin:20px;background:#111;color:#ddd;font:15px system-ui}a{color:inherit}main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}h2{font-size:18px;margin:16px 0 12px}img{width:100%;height:auto;display:block}@media(max-width:800px){main{grid-template-columns:1fr}}</style><a href="预览.html">返回预览</a><main><section><h2>改前</h2><img src="改前-多个项目-面板.png" alt="改前"></section><section><h2>改后</h2><img src="项目ZIP-5个作品-面板.png" alt="改后"></section></main></html>', 'utf-8')
print(out / '预览.html')
