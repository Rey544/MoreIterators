import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
const source=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const out=path.resolve(source,'../evidence/hierarchy-20261109');
const editor=path.join(source,'editor'),read=name=>fs.readFileSync(path.join(editor,name),'utf8');
fs.mkdirSync(out,{recursive:true});
const catalogs=Object.fromEntries(['zh-CN','en'].map(locale=>[locale,JSON.parse(read('locales/'+locale+'.json'))]));
const setup=`const CATALOGS=${JSON.stringify(catalogs)};const EASING_CATALOGS=CATALOGS;window.confirm=()=>true;`;
const helpers=`
const checks=[],$h=id=>document.getElementById(id),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const check=(value,message)=>{if(!value)throw Error(message);checks.push(message);};
const wait=async fn=>{for(let i=0;i<300;i++){if(fn())return;await new Promise(r=>setTimeout(r,10));}throw Error('UI wait timed out');};
const tick=()=>new Promise(r=>setTimeout(r,20));
const change=(id,value,type='input')=>{const node=$h(id);if(node.type==='checkbox')node.checked=value;else node.value=value;node.dispatchEvent(new Event(type,{bubbles:true}));};
const before=(a,b)=>!!(a.compareDocumentPosition(b)&Node.DOCUMENT_POSITION_FOLLOWING);
const noOverflow=()=>check(document.documentElement.scrollWidth<=innerWidth,'Page fits viewport width');
`;
function page(name,styles,fixture,scripts,tests){
 let markup=read(name+'.html').match(/<body[^>]*>([\s\S]*?)<\/body>/)[1].replace(/<script[^>]*>[\s\S]*?<\/script>/g,'');
 return '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+styles.map(read).join('\n')+'</style></head><body class="mi-studio '+(name==='projections'?'projection-studio':'')+'">'+markup+'<script>'+setup+fixture+scripts.map(read).join('\n')+helpers+tests+'</script></body></html>';
}
const projectionFixture=fs.readFileSync(path.join(source,'tests/projection_easing_browser.js'),'utf8')+`
easingGroup.tracks.push({...structuredClone(easingGroup.tracks[0]),id:'track-second',name:'Second track'});
const secondGroup={...structuredClone(easingGroup),uid:'group-second',name:'Second animation'};
const hierarchyCalls=[],projectionFetch=window.fetch;let storedSettings={mask:{enabled:false,x:0,y:0,width:1,height:1},revision:0};
window.fetch=async(input,options={})=>{const route=new URL(input,'http://fixture.invalid').pathname,body=options.body?JSON.parse(options.body):null;hierarchyCalls.push({route,body});
 if(route==='/api/projection-settings'){if(body)storedSettings={...structuredClone(body.settings),revision:storedSettings.revision+1};return {ok:true,json:async()=>structuredClone(storedSettings)};}
 if(route==='/api/projections')return {ok:true,json:async()=>({projects:[{projectId:easingGroup.projectId,name:'Fixture'}],projections:[easingGroup,secondGroup],applied:{}})};
 return projectionFetch(input,options);};releaseReference();
`;
const projectionTests=`
window.runHierarchy=async()=>{
 await wait(()=>!$h('studio').inert&&$h('trackName').value==='Circle');
 check($h('projectMaskSettings').closest('.project-settings')&&!$h('projectMaskSettings').closest('.group-settings'),'Project mask is outside animation group settings');
 check($h('showMask').closest('.preview-tools')&&!$h('showMask').closest('.project-settings'),'Mask outline belongs to preview tools');
 check($h('trackUp').closest('.track-fields')&&$h('trackDown').closest('.track-fields'),'Track order belongs to track fields');
 check(before($h('trackUp'),document.querySelector('.frame-heading')),'Track order precedes keyframe controls');
 const save=async()=>{const count=hierarchyCalls.filter(c=>c.route==='/api/projection-save').length;$h('save').click();await wait(()=>!$h('save').disabled&&hierarchyCalls.filter(c=>c.route==='/api/projection-save').length>count);};
 await save();const original=structuredClone(easingSaved),clean=$h('saveState').dataset.state;
 hierarchyCalls.length=0;change('showMask',false,'change');await tick();
 check($h('saveState').dataset.state===clean&&!MIUndo.state.undo,'Mask outline does not mark authored data dirty');
 await save();check(same(easingSaved,original),'Preview toggle leaves serialized animation unchanged');
 check(!hierarchyCalls.some(c=>c.route==='/api/projection-settings'&&c.body),'Preview toggle does not save project mask');
 $h('projectMaskSettings').open=true;change('projectMaskEnabled',true,'change');change('projectMaskx',12);change('projectMaskwidth',70);await tick();
 await save();check(storedSettings.mask.enabled&&storedSettings.mask.x===.12&&storedSettings.mask.width===.7,'Project mask saves at project scope');
 check(same(easingSaved,original),'Project mask does not rewrite animation tracks');
 change('saved','group-second','change');await wait(()=>!$h('studio').inert&&$h('groupName').value==='Second animation');
 check($h('projectMaskx').value==='12'&&$h('projectMaskEnabled').checked,'Project mask remains shared across animation groups');
 check($h('projectMaskSettings').open,'Mask disclosure survives group change');
 $h('trackUp').click();await tick();await save();check(easingSaved.tracks[1].id==='fixture-track','Track up moves entire selected track');
 check(same(easingSaved.tracks[1].frames,original.tracks[0].frames),'Track order preserves frame values and frame order');
 await MIUndo.undo();await save();check(easingSaved.tracks[0].id==='fixture-track','Undo restores track order');
 await MIUndo.redo();await save();check(easingSaved.tracks[1].id==='fixture-track','Redo restores track order');
 check(!easingErrors.length,'Projection browser reports no errors');noOverflow();return {checks:checks.length,passed:checks};
};
`;
const roomFixture=fs.readFileSync(path.join(source,'tests/room_picker_fixture.js'),'utf8')+`
const crossRoom={name:'YY_PLAIN',region:'YY',connections:['DISCONNECTED'],exitCount:1,verified:true};roomItems.push(crossRoom);
const roomFetch=window.fetch;
window.fetch=async(input,options={})=>{const route=new URL(input,'http://fixture.invalid').pathname;
 if(route==='/api/rooms'){roomCalls.push({route:'rooms',body:null});return {ok:true,json:async()=>({source:'live',fresh:true,complete:true,capturedAt:new Date().toISOString(),regions:[{name:'ZZ',rooms:roomItems.filter(r=>r.region==='ZZ')},{name:'YY',rooms:[crossRoom]}],ownedRooms:[{room:'ZZ_AI'},{room:'ZZ_ENTRY'}]})};}
 return roomFetch(input,options);};
`;
const roomTests=`
window.runHierarchy=async()=>{
 await wait(()=>!$h('bindingFields').disabled&&$h('ai').value==='ZZ_AI');
 for(const id of ['region','ai','oracleId'])check($h(id).closest('#bindingIdentity'),'Identity group contains '+id);
 for(const id of ['aiNode','entryMode','entry','entryNode'])check($h(id).closest('#bindingConnections'),'Connection group contains '+id);
 check($h('overseerForm').closest('#overseerWorkspace')&&!$h('overseerForm').closest('#bindingForm'),'Overseer has separate editor and save form');
 check(document.querySelector('#overseerWorkspace>summary h2'),'Overseer editor has its own disclosure heading');
 const values=()=>Object.fromEntries(['region','ai','oracleId','entryMode','entry','aiNode','entryNode'].map(id=>[id,$h(id).value]));
 change('ai','ZZ_AUTHORED');change('oracleId','Authored_Oracle');await tick();const authored=values();
 change('catalogRegion','','change');const choose=name=>[...document.querySelectorAll('.room-card')].find(el=>el.querySelector('strong').textContent===name).querySelector('.room-card-header button:last-child');
 choose('ZZ_POOL').click();await tick();
 check($h('ai').value===authored.ai&&$h('oracleId').value===authored.oracleId&&$h('region').value===authored.region,'Same-region entry selection preserves edited identifiers');
 check($h('entry').value==='ZZ_POOL'&&$h('entryNode').value==='1','Same-region selection picks actual free exit');
 const beforeCross=values(),posts=roomCalls.filter(c=>c.body).length;let confirmation='';window.confirm=text=>{confirmation=text;return false;};
 choose('YY_PLAIN').click();await tick();check(same(values(),beforeCross),'Cancelled cross-region selection preserves complete draft');
 check(confirmation.includes('ZZ_AUTHORED')&&confirmation.includes('YY_AUTHORED')&&confirmation.includes('YY_PLAIN'),'Cross-region confirmation shows exact before and after identifiers');
 check(roomCalls.filter(c=>c.body).length===posts,'Cancelled selection writes nothing');
 window.confirm=()=>true;choose('YY_PLAIN').click();await tick();
 check($h('region').value==='YY'&&$h('ai').value==='YY_AUTHORED'&&$h('entry').value==='YY_PLAIN','Confirmed cross-region selection updates region and preserves chamber suffix');
 check($h('oracleId').value==='Authored_Oracle'&&$h('aiNode').value==='0'&&$h('entryNode').value==='0','Confirmed connection preserves unrelated identifiers and valid nodes');
 await MIUndo.undo();check(same(values(),beforeCross),'Undo restores complete prior connection draft');
 await MIUndo.redo();check($h('ai').value==='YY_AUTHORED','Redo restores explicit cross-region choice');
 await MIUndo.undo();change('ai','CUSTOM_AUTHORED');await tick();const mismatched=values();choose('YY_PLAIN').click();await tick();
 check(same(values(),mismatched),'Mismatched edited chamber ID is not overwritten by entry selection');
 check($h('notice').textContent===MI18n.t('rooms.identityMismatch'),'Mismatched identifier receives actionable localized error');
 await MIUndo.undo();$h('overseerWorkspace').open=false;$h('refreshCatalog').click();await tick();check(!$h('overseerWorkspace').open,'Catalog refresh preserves overseer disclosure state');
 $h('overseerWorkspace').open=true;const savedBinding=values();await MIStudioPage.saveBeforeNavigate();
 const draft=roomCalls.filter(c=>c.route==='room-draft'&&c.body).at(-1)?.body.binding;
 check(draft&&draft.ai===savedBinding.ai&&draft.oracleId===savedBinding.oracleId,'Saving draft retains edited identifiers');
 check(!roomCalls.some(c=>c.route==='room-binding/apply'||c.route==='overseer/apply'||c.route==='overseer/save'),'Connection edits neither apply to game nor save overseer');
 check(!roomErrors.length,'Room browser reports no uncaught errors');noOverflow();return {checks:checks.length,passed:checks};
};
`;
const sceneTests=`
window.runHierarchy=async()=>{
 await MI18n.ready;let changes=0;MIExportScene.mount($h('sceneHost'),{onChange:()=>changes++});
 const png=(()=>{const c=document.createElement('canvas');c.width=40;c.height=40;c.getContext('2d').fillRect(0,0,40,40);return c.toDataURL();})();
 const value={schema:'moreiterators.export-scenes.v1',scenes:[{kind:'select_menu_scene',idle_depths:[2.8,4.2],select_menu_pos:[20,40],glow_pos:[100,200],slugcat_depth:3,images:[{name:'Authored',png,pos:[100,120],depth:2.8,shader:'Basic',flatmode:false}]}]};
 MIExportScene.reset(value);await tick();
 const global=()=>document.querySelector('.mi-scene-advanced'),layers=document.querySelector('.mi-scene-layer-editor'),kind=document.querySelector('.mi-scene-toolbar select');
 check(before(global(),layers),'Scene global settings precede layer editor');
 check(document.querySelector('.mi-scene-layer-heading button')&&!document.querySelector('.mi-scene-toolbar input[type=file][accept="image/png"]'),'Add layer action belongs to layer editor');
 check(same(MIExportScene.serialize(),value),'Mount and grouping preserve existing scene values');
 global().open=true;const imageBefore=structuredClone(MIExportScene.serialize().scenes[0].images);
 const focus=global().querySelector('input[type=text]');focus.value='3.1, 5.2';focus.dispatchEvent(new Event('change'));await tick();
 check(same(MIExportScene.serialize().scenes[0].idle_depths,[3.1,5.2]),'Global focus field edits scene scope');
 check(same(MIExportScene.serialize().scenes[0].images,imageBefore),'Global focus edit preserves all image parameters');
 const globalsBefore=structuredClone(MIExportScene.serialize().scenes[0]);delete globalsBefore.images;
 const depth=[...document.querySelectorAll('.mi-scene-properties label')].find(n=>n.firstChild.textContent===MI18n.text('深度')).querySelector('input');depth.value='4.6';depth.dispatchEvent(new Event('change'));await tick();
 const globalsAfter=structuredClone(MIExportScene.serialize().scenes[0]);delete globalsAfter.images;check(same(globalsAfter,globalsBefore),'Layer depth edit preserves all scene settings');
 kind.value='sleep_scene';kind.dispatchEvent(new Event('change'));check(global().open,'Scene switch preserves open global settings');
 check(global().querySelectorAll('.mi-scene-position').length===0,'Selection-only controls hide for sleep scene');
 kind.value='select_menu_scene';kind.dispatchEvent(new Event('change'));check(global().querySelectorAll('.mi-scene-position').length===3,'Selection-only controls return for character selection');
 check(global().querySelector('input[type=text]').value==='3.1, 5.2','Scene switch retains authored focus');
 const imported={id:'Imported',scene_folder:'scene',idle_depths:[6.2],select_menu_pos:[50,80],images:[{name:'Authored',pos:[5,6],depth:2.8,shader:'Basic'}]};
 const imageFile=new File([await(await fetch(png)).blob()],'Authored.png',{type:'image/png'});
 await MIExportScene.importFiles([new File([JSON.stringify(imported)],'scene.json',{type:'application/json'}),imageFile]);
 check(global().open&&global().querySelector('input[type=text]').value==='6.2','Native import refreshes global fields and retains disclosure');
 check(MIExportScene.serialize().scenes[0].images[0].pos.join(',')==='5,6','Native import preserves actual image coordinates');
 check(changes>=3,'Scoped edits notify existing persistence owner');noOverflow();return {checks:checks.length,passed:checks};
};
`;
const pages={
 projections:page('projections',['projections.css','studio-theme.css'],projectionFixture,['i18n.js','studio-undo.js','projections.js'],projectionTests),
 rooms:page('rooms',['dialogue.css','rooms.css','room-picker.css','studio-theme.css'],roomFixture,['i18n.js','room-picker.js','studio-undo.js','rooms.js'],roomTests),
 scene:'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+read('studio-theme.css')+read('scene-assets.css')+'body{margin:0;padding:20px}main{max-width:760px;margin:auto}</style></head><body class="mi-studio"><main><div id="sceneHost"></div></main><script>'+setup+`const nativeFetch=fetch;window.fetch=(input,...args)=>String(input).startsWith('/locales/')?Promise.resolve({ok:true,json:async()=>CATALOGS[String(input).split('/').pop().replace('.json','')]}):nativeFetch(input,...args);`+read('i18n.js')+read('scene-assets.js')+helpers+sceneTests+'</script></body></html>'
};
for(const[kind,html]of Object.entries(pages))fs.writeFileSync(path.join(out,kind+'-hierarchy.html'),html);
const profile=fs.mkdtempSync(path.join(out,'profile-hierarchy-'));
const browser=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-background-timer-throttling','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:['ignore','ignore','pipe']});
let socket,stderr='';browser.stderr.on('data',chunk=>stderr+=chunk);const sleep=ms=>new Promise(r=>setTimeout(r,ms));
try{
 const active=path.join(profile,'DevToolsActivePort');for(let i=0;i<200&&!fs.existsSync(active);i++)await sleep(50);if(!fs.existsSync(active))throw Error(stderr);
 const port=fs.readFileSync(active,'utf8').split(/\r?\n/)[0],tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();socket=new WebSocket(tabs.find(tab=>tab.type==='page').webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
 let serial=0;const pending=new Map();socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.id){const item=pending.get(data.id);pending.delete(data.id);data.error?item.reject(Error(JSON.stringify(data.error))):item.resolve(data.result);}else if(data.method==='Page.javascriptDialogOpening')call('Page.handleJavaScriptDialog',{accept:true});};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));});
 const evaluate=async expression=>{const result=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description||JSON.stringify(result.exceptionDetails));return result.result.value;};
 await call('Page.enable');const results=[];
 for(const kind of Object.keys(pages))for(const locale of ['zh-CN','en'])for(const width of [1366,420]){
  await call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url:pathToFileURL(path.join(out,kind+'-hierarchy.html')).href+'?lang='+locale+'&test='+Date.now()});await sleep(100);
  for(let i=0;i<100&&!(await evaluate('typeof runHierarchy==="function"'));i++)await sleep(30);
  const result=await evaluate('runHierarchy()');results.push({kind,locale,width,...result});
  await sleep(100);const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});fs.writeFileSync(path.join(out,kind+'-'+locale+'-'+width+'.png'),Buffer.from(shot.data,'base64'));
 }
 fs.writeFileSync(path.join(out,'parameter-hierarchy-results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify({runs:results.length,checks:results.reduce((n,x)=>n+x.checks,0),results},null,2));
}finally{socket?.close();browser.kill();await sleep(400);if(path.dirname(fs.realpathSync(profile))===fs.realpathSync(out))try{fs.rmSync(profile,{recursive:true,force:true});}catch{}}
