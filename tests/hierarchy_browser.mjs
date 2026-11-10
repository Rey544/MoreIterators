import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const editor=fileURLToPath(new URL('../editor/',import.meta.url)),temporary=fs.mkdtempSync(path.join(os.tmpdir(),'mi-hierarchy-'));
const profile=path.join(temporary,'profile'),saved=[],exports=[],errors=[],sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const project={projectId:'fixture',name:'First project',editor:{externalRoomTools:true},design:{}},second={...project,projectId:'second',name:'Second project'};
const legacy={schema:'moreiterators.broadcast.v1',id:'LEGACY',name:'Legacy',uid:'1'.repeat(32),revision:0,region:'',room:'',x:.5,y:.5,pages:[{lines:[{text:'Moon: first',color:'#229955',font:'display',size:1.5,speed:.5,hold:4},{text:'unprefixed second',color:'#992255',font:'normal',size:.8,speed:2,hold:.3}]}]};
const version=(id)=>({id,origin:'project',origins:['project'],hash:id,complete:true,issues:[],pairedSource:true,cameraCount:1,modifiedAt:'2026-11-09T12:00:00Z'});
const report={snapshotToken:'fixture-snapshot',requiresChoices:true,issues:[],assets:[],rooms:['XX_AI','XX_ENTRY'].map(room=>({projectId:'fixture',room,renderVersions:[version('render-'+room)],settingsVersions:[version('settings-'+room)]})),parameterConflicts:[{projectId:'fixture',room:'XX_ENTRY',kind:'gravity',certainty:'potential',sourceMode:'zero',settingsVersionIds:['settings-XX_ENTRY']}]};
const fixture=`let project=${JSON.stringify(project)},projects=${JSON.stringify([project,second])};const serialize=()=>structuredClone(project);async function save(){};function run(fn){return async(...args)=>{try{return await fn(...args)}catch(error){window.fixtureErrors.push(error.message)}}}window.fixtureErrors=[];const api=async(path,value)=>{const response=await fetch('/api/'+path,value===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});return response.json()};window.MIExportScene={mount(){},reset(){},serialize(){return null},setEnabled(value){window.sceneEnabled=value}};`;
const send=(res,value)=>{res.writeHead(200,{'content-type':'application/json; charset=utf-8'});res.end(JSON.stringify(value));};
const server=http.createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://fixture.invalid');
 if(url.pathname.startsWith('/api/')){
  let raw='';for await(const chunk of req)raw+=chunk;const data=raw?JSON.parse(raw):null;
  if(url.pathname==='/api/export-settings')return send(res,data?{ok:true}:{id:'fixture.mod',name:'Fixture',version:'0.4.0',authors:'Fixture',description:'',cover:''});
  if(url.pathname==='/api/pearl-projects')return send(res,{projects:[],activeId:''});
  if(url.pathname==='/api/project-package-rooms')return send(res,{projectId:url.searchParams.get('id'),extraRooms:[],rooms:[{name:'XX_AI',region:'XX',kind:'ai',required:true,available:true},{name:'XX_ENTRY',region:'XX',kind:'entry',required:true,available:true}]});
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
 await call('Page.navigate',{url:origin+'/?lang=en'});await until(`window.MI18n&&document.getElementById('export').onclick`);await click('#export');await until(`document.getElementById('exportDialog').open&&!document.getElementById('pack-build').disabled`);
 await click('[name=part][value=room]');assert.equal(await evaluate(`document.querySelector('[name=exportFormat]:checked').value`),'project');assert.equal(await evaluate(`document.getElementById('export-completeContent').hidden`),false);
 await click('#export-completeContent');assert.equal(await evaluate(`document.querySelector('[name=part][value=room]').checked`),true);
 await click('[name=exportScope][value=region]');await until(`document.getElementById('export-region').value==='XX'`);assert.equal(await evaluate(`document.getElementById('export-projectContent').hidden`),false);assert.equal(await evaluate(`document.querySelector('[name=exportFormat]:checked').value`),'project');assert.equal(await evaluate(`document.getElementById('pack-build').disabled`),true);
 await click('[name=exportFormat][value=playable]');await until(`!document.getElementById('pack-build').disabled`);assert.equal(await evaluate(`document.getElementById('export-associated').hidden||document.getElementById('pack-dialogue').parentElement.hidden`),false);
 await click('[name=exportFormat][value=region]');assert.equal(await evaluate(`document.getElementById('export-associated').hidden`),true);
 await click('[name=exportScope][value=project]');await click('[name=exportFormat][value=mod]');assert.equal(await evaluate('window.sceneEnabled'),false);assert.equal(await evaluate(`document.getElementById('export-coverTitle').textContent`),'Cover');
 await click('[name=exportFormat][value=playable]');assert.equal(await evaluate('window.sceneEnabled'),true);
 await click('[name=exportFormat][value=project]');await click('#pack-build');await until(`document.querySelector('select[data-policy]')`);
 assert.equal(await evaluate(`document.querySelector('select[data-policy]').dataset.room`),'XX_ENTRY');assert.equal(await evaluate(`document.querySelector('select[data-policy]').closest('.export-room-version').querySelector('h4').textContent`),'XX_ENTRY');assert.equal(await evaluate(`document.getElementById('pack-build').disabled`),true);
 await click('#export-locateChoice');assert.equal(await evaluate(`document.activeElement.dataset.room`),'XX_ENTRY');await input('select[data-policy]','room');await click('#pack-build');await until(`!!document.querySelector('#pack-status a')`);assert.deepEqual(exports.at(-1).roomSourceChoices.policies,{fixture:{gravity:{XX_ENTRY:'room'}}});
 for(const width of [1200,420]){await call('Emulation.setDeviceMetricsOverride',{width,height:950,deviceScaleFactor:1,mobile:false});assert.equal(await evaluate(`document.getElementById('exportDialog').scrollWidth<=document.getElementById('exportDialog').clientWidth+1`),true);}
 await call('Page.navigate',{url:origin+'/broadcasts?lang=en'});await until(`typeof project!=='undefined'&&project&&!loading`);
 assert.equal(await evaluate(`Object.hasOwn(project,'style')`),false);assert.equal(await evaluate(`document.getElementById('speed').value`),'');assert.equal(await evaluate(`getComputedStyle(document.querySelectorAll('#preview p')[1]).color`),'rgb(153, 34, 85)');
 await input('#name','Renamed','input');await click('#save');await until(`!saving&&document.getElementById('notice').textContent.includes('Renamed')`);assert.deepEqual(saved[0].pages,legacy.pages);assert.equal(Object.hasOwn(saved[0],'style'),false);
 await input('#speed','1.5','input');await click('#save');await until(`!saving&&project.revision===2`);for(let index=0;index<2;index++){assert.equal(saved[1].pages[0].lines[index].speed,1.5);for(const field of ['font','size','hold','color'])assert.equal(saved[1].pages[0].lines[index][field],legacy.pages[0].lines[index][field]);}
 await click('#useCharacterColors');assert.equal(await evaluate(`document.getElementById('speakers').closest('details').hidden`),true);
 assert.deepEqual(errors,[]);console.log('Hierarchy browser: export scope/format, room-specific policy, layout and legacy rename/style/color checks passed.');
}finally{
 socket?.close();browser.kill();await new Promise(resolve=>server.close(resolve));await sleep(300);
 const resolved=path.resolve(temporary);if(path.dirname(resolved)!==path.resolve(os.tmpdir())||!path.basename(resolved).startsWith('mi-hierarchy-'))throw Error('Unexpected temporary path');fs.rmSync(resolved,{recursive:true,force:true,maxRetries:5,retryDelay:200});
}
