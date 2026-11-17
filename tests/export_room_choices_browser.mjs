import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const tests=path.dirname(fileURLToPath(import.meta.url)),editor=path.resolve(tests,'../editor'),source=path.resolve(editor,'..');
const output=path.resolve(source,'../evidence/export-choices'),temporary=fs.mkdtempSync(path.join(os.tmpdir(),'mi-export-choices-'));
const profile=path.join(temporary,'profile'),downloads=path.join(temporary,'downloads');fs.mkdirSync(downloads);fs.mkdirSync(output,{recursive:true});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms)),clone=value=>structuredClone(value),calls=[],exports=[],preferences=[],failures=[],screenshots=[];
let checks=0,mode='conflict',snapshot=1,staleOnce=false;
const check=(value,message)=>{checks++;if(!value)throw Error(message);};
const version=(id,origin,complete=true,extra={})=>({id,origin,origins:id==='render-project'?['project','local']:[origin],providers:origin==='enabled'?[{id:'fixture.palette',name:'Palette Test'}]:[],modifiedAt:'2026-11-09T12:30:00Z',hash:id,complete,issues:complete?[]:['fixture incomplete'],...extra});
const report=()=>{
 if(mode==='none')return {schema:'moreiterators.room-source-choices.v1',snapshotToken:'snapshot-'+snapshot,requiresChoices:false,rooms:[],assets:[],issues:[]};
 const conflict=mode==='conflict',missing=mode==='missing',unpaired=mode==='unpaired';
 return {schema:'moreiterators.room-source-choices.v1',snapshotToken:'snapshot-'+snapshot,requiresChoices:conflict,parameterConflicts:conflict?['palette','gravity'].map(kind=>({projectId:'fixture',room:'XX_AI',kind,certainty:'potential',sourceMode:'mi',settingsVersionIds:['settings-installed']})):[],rooms:[{projectId:'fixture',room:'XX_AI',sourceAvailable:true,state:missing?'missing':'ready',recommendedSourceId:missing?null:'render-project',recommendedSettingsId:'settings-local',sourceConflict:conflict,settingsConflict:conflict,renderVersions:missing?[version('render-bad','installed',false)]:conflict?[version('render-project','project',true,{pairedSource:true,cameraCount:2}),version('render-local','local',true,{pairedSource:false,cameraCount:2}),version('render-bad','installed',false,{cameraCount:1})]:[version('render-project','project',true,{pairedSource:!unpaired,cameraCount:2})],settingsVersions:conflict?[version('settings-local','local'),version('settings-installed','installed')]:[version('settings-local','local')]}],assets:conflict?[{key:'palettes/palette9100.png',relative:'palettes/palette9100.png',projectIds:['fixture','fixture-two'],projectId:'fixture',conflict:true,versions:[version('asset-project','project',true,{projectIds:['fixture']}),version('asset-enabled','enabled',true,{projectIds:['fixture-two']})]}]:[],issues:missing?[{projectId:'fixture',room:'XX_AI',kind:'source',code:'room_choices_missing'}]:[]};
};
const project={projectId:'fixture',name:'测试作品',schema:'moreiterators.project.v1',design:{layers:{},roomPaletteMode:'room',roomGravityMode:'mi',entryGravityMode:'room',roomWorkColor:'#476d67',roomReceptionColor:'#bd8152',roomBrightness:1,roomContrast:1,roomSaturation:1,roomTransition:3,haloColor:'#abcabc',haloScale:1,haloOpacity:.7},textures:{},editor:{externalRoomTools:true}};
const other={...clone(project),projectId:'fixture-two',name:'另一作品'};
const app=fs.readFileSync(path.join(editor,'app.js'),'utf8'),wardrobe=fs.readFileSync(path.join(editor,'wardrobe.js'),'utf8');
const between=(text,start,end)=>text.slice(text.indexOf(start),text.indexOf(end));
const presetFolders=JSON.parse(fs.readFileSync(path.join(source,'templates/rooms/chambers/manifest.json'),'utf8')).presets;
const catalog=presetFolders.map(folder=>{const spec=JSON.parse(fs.readFileSync(path.join(source,'templates/rooms/chambers',folder,'manifest.json'),'utf8'));return {...spec,preview:'/fixture-preview/'+folder+'.png',sizes:[{id:'original',columns:0,rows:0,width:spec.width,height:spec.height,cameraCount:spec.cameraCount},...[ [1,1],[2,1],[3,1],[1,2],[1,3],[2,2],[2,3],[3,2],[3,3] ].filter(([columns,rows])=>columns*70>=spec.width&&rows*40>=spec.height).map(([columns,rows])=>({id:columns+'x'+rows,columns,rows,width:columns*70,height:rows*40,cameraCount:columns*rows}))]};});
const fixtureScript=`
const $=id=>document.getElementById(id),api=async(path,data)=>{await MI18n.ready;const response=await fetch('/api/'+path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),value=await response.json();if(!response.ok)throw Error(MI18n.error(value,response.statusText));return value;};
let project=${JSON.stringify(project)},projects=${JSON.stringify([project,other])},chamberPresets=${JSON.stringify(catalog)},loading=false,creatingProject=false,savingProject=false,applyingProject=false,restoringHistory=false,changingProject=false,historyBusy=false;
const fixtureErrors=[],noop=()=>{},serialize=()=>project;
function run(fn){return async(...args)=>{try{return await fn(...args);}catch(error){fixtureErrors.push({message:error.message,code:error.code});}};}
async function save(){window.fixtureSaves=(window.fixtureSaves||0)+1;}
const changed=noop,markDirty=noop,wardrobeSettings=noop,buildNecklaceSettings=noop,buildPearlAccessorySettings=noop,buildGradientSettings=noop;
const Eyes={settings:noop},HeadSegments={settings:noop,targets:noop},PuppetArms={settings:noop},AudioSettings={settings:noop},VoiceSettings={settings:noop};
window.MIExportScene={mount:noop,reset:noop,setEnabled:noop,serialize:()=>null};
${between(wardrobe,'function garmentField(','function garmentButton(')}
${between(wardrobe,'function garmentButton(','function garmentPaint(')}
${between(wardrobe,'let settingsConditions=','function wardrobeSettings(')}
${between(app,'const sections=','function composite(')}
${between(app,'function syncProjectControls(','function snapshot(')}
${between(app,'function presetName(','async function loadChamberPresets(')}
MI18n.ready.then(()=>{buildSettings();refreshChamberPresets();$('projectName').value=project.name;});
`;
let html=fs.readFileSync(path.join(editor,'index.html'),'utf8').replace(/<script\b[^>]*src="([^"]+)"[^>]*><\/script>/g,(whole,src)=>src==='/i18n.js'?whole:'');
html=html.replace('</body>','<script>'+fixtureScript.replaceAll('</script','<\/script')+'</script><script src="/standalone.js"></script></body>');
const respond=(res,value,status=200)=>{res.writeHead(status,{'content-type':'application/json; charset=utf-8'});res.end(JSON.stringify(value));};
const server=http.createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://fixture.invalid');
 if(url.pathname==='/'){res.writeHead(200,{'content-type':'text/html; charset=utf-8'});return res.end(html);}
 if(url.pathname.startsWith('/fixture-preview/')){const name=path.basename(url.pathname,'.png');if(!presetFolders.includes(name))throw Error('Unknown preview');res.writeHead(200,{'content-type':'image/png'});return res.end(fs.readFileSync(path.join(source,'templates/rooms/chambers',name,'thumbnail.png')));}
 if(url.pathname==='/exports/fixture.zip'){res.writeHead(200,{'content-type':'application/zip','content-disposition':'attachment; filename="fixture.zip"'});return res.end(Buffer.from('504b0506000000000000000000000000000000000000','hex'));}
 if(url.pathname.startsWith('/api/')){
  let raw='';for await(const chunk of req)raw+=chunk;const data=raw?JSON.parse(raw):null;calls.push({path:url.pathname,data:clone(data)});
  if(url.pathname==='/api/export-settings'){if(data){preferences.push(clone(data));return respond(res,{ok:true});}return respond(res,{id:'fixture.mod',name:'测试导出',authors:'Fixture',description:'',version:'0.4.0',cover:'',scene:null});}
  if(url.pathname==='/api/pearl-projects')return respond(res,{projects:[],activeId:''});
  if(url.pathname==='/api/project-package-rooms')return respond(res,{projectId:url.searchParams.get('id'),extraRooms:[],rooms:[{name:'XX_AI',kind:'ai',required:true,available:true,region:'XX'},{name:'XX_ENTRY',kind:'entry',required:true,available:true,region:'XX'},{name:'XX_SIDE',kind:'extra',required:false,available:true,region:'XX'}]});
  if(url.pathname==='/api/export-room-check')return respond(res,report());
  if(url.pathname==='/api/export-room-plan')return respond(res,{rooms:[{sourceRoom:'XX_SIDE',name:'FX_SIDE'}]});
  if(url.pathname==='/api/region-package-choices')return respond(res,{regions:[{code:'XX',available:true}]});
  if(url.pathname==='/api/region-package-inspect')return respond(res,{ok:true,rooms:['XX_AI','XX_ENTRY','XX_SIDE'],blockers:[],dependencies:[]});
  if(['/api/export-project-package','/api/export-standalone','/api/export-playable','/api/export-region-package','/api/export'].includes(url.pathname)){
   exports.push({path:url.pathname,data:clone(data)});if(staleOnce){staleOnce=false;snapshot++;return respond(res,{code:'room_choices_stale',error:'Room files changed. Review the available versions again.'},400);}return respond(res,{url:'/exports/fixture.zip'});
  }
  throw Error('Unexpected isolated endpoint '+url.pathname);
 }
 if(url.pathname==='/favicon.ico'){res.writeHead(204);return res.end();}
 const file=path.resolve(editor,'.'+decodeURIComponent(url.pathname));if(!file.startsWith(editor+path.sep)||!fs.existsSync(file)){res.writeHead(404);return res.end();}
 const types={'.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.woff2':'font/woff2','.png':'image/png'};res.writeHead(200,{'content-type':types[path.extname(file)]||'application/octet-stream'});res.end(fs.readFileSync(file));
 }catch(error){failures.push(error.stack);respond(res,{error:error.message},500);}});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
const browser=spawn(process.env.MI_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
let socket,closeBrowser,stderr='';browser.stderr.on('data',chunk=>stderr+=chunk);
try{
 const portFile=path.join(profile,'DevToolsActivePort');for(let i=0;i<200&&!fs.existsSync(portFile);i++)await sleep(50);if(!fs.existsSync(portFile))throw Error(stderr);
 const port=fs.readFileSync(portFile,'utf8').split(/\r?\n/)[0],tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();socket=new WebSocket(tabs.find(tab=>tab.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 let serial=0;const pending=new Map();socket.onmessage=event=>{const result=JSON.parse(event.data);if(result.id){const task=pending.get(result.id);pending.delete(result.id);result.error?task.reject(Error(JSON.stringify(result.error))):task.resolve(result.result);}else if(result.method==='Runtime.exceptionThrown')failures.push(result.params.exceptionDetails.exception?.description||result.params.exceptionDetails.text);};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});closeBrowser=()=>call('Browser.close');
 const evaluate=async expression=>{const value=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(value.exceptionDetails)throw Error(value.exceptionDetails.exception?.description||value.exceptionDetails.text);return value.result.value;};
 const until=async(expression,label)=>{for(let i=0;i<300;i++){if(await evaluate(expression))return;await sleep(10);}throw Error('Timed out: '+label);};
 const click=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
 const select=async(selector,value)=>evaluate(`(()=>{const n=document.querySelector(${JSON.stringify(selector)});n.value=${JSON.stringify(value)};n.dispatchEvent(new Event('change',{bubbles:true}));})()`);
 const screenshot=async(name,clip)=>{const value=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false,...(clip?{clip:{...clip,scale:1}}:{})});const file=path.join(output,name);fs.writeFileSync(file,Buffer.from(value.data,'base64'));screenshots.push(file);};
 const waitBuild=()=>until(`!document.getElementById('pack-build').disabled||!!document.querySelector('#export-roomVersions input')||fixtureErrors.length>0`,'build result');
 async function open(){await evaluate(`document.querySelectorAll('[name=part]').forEach(input=>input.checked=true);document.querySelector('[name=exportFormat][value=project]').checked=true;document.querySelectorAll('#export-associated input').forEach(input=>input.checked=false);fixtureErrors.length=0;`);await click('#export');await until(`document.getElementById('exportDialog').open&&!document.getElementById('pack-build').disabled`,'open export');}
 async function build(){await until(`!document.getElementById('pack-build').disabled`,'ready to export');await click('#pack-build');await sleep(30);await waitBuild();}
 async function chooseConflict(){await click('input[value="render-local"]');await click('input[value="settings-installed"]');await click('input[value="asset-enabled"]');for(const kind of ['palette','gravity'])if(await evaluate(`!!document.querySelector('select[data-policy="${kind}"]')`))await select(`select[data-policy="${kind}"]`,'project');}
 await call('Runtime.enable');await call('Page.enable');await call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloads,eventsEnabled:true});await call('Emulation.setDeviceMetricsOverride',{width:1366,height:1000,deviceScaleFactor:1,mobile:false});
 await call('Page.navigate',{url:origin+'/?lang=zh-CN'});await until(`typeof project!=='undefined'&&!!window.MI18n&&document.querySelector('[data-wardrobe-key="roomWorkColor"]')&&document.getElementById('chamberPreset').options.length===6`,'fixture initialization');
 const before=await evaluate('JSON.stringify(project)');
 check(await evaluate(`!document.querySelector('[data-section-id=chamber]').open&&!document.querySelector('[data-section-id=waiting]').open&&!document.querySelector('[data-section-id=chamberPresets]').open&&document.getElementById('replaceChamberPreset').disabled`),'Room controls should begin folded without a replacement choice');
 await evaluate(`document.querySelector('[data-section-id=chamber]').open=true;document.querySelector('[data-section-id=chamberPresets]').open=true;document.getElementById('settings').scrollTop=0;document.getElementById('chamberPreset').value='mi-chamber-irregular';refreshChamberPresetPreview();`);await until(`document.getElementById('chamberPresetPreview').complete&&document.getElementById('chamberPresetPreview').naturalWidth>0`,'preset preview');
 for(const [locale,width]of [['zh-CN',1366],['en',1366],['zh-CN',420],['en',420]]){
  await evaluate(`MI18n.setLocale(${JSON.stringify(locale)});refreshChamberPresets();`);await call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});await evaluate(`window.scrollTo(0,0);document.getElementById('settings').scrollTop=0;`);await sleep(20);
  const sidebar=await evaluate(`(()=>{const r=document.getElementById('settings').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:Math.min(r.height,innerHeight-r.y)};})()`);await screenshot('room-tools-'+locale+'-'+width+'.png',sidebar);
  check(await evaluate(`document.documentElement.scrollWidth<=innerWidth+1&&!document.getElementById('chamberPreset').disabled&&!document.getElementById('replaceChamberPreset').disabled&&document.getElementById('chamberSize').value==='original'&&!document.querySelector('[data-i18n="appearance.roomWorkflow"]')`),'Room tools overflow or retain disabled/removed UI at '+locale+' '+width);
 }
 await evaluate(`MI18n.setLocale('zh-CN');refreshChamberPresets();`);await call('Emulation.setDeviceMetricsOverride',{width:1366,height:1000,deviceScaleFactor:1,mobile:false});
 check(await evaluate(`document.querySelectorAll('#externalRoomTools').length===1&&document.getElementById('externalRoomTools').closest('[data-section-id=chamber]')`),'Third-party tool option is duplicated or outside chamber settings');
 await open();await build();await until(`document.querySelectorAll('#exportDialog input[data-room],#export-roomVersions input[data-asset]').length===7`,'conflict options');
 check(exports.length===0,'Conflict exported without a choice');
 check(await evaluate(`!document.getElementById('pack-build').disabled&&document.querySelector('input[value="render-project"]').checked&&document.querySelector('input[value="settings-local"]').checked&&!document.querySelector('#export-roomVersions input:checked')`),'Recommended room files were not selected or asset conflict was silently resolved');
 const unresolvedScans=calls.filter(call=>call.path==='/api/export-room-check').length;await build();check(calls.filter(call=>call.path==='/api/export-room-check').length===unresolvedScans+1&&await evaluate(`document.activeElement.dataset.asset==='palettes/palette9100.png'&&document.getElementById('pack-status').textContent.includes('palettes/palette9100.png')`),'Unresolved asset choice did not refresh files and focus the asset');
 check(await evaluate(`document.querySelector('input[value="render-bad"]').disabled`),'Incomplete render is selectable');
 check(await evaluate(`(()=>{const origin=document.querySelector('input[value="render-project"]').nextElementSibling.firstElementChild;return origin.textContent==='项目内文件'&&origin.title.includes(String.fromCharCode(10));})()`),'Duplicate source origins clutter the main version label');
 check(await evaluate(`(()=>{const input=document.querySelector('input[value="render-bad"]'),opacity=+getComputedStyle(input.closest('label')).opacity*+getComputedStyle(input.nextElementSibling).opacity;return opacity>=.4;})()`),'Incomplete-version text is too dim to read');
 check(await evaluate(`document.querySelector('input[value="asset-enabled"]').closest('label').textContent.includes('Palette Test')`),'Enabled asset source lacks its public mod name');
 check(await evaluate(`document.querySelectorAll('#export-roomVersions select[data-policy]').length===0`),'Policy controls were shown before their settings version was chosen');
 check(await evaluate(`(()=>{const value=document.getElementById('export-roomVersions').textContent;return value.includes('2026')&&!/[A-Za-z]:/.test(value)&&!value.includes('export.roomVersion.')&&!value.includes('·')&&!value.includes('|');})()`),'Version UI exposes a raw key/private path or lacks dates');
 await click('input[value="render-local"]');await click('input[value="settings-installed"]');const missingAssetExports=exports.length;await build();check(exports.length===missingAssetExports&&await evaluate(`document.activeElement.dataset.asset==='palettes/palette9100.png'&&document.getElementById('pack-status').textContent.includes('palettes/palette9100.png')`),'Missing asset choice did not focus the specific asset after a fresh check');
 await chooseConflict();check(await evaluate(`!document.getElementById('pack-build').disabled&&document.getElementById('export-roomVersionNotice').textContent.includes('没有配套编辑工程')`),'Unpaired render warning or complete selection is missing');
 check(await evaluate(`!document.querySelector('select[data-policy]')`),'Export repeats saved gravity or palette choices');
 check(await evaluate('JSON.stringify(project)')===before,'Export choices mutated the project');
 for(const [locale,width]of [['zh-CN',1366],['en',1366],['zh-CN',420],['en',420]]){
  await evaluate(`MI18n.setLocale(${JSON.stringify(locale)})`);await call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});await evaluate(`document.getElementById('export-roomVersions').scrollIntoView({block:'start'});`);await sleep(20);
  check(await evaluate(`(()=>{const d=document.getElementById('exportDialog');return d.scrollWidth<=d.clientWidth+1&&document.documentElement.scrollWidth<=innerWidth+1;})()`),'Room conflict layout overflows at '+locale+' '+width);
  check(await evaluate(`!document.getElementById('export-roomVersions').textContent.includes('export.roomVersion.')`),'Untranslated room choices at '+locale);
  await screenshot('export-conflict-'+locale+'-'+width+'.png');
 }
 await evaluate(`MI18n.setLocale('zh-CN')`);await build();await until(`document.querySelector('#pack-status a')`,'project export');
 let last=exports.at(-1);check(last.path==='/api/export-project-package'&&last.data.roomSourceChoices.snapshotToken==='snapshot-1','Project export lacks the inspected snapshot');
 check(JSON.stringify(last.data.roomSourceChoices.choices)==='{"fixture/XX_AI":{"source":"render-local","settings":"settings-installed"}}','Render/settings choices were not independent');
 check(last.data.roomSourceChoices.assetChoices['palettes/palette9100.png']==='asset-enabled','Merged asset choice was not sent');
 check(!('policies' in last.data.roomSourceChoices),'Export added redundant gravity or palette overrides');
 check(preferences.every(value=>!('roomSourceChoices'in value)),'Version choices were saved as project export preferences');
 check(await evaluate('JSON.stringify(project)')===before,'Export changed project modes or settings');
 mode='single';await open();const singleBefore=exports.length;await build();check(exports.length===singleBefore+1,'A single complete version without parameter risks was blocked');
 check(await evaluate(`!document.querySelector('#export-roomVersions input[type=radio]')&&!document.getElementById('pack-build').disabled`),'Single complete versions clutter the UI or block export');await until(`document.querySelector('#pack-status a')`,'single export');
 check(!('policies' in exports.at(-1).data.roomSourceChoices),'A risk-free export added parameter overrides');
 mode='unpaired';await open();await build();check(await evaluate(`document.getElementById('export-roomVersionNotice').textContent.includes('没有配套编辑工程')`),'Single unpaired render did not warn before export');
 mode='missing';await open();await build();check(await evaluate(`!document.getElementById('pack-build').disabled&&document.getElementById('pack-status').textContent.includes('XX_AI 缺少渲染文件')`),'Missing complete render did not name the missing room files');
 mode='single';await click('#export-refreshRooms');await until(`!document.getElementById('pack-build').disabled`,'recheck missing room');check(await evaluate(`!document.querySelector('input[value="render-bad"]')`),'Recheck retained the incomplete version');
 mode='conflict';await open();await build();await chooseConflict();staleOnce=true;const checksBefore=calls.filter(call=>call.path==='/api/export-room-check').length;await build();await until(`fixtureErrors.some(error=>error.code==='room_choices_stale')`,'stale error');
 check(calls.filter(call=>call.path==='/api/export-room-check').length===checksBefore+2,'Stale export did not refresh preflight');
 check(await evaluate(`!document.getElementById('pack-build').disabled&&document.querySelectorAll('#exportDialog input[data-room]:checked,#export-roomVersions input[data-asset]:checked').length===3`),'Recheck lost unchanged source selections');
 await chooseConflict();await build();await until(`document.querySelector('#pack-status a')`,'fresh export');check(exports.at(-1).data.roomSourceChoices.snapshotToken==='snapshot-2','Fresh export reused a stale token');
 mode='single';await open();await click('[name=exportFormat][value=mod]');await click('#export-roomChoices input[value="XX_SIDE"]');const modBefore=exports.length;await build();check(exports.length===modBefore&&await evaluate(`!document.getElementById('export-review').hidden&&document.getElementById('export-review').textContent.includes('FX_SIDE')`),'Room number preview was bypassed');await build();await until(`document.querySelector('#pack-status a')`,'mod export');
 last=exports.at(-1);check(last.path==='/api/export-standalone'&&JSON.stringify(last.data.extraRooms)==='["XX_SIDE"]'&&JSON.stringify(last.data.roomSourceChoices.extraRooms)==='["XX_SIDE"]','Standalone extra-room choices do not match the checked request');
 check(calls.filter(call=>call.path==='/api/export-room-plan').at(-1).data.roomSourceChoices.snapshotToken==='snapshot-2','Room number preview did not receive the same version selection');
 mode='conflict';await open();await click('[name=exportFormat][value=mod]');await click('#export-roomChoices input[value="XX_SIDE"]');const plansBefore=calls.filter(call=>call.path==='/api/export-room-plan').length;await build();
 check(calls.filter(call=>call.path==='/api/export-room-plan').length===plansBefore,'Room plan was requested with unresolved version conflicts');await chooseConflict();await build();
 check(calls.filter(call=>call.path==='/api/export-room-plan').length===plansBefore+1&&await evaluate(`!document.getElementById('export-review').hidden`),'Complete choices did not produce a version-specific room plan');
 await click('input[value="render-project"]');check(await evaluate(`document.getElementById('export-review').hidden`),'Changing a source kept an outdated room plan');await build();
 check(calls.filter(call=>call.path==='/api/export-room-plan').length===plansBefore+2&&calls.filter(call=>call.path==='/api/export-room-plan').at(-1).data.roomSourceChoices.choices['fixture/XX_AI'].source==='render-project','Changed selection did not rebuild the room plan');
 await open();await click('#pack-projects input[value="fixture-two"]');check(await evaluate(`document.querySelector('[name=exportFormat]:checked').value==='project'`),'Adding a project silently changed the format');await click('[name=exportFormat][value=mod]');await until(`!document.getElementById('pack-build').disabled`,'second project rooms');await build();
 check(await evaluate(`document.querySelectorAll('.export-room-asset').length===1&&document.querySelector('.export-room-asset').textContent.includes('Palette Test')`),'Shared assets are duplicated or their public provider is missing');
 mode='single';
 await open();await click('[name=exportFormat][value=assets]');await build();await build();await until(`document.querySelector('#pack-status a')`,'assets export');check(exports.at(-1).path==='/api/export'&&exports.at(-1).data.roomSourceChoices,'Room asset ZIP skipped version choices');
 await open();await click('[name=exportFormat][value=playable]');await build();await build();await until(`document.querySelector('#pack-status a')`,'playable export');check(exports.at(-1).path==='/api/export-playable'&&exports.at(-1).data.roomSourceChoices,'Playable export skipped version choices');
 await open();await click('[name=exportScope][value=region]');await click('[name=exportFormat][value=region]');await until(`!document.getElementById('pack-build').disabled`,'region inspect');await build();await build();await until(`document.querySelector('#pack-status a')`,'region export');check(exports.at(-1).path==='/api/export-region-package'&&exports.at(-1).data.roomSourceChoices,'Region export skipped version choices');
 check(calls.filter(call=>call.path==='/api/export-room-check').at(-1).data.scope==='region'&&calls.filter(call=>call.path==='/api/export-room-check').at(-1).data.region==='XX'&&exports.at(-1).data.scope==='region','Region scope was lost from check or export');
 mode='none';await open();await click('[name=part][value=room]');await click('[name=exportFormat][value=assets]');const noRoomChecks=calls.filter(call=>call.path==='/api/export-room-check').length;await build();await until(`document.querySelector('#pack-status a')`,'no-room export');check(calls.filter(call=>call.path==='/api/export-room-check').length===noRoomChecks&&!exports.at(-1).data.roomSourceChoices,'A room-free export checked or carried room choices');
 await evaluate(`project.editor.externalRoomTools=false;projects[0].editor.externalRoomTools=false;`);await open();await build();await until(`document.querySelector('#pack-status a')`,'ordinary export');check(await evaluate(`document.getElementById('export-roomVersions').hidden`),'Ordinary projects show third-party policies or choices');
 check(failures.length===0,'Unexpected browser/server errors: '+failures.join('\n'));
 const result={ok:true,checks,exports:exports.map(value=>value.path),screenshots};fs.writeFileSync(path.join(output,'export-browser-report.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{if(closeBrowser)await Promise.race([closeBrowser().catch(()=>{}),sleep(2000)]);socket?.close();browser.kill();await new Promise(resolve=>server.close(resolve));await sleep(600);const resolved=path.resolve(temporary);if(path.dirname(resolved)!==path.resolve(os.tmpdir())||!path.basename(resolved).startsWith('mi-export-choices-'))throw Error('Unexpected temporary path');fs.rmSync(resolved,{recursive:true,force:true,maxRetries:10,retryDelay:200});}
