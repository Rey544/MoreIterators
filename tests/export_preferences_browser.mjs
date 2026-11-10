import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const editor=fileURLToPath(new URL('../editor/',import.meta.url)),temporary=fs.mkdtempSync(path.join(os.tmpdir(),'mi-hierarchy-'));
const profile=path.join(temporary,'profile'),saved=[],exports=[],preferenceWrites=[],errors=[],sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const project={projectId:'fixture',name:'First project',editor:{externalRoomTools:true},design:{}},second={...project,projectId:'second',name:'Second project'};
let preferences={id:'fixture.mod',name:'Fixture',version:'0.4.0',authors:'Fixture author',description:'Original description',cover:'data:image/png;base64,fixture',dialogue:false,pearls:false,broadcasts:true,workPearls:true,projections:true,startRoom:'XX_AI',scope:'region',region:'XX',parts:['textures','room'],format:'playable',projects:['fixture','second'],extraRooms:['XX_SIDE'],pearlCollectionId:'saved-collection',scene:{schema:'moreiterators.scene-assets.v1',scenes:[{kind:'select_menu_scene',name:'Authored scene',images:[]}]}};
const legacy={schema:'moreiterators.broadcast.v1',id:'LEGACY',name:'Legacy',uid:'1'.repeat(32),revision:0,region:'',room:'',x:.5,y:.5,pages:[{lines:[{text:'Moon: first',color:'#229955',font:'display',size:1.5,speed:.5,hold:4},{text:'unprefixed second',color:'#992255',font:'normal',size:.8,speed:2,hold:.3}]}]};
const version=(id)=>({id,origin:'project',origins:['project'],hash:id,complete:true,issues:[],pairedSource:true,cameraCount:1,modifiedAt:'2026-11-09T12:00:00Z'});
const report={snapshotToken:'fixture-snapshot',requiresChoices:true,issues:[],assets:[],rooms:['XX_AI','XX_ENTRY'].map(room=>({projectId:'fixture',room,renderVersions:[version('render-'+room)],settingsVersions:[version('settings-'+room)]})),parameterConflicts:[{projectId:'fixture',room:'XX_ENTRY',kind:'gravity',certainty:'potential',sourceMode:'zero',settingsVersionIds:['settings-XX_ENTRY']}]};
const fixture=`let project=${JSON.stringify(project)},projects=${JSON.stringify([project,second])};const serialize=()=>structuredClone(project);async function save(){};function run(fn){return async(...args)=>{try{return await fn(...args)}catch(error){window.fixtureErrors.push(error.message)}}}window.fixtureErrors=[];const api=async(path,value)=>{const response=await fetch('/api/'+path,value===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});return response.json()};window.MIExportScene={mount(){},reset(){},serialize(){return null},setEnabled(value){window.sceneEnabled=value}};`;
const send=(res,value)=>{res.writeHead(200,{'content-type':'application/json; charset=utf-8'});res.end(JSON.stringify(value));};
const server=http.createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://fixture.invalid');
 if(url.pathname.startsWith('/api/')){
  let raw='';for await(const chunk of req)raw+=chunk;const data=raw?JSON.parse(raw):null;
  if(url.pathname==='/api/export-settings'){if(data){preferenceWrites.push(structuredClone(data));preferences=structuredClone(data);}return send(res,data?{ok:true}:preferences);}
  if(url.pathname==='/api/pearl-projects')return send(res,{projects:[{id:'saved-collection',name:'Saved collection'},{id:'active-collection',name:'Active collection'}],activeId:'active-collection'});
  if(url.pathname==='/api/project-package-rooms')return send(res,{projectId:url.searchParams.get('id'),extraRooms:['XX_SIDE'],rooms:[{name:'XX_AI',region:'XX',kind:'ai',required:true,available:true},{name:'XX_ENTRY',region:'XX',kind:'entry',required:true,available:true},{name:'XX_SIDE',region:'XX',kind:'extra',required:false,available:true}]});
  if(url.pathname==='/api/region-package-choices')return send(res,{regions:[{code:'XX',available:true}]});
  if(url.pathname==='/api/region-package-inspect')return send(res,{ok:true,rooms:['XX_AI','XX_ENTRY'],blockers:[],dependencies:[]});
  if(url.pathname==='/api/export-room-check')return send(res,report);
  if(url.pathname.startsWith('/api/export-')){exports.push(data);return send(res,{url:'/fixture.zip'});}
  if(url.pathname==='/api/broadcasts')return send(res,[legacy]);
  if(url.pathname==='/api/broadcast-rooms')return send(res,[]);
  if(url.pathname==='/api/broadcast-save'){saved.push(structuredClone(data));return send(res,{project:{...data,revision:data.revision+1}});}
  throw Error('Unexpected fixture API '+url.pathname);
 }
 if(url.pathname==='/favicon.ico'){res.writeHead(204);return res.end();}
 if(url.pathname==='/fixture.zip'){res.writeHead(200,{'content-type':'application/zip'});return res.end(Buffer.from('504b0506000000000000000000000000000000000000','hex'));}
 const resource=url.pathname==='/'?'index.html':url.pathname==='/broadcasts'?'broadcasts.html':decodeURIComponent(url.pathname).slice(1),file=path.resolve(editor,resource);
 if(!file.startsWith(path.resolve(editor)+path.sep)||!fs.existsSync(file)){res.writeHead(404);return res.end();}
 let content=fs.readFileSync(file);
 if(resource.endsWith('.html')){
  content=content.toString().replace(/<script\b[^>]*src="([^"]+)"[^>]*><\/script>/g,(whole,src)=>src==='/i18n.js'||resource==='broadcasts.html'&&['/broadcasts.js','/studio-undo.js'].includes(src)?whole:'');
  if(resource==='index.html')content=content.replace('</body>','<script>'+fixture+'</script><script src="/standalone.js"></script></body>');
 }
 res.writeHead(200,{'content-type':({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'})[path.extname(file)]||'application/octet-stream'});res.end(content);
}catch(error){errors.push(error.stack);res.writeHead(500);res.end(error.message);}});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin='http://127.0.0.1:'+server.address().port;
const browser=spawn(process.env.MI_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless','--disable-gpu','--no-first-run','--disable-background-networking','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{windowsHide:true,stdio:'ignore'});
let socket;
try{
 const portFile=path.join(profile,'DevToolsActivePort');for(let index=0;index<200&&!fs.existsSync(portFile);index++)await sleep(30);
 const port=fs.readFileSync(portFile,'utf8').split(/\r?\n/)[0],tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();socket=new WebSocket(tabs.find(tab=>tab.type==='page').webSocketDebuggerUrl);await new Promise(resolve=>socket.onopen=resolve);
 let id=0;const pending=new Map();socket.onmessage=event=>{const value=JSON.parse(event.data);if(value.id){const task=pending.get(value.id);pending.delete(value.id);value.error?task.reject(Error(JSON.stringify(value.error))):task.resolve(value.result)}else if(value.method==='Runtime.exceptionThrown')errors.push(value.params.exceptionDetails.exception?.description||value.params.exceptionDetails.text);};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const serial=++id;pending.set(serial,{resolve,reject});socket.send(JSON.stringify({id:serial,method,params}));});
 const evaluate=async expression=>{const result=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description||result.exceptionDetails.text);return result.result.value;};
 const until=async expression=>{for(let index=0;index<200;index++){if(await evaluate(expression))return;await sleep(20)}throw Error('Timed out: '+expression);};
 const click=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
 const input=(selector,value,event='change')=>evaluate(`(()=>{const element=document.querySelector(${JSON.stringify(selector)});element.value=${JSON.stringify(value)};element.dispatchEvent(new Event(${JSON.stringify(event)},{bubbles:true}))})()`);
 await call('Runtime.enable');await call('Page.enable');await call('Emulation.setDeviceMetricsOverride',{width:1200,height:950,deviceScaleFactor:1,mobile:false});
 await call('Page.navigate',{url:origin+'/?lang=en'});await until(`window.MI18n&&document.getElementById('export')?.onclick`);
 const open=async()=>{await click('#export');await until(`document.getElementById('exportDialog').open&&!document.getElementById('exportDialog').inert`);};
 const close=async()=>{await click('[data-export-close]');await until(`!document.getElementById('exportDialog').open`);};
 const state=()=>evaluate(`(()=>{const element=id=>document.getElementById(id);return {...Object.fromEntries(['id','name','authors','description','version'].map(key=>[key,element('pack-'+key).value])),...Object.fromEntries(['dialogue','pearls','broadcasts','workPearls','projections'].map(key=>[key,element('pack-'+key).checked])),scope:document.querySelector('[name=exportScope]:checked').value,format:document.querySelector('[name=exportFormat]:checked').value,parts:[...document.querySelectorAll('[name=part]:checked')].map(input=>input.value),projects:[...element('pack-projects').querySelectorAll('input:checked')].map(input=>input.value),extraRooms:[...element('export-roomChoices').querySelectorAll('input:checked')].map(input=>input.value),region:element('export-region').value,startRoom:element('export-startRoom').value,pearlCollectionId:element('pack-pearlCollection').value}})()`);
 const original=structuredClone(preferences);
 await open();const restored=await state();for(const [key,value]of Object.entries(restored))assert.deepEqual(value,original[key],key);
 await close();await sleep(500);assert.equal(preferenceWrites.length,0,'Opening and closing wrote preferences');
 await open();await input('#pack-description','Metadata edit only','input');await close();
 assert.deepEqual(preferenceWrites.at(-1),{...original,description:'Metadata edit only',settingsProject:'fixture'});
 await open();await click('[name=exportScope][value=project]');await click('[name=exportFormat][value=project]');await close();
 const retained=structuredClone(preferences);await open();assert.equal((await state()).scope,'project');assert.equal((await state()).format,'project');assert.equal(await evaluate(`document.getElementById('pack-build').disabled`),true);assert.deepEqual((await state()).parts,original.parts);assert.deepEqual((await state()).extraRooms,original.extraRooms);
 await input('#pack-description','Blocked format metadata','input');await close();assert.deepEqual(preferences,{...retained,description:'Blocked format metadata'});
 await open();await input('#export-startRoom','XX_ENTRY');await close();await open();assert.equal((await state()).startRoom,'XX_ENTRY');
 await click('#export-roomChoices input[value=XX_SIDE]');await close();await open();assert.deepEqual((await state()).extraRooms,[]);await close();
 preferences={...original,projects:['missing-project'],extraRooms:['XX_GONE'],region:'ZZ',startRoom:'XX_REMOVED',pearlCollectionId:'missing-collection',parts:[],format:'assets',scope:'project'};
 const missing=structuredClone(preferences);await open();const unavailable=await state();for(const key of ['projects','extraRooms','region','startRoom','pearlCollectionId','parts','format','scope'])assert.deepEqual(unavailable[key],missing[key],key);assert.equal(await evaluate(`document.getElementById('pack-build').disabled`),true);
 await input('#pack-description','Missing references metadata','input');await close();assert.deepEqual(preferences,{...missing,description:'Missing references metadata',settingsProject:'fixture'});
 const writesBeforeSwitch=preferenceWrites.length;
 await evaluate(`window.preferenceFetch=fetch;window.preferenceGate=new Promise(resolve=>window.releasePreference=resolve);window.preferenceRequested=false;window.fetch=async(...args)=>{if(String(args[0]).includes('/api/export-settings?id=')){window.preferenceRequested=true;await preferenceGate;}return preferenceFetch(...args)};window.openingExport=document.getElementById('export').onclick();void 0`);
 await until('window.preferenceRequested');await evaluate('project=projects[1];releasePreference();openingExport');
 assert.equal(await evaluate(`document.getElementById('exportDialog').open`),false,'A delayed export opened with another project\'s preferences');
 assert.equal(preferenceWrites.length,writesBeforeSwitch,'A canceled export opening wrote preferences');
 await evaluate('window.fetch=preferenceFetch');preferences={...original,name:'Second project export',projects:['second']};
 await open();assert.equal((await state()).name,'Second project export');await input('#pack-description','Second project metadata','input');await close();
 assert.equal(preferenceWrites.at(-1).settingsProject,'second');assert.equal(preferenceWrites.at(-1).name,'Second project export');
 await evaluate(`window.preferenceGate=new Promise(resolve=>window.releasePreference=resolve);window.preferenceRequested=false;window.fetch=async(...args)=>{if(String(args[0]).includes('/api/export-settings?id=')){window.preferenceRequested=true;await preferenceGate;}return preferenceFetch(...args)};window.openingExport=document.getElementById('export').onclick();void 0`);
 await until('window.preferenceRequested');await evaluate('window.MIStudioPage={isBusy:()=>true};releasePreference();openingExport');
 assert.equal(await evaluate(`document.getElementById('exportDialog').open`),false,'A delayed export opened during a pending project switch');
 await evaluate('delete window.MIStudioPage;window.fetch=preferenceFetch');
 assert.deepEqual(errors,[]);assert.deepEqual(await evaluate('window.fixtureErrors'),[]);assert.deepEqual(exports,[]);console.log('Export preferences browser: stored fields and unavailable references preserved; delayed openings cannot cross completed or pending project switches.');
}finally{
 socket?.close();browser.kill();await new Promise(resolve=>server.close(resolve));await sleep(300);
 const resolved=path.resolve(temporary);if(path.dirname(resolved)!==path.resolve(os.tmpdir())||!path.basename(resolved).startsWith('mi-hierarchy-'))throw Error('Unexpected temporary path');fs.rmSync(resolved,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
